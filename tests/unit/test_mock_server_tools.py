"""
Tests for the modular MockMCPServer tools.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.mock.server import MockMCPServer
from lightfast_mcp.servers.mock.tools import (
    execute_mock_action,
    fetch_mock_data,
    get_server_status,
)


@pytest.fixture
def mock_server():
    """Create a MockMCPServer instance for testing."""
    config = ServerConfig(
        name="test-mock",
        description="Test mock server",
        config={"type": "mock", "delay_seconds": 0.01},
    )
    return MockMCPServer(config)


@pytest.mark.asyncio
async def test_get_server_status(mock_server):
    """Unit test for the get_server_status tool."""
    # Mock the FastMCP instance
    mock_mcp = MagicMock()
    mock_mcp.name = "test-mock"
    mock_server.mcp = mock_mcp

    status = await get_server_status(ctx=None)

    assert isinstance(status, dict)
    assert status.get("status") == "running"
    assert status.get("server_name") == "test-mock"
    assert "timestamp" in status


@pytest.mark.asyncio
async def test_fetch_mock_data():
    """Unit test for the fetch_mock_data tool."""
    data_id = "test-data-123"
    delay = 0.01  # Use a very small delay for testing to keep tests fast

    result = await fetch_mock_data(ctx=None, data_id=data_id, delay_seconds=delay)
    await asyncio.sleep(delay + 0.01)  # Ensure the mock delay has passed

    assert isinstance(result, dict)
    assert result.get("id") == data_id
    assert data_id in result.get("content", "")
    assert result.get("details", {}).get("is_mock") is True
    assert "retrieved_at" in result


@pytest.mark.asyncio
async def test_execute_mock_action():
    """Unit test for the execute_mock_action tool."""
    action_name = "test_action"
    params = {"param1": "value1", "param2": 100}
    delay = 0.01  # Use a very small delay for testing

    result = await execute_mock_action(
        ctx=None, action_name=action_name, parameters=params, delay_seconds=delay
    )
    await asyncio.sleep(delay + 0.01)  # Ensure the mock delay has passed

    assert isinstance(result, dict)
    assert result.get("action_name") == action_name
    assert result.get("status") == "completed_mock"
    assert result.get("parameters_received") == params
    assert action_name in result.get("message", "")
    assert "completed_at" in result


@pytest.mark.asyncio
async def test_fetch_mock_data_default_delay():
    """Test fetch_mock_data with default delay."""
    data_id = "test-default-delay"
    result = await fetch_mock_data(ctx=None, data_id=data_id)
    await asyncio.sleep(0.01)

    assert result.get("id") == data_id
    assert isinstance(result.get("details", {}), dict)


@pytest.mark.asyncio
async def test_execute_mock_action_no_params():
    """Test execute_mock_action with no parameters and default delay."""
    action_name = "action_no_params"
    result = await execute_mock_action(ctx=None, action_name=action_name)
    await asyncio.sleep(0.01)

    assert result.get("action_name") == action_name
    assert result.get("parameters_received") == {}


@pytest.mark.asyncio
async def test_tool_integration_with_server(mock_server):
    """Test that tools work properly when integrated with the server."""
    # Test using the lifespan context directly
    async with mock_server._server_lifespan(mock_server.mcp):
        # Server should be running now
        assert mock_server.info.is_running is True
        assert mock_server.info.is_healthy is True

        # Test that tools are properly registered
        tools = mock_server.get_tools()
        assert "get_server_status" in tools
        assert "fetch_mock_data" in tools
        assert "execute_mock_action" in tools

        # Test calling tools through the tools module functions
        from lightfast_mcp.servers.mock.tools import (
            execute_mock_action,
            fetch_mock_data,
            get_server_status,
        )

        # Test get_server_status
        status = await get_server_status(ctx=None)
        assert status["status"] == "running"
        assert status["server_type"] == "mock"

        # Test fetch_mock_data
        data = await fetch_mock_data(
            ctx=None, data_id="integration-test", delay_seconds=0.01
        )
        assert data["id"] == "integration-test"
        assert "content" in data

        # Test execute_mock_action
        result = await execute_mock_action(
            ctx=None, action_name="integration-action", delay_seconds=0.01
        )
        assert result["action_name"] == "integration-action"
        assert result["status"] == "completed_mock"

    # After lifespan context, server should be stopped
    assert mock_server.info.is_running is False
