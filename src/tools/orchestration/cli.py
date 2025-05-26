#!/usr/bin/env python3
"""
Lightfast MCP Orchestrator - Multi-server management for creative applications.

This is the main entry point for orchestrating multiple MCP servers simultaneously.
Users can select which servers to start, run them in the background, and then
use the dedicated AI client to interact with them.
"""

import argparse
import asyncio

from lightfast_mcp.utils.logging_utils import configure_logging, get_logger

from .config_loader import ConfigLoader
from .server_orchestrator import get_orchestrator
from .server_selector import ServerSelector

# Configure logging
configure_logging(level="INFO")
logger = get_logger("LightfastMCPOrchestrator")


# Async wrapper functions for CLI


def start_multiple_servers_sync(configs, background=True, show_logs=True):
    """Sync wrapper for async start_multiple_servers."""
    orchestrator = get_orchestrator()

    async def _async_start():
        result = await orchestrator.start_multiple_servers(
            configs, background, show_logs
        )
        return result.data if result.is_success else {}

    return asyncio.run(_async_start())


def get_server_urls_sync():
    """Get server URLs from orchestrator."""
    orchestrator = get_orchestrator()
    servers = orchestrator.get_running_servers()
    return {name: info.url for name, info in servers.items() if info.url}


def wait_for_shutdown_sync():
    """Wait for shutdown signal."""
    orchestrator = get_orchestrator()
    orchestrator._shutdown_event.wait()


def shutdown_all_sync():
    """Shutdown all servers."""
    orchestrator = get_orchestrator()
    orchestrator.shutdown_all()


def create_sample_config():
    """Create a sample configuration file."""
    print("[CONFIG] Creating sample configuration...")

    config_loader = ConfigLoader()
    success = config_loader.create_sample_config("servers.yaml")

    if success:
        print("[OK] Sample configuration created at: config/servers.yaml")
        print("[INFO] Edit this file to customize your server settings.")
        print("[START] Run 'lightfast-mcp-orchestrator start' to begin!")
    else:
        print("[ERROR] Failed to create sample configuration")


def list_available_servers():
    """List all available server types and configurations."""
    print("[INFO] Available Server Types:")
    print("=" * 50)

    from .server_registry import get_registry

    registry = get_registry()
    server_info = registry.get_server_info()

    for server_type, info in server_info.items():
        print(f"[SERVER] {server_type}")
        print(f"   Version: {info['version']}")
        print(f"   Description: {info['description']}")
        if info["required_dependencies"]:
            print(f"   Dependencies: {', '.join(info['required_dependencies'])}")
        if info["required_apps"]:
            print(f"   Required Apps: {', '.join(info['required_apps'])}")
        print()

    print("[CONFIG] Server Configurations:")
    print("=" * 50)

    config_loader = ConfigLoader()
    configs = config_loader.load_servers_config()

    if not configs:
        print("[ERROR] No server configurations found.")
        print(
            "   Run 'lightfast-mcp-orchestrator init' to create a sample configuration."
        )
        return

    for config in configs:
        server_type = config.config.get("type", "unknown")
        print(f"[SERVER] {config.name} ({server_type})")
        print(f"   Description: {config.description}")
        print(f"   Transport: {config.transport}")
        if config.transport in ["http", "streamable-http"]:
            print(f"   URL: http://{config.host}:{config.port}{config.path}")
        print()


def start_servers_interactive(show_logs: bool = True):
    """Start servers with interactive selection."""
    print("[START] Lightfast MCP Multi-Server Orchestrator")
    print("=" * 50)

    # Interactive server selection
    selector = ServerSelector()
    selected_configs = selector.load_available_servers()

    if not selected_configs:
        print("[ERROR] No server configurations found.")
        print("   Would you like to create a sample configuration? (y/n)")
        try:
            create_sample = input().strip().lower()
            if create_sample in ["y", "yes"]:
                config_loader = ConfigLoader()
                if config_loader.create_sample_config("servers.yaml"):
                    print("[OK] Sample configuration created at: config/servers.yaml")
                    print("[INFO] Loading the new configuration...")
                    selected_configs = selector.load_available_servers()
                else:
                    print("[ERROR] Failed to create sample configuration")
                    return
            else:
                print("[BYE] No configuration created. Goodbye!")
                return
        except KeyboardInterrupt:
            print("\n[BYE] Cancelled. Goodbye!")
            return

    if not selected_configs:
        print("[ERROR] Still no server configurations available.")
        return

    # Let user select servers
    selected_configs = selector.select_servers_interactive()

    if not selected_configs:
        print("[BYE] No servers selected. Goodbye!")
        return

    print(f"\n[START] Starting {len(selected_configs)} servers...")
    print("   This may take a few moments as servers initialize...")

    results = start_multiple_servers_sync(
        selected_configs, background=True, show_logs=show_logs
    )

    # Show results
    successful = sum(1 for success in results.values() if success)
    print(f"[OK] Successfully started {successful}/{len(selected_configs)} servers")

    # Show any failures
    failed_servers = [name for name, success in results.items() if not success]
    if failed_servers:
        print(f"[ERROR] Failed to start: {', '.join(failed_servers)}")

    if successful > 0:
        # Show server URLs
        urls = get_server_urls_sync()
        if urls:
            print("\n[URLS] Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        print(
            "\n[INFO] Servers are running! Use the dedicated AI client to interact with them."
        )
        print(
            "   Run 'uv run lightfast-conversation-client chat' to start the AI client."
        )
        print("   Press Ctrl+C to shutdown all servers.\n")

        try:
            # Wait for shutdown
            wait_for_shutdown_sync()
        except KeyboardInterrupt:
            print("\n[STOP] Shutting down servers...")
            shutdown_all_sync()
            print("[BYE] All servers stopped. Goodbye!")


def start_servers_by_names(server_names: list[str], show_logs: bool = True):
    """Start specific servers by name."""
    config_loader = ConfigLoader()
    all_configs = config_loader.load_servers_config()

    if not all_configs:
        print("[ERROR] No server configurations found.")
        return

    # Find requested servers
    selected_configs = []
    for name in server_names:
        config = next((c for c in all_configs if c.name == name), None)
        if config:
            selected_configs.append(config)
        else:
            print(f"[WARN] Server configuration not found: {name}")

    if not selected_configs:
        print("[ERROR] No valid servers to start.")
        return

    # Start servers
    results = start_multiple_servers_sync(
        selected_configs, background=True, show_logs=show_logs
    )

    # Show results
    successful = sum(1 for success in results.values() if success)
    print(f"[OK] Successfully started {successful}/{len(selected_configs)} servers")

    if successful > 0:
        urls = get_server_urls_sync()
        if urls:
            print("\n[URLS] Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        try:
            wait_for_shutdown_sync()
        except KeyboardInterrupt:
            print("\n[STOP] Shutting down servers...")
            shutdown_all_sync()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Lightfast MCP Orchestrator - Multi-server management for creative applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lightfast-mcp-orchestrator init                        # Create sample configuration
  lightfast-mcp-orchestrator list                        # List available servers
  lightfast-mcp-orchestrator start                       # Interactive server selection
  lightfast-mcp-orchestrator start blender-server        # Start specific server
  lightfast-mcp-orchestrator start --hide-logs           # Start servers without showing logs
  lightfast-mcp-orchestrator start --verbose             # Start with debug logging and server logs



AI Client (use after starting servers):
  uv run lightfast-conversation-client chat         # Start interactive AI chat
  uv run lightfast-conversation-client test         # Quick AI test
        """,
    )

    parser.add_argument(
        "command", choices=["init", "list", "start"], help="Command to run"
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
        print("[DEBUG] Debug logging enabled")

    # Determine log visibility (--hide-logs takes precedence)
    show_logs = not args.hide_logs if args.hide_logs else args.show_logs
    if args.verbose:
        print(
            f"[INFO] Server logs visibility: {'Enabled' if show_logs else 'Disabled'}"
        )

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


if __name__ == "__main__":
    main()
