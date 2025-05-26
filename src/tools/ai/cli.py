"""
DEPRECATED CLI interface for multi-server AI client.

⚠️  WARNING: This CLI is deprecated and will be removed in a future version.
    Please use the new conversation client instead:

    uv run lightfast-conversation-client chat

    Or use the task shortcut:
    uv run task conversation_client
"""

import sys

import typer
from rich.console import Console

app = typer.Typer(help="DEPRECATED: Multi-server AI client CLI")
console = Console()


@app.callback(invoke_without_command=True)
def main():
    """Show deprecation warning and exit."""
    console.print(
        "[bold yellow]⚠️  DEPRECATION WARNING[/bold yellow]\n"
        "This CLI (lightfast-mcp-ai) is deprecated and will be removed in a future version.\n"
        "Please use the new conversation client instead:\n\n"
        "[bold green]uv run lightfast-conversation-client chat[/bold green]\n"
        "or\n"
        "[bold green]uv run task conversation_client[/bold green]\n"
    )
    sys.exit(1)


@app.command()
def chat():
    """DEPRECATED: Use lightfast-conversation-client instead."""
    main()


@app.command()
def test():
    """DEPRECATED: Use lightfast-conversation-client instead."""
    main()


if __name__ == "__main__":
    app()
