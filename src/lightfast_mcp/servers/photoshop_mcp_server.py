import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import websockets
from mcp.server.fastmcp import Context, FastMCP

from ..exceptions import (
    BlenderConnectionError as PhotoshopConnectionError,
)
from ..exceptions import (
    BlenderMCPError as PhotoshopMCPError,
)
from ..exceptions import (
    BlenderTimeoutError as PhotoshopTimeoutError,
)

# Import from your new logging utility
from ..utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("PhotoshopMCPServer")

# WebSocket server settings
WS_PORT = 8765
WS_HOST = "localhost"

# Active connections set
connected_clients: set[websockets.WebSocketServerProtocol] = set()

# Command queue for handling commands from MCP tools to be sent to Photoshop
command_queue = asyncio.Queue()

# Response storage for commands waiting for responses
responses: dict[str, asyncio.Future] = {}

# Unique command ID counter
command_id_counter = 0


async def handle_photoshop_client(websocket: websockets.WebSocketServerProtocol):
    """Handle a WebSocket connection from Photoshop."""
    global connected_clients

    client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"Photoshop client connected from {client_info}")

    # Add client to connected set
    connected_clients.add(websocket)

    try:
        # Send a ping to verify connection
        ping_result = await send_to_photoshop("ping", {})
        logger.info(f"Initial ping response: {ping_result}")

        # Process incoming messages from this client
        async for message in websocket:
            try:
                # Parse the incoming message
                data = json.loads(message)
                logger.info(f"Received message from Photoshop: {data}")

                # Check if this is a response to a command we sent
                if "command_id" in data:
                    command_id = data["command_id"]
                    if command_id in responses:
                        # Get the future for this command and set its result
                        future = responses[command_id]
                        future.set_result(data.get("result", {}))
                        # Clean up the response entry
                        del responses[command_id]
                        logger.info(f"Processed response for command ID {command_id}")
                else:
                    # This is not a response to our command - could be a notification
                    # or other message from Photoshop that we're not currently handling
                    logger.info(f"Received unsolicited message from Photoshop: {data}")

            except json.JSONDecodeError:
                logger.error(f"Received invalid JSON from Photoshop: {message}")
            except Exception as e:
                logger.error(f"Error processing message from Photoshop: {str(e)}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed by Photoshop client at {client_info}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {str(e)}")
    finally:
        # Remove client from connected set
        connected_clients.remove(websocket)
        logger.info(f"Photoshop client at {client_info} disconnected")


async def send_to_photoshop(command_type: str, params: dict[str, Any] = None) -> dict[str, Any]:
    """Send a command to a connected Photoshop client and wait for response."""
    global command_id_counter, responses

    # Check if we have any connected clients
    if not connected_clients:
        raise PhotoshopConnectionError("No Photoshop clients connected to send command to")

    # Increment command ID
    command_id_counter += 1
    command_id = f"cmd_{command_id_counter}"

    # Create a future to receive the response
    response_future = asyncio.Future()
    responses[command_id] = response_future

    # Create the command message
    command = {
        "command_id": command_id,
        "type": command_type,
        "params": params or {},
    }

    command_json = json.dumps(command)
    logger.info(f"Sending command to Photoshop: {command_type} (ID: {command_id})")

    # Send to all connected clients (usually just one)
    # In a more robust implementation, you might want to target specific clients
    try:
        # Choose the first client in our example
        client = next(iter(connected_clients))
        await client.send(command_json)

        # Wait for the response with a timeout
        try:
            result = await asyncio.wait_for(response_future, timeout=30.0)
            logger.info(f"Received response for command {command_id}")
            return result
        except TimeoutError:
            logger.error(f"Timeout waiting for response to command {command_id}")
            # Clean up
            if command_id in responses:
                del responses[command_id]
            raise PhotoshopTimeoutError(f"Timeout waiting for Photoshop response for command '{command_type}'")

    except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
        logger.error(f"Connection error while sending command: {str(e)}")
        # Clean up
        if command_id in responses:
            del responses[command_id]
        raise PhotoshopConnectionError(f"Connection to Photoshop lost: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error sending command: {str(e)}")
        # Clean up
        if command_id in responses:
            del responses[command_id]
        raise PhotoshopMCPError(f"Error sending command to Photoshop: {str(e)}")


async def check_photoshop_connected() -> bool:
    """Check if any Photoshop clients are connected."""
    return len(connected_clients) > 0


async def start_websocket_server():
    """Start the WebSocket server for Photoshop clients to connect to."""
    logger.info(f"Starting WebSocket server on {WS_HOST}:{WS_PORT}")

    try:
        server = await websockets.serve(handle_photoshop_client, WS_HOST, WS_PORT)
        logger.info(f"WebSocket server is running on ws://{WS_HOST}:{WS_PORT}")
        return server
    except Exception as e:
        logger.error(f"Failed to start WebSocket server: {str(e)}")
        raise PhotoshopMCPError(f"Failed to start WebSocket server: {str(e)}")


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    global connected_clients

    websocket_server = None

    try:
        logger.info("Photoshop MCP Server starting up...")

        # Start the WebSocket server
        websocket_server = await start_websocket_server()

        # Provide context to the MCP server
        yield {"websocket_server": websocket_server}

    except Exception as e:
        logger.error(f"Unexpected error during Photoshop MCP server startup: {type(e).__name__}: {str(e)}")
        raise PhotoshopMCPError(f"Fatal server startup error: {str(e)}") from e

    finally:
        # Clean up
        if websocket_server:
            logger.info("Shutting down WebSocket server...")
            websocket_server.close()
            await websocket_server.wait_closed()

        # Clear connected clients
        connected_clients.clear()
        logger.info("Photoshop MCP Server shutdown complete.")


mcp = FastMCP(
    "PhotoshopMCP",
    description="A simplified MCP server for basic Photoshop interaction via WebSockets.",
    lifespan=server_lifespan,
)


@mcp.tool()
async def get_document_info(ctx: Context) -> str:
    """
    Get detailed information about the current Photoshop document.
    This corresponds to the 'get_document_info' command in the Photoshop addon.
    """
    try:
        logger.info("Executing get_document_info command.")

        # Check if Photoshop is connected
        if not await check_photoshop_connected():
            error_result = {
                "status": "error",
                "message": "No Photoshop clients connected",
                "error_type": "PhotoshopConnectionError",
            }
            return json.dumps(error_result)

        # Send the command to Photoshop
        result = await send_to_photoshop("get_document_info")

        # Add diagnostic information
        result["_connection_info"] = {"connected_clients": len(connected_clients), "type": "WebSocket Server"}

        return json.dumps(result)
    except PhotoshopMCPError as e:
        logger.error(f"Error getting document info: {str(e)}")
        error_result = {"status": "error", "message": str(e), "error_type": type(e).__name__}
        return json.dumps(error_result)
    except Exception as e:
        logger.error(f"Unexpected error in get_document_info: {type(e).__name__}: {str(e)}")
        error_result = {"status": "error", "message": f"Unexpected: {str(e)}", "error_type": type(e).__name__}
        return json.dumps(error_result)


@mcp.tool()
async def execute_jsx(ctx: Context, jsx_code: str) -> str:
    """
    Execute JSX code in Photoshop.
    This allows running arbitrary JavaScript code in the Photoshop environment.
    """
    try:
        logger.info("Executing execute_jsx command.")

        # Check if Photoshop is connected
        if not await check_photoshop_connected():
            error_result = {
                "status": "error",
                "message": "No Photoshop clients connected",
                "error_type": "PhotoshopConnectionError",
            }
            return json.dumps(error_result)

        # Send the command to Photoshop
        result = await send_to_photoshop("execute_jsx", {"code": jsx_code})

        return json.dumps(result)
    except PhotoshopMCPError as e:
        logger.error(f"Error executing JSX code: {str(e)}")
        error_result = {"status": "error", "message": str(e), "error_type": type(e).__name__}
        return json.dumps(error_result)
    except Exception as e:
        logger.error(f"Unexpected error in execute_jsx: {type(e).__name__}: {str(e)}")
        error_result = {"status": "error", "message": f"Unexpected: {str(e)}", "error_type": type(e).__name__}
        return json.dumps(error_result)


def main():
    """Start the Photoshop MCP server."""
    import sys

    # Log the arguments and module info for debugging
    logger.info(f"Starting Photoshop MCP server with args: {sys.argv}")
    logger.info(f"WebSocket server for Photoshop clients will run on ws://{WS_HOST}:{WS_PORT}")

    # Set default port for MCP server (not the WebSocket server)
    port = 35750

    # Check if port is specified in command line args
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            logger.error(f"Invalid port number for MCP server: {sys.argv[1]}")
            sys.exit(1)

    logger.info(f"Starting Photoshop MCP server on port {port}...")
    # Use mcp.run() similar to other server implementations
    mcp.run()


if __name__ == "__main__":
    main()
