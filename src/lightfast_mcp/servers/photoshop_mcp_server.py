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

# System prompt for Photoshop MCP
DEFAULT_SYSTEM_PROMPT = """
You are a helpful assistant with the ability to control Photoshop. 
You can create and modify images, manage layers, and help users with image editing tasks.
When asked to create or modify images, analyze what the user is asking for and use the available tools.

For creating or modifying Photoshop content:
1. Use Photoshop's batchPlay API for reliable automation of image editing tasks
2. BatchPlay accepts ActionDescriptor objects that represent commands in Photoshop
3. Actions can include creating layers, shapes, applying effects, and manipulating selections
4. For simple shapes and edits, use batchPlay with the appropriate descriptors
5. Pay attention to coordinate systems and units (points, pixels, percentages)

When writing batchPlay commands:
- Use proper object structure with _obj and _target properties
- Include proper _enum values where required by Photoshop
- Set appropriate color values, dimensions, and positioning
- Handle errors by checking results and providing feedback

Example 1 - Complete rectangle creation workflow:
```javascript
// Initial setup and constants
const photoshop = require('photoshop');
const app = photoshop.app;
const batchPlay = photoshop.action.batchPlay;

// Get active document or create a new one if none exists
let doc = app.activeDocument;
if (!doc) {
    // Create a new document if none is open
    doc = app.documents.add({
        width: 800,
        height: 600,
        resolution: 72,
        mode: 'RGBColorMode',
        fill: 'white'
    });
}

// Get color values (from a color picker in this example)
const colorHex = "#3498db"; // Example color
const r = parseInt(colorHex.substring(1, 3), 16);
const g = parseInt(colorHex.substring(3, 5), 16);
const b = parseInt(colorHex.substring(5, 7), 16);

// Define rectangle dimensions and position
const docWidth = doc.width;
const docHeight = doc.height;
const width = Math.round(docWidth / 6);
const height = Math.round(docHeight / 6);
const x = Math.round((docWidth - width) / 2);
const y = Math.round((docHeight - height) / 2);

// First select the document
batchPlay(
    [{
        _obj: "select",
        _target: [{
            _ref: "document",
            _enum: "ordinal",
            _value: "targetEnum"
        }],
        _options: { dialogOptions: "dontDisplay" }
    }],
    { synchronousExecution: true, modalBehavior: "fail" }
);

// Create a shape layer with rectangle
batchPlay(
    [{
        _obj: "make",
        _target: [{ _ref: "layer" }],
        using: {
            _obj: "shapeLayer",
            type: {
                _obj: "solidColorLayer",
                color: {
                    _obj: "RGBColor",
                    red: r, green: g, blue: b
                }
            },
            bounds: {
                _obj: "rectangle",
                top: y, left: x, bottom: y + height, right: x + width
            },
            name: "Rectangle Layer"
        },
        _options: { dialogOptions: "dontDisplay" }
    }],
    { synchronousExecution: true, modalBehavior: "fail" }
);
```

Example 2 - Creating a circle shape:
```javascript
// Initial setup and constants
const photoshop = require('photoshop');
const app = photoshop.app;
const batchPlay = photoshop.action.batchPlay;

// Get or create document
let doc = app.activeDocument || app.documents.add({
    width: 800, height: 600, resolution: 72, 
    mode: 'RGBColorMode', fill: 'white'
});

// Define color
const r = 52, g = 152, b = 219; // Blue color

// Define circle dimensions
const docWidth = doc.width;
const docHeight = doc.height;
const radius = Math.round(Math.min(docWidth, docHeight) / 8);
const centerX = Math.round(docWidth / 2);
const centerY = Math.round(docHeight / 2);

// Select document first
batchPlay(
    [{
        _obj: "select",
        _target: [{
            _ref: "document",
            _enum: "ordinal",
            _value: "targetEnum"
        }],
        _options: { dialogOptions: "dontDisplay" }
    }],
    { synchronousExecution: true, modalBehavior: "fail" }
);

// Create circle shape layer
batchPlay(
    [{
        _obj: "make",
        _target: [{ _ref: "layer" }],
        using: {
            _obj: "shapeLayer",
            type: {
                _obj: "solidColorLayer",
                color: {
                    _obj: "RGBColor",
                    red: r, green: g, blue: b
                }
            },
            bounds: {
                _obj: "ellipse",
                top: centerY - radius,
                left: centerX - radius,
                bottom: centerY + radius,
                right: centerX + radius
            },
            name: "Circle Layer"
        },
        _options: { dialogOptions: "dontDisplay" }
    }],
    { synchronousExecution: true, modalBehavior: "fail" }
);
```

For more complex operations, provide step-by-step guidance using Photoshop's UXP and batchPlay API.
"""


async def _process_incoming_messages_for_client(websocket: websockets.WebSocketServerProtocol, client_info: str):
    """Dedicated task to process incoming messages from a single Photoshop client."""
    global responses  # Ensure access to the global responses dictionary
    try:
        async for message in websocket:
            try:
                logger.info(f"Raw message received from Photoshop ({client_info}): {message}")
                data = json.loads(message)
                logger.info(f"Received message from Photoshop ({client_info}, parsed): {data}")

                if "command_id" in data:
                    command_id = data["command_id"]
                    logger.info(f"Message from {client_info} contains command_id: {command_id}")
                    if command_id in responses:
                        logger.info(
                            f"Command_id {command_id} (from {client_info}) found in server responses dict. Resolving future."
                        )
                        future = responses[command_id]
                        if not future.done():
                            future.set_result(data.get("result", {}))
                        else:
                            logger.warning(
                                f"Future for command_id {command_id} (from {client_info}) was already done. Not resolving again."
                            )

                        # Clean up the response entry, critical to prevent re-processing or memory leaks
                        if (
                            command_id in responses
                        ):  # Re-check as future might have been cleared by another thread/task on resolve (though unlikely here)
                            del responses[command_id]
                        logger.info(
                            f"Processed and removed response entry for command ID {command_id} from {client_info}"
                        )
                    else:
                        logger.warning(
                            f"Command_id {command_id} (from {client_info}) received, but NOT found in server responses dict. Current responses keys: {list(responses.keys())}. This might be a late response for a timed-out command."
                        )
                else:
                    logger.info(f"Received unsolicited message (no command_id) from Photoshop ({client_info}): {data}")

            except json.JSONDecodeError:
                logger.error(f"Received invalid JSON from Photoshop ({client_info}): {message}")
            except Exception as e:
                logger.error(f"Error processing message from Photoshop ({client_info}): {str(e)}", exc_info=True)
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection gracefully closed by Photoshop client at {client_info} during message processing.")
    except Exception as e:
        logger.error(f"Error in WebSocket message processing loop for {client_info}: {str(e)}", exc_info=True)
    finally:
        logger.info(f"Message processing task for {client_info} finished.")
        # Ensure client is removed from active set if this task ends due to connection closure
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            logger.info(f"Removed {client_info} from connected_clients set as its message processing task ended.")


async def handle_photoshop_client(websocket: websockets.WebSocketServerProtocol):
    """Handle a WebSocket connection from Photoshop."""
    global connected_clients

    client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"

    if websocket in connected_clients:
        logger.warning(
            f"Client {client_info} is already in connected_clients. This should not happen. Ignoring new connection attempt or closing old one might be needed."
        )
        # Potentially close the new websocket or find and close the old one.
        # For now, we'll proceed, but this indicates a potential issue if multiple handlers are created for the same client object.
        # However, websockets.serve typically creates a new handler for each new connection.
        # So, if this is the same client *reconnecting*, the old websocket object might be stale.
        # Let's ensure the set only contains active connections.
        # A robust way is to clean stale entries from connected_clients periodically or on disconnect.
        pass  # Continuing, will add to set again if not present or replace if object is same.

    logger.info(f"Photoshop client connected from {client_info}")
    connected_clients.add(websocket)

    message_handler_task = None
    try:
        # Start a dedicated task to process incoming messages from this client
        message_handler_task = asyncio.create_task(_process_incoming_messages_for_client(websocket, client_info))
        message_handler_task.set_name(f"MessageHandler-{client_info}")

        # Send an initial ping to verify connection.
        # This send_to_photoshop call will now have its response processed by the message_handler_task.
        logger.info(f"Attempting initial ping to {client_info}...")
        ping_result = await send_to_photoshop("ping", {})  # This will pick a client from connected_clients
        logger.info(f"Initial ping response from a Photoshop client (hopefully {client_info}): {ping_result}")

        # If the client pongs successfully, it means it's responsive.
        # The message_handler_task will continue to listen for further messages (like command results).
        # We await the handler task to keep the connection alive and handle its termination.
        if message_handler_task:
            await message_handler_task

    except PhotoshopTimeoutError as pte:
        logger.error(
            f"Timeout during initial ping for {client_info}: {pte}. The client might not be responding or the message handler failed."
        )
        # The connection will likely be closed by send_to_photoshop's exception handling or client-side closure.
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed by Photoshop client at {client_info} (observed in main handler task).")
    except Exception as e:
        logger.error(f"Error in main WebSocket handler for {client_info}: {str(e)}", exc_info=True)
    finally:
        logger.info(f"Main handler for {client_info} is ending. Cleaning up.")
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            logger.info(f"Removed {client_info} from connected_clients set during main handler cleanup.")

        if message_handler_task and not message_handler_task.done():
            logger.info(f"Cancelling message handler task for {client_info}.")
            message_handler_task.cancel()
            try:
                await message_handler_task  # Allow cancellation to propagate and cleanup within the task.
            except asyncio.CancelledError:
                logger.info(f"Message handler task for {client_info} was successfully cancelled.")
            except Exception as e_cancel:  # Catch any other exceptions during await of cancelled task
                logger.error(
                    f"Error awaiting cancelled message handler task for {client_info}: {e_cancel}", exc_info=True
                )
        elif message_handler_task and message_handler_task.done():
            logger.info(f"Message handler task for {client_info} had already completed.")

        logger.info(f"Photoshop client at {client_info} fully disconnected and cleaned up.")


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
        logger.info(f"Command {command_id} ({command_type}) sent to {client.remote_address}. Waiting for response...")
        try:
            result = await asyncio.wait_for(response_future, timeout=30.0)
            logger.info(f"Received response for command {command_id} ({command_type}): {result}")
            return result
        except TimeoutError:  # Explicitly asyncio.TimeoutError for Python 3.7+
            logger.error(f"Timeout waiting for response to command {command_id} ({command_type}) after 30s.")
            # Clean up the response future from the global dictionary as it will not be fulfilled
            if command_id in responses:
                # Check if the future was somehow resolved by a racing condition (very unlikely)
                if not responses[command_id].done():
                    responses[command_id].set_exception(
                        PhotoshopTimeoutError(f"Server-side timeout for command '{command_type}' (ID: {command_id})")
                    )
                # Even if done, remove it to prevent old entries from accumulating if logic error occurs
                del responses[command_id]
            raise PhotoshopTimeoutError(
                f"Timeout waiting for Photoshop response for command '{command_type}' (ID: {command_id})"
            )

    except (
        websockets.exceptions.ConnectionClosed,
        ConnectionRefusedError,
        ConnectionResetError,
    ) as e:  # Added more connection errors
        logger.error(
            f"Connection error while sending/awaiting command {command_id} ({command_type}): {type(e).__name__} - {str(e)}"
        )
        if command_id in responses:
            if not responses[command_id].done():
                responses[command_id].set_exception(
                    PhotoshopConnectionError(
                        f"Connection to Photoshop lost while awaiting {command_type} (ID: {command_id}): {str(e)}"
                    )
                )
            del responses[command_id]
        raise PhotoshopConnectionError(f"Connection to Photoshop lost: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error sending command: {str(e)}")
        # Clean up
        if command_id in responses:
            del responses[command_id]
        raise PhotoshopMCPError(f"Error sending command to Photoshop: {str(e)}")


async def check_photoshop_connected() -> bool:
    """Temporarily simplified check: Check if any Photoshop clients are in the set and log their types."""
    if not connected_clients:
        logger.info("check_photoshop_connected (simplified): No clients in connected_clients set.")
        return False

    logger.info(
        f"check_photoshop_connected (simplified): connected_clients set contains {len(connected_clients)} item(s)."
    )
    for i, client_obj in enumerate(connected_clients):
        logger.info(f"  Item {i} type: {type(client_obj)}, repr: {client_obj!r}")
        # Attempt to check attributes that a connection object should have, for diagnostic purposes
        try:
            logger.info(f"    Item {i} remote_address: {getattr(client_obj, 'remote_address', 'N/A')}")
            logger.info(f"    Item {i} state: {getattr(client_obj, 'state', 'N/A')}")
            closed_future = getattr(client_obj, "closed", None)
            if closed_future is not None:
                logger.info(f"    Item {i} closed future done: {closed_future.done()}")
            else:
                logger.info(f"    Item {i} has no 'closed' attribute.")
        except Exception as e:
            logger.error(f"    Error accessing attributes for item {i}: {e}")

    # For this temporary test, consider connected if the set is not empty.
    # This bypasses the problematic isinstance/state checks for now.
    if len(connected_clients) > 0:
        logger.info("check_photoshop_connected (simplified): Returning True as connected_clients is not empty.")
        return True
    else:
        logger.info("check_photoshop_connected (simplified): Returning False as connected_clients is empty.")
        return False


async def start_websocket_server():
    """Start the WebSocket server for Photoshop clients to connect to."""
    logger.info(f"Starting WebSocket server on {WS_HOST}:{WS_PORT}")

    try:
        # The serve() function itself returns a Server object, not ServerConnection.
        # ServerConnection objects are passed to the handler (handle_photoshop_client).
        server = await websockets.serve(handle_photoshop_client, WS_HOST, WS_PORT)
        logger.info(f"WebSocket server is running on ws://{WS_HOST}:{WS_PORT} - Server object: {server!r}")
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
    instructions=DEFAULT_SYSTEM_PROMPT,
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
    DEPRECATED: Use execute_photoshop_code instead for UXP panels.
    """
    try:
        logger.info(f"Executing execute_jsx command (deprecated): {jsx_code[:100]}...")

        # Check if Photoshop is connected
        if not await check_photoshop_connected():
            error_result = {
                "status": "error",
                "message": "No Photoshop clients connected",
                "error_type": "PhotoshopConnectionError",
            }
            return json.dumps(error_result)

        # Send the command to Photoshop using the old command type for backward compatibility if needed
        # but ideally, this tool should also use 'execute_photoshop_code_cmd' if the UXP side can handle it
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


@mcp.tool()
async def execute_photoshop_code(ctx: Context, uxp_javascript_code: str) -> str:
    """
    Execute UXP JavaScript code in the connected Photoshop panel.
    This allows running arbitrary UXP-compatible JavaScript in Photoshop's UXP context.
    The script will have access to 'photoshop', 'app', 'batchPlay' and 'addToLog' from the panel's scope.
    """
    try:
        logger.info(f"Executing execute_photoshop_code command: {uxp_javascript_code[:200]}...")

        if not await check_photoshop_connected():
            error_result = {
                "status": "error",
                "message": "No Photoshop clients connected to execute code.",
                "error_type": "PhotoshopConnectionError",
            }
            return json.dumps(error_result)

        # Send the command to Photoshop to execute the UXP JavaScript code
        result = await send_to_photoshop("execute_photoshop_code_cmd", {"script": uxp_javascript_code})

        # The result from send_to_photoshop should be the direct JSON response from the UXP panel
        return json.dumps(result)

    except PhotoshopMCPError as e:
        logger.error(f"Error executing Photoshop UXP code: {str(e)}")
        error_result = {"status": "error", "message": str(e), "error_type": type(e).__name__}
        return json.dumps(error_result)
    except Exception as e:
        logger.error(f"Unexpected error in execute_photoshop_code: {type(e).__name__}: {str(e)}")
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
