"""
Tool functions for the Mock MCP server.

These functions implement the actual tools that can be called via the MCP protocol.
"""

import asyncio
import json
import time
from typing import Any

from fastmcp import Context

from ...utils.logging_utils import get_logger

logger = get_logger("MockTools")

# Global reference to current server instance for tools to access configuration
_current_server = None


def set_current_server(server):
    """Set the current server instance for tools to access."""
    global _current_server
    _current_server = server


async def get_server_status(ctx: Context) -> dict[str, Any]:
    """
    Get the current status of the mock MCP server.
    """
    logger.info("Received request for server status.")
    await asyncio.sleep(0.1)  # Simulate a very small delay

    if _current_server and hasattr(_current_server, "mcp") and _current_server.mcp:
        server_name = _current_server.mcp.name
        config_name = _current_server.config.name
        description = _current_server.config.description
        version = _current_server.SERVER_VERSION
        server_info = getattr(_current_server, "info", None)
        tools_count = len(
            server_info.tools if server_info and hasattr(server_info, "tools") else []
        )
    else:
        # Fallback for testing
        server_name = "test-mock"
        config_name = "test-mock"
        description = "Mock MCP Server for testing"
        version = "1.0.0"
        tools_count = 3

    return {
        "status": "running",
        "server_name": server_name,
        "config_name": config_name,
        "server_type": "mock",
        "version": version,
        "description": description,
        "timestamp": time.time(),
        "tools_available": tools_count,
        "uptime_seconds": time.time()
        - getattr(_current_server, "_start_time", time.time())
        if _current_server
        else 0,
    }


async def fetch_mock_data(
    ctx: Context, data_id: str, delay_seconds: float | None = None
) -> dict[str, Any]:
    """
    Fetches mock data associated with a given ID after a specified delay.

    Parameters:
    - data_id: The identifier for the mock data to fetch.
    - delay_seconds: The time in seconds to wait before returning the data.
    """
    default_delay = 0.5
    if _current_server and hasattr(_current_server, "default_delay"):
        default_delay = _current_server.default_delay

    if delay_seconds is None:
        delay_seconds = default_delay

    logger.info(
        f"Received request to fetch mock data for id: '{data_id}' with delay: {delay_seconds}s."
    )
    await asyncio.sleep(delay_seconds)

    server_name = "mock-server"
    if _current_server and hasattr(_current_server, "config"):
        server_name = _current_server.config.name

    mock_data = {
        "id": data_id,
        "content": f"This is mock content for {data_id}.",
        "details": {
            "field1": "value1",
            "field2": 123,
            "is_mock": True,
            "server_name": server_name,
        },
        "retrieved_at": time.time(),
        "delay_used": delay_seconds,
    }

    logger.info(f"Returning mock data for id: '{data_id}'.")
    return mock_data


async def execute_mock_action(
    ctx: Context,
    action_name: str,
    parameters: dict[str, Any] | None = None,
    delay_seconds: float | None = None,
) -> dict[str, Any]:
    """
    Simulates the execution of an action with given parameters after a specified delay.

    Parameters:
    - action_name: The name of the mock action to execute.
    - parameters: A dictionary of parameters for the action.
    - delay_seconds: The time in seconds to wait before returning the action result.
    """
    if parameters is None:
        parameters = {}

    default_delay = 0.5
    if _current_server and hasattr(_current_server, "default_delay"):
        default_delay = _current_server.default_delay

    if delay_seconds is None:
        delay_seconds = default_delay

    logger.info(
        f"Received request to execute mock action: '{action_name}' with params: "
        f"{json.dumps(parameters)} and delay: {delay_seconds}s."
    )

    await asyncio.sleep(delay_seconds)

    server_name = "mock-server"
    if _current_server and hasattr(_current_server, "config"):
        server_name = _current_server.config.name

    result = {
        "action_name": action_name,
        "status": "completed_mock",
        "parameters_received": parameters,
        "message": f"Mock action '{action_name}' executed successfully on {server_name}.",
        "completed_at": time.time(),
        "delay_used": delay_seconds,
        "server_info": {
            "name": server_name,
            "type": "mock",
            "version": "1.0.0",
        },
    }

    logger.info(f"Returning result for mock action: '{action_name}'.")
    return result
