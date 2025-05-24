#!/usr/bin/env python3
"""
Demo of the new modular MCP server architecture.

This script demonstrates:
1. Server auto-discovery
2. Multi-server management
3. AI client integration with multiple servers
4. Configuration management
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path for development
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from lightfast_mcp.clients import MultiServerAIClient
from lightfast_mcp.core import (
    ConfigLoader,
    ServerConfig,
    get_manager,
    get_registry,
)
from lightfast_mcp.utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("ModularDemo")


async def demo_server_discovery():
    """Demonstrate server auto-discovery."""
    print("🔍 DEMO: Server Auto-Discovery")
    print("=" * 50)

    registry = get_registry()

    # Show discovered server types
    server_info = registry.get_server_info()
    print(f"📦 Found {len(server_info)} server types:")

    for server_type, info in server_info.items():
        print(f"   • {server_type} (v{info['version']})")
        print(f"     {info['description']}")
        if info["required_apps"]:
            print(f"     Requires: {', '.join(info['required_apps'])}")
        print()

    return server_info


async def demo_configuration_management():
    """Demonstrate configuration loading and management."""
    print("📝 DEMO: Configuration Management")
    print("=" * 50)

    config_loader = ConfigLoader()

    # Create sample config if it doesn't exist
    config_file = Path("config/servers.yaml")
    if not config_file.exists():
        print("Creating sample configuration...")
        config_loader.create_sample_config()

    # Load configurations
    configs = config_loader.load_servers_config()
    print(f"📋 Loaded {len(configs)} server configurations:")

    for config in configs:
        server_type = config.config.get("type", "unknown")
        print(f"   • {config.name} ({server_type})")
        print(f"     Description: {config.description}")
        if config.transport in ["http", "streamable-http"]:
            print(f"     URL: http://{config.host}:{config.port}{config.path}")
        print()

    return configs


async def demo_multi_server_management(configs):
    """Demonstrate multi-server management."""
    print("🚀 DEMO: Multi-Server Management")
    print("=" * 50)

    manager = get_manager()

    # Filter to only mock servers for this demo (don't require external apps)
    mock_configs = [c for c in configs if c.config.get("type") == "mock"]

    if not mock_configs:
        print("⚠️  No mock server configurations found. Creating a demo config...")
        demo_config = ServerConfig(
            name="demo-mock-server",
            description="Demo mock server for testing",
            port=8099,  # Use a different port to avoid conflicts
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.2},
        )
        mock_configs = [demo_config]

    print(f"Starting {len(mock_configs)} mock servers...")

    # Start servers in background
    results = manager.start_multiple_servers(mock_configs, background=True)

    successful = sum(1 for success in results.values() if success)
    print(f"✅ Successfully started {successful}/{len(mock_configs)} servers")

    if successful > 0:
        # Show running servers
        running_servers = manager.get_running_servers()
        print(f"\n📊 Running Servers ({len(running_servers)}):")

        for name, info in running_servers.items():
            print(f"   • {name}: {'✅ Healthy' if info.is_healthy else '❌ Unhealthy'}")
            if info.url:
                print(f"     URL: {info.url}")
            print(f"     Tools: {', '.join(info.tools)}")

        # Show server URLs
        urls = manager.get_server_urls()
        if urls:
            print("\n📡 Server URLs:")
            for name, url in urls.items():
                print(f"   • {name}: {url}")

        return urls
    else:
        print("❌ No servers started successfully")
        return {}


async def demo_ai_integration(server_urls):
    """Demonstrate AI integration with multiple servers."""
    print("\n🤖 DEMO: AI Integration")
    print("=" * 50)

    if not server_urls:
        print("❌ No servers available for AI integration demo")
        return

    # Check if we have API keys (optional for demo)
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))

    if not has_api_key:
        print("⚠️  No AI API keys found. Demonstrating client setup only...")
        print("   Set ANTHROPIC_API_KEY or OPENAI_API_KEY to try full AI integration")

    try:
        # Create client (this will fail gracefully without API key)
        ai_provider = os.getenv("AI_PROVIDER", "claude")

        if has_api_key:
            client = MultiServerAIClient(ai_provider=ai_provider)
        else:
            print(f"📝 Would create {ai_provider.upper()} client here...")
            print("📝 Client setup process:")

        # Add servers to client
        print("🔗 Adding servers to AI client:")
        for name, url in server_urls.items():
            print(f"   • {name}: {url}")
            if has_api_key:
                client.add_server(name, url, f"Demo {name}")

        if has_api_key:
            # Connect to servers
            print("\n📡 Connecting to servers...")
            connection_results = await client.connect_to_servers()

            successful_connections = sum(1 for success in connection_results.values() if success)
            print(f"✅ Connected to {successful_connections}/{len(server_urls)} servers")

            if successful_connections > 0:
                # Show available tools
                tools_by_server = client.get_all_tools()
                print("\n🛠️  Available Tools:")
                for server_name, tools in tools_by_server.items():
                    print(f"   {server_name}: {', '.join(tools)}")

                # Demo tool execution
                print("\n🎯 Testing tool execution...")
                result = await client.execute_tool("get_server_status")
                print(f"Tool result: {result.get('status', 'No status')}")

                # Cleanup
                await client.disconnect_from_servers()
            else:
                print("❌ Could not connect to any servers")
        else:
            print("📝 Connection process would happen here...")
            print("📝 AI would receive context about all available tools")
            print("📝 User could then chat with AI to control multiple applications")

    except Exception as e:
        print(f"⚠️  AI integration demo error (expected without API key): {e}")


async def demo_cleanup():
    """Clean up demo servers."""
    print("\n🧹 DEMO: Cleanup")
    print("=" * 50)

    manager = get_manager()

    running_count = manager.get_server_count()
    if running_count > 0:
        print(f"Shutting down {running_count} running servers...")
        manager.shutdown_all()
        print("✅ All servers stopped")
    else:
        print("No servers to clean up")


async def main():
    """Run the complete modular system demo."""
    print("🎨 Lightfast MCP - Modular Architecture Demo")
    print("🔗 Multi-Server AI Integration for Creative Applications")
    print("=" * 70)

    try:
        # 1. Demonstrate server discovery
        server_info = await demo_server_discovery()

        print("\n" + "=" * 70)

        # 2. Demonstrate configuration management
        configs = await demo_configuration_management()

        print("\n" + "=" * 70)

        # 3. Demonstrate multi-server management
        server_urls = await demo_multi_server_management(configs)

        print("\n" + "=" * 70)

        # 4. Demonstrate AI integration
        await demo_ai_integration(server_urls)

        print("\n" + "=" * 70)

        # 5. Cleanup
        await demo_cleanup()

        print("\n" + "=" * 70)
        print("🎯 Demo Complete!")
        print("\n📚 Key Benefits Demonstrated:")
        print("   ✅ Auto-discovery of server types")
        print("   ✅ Flexible YAML configuration")
        print("   ✅ Multi-server concurrent management")
        print("   ✅ AI integration with tool routing")
        print("   ✅ Health monitoring and cleanup")

        print("\n🚀 Next Steps:")
        print("   1. Run: python lightfast_mcp_manager.py init")
        print("   2. Run: python lightfast_mcp_manager.py start")
        print("   3. Run: python lightfast_mcp_manager.py ai")
        print("   4. Create your own server following DEV.md")

    except KeyboardInterrupt:
        print("\n👋 Demo interrupted. Cleaning up...")
        await demo_cleanup()
    except Exception as e:
        logger.error(f"Demo error: {e}")
        print(f"❌ Demo error: {e}")
        await demo_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
