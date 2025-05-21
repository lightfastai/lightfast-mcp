import asyncio
import json
import time
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

# Import from your new logging utility
from ..utils.logging_utils import configure_logging, get_logger

# Configure logging using your new utility
# This will configure the root "FastMCP" logger and by extension child loggers obtained via get_logger
# You might want to pass a LOG_LEVEL from an environment variable here if desired.
configure_logging(level="INFO")  # Default to INFO, can be changed or made env-dependent

# Get a specific logger for this server, nested under "FastMCP"
# The name here will be prefixed with "FastMCP." by get_logger, e.g., "FastMCP.MockServer"
logger = get_logger("MockServer")

SERVER_NAME = "MockMCP"  # This is used by FastMCP, not directly for logger name anymore
# SERVER_DESCRIPTION is no longer used in mock_server.py logic

# Create the MCP server
mcp = FastMCP(
    SERVER_NAME,
    # description parameter is not used by FastMCP constructor in the mcp version we targetted earlier for fixes
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
        "server_name": mcp.name,  # FastMCP stores the name given at construction
        # "description": SERVER_DESCRIPTION, # Description is no longer returned
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
    # Use json.dumps for parameters in the log for better readability if it's complex
    logger.info(
        f"Received request to execute mock action: '{action_name}' with params: "
        f"{json.dumps(parameters)} and delay: {delay_seconds}s."
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
    # Logging is configured once at the top of the module.
    logger.info(f"Initializing Mock MCP Server: {SERVER_NAME} (logger: {logger.name}) for host communication.")
    mcp.run()  # Runs using the stdio transport by default when launched by a host


if __name__ == "__main__":
    main()
