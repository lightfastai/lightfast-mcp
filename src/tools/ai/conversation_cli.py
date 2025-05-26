"""CLI interface for the new ConversationClient."""

import asyncio
import os
import signal
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from tools.common import get_logger
from tools.orchestration.config_loader import load_server_configs

from .conversation_client import ConversationClient, create_conversation_client

app = typer.Typer(help="Conversation client CLI using the new architecture")
console = Console()
logger = get_logger("ConversationCLI")

# Global client for signal handling
current_client: Optional[ConversationClient] = None


def handle_interrupt(signum, frame):
    """Handle Ctrl+C gracefully."""
    if current_client:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
        asyncio.create_task(current_client.disconnect_from_servers())
    sys.exit(0)


signal.signal(signal.SIGINT, handle_interrupt)


def print_step_info(step) -> None:
    """Print information about a completed conversation step."""
    step_title = f"Step {step.step_number + 1}"

    if step.text and step.tool_calls:
        step_title += " (Text + Tool Calls)"
    elif step.tool_calls:
        step_title += " (Tool Calls Only)"
    elif step.text:
        step_title += " (Text Only)"

    # Print step header
    console.print(f"\n[bold blue]{step_title}[/bold blue]")

    # Print text if present
    if step.text:
        console.print(Panel(Markdown(step.text), title="Response", border_style="blue"))

    # Print tool calls and results
    if step.tool_calls:
        for i, tool_call in enumerate(step.tool_calls):
            tool_title = f"Tool Call {i + 1}: {tool_call.tool_name}"

            # Find corresponding result
            result = None
            for tool_result in step.tool_results:
                if tool_result.id == tool_call.id:
                    result = tool_result
                    break

            # Format tool call info
            info_parts = [f"**Tool:** {tool_call.tool_name}"]
            if tool_call.server_name:
                info_parts.append(f"**Server:** {tool_call.server_name}")
            if tool_call.arguments:
                info_parts.append(f"**Arguments:** `{tool_call.arguments}`")

            if result:
                if result.is_success:
                    info_parts.append(f"**Result:** {result.result}")
                    border_style = "green"
                elif result.is_error:
                    info_parts.append(f"**Error:** {result.error}")
                    border_style = "red"
                else:
                    info_parts.append("**Status:** Pending")
                    border_style = "yellow"
            else:
                info_parts.append("**Status:** No result")
                border_style = "yellow"

            console.print(
                Panel(
                    "\n".join(info_parts), title=tool_title, border_style=border_style
                )
            )


@app.command()
def chat(
    config_path: str = typer.Option(
        "config/servers.yaml",
        "--config",
        "-c",
        help="Path to server configuration file",
    ),
    ai_provider: str = typer.Option(
        "claude", "--provider", "-p", help="AI provider (claude or openai)"
    ),
    max_steps: int = typer.Option(
        None,
        "--max-steps",
        "-s",
        help="Maximum number of steps (overrides environment variable)",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="API key (optional, uses environment variables)"
    ),
):
    """Start an interactive chat session with AI and connected MCP servers."""
    asyncio.run(async_chat(config_path, ai_provider, max_steps, api_key))


async def async_chat(
    config_path: str, ai_provider: str, max_steps: Optional[int], api_key: Optional[str]
):
    """Async chat implementation."""
    global current_client

    try:
        # Load server configuration
        servers = load_server_configs(config_path)
        if not servers:
            console.print(
                "[red]No servers configured. Please check your configuration file.[/red]"
            )
            return

        # Get max_steps from environment if not provided
        if max_steps is None:
            max_steps = int(os.getenv("LIGHTFAST_MAX_STEPS", "5"))

        console.print("[green]Loading servers and connecting...[/green]")

        # Create and connect client
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Connecting to servers...", total=None)

            client_result = await create_conversation_client(
                servers=servers,
                ai_provider=ai_provider,
                api_key=api_key,
                max_steps=max_steps,
            )

            if not client_result.is_success:
                console.print(
                    f"[red]Failed to create client: {client_result.error}[/red]"
                )
                return

            current_client = client_result.data
            progress.update(task, description="Connected!")

        # Display connected servers and tools
        if current_client is not None:
            connected_servers = current_client.get_connected_servers()
            if connected_servers:
                console.print(
                    f"\n[green]✓ Connected to {len(connected_servers)} servers:[/green]"
                )
                tools_by_server = current_client.get_available_tools()
                for server in connected_servers:
                    tools = tools_by_server.get(server, [])
                    console.print(f"  • {server}: {len(tools)} tools")
            else:
                console.print(
                    "[yellow]Warning: No servers connected successfully[/yellow]"
                )
        else:
            console.print("[red]Error: Client is not available[/red]")

        console.print(f"\n[blue]AI Provider:[/blue] {ai_provider}")
        console.print(f"[blue]Max Steps:[/blue] {max_steps}")
        console.print(
            "\n[green]Chat started! Type 'quit' or 'exit' to end the session.[/green]"
        )
        console.print("[dim]Use Ctrl+C to exit gracefully.[/dim]\n")

        # Interactive chat loop
        while True:
            try:
                # Get user input
                user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    break

                if not user_input:
                    continue

                console.print("\n[yellow]🤖 Processing...[/yellow]")

                # Send message and get result
                if current_client is not None:
                    chat_result = await current_client.chat(user_input)

                    if not chat_result.is_success:
                        console.print(f"[red]Error: {chat_result.error}[/red]")
                        continue

                    conversation_result = chat_result.data

                    # Display the steps
                    for step in conversation_result.steps:
                        print_step_info(step)

                    console.print("\n" + "=" * 50 + "\n")
                else:
                    console.print("[red]Error: Client is not available[/red]")

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error during chat: {e}[/red]")
                logger.error(f"Chat error: {e}")

    except Exception as e:
        console.print(f"[red]Failed to start chat: {e}[/red]")
        logger.error(f"Setup error: {e}")

    finally:
        if current_client:
            console.print("[yellow]Disconnecting from servers...[/yellow]")
            await current_client.disconnect_from_servers()
            console.print("[green]Disconnected. Goodbye![/green]")


@app.command()
def test(
    config_path: str = typer.Option(
        "config/servers.yaml",
        "--config",
        "-c",
        help="Path to server configuration file",
    ),
    ai_provider: str = typer.Option(
        "claude", "--provider", "-p", help="AI provider (claude or openai)"
    ),
    max_steps: int = typer.Option(
        3, "--max-steps", "-s", help="Maximum number of steps for test"
    ),
    message: str = typer.Option(
        "Hello! What tools do you have available?",
        "--message",
        "-m",
        help="Test message to send",
    ),
):
    """Test the conversation client with a single message."""
    asyncio.run(async_test(config_path, ai_provider, max_steps, message))


async def async_test(config_path: str, ai_provider: str, max_steps: int, message: str):
    """Async test implementation."""
    global current_client

    try:
        # Load server configuration
        servers = load_server_configs(config_path)
        if not servers:
            console.print("[red]No servers configured.[/red]")
            return

        console.print("[green]Testing conversation client...[/green]")

        # Create and connect client
        client_result = await create_conversation_client(
            servers=servers,
            ai_provider=ai_provider,
            max_steps=max_steps,
        )

        if not client_result.is_success:
            console.print(f"[red]Failed to create client: {client_result.error}[/red]")
            return

        current_client = client_result.data

        # Display status
        if current_client is not None:
            connected_servers = current_client.get_connected_servers()
            console.print(f"Connected servers: {connected_servers}")

            tools_by_server = current_client.get_available_tools()
            console.print(f"Available tools: {tools_by_server}")
        else:
            console.print("[red]Error: Client is not available[/red]")
            return

        # Send test message
        console.print(f"\n[cyan]Sending message:[/cyan] {message}")

        if current_client is not None:
            chat_result = await current_client.chat(message)

            if not chat_result.is_success:
                console.print(f"[red]Chat failed: {chat_result.error}[/red]")
                return

            conversation_result = chat_result.data

            # Display results
            console.print(
                f"\n[green]Completed {len(conversation_result.steps)} steps:[/green]"
            )
            for step in conversation_result.steps:
                print_step_info(step)

            # Display summary
            console.print("\n[blue]Conversation Summary:[/blue]")
            console.print(
                f"  • Total tool calls: {conversation_result.total_tool_calls}"
            )
            console.print(
                f"  • Successful: {conversation_result.successful_tool_calls}"
            )
            console.print(f"  • Failed: {conversation_result.failed_tool_calls}")
            console.print(f"  • Success rate: {conversation_result.success_rate:.1%}")
        else:
            console.print("[red]Error: Client is not available[/red]")

    except Exception as e:
        console.print(f"[red]Test failed: {e}[/red]")
        logger.error(f"Test error: {e}")

    finally:
        if current_client:
            await current_client.disconnect_from_servers()


if __name__ == "__main__":
    app()
