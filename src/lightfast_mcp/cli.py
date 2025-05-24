#!/usr/bin/env python3
"""
Lightfast MCP Manager - Multi-server management for creative applications.

This is the main entry point for managing multiple MCP servers simultaneously.
Users can select which servers to start, run them in the background, and use
AI integration to control multiple creative applications at once.
"""

import argparse
import asyncio
import os

from .clients import MultiServerAIClient, ServerSelector
from .core import (
    ConfigLoader,
    get_manager,
)
from .utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("LightfastMCPManager")


def create_sample_config():
    """Create a sample configuration file."""
    print("📝 Creating sample configuration...")

    config_loader = ConfigLoader()
    success = config_loader.create_sample_config("servers.yaml")

    if success:
        print("✅ Sample configuration created at: config/servers.yaml")
        print("📝 Edit this file to customize your server settings.")
        print("🚀 Run 'lightfast-mcp-manager start' to begin!")
    else:
        print("❌ Failed to create sample configuration")


def list_available_servers():
    """List all available server types and configurations."""
    print("🔍 Available Server Types:")
    print("=" * 50)

    from .core.server_registry import get_registry

    registry = get_registry()
    server_info = registry.get_server_info()

    for server_type, info in server_info.items():
        print(f"📦 {server_type}")
        print(f"   Version: {info['version']}")
        print(f"   Description: {info['description']}")
        if info["required_dependencies"]:
            print(f"   Dependencies: {', '.join(info['required_dependencies'])}")
        if info["required_apps"]:
            print(f"   Required Apps: {', '.join(info['required_apps'])}")
        print()

    print("📋 Server Configurations:")
    print("=" * 50)

    config_loader = ConfigLoader()
    configs = config_loader.load_servers_config()

    if not configs:
        print("❌ No server configurations found.")
        print("   Run 'lightfast-mcp-manager init' to create a sample configuration.")
        return

    for config in configs:
        server_type = config.config.get("type", "unknown")
        print(f"🚀 {config.name} ({server_type})")
        print(f"   Description: {config.description}")
        print(f"   Transport: {config.transport}")
        if config.transport in ["http", "streamable-http"]:
            print(f"   URL: http://{config.host}:{config.port}{config.path}")
        print()


def start_servers_interactive(show_logs: bool = True):
    """Start servers with interactive selection."""
    print("🚀 Lightfast MCP Multi-Server Manager")
    print("=" * 50)

    # Interactive server selection
    selector = ServerSelector()
    selected_configs = selector.load_available_servers()

    if not selected_configs:
        print("❌ No server configurations found.")
        print("   Would you like to create a sample configuration? (y/n)")
        try:
            create_sample = input().strip().lower()
            if create_sample in ["y", "yes"]:
                config_loader = ConfigLoader()
                if config_loader.create_sample_config("servers.yaml"):
                    print("✅ Sample configuration created at: config/servers.yaml")
                    print("🔄 Loading the new configuration...")
                    selected_configs = selector.load_available_servers()
                else:
                    print("❌ Failed to create sample configuration")
                    return
            else:
                print("👋 No configuration created. Goodbye!")
                return
        except KeyboardInterrupt:
            print("\n👋 Cancelled. Goodbye!")
            return

    if not selected_configs:
        print("❌ Still no server configurations available.")
        return

    # Let user select servers
    selected_configs = selector.select_servers_interactive()

    if not selected_configs:
        print("👋 No servers selected. Goodbye!")
        return

    # Start selected servers
    manager = get_manager()

    print(f"\n🚀 Starting {len(selected_configs)} servers...")
    print("   This may take a few moments as servers initialize...")

    results = manager.start_multiple_servers(
        selected_configs, background=True, show_logs=show_logs
    )

    # Show results
    successful = sum(1 for success in results.values() if success)
    print(f"✅ Successfully started {successful}/{len(selected_configs)} servers")

    # Show any failures
    failed_servers = [name for name, success in results.items() if not success]
    if failed_servers:
        print(f"❌ Failed to start: {', '.join(failed_servers)}")

    if successful > 0:
        # Show server URLs
        urls = manager.get_server_urls()
        if urls:
            print("\n📡 Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        print("\n🎯 Servers are running! Use the AI client to interact with them.")
        print(
            "   Run 'lightfast-mcp-manager ai' (or 'uv run task ai_client') to start the AI client."
        )
        print("   Press Ctrl+C to shutdown all servers.\n")

        try:
            # Wait for shutdown
            manager.wait_for_shutdown()
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down servers...")
            manager.shutdown_all()
            print("👋 All servers stopped. Goodbye!")


def start_servers_by_names(server_names: list[str], show_logs: bool = True):
    """Start specific servers by name."""
    config_loader = ConfigLoader()
    all_configs = config_loader.load_servers_config()

    if not all_configs:
        print("❌ No server configurations found.")
        return

    # Find requested servers
    selected_configs = []
    for name in server_names:
        config = next((c for c in all_configs if c.name == name), None)
        if config:
            selected_configs.append(config)
        else:
            print(f"⚠️  Server configuration not found: {name}")

    if not selected_configs:
        print("❌ No valid servers to start.")
        return

    # Start servers
    manager = get_manager()
    results = manager.start_multiple_servers(
        selected_configs, background=True, show_logs=show_logs
    )

    # Show results
    successful = sum(1 for success in results.values() if success)
    print(f"✅ Successfully started {successful}/{len(selected_configs)} servers")

    if successful > 0:
        urls = manager.get_server_urls()
        if urls:
            print("\n📡 Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        try:
            manager.wait_for_shutdown()
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down servers...")
            manager.shutdown_all()


def _display_step_info(
    step_num: int, total_steps: int, tool_calls: list, tool_results: list
):
    """Display information about a step."""
    print(f"  📍 Step {step_num + 1}/{total_steps}")

    if tool_calls:
        for tool_call in tool_calls:
            server_info = (
                f" on {tool_call.server_name}" if tool_call.server_name else ""
            )
            print(f"    🔧 Calling {tool_call.tool_name}{server_info}")
            if tool_call.arguments:
                print(f"       Arguments: {tool_call.arguments}")

    if tool_results:
        for result in tool_results:
            if result.error:
                print(f"    ❌ {result.tool_name}: {result.error}")
            else:
                print(f"    ✅ {result.tool_name}: Success")
                if result.result:
                    # Show a preview of the result
                    result_str = str(result.result)
                    if len(result_str) > 100:
                        result_str = result_str[:100] + "..."
                    print(f"       Result: {result_str}")


async def start_ai_client():
    """Start the AI client for multi-server interaction."""
    print("🤖 Lightfast MCP AI Client")
    print("=" * 50)

    # Check for API keys
    ai_provider = os.getenv("AI_PROVIDER", "claude").lower()
    max_steps = int(os.getenv("MAX_STEPS", "5"))

    try:
        client = MultiServerAIClient(ai_provider=ai_provider, max_steps=max_steps)
    except ValueError as e:
        print(f"❌ {e}")
        print("   Set your API key in the environment:")
        if ai_provider == "claude":
            print("   export ANTHROPIC_API_KEY=your_key_here")
        elif ai_provider == "openai":
            print("   export OPENAI_API_KEY=your_key_here")
        return

    # Auto-discover running servers (look for common ports)
    common_ports = [8001, 8002, 8003, 8004, 8005]
    print("🔍 Auto-discovering running servers...")
    print("   Waiting a moment for servers to fully start up...")

    # Give servers time to fully start up
    await asyncio.sleep(2)

    discovered_servers = {}
    for port in common_ports:
        url = f"http://localhost:{port}/mcp"
        try:
            # Quick check if server is responding
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)  # Increased timeout
            result = sock.connect_ex(("localhost", port))
            sock.close()

            if result == 0:
                server_name = f"server-{port}"
                discovered_servers[server_name] = url
                print(f"   ✅ Found server at {url}")
            else:
                print(f"   ⚪ No server found at port {port}")
        except Exception as e:
            print(f"   ❌ Error checking port {port}: {e}")

    if not discovered_servers:
        print("❌ No running MCP servers found.")
        print("   Start some servers first with 'lightfast-mcp-manager start'")
        print("   Make sure to wait a few seconds for servers to fully start.")
        return

    # Add discovered servers to client
    for name, url in discovered_servers.items():
        client.add_server(name, url)

    # Connect to servers
    print(f"\n📡 Connecting to {len(discovered_servers)} servers...")
    try:
        connection_results = await client.connect_to_servers()
    except Exception as e:
        print(f"❌ Error connecting to servers: {e}")
        print(
            "   This might be due to server startup timing. Try again in a few seconds."
        )
        return

    successful_connections = sum(
        1 for success in connection_results.values() if success
    )
    print(f"✅ Connected to {successful_connections}/{len(discovered_servers)} servers")

    if successful_connections == 0:
        print("❌ Could not connect to any servers.")
        print("   Servers might still be starting up. Try again in a few seconds.")
        return

    # Show available tools
    tools_by_server = client.get_all_tools()
    print("\n🛠️  Available Tools:")
    for server_name, tools in tools_by_server.items():
        print(f"   {server_name}: {', '.join(tools)}")

    print(f"\n🤖 AI Client ready! (Using {ai_provider.upper()}, max {max_steps} steps)")
    print("Ask questions about your creative applications or request actions...")
    print("Type 'quit' to exit\n")

    try:
        while True:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break

            if not user_input:
                continue

            try:
                print("🤔 AI is thinking...")

                # Set max_steps on the client before generating
                client.conversation_state.max_steps = max_steps

                # Use the streaming approach instead of waiting for all steps
                step_count = 0

                async for step in client.generate_with_steps(user_input):
                    step_count += 1

                    print(f"\n📍 Step {step_count}")
                    print("-" * 20)

                    # Display tool calls as they happen
                    if step.tool_calls:
                        for tool_call in step.tool_calls:
                            server_info = (
                                f" on {tool_call.server_name}"
                                if tool_call.server_name
                                else ""
                            )
                            print(f"🔧 Calling {tool_call.tool_name}{server_info}")
                            if tool_call.arguments:
                                print(f"   Arguments: {tool_call.arguments}")

                    # Display tool results
                    if step.tool_results:
                        for result in step.tool_results:
                            if result.error:
                                print(f"❌ {result.tool_name}: {result.error}")
                            else:
                                print(f"✅ {result.tool_name}: Success")
                                if result.result:
                                    # Show a preview of the result
                                    result_str = str(result.result)
                                    if len(result_str) > 150:
                                        result_str = result_str[:150] + "..."
                                    print(f"   Result: {result_str}")

                    # Display text response if any
                    if step.text:
                        print(f"💬 {step.text}")

                    # Show completion status for final step
                    if step.finish_reason == "stop":
                        print("✅ Conversation completed")
                        break

                # Get final conversation state
                conv_state = client.get_conversation_state()

                # Show final status
                if conv_state.current_step >= max_steps:
                    print(f"\n⚠️  Reached max steps ({max_steps})")

                print()  # Add spacing

            except Exception as e:
                print(f"❌ Error: {e}\n")

    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

    finally:
        await client.disconnect_from_servers()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Lightfast MCP Manager - Multi-server management for creative applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lightfast-mcp-manager init                        # Create sample configuration
  lightfast-mcp-manager list                        # List available servers
  lightfast-mcp-manager start                       # Interactive server selection
  lightfast-mcp-manager start blender-server        # Start specific server
  lightfast-mcp-manager start --hide-logs           # Start servers without showing logs
  lightfast-mcp-manager start --verbose             # Start with debug logging and server logs
  lightfast-mcp-manager ai                          # Start AI client

Environment Variables:
  AI_PROVIDER=claude|openai                         # AI provider (default: claude)
  MAX_STEPS=5                                       # Maximum conversation steps (default: 5)
  ANTHROPIC_API_KEY=...                            # Required for Claude
  OPENAI_API_KEY=...                               # Required for OpenAI
        """,
    )

    parser.add_argument(
        "command", choices=["init", "list", "start", "ai"], help="Command to run"
    )

    parser.add_argument(
        "servers", nargs="*", help="Server names to start (for 'start' command)"
    )

    parser.add_argument("--config", help="Configuration file path")

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--show-logs",
        action="store_true",
        default=True,
        help="Show server logs in terminal (default: True)",
    )

    parser.add_argument(
        "--hide-logs", action="store_true", help="Hide server logs from terminal"
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        configure_logging(level="DEBUG")
        print("🔍 Debug logging enabled")

    # Determine log visibility (--hide-logs takes precedence)
    show_logs = not args.hide_logs if args.hide_logs else args.show_logs
    if args.verbose:
        print(f"📊 Server logs visibility: {'Enabled' if show_logs else 'Disabled'}")

    # Handle commands
    if args.command == "init":
        create_sample_config()

    elif args.command == "list":
        list_available_servers()

    elif args.command == "start":
        if args.servers:
            start_servers_by_names(args.servers, show_logs=show_logs)
        else:
            start_servers_interactive(show_logs=show_logs)

    elif args.command == "ai":
        asyncio.run(start_ai_client())


if __name__ == "__main__":
    main()
