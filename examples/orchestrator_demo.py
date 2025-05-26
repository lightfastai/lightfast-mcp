#!/usr/bin/env python3
"""
ServerOrchestrator Demo - Practical Usage Examples
"""

import asyncio
import time

from tools.common import get_logger
from tools.orchestration import get_orchestrator
from tools.orchestration.config_loader import ConfigLoader

logger = get_logger("OrchestratorDemo")


async def demo_basic_usage():
    """Demo basic server orchestration."""
    print("🚀 ServerOrchestrator Demo - Basic Usage")
    print("=" * 50)

    # Get orchestrator instance
    orchestrator = get_orchestrator()

    # Load server configurations
    config_loader = ConfigLoader()
    server_configs = config_loader.load_servers_config()

    if not server_configs:
        print("❌ No server configurations found!")
        print("   Run: uv run lightfast-mcp-orchestrator init")
        return

    print(f"📋 Found {len(server_configs)} server configurations:")
    for config in server_configs:
        print(f"   • {config.name} ({config.config.get('type')}) - {config.transport}")

    print("\n🔄 Starting servers concurrently...")
    start_time = time.time()

    # Start all servers concurrently (this is the magic!)
    result = await orchestrator.start_multiple_servers(
        server_configs, background=True, show_logs=True
    )

    startup_time = time.time() - start_time

    if result.is_success:
        startup_results = result.data
        successful = sum(1 for success in startup_results.values() if success)

        print(f"✅ Startup completed in {startup_time:.2f}s")
        print(f"🎯 Successfully started {successful}/{len(server_configs)} servers")

        # Show detailed results
        print("\n📊 Startup Results:")
        for server_name, success in startup_results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   {status}: {server_name}")

        # Show running server info
        print("\n🟢 Running Servers:")
        running_servers = orchestrator.get_running_servers()
        for name, server_info in running_servers.items():
            uptime = server_info.uptime_seconds if server_info.uptime_seconds else 0
            print(f"   • {name}: {server_info.state} (uptime: {uptime:.1f}s)")
            if server_info.url:
                print(f"     URL: {server_info.url}")
            if server_info.pid:
                print(f"     PID: {server_info.pid}")

        # Wait a bit to show they're running
        print("\n⏳ Servers running... (waiting 5 seconds)")
        await asyncio.sleep(5)

        # Graceful shutdown
        print("\n🛑 Shutting down all servers...")
        orchestrator.shutdown_all()
        print("✅ All servers stopped")

    else:
        print(f"❌ Failed to start servers: {result.error}")


async def demo_individual_server_management():
    """Demo individual server management."""
    print("\n🎯 ServerOrchestrator Demo - Individual Management")
    print("=" * 50)

    orchestrator = get_orchestrator()

    # Create a custom server config
    from lightfast_mcp.core.base_server import ServerConfig

    config = ServerConfig(
        name="demo-server",
        description="Demo Mock Server",
        host="localhost",
        port=8999,
        transport="streamable-http",
        path="/mcp",
        config={"type": "mock"},
    )

    print(f"🚀 Starting individual server: {config.name}")

    # Start single server
    result = await orchestrator.start_server(config, background=True)

    if result.is_success:
        server_info = result.data
        print(f"✅ Started {server_info.name}")
        print(f"   URL: {server_info.url}")
        print(f"   PID: {server_info.pid}")
        print(f"   State: {server_info.state}")

        # Wait a bit
        await asyncio.sleep(2)

        # Stop the server
        print(f"\n🛑 Stopping {config.name}...")
        success = orchestrator.stop_server(config.name)
        print(f"Stop result: {'✅ SUCCESS' if success else '❌ FAILED'}")

    else:
        print(f"❌ Failed to start server: {result.error}")
        print(f"   Error code: {result.error_code}")


async def demo_error_handling():
    """Demo error handling and recovery."""
    print("\n🛡️ ServerOrchestrator Demo - Error Handling")
    print("=" * 50)

    orchestrator = get_orchestrator()

    # Try to start a server with invalid config
    from lightfast_mcp.core.base_server import ServerConfig

    bad_config = ServerConfig(
        name="bad-server",
        description="Server with bad config",
        host="localhost",
        port=8999,
        transport="streamable-http",
        config={"type": "nonexistent"},  # Invalid server type
    )

    print("🧪 Testing error handling with invalid server type...")

    result = await orchestrator.start_server(bad_config, background=True)

    if result.is_failed:
        print("✅ Error properly caught!")
        print(f"   Error: {result.error}")
        print(f"   Code: {result.error_code}")
        print(f"   Status: {result.status}")
    else:
        print("❌ Expected error but server started?!")


async def main():
    """Run all demos."""
    try:
        await demo_basic_usage()
        await demo_individual_server_management()
        await demo_error_handling()

        print("\n🎉 Demo completed successfully!")

    except Exception as e:
        logger.error("Demo failed", error=e)
        print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
