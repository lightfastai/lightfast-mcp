import asyncio
import json
import logging
import time
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MockMCPServer")  # Changed logger name

# Create the MCP server
mcp = FastMCP(
    "MockMCP",  # Changed server name
)


@mcp.tool()
async def get_server_status(ctx: Context) -> dict[str, Any]:
    """
    Get the current status of the mock MCP server.
    """
    logger.info("Received request for server status.")
    await asyncio.sleep(0.1)  # Simulate a very small delay
    return {
        "status": "running",
        "server_name": mcp.name,
        "timestamp": time.time(),
    }


@mcp.tool()
async def fetch_mock_data(ctx: Context, data_id: str, delay_seconds: float = 1.0) -> dict[str, Any]:
    """
    Fetches mock data associated with a given ID after a specified delay.

    Parameters:
    - data_id: The identifier for the mock data to fetch.
    - delay_seconds: The time in seconds to wait before returning the data.
    """
    logger.info(f"Received request to fetch mock data for id: '{data_id}' with delay: {delay_seconds}s.")
    await asyncio.sleep(delay_seconds)
    mock_data = {
        "id": data_id,
        "content": f"This is mock content for {data_id}.",
        "details": {"field1": "value1", "field2": 123, "is_mock": True},
        "retrieved_at": time.time(),
    }
    logger.info(f"Returning mock data for id: '{data_id}'.")
    return mock_data


@mcp.tool()
async def execute_mock_action(
    ctx: Context,
    action_name: str,
    parameters: dict[str, Any] = None,
    delay_seconds: float = 0.5,
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
    logger.info(
        f"Received request to execute mock action: '{action_name}' with params: {json.dumps(parameters)} and delay: {delay_seconds}s."  # noqa: E501
    )
    await asyncio.sleep(delay_seconds)
    result = {
        "action_name": action_name,
        "status": "completed_mock",
        "parameters_received": parameters,
        "message": f"Mock action '{action_name}' executed successfully.",
        "completed_at": time.time(),
    }
    logger.info(f"Returning result for mock action: '{action_name}'.")
    return result


def main():
    """Run the Mock MCP server"""
    logger.info(f"Initializing Mock MCP Server: {mcp.name} for host communication.")
    mcp.run()  # Runs using the stdio transport by default when launched by a host


if __name__ == "__main__":
    main()
