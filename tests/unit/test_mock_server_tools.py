import asyncio

import pytest

# Import the module itself to access mcp.name if needed, and the tool functions
from lightfast_mcp import mock_server
from lightfast_mcp.mock_server import (
    execute_mock_action,
    fetch_mock_data,
    get_server_status,
)

# Basic pytest marker for async functions
pytestmark = pytest.mark.asyncio


async def test_get_server_status():
    """Unit test for the get_server_status tool."""
    status = await get_server_status(ctx=None)

    assert isinstance(status, dict)
    assert status.get("status") == "running"
    # Access mcp.name through the imported module if direct access in tests is tricky
    # or rely on the fact that get_server_status itself uses mcp.name from its own module scope
    assert status.get("server_name") == mock_server.mcp.name  # Assumes mcp object is accessible this way
    # Description is no longer returned by the tool
    # assert status.get("description") == SERVER_DESCRIPTION
    assert "timestamp" in status


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


async def test_execute_mock_action():
    """Unit test for the execute_mock_action tool."""
    action_name = "test_action"
    params = {"param1": "value1", "param2": 100}
    delay = 0.01  # Use a very small delay for testing

    result = await execute_mock_action(ctx=None, action_name=action_name, parameters=params, delay_seconds=delay)
    await asyncio.sleep(delay + 0.01)  # Ensure the mock delay has passed

    assert isinstance(result, dict)
    assert result.get("action_name") == action_name
    assert result.get("status") == "completed_mock"
    assert result.get("parameters_received") == params
    assert action_name in result.get("message", "")
    assert "completed_at" in result


async def test_fetch_mock_data_default_delay():
    """Test fetch_mock_data with default delay."""
    data_id = "test-default-delay"
    result = await fetch_mock_data(ctx=None, data_id=data_id)
    await asyncio.sleep(0.01)

    assert result.get("id") == data_id
    assert isinstance(result.get("details", {}), dict)


async def test_execute_mock_action_no_params():
    """Test execute_mock_action with no parameters and default delay."""
    action_name = "action_no_params"
    result = await execute_mock_action(ctx=None, action_name=action_name)
    await asyncio.sleep(0.01)

    assert result.get("action_name") == action_name
    assert result.get("parameters_received") == {}
