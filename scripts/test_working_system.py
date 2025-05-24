#!/usr/bin/env python3
"""
Working system test for the clean modular lightfast-mcp architecture.

This demonstrates that the core system works correctly with UV.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for testing
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from lightfast_mcp.core import ServerConfig, get_manager, get_registry


async def test_registry_discovery():
    """Test that the registry can discover servers."""
    print("🔍 Testing server discovery...")

    registry = get_registry()
    available_types = registry.get_available_server_types()

    print(f"✅ Discovered {len(available_types)} server types: {available_types}")
    assert len(available_types) > 0, "Should discover at least one server type"

    return available_types


async def test_server_creation():
    """Test creating servers via registry."""
    print("🏗️  Testing server creation...")

    registry = get_registry()
    available_types = registry.get_available_server_types()

    servers_created = []

    for server_type in available_types:
        print(f"  Creating {server_type} server...")

        config = ServerConfig(
            name=f"test-{server_type}",
            description=f"Test {server_type} server",
            config={"type": server_type},
        )

        try:
            server = registry.create_server(server_type, config)
            servers_created.append((server_type, server))
            print(f"  ✅ Created {server_type} server: {server}")
        except Exception as e:
            print(f"  ❌ Failed to create {server_type} server: {e}")

    assert len(servers_created) > 0, "Should be able to create at least one server"
    return servers_created


async def test_mock_tools():
    """Test that mock tools work correctly."""
    print("🛠️  Testing mock server tools...")

    # Test the tools directly
    from lightfast_mcp.servers.mock.tools import (
        execute_mock_action,
        fetch_mock_data,
        get_server_status,
    )

    # Test get_server_status
    status = await get_server_status(ctx=None)
    print(f"  ✅ get_server_status returned: {status.get('status')}")
    assert status.get("status") == "running"

    # Test fetch_mock_data
    data = await fetch_mock_data(ctx=None, data_id="test-123", delay_seconds=0.01)
    print(f"  ✅ fetch_mock_data returned data for: {data.get('id')}")
    assert data.get("id") == "test-123"

    # Test execute_mock_action
    result = await execute_mock_action(
        ctx=None, action_name="test_action", delay_seconds=0.01
    )
    print(f"  ✅ execute_mock_action completed: {result.get('action_name')}")
    assert result.get("action_name") == "test_action"

    print("✅ All mock tools working correctly")


async def test_manager_functionality():
    """Test basic manager functionality."""
    print("📋 Testing manager functionality...")

    manager = get_manager()
    print(f"  ✅ Manager instance created: {manager}")

    # Test that we can get server URLs (even if empty)
    urls = manager.get_server_urls()
    print(f"  ✅ Got server URLs: {urls}")

    return manager


async def main():
    """Run all tests."""
    print("🧪 Testing Modular Lightfast MCP System with UV")
    print("=" * 50)

    try:
        # Test registry discovery
        available_types = await test_registry_discovery()
        print()

        # Test server creation
        servers = await test_server_creation()
        print()

        # Test mock tools functionality
        await test_mock_tools()
        print()

        # Test manager
        manager = await test_manager_functionality()
        print()

        print("🎉 All tests passed!")
        print()
        print("✅ Core System Status:")
        print(f"  • Server types discovered: {len(available_types)}")
        print(f"  • Servers created successfully: {len(servers)}")
        print(f"  • Manager instance: {manager.__class__.__name__}")
        print("  • Mock tools: Working")
        print()
        print("🚀 Your modular MCP system is working correctly with UV!")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
