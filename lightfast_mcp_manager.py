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
import sys
from pathlib import Path

# Add src to Python path for development
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from lightfast_mcp.clients import MultiServerAIClient, ServerSelector
from lightfast_mcp.core import (
    ConfigLoader,
    get_manager,
)
from lightfast_mcp.utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("LightfastMCPManager")


def create_sample_config():
    """Create a sample configuration file."""
    print("📝 Creating sample configuration...")

    config_loader = ConfigLoader()
    success = config_loader.create_sample_config("config/servers.yaml")

    if success:
        print("✅ Sample configuration created at: config/servers.yaml")
        print("📝 Edit this file to customize your server settings.")
        print("🚀 Run 'python lightfast_mcp_manager.py start' to begin!")
    else:
        print("❌ Failed to create sample configuration")


def list_available_servers():
    """List all available server types and configurations."""
    print("🔍 Available Server Types:")
    print("=" * 50)

    from lightfast_mcp.core.server_registry import get_registry

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
        print("   Run 'python lightfast_mcp_manager.py init' to create a sample configuration.")
        return

    for config in configs:
        server_type = config.config.get("type", "unknown")
        print(f"🚀 {config.name} ({server_type})")
        print(f"   Description: {config.description}")
        print(f"   Transport: {config.transport}")
        if config.transport in ["http", "streamable-http"]:
            print(f"   URL: http://{config.host}:{config.port}{config.path}")
        print()


def start_servers_interactive():
    """Start servers with interactive selection."""
    print("🚀 Lightfast MCP Multi-Server Manager")
    print("=" * 50)

    # Interactive server selection
    selector = ServerSelector()
    selected_configs = selector.load_available_servers()

    if not selected_configs:
        print("❌ No server configurations found.")
        print("   Run 'python lightfast_mcp_manager.py init' to create a sample configuration.")
        return

    # Let user select servers
    selected_configs = selector.select_servers_interactive()

    if not selected_configs:
        print("👋 No servers selected. Goodbye!")
        return

    # Start selected servers
    manager = get_manager()

    print(f"\n🚀 Starting {len(selected_configs)} servers...")
    results = manager.start_multiple_servers(selected_configs, background=True)

    # Show results
    successful = sum(1 for success in results.values() if success)
    print(f"✅ Successfully started {successful}/{len(selected_configs)} servers")

    if successful > 0:
        # Show server URLs
        urls = manager.get_server_urls()
        if urls:
            print("\n📡 Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        print("\n🎯 Servers are running! Use the AI client to interact with them.")
        print("   Run 'python lightfast_mcp_manager.py ai' to start the AI client.")
        print("   Press Ctrl+C to shutdown all servers.\n")

        try:
            # Wait for shutdown
            manager.wait_for_shutdown()
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down servers...")
            manager.shutdown_all()
            print("👋 All servers stopped. Goodbye!")


def start_servers_by_names(server_names: list[str]):
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
    results = manager.start_multiple_servers(selected_configs, background=True)

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


async def start_ai_client():
    """Start the AI client for multi-server interaction."""
    print("🤖 Lightfast MCP AI Client")
    print("=" * 50)

    # Check for API keys
    ai_provider = os.getenv("AI_PROVIDER", "claude").lower()

    try:
        client = MultiServerAIClient(ai_provider=ai_provider)
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

    discovered_servers = {}
    for port in common_ports:
        url = f"http://localhost:{port}/mcp"
        try:
            # Quick check if server is responding
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex(("localhost", port))
            sock.close()

            if result == 0:
                server_name = f"server-{port}"
                discovered_servers[server_name] = url
                print(f"   ✅ Found server at {url}")
        except:
            pass

    if not discovered_servers:
        print("❌ No running MCP servers found.")
        print("   Start some servers first with 'python lightfast_mcp_manager.py start'")
        return

    # Add discovered servers to client
    for name, url in discovered_servers.items():
        client.add_server(name, url)

    # Connect to servers
    print(f"\n📡 Connecting to {len(discovered_servers)} servers...")
    connection_results = await client.connect_to_servers()

    successful_connections = sum(1 for success in connection_results.values() if success)
    print(f"✅ Connected to {successful_connections}/{len(discovered_servers)} servers")

    if successful_connections == 0:
        print("❌ Could not connect to any servers.")
        return

    # Show available tools
    tools_by_server = client.get_all_tools()
    print("\n🛠️  Available Tools:")
    for server_name, tools in tools_by_server.items():
        print(f"   {server_name}: {', '.join(tools)}")

    print(f"\n🤖 AI Client ready! (Using {ai_provider.upper()})")
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
                # Get AI response
                print("🤔 AI is thinking...")
                ai_response = await client.chat_with_ai(user_input)

                # Process any tool calls
                final_response = await client.process_ai_response(ai_response)

                print(f"🤖 AI: {final_response}\n")

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
  python lightfast_mcp_manager.py init                    # Create sample configuration
  python lightfast_mcp_manager.py list                    # List available servers
  python lightfast_mcp_manager.py start                   # Interactive server selection
  python lightfast_mcp_manager.py start blender-server    # Start specific server
  python lightfast_mcp_manager.py ai                      # Start AI client
        """,
    )

    parser.add_argument("command", choices=["init", "list", "start", "ai"], help="Command to run")

    parser.add_argument("servers", nargs="*", help="Server names to start (for 'start' command)")

    parser.add_argument("--config", help="Configuration file path")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        configure_logging(level="DEBUG")

    # Handle commands
    if args.command == "init":
        create_sample_config()

    elif args.command == "list":
        list_available_servers()

    elif args.command == "start":
        if args.servers:
            start_servers_by_names(args.servers)
        else:
            start_servers_interactive()

    elif args.command == "ai":
        asyncio.run(start_ai_client())


if __name__ == "__main__":
    main()
