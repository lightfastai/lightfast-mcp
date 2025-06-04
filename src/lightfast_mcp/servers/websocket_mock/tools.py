"""
Tool functions for the WebSocket Mock MCP server.

These functions implement the actual tools that can be called via the MCP protocol
to interact with the WebSocket server and connected clients.
"""

import asyncio
import json
import time
from typing import Any, Dict

from fastmcp import Context

from ...utils.logging_utils import get_logger

logger = get_logger("WebSocketMockTools")

# Global reference to current server instance for tools to access
_current_server = None


def set_current_server(server):
    """Set the current server instance for tools to access."""
    global _current_server
    _current_server = server


def _is_websocket_closed(websocket) -> bool:
    """Check if a WebSocket connection is closed (compatible with different websockets versions)."""
    try:
        # Try the newer websockets library approach
        if hasattr(websocket, "closed"):
            return websocket.closed
        # Try the older approach
        elif hasattr(websocket, "state"):
            from websockets.protocol import State

            return websocket.state == State.CLOSED
        # Fallback - assume it's open if we can't determine
        else:
            return False
    except Exception:
        # If we can't determine, assume it's closed to be safe
        return True


async def get_websocket_server_status(ctx: Context) -> Dict[str, Any]:
    """
    Get the current status of the WebSocket server and connected clients.

    Returns detailed information about the WebSocket server including:
    - Server running status
    - Connection details
    - Connected clients count
    - Server statistics
    """
    logger.info("Received request for WebSocket server status.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server
    server_info = ws_server.get_server_info()

    # Add MCP server information
    mcp_info = {
        "mcp_server_name": _current_server.config.name
        if _current_server.config
        else "WebSocketMockMCP",
        "mcp_server_type": "websocket_mock",
        "mcp_server_version": getattr(_current_server, "SERVER_VERSION", "1.0.0"),
    }

    return {
        "websocket_server": server_info,
        "mcp_server": mcp_info,
        "timestamp": time.time(),
    }


async def send_websocket_message(
    ctx: Context,
    message_type: str,
    payload: Dict[str, Any] | None = None,
    target_client: str | None = None,
) -> Dict[str, Any]:
    """
    Send a message to WebSocket clients.

    Parameters:
    - message_type: The type of message to send
    - payload: Optional payload data to include in the message
    - target_client: Optional client ID to send to specific client (if None, sends to all)

    Returns the result of the send operation.
    """
    logger.info(f"Received request to send WebSocket message: {message_type}")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_clients",
            "message": "No clients connected to send message to",
            "timestamp": time.time(),
        }

    # Prepare message
    message = {
        "type": message_type,
        "from_mcp_server": True,
        "payload": payload or {},
        "timestamp": time.time(),
    }

    try:
        sent_count = 0
        errors = []

        if target_client:
            # Send to specific client
            if target_client in ws_server.clients:
                client = ws_server.clients[target_client]
                if not _is_websocket_closed(client.websocket):
                    await client.websocket.send(json.dumps(message))
                    sent_count = 1
                else:
                    errors.append(f"Client {target_client} connection is closed")
            else:
                errors.append(f"Client {target_client} not found")
        else:
            # Send to all clients
            send_tasks = []
            for client in ws_server.clients.values():
                if not _is_websocket_closed(client.websocket):
                    send_tasks.append(client.websocket.send(json.dumps(message)))

            if send_tasks:
                results = await asyncio.gather(*send_tasks, return_exceptions=True)
                sent_count = sum(1 for r in results if not isinstance(r, Exception))
                errors = [str(r) for r in results if isinstance(r, Exception)]

        return {
            "status": "sent",
            "message_type": message_type,
            "target_client": target_client,
            "sent_to_clients": sent_count,
            "total_clients": len(ws_server.clients),
            "errors": errors,
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error(f"Error sending WebSocket message: {e}")
        return {
            "status": "error",
            "error": f"Exception while sending message: {str(e)}",
            "timestamp": time.time(),
        }


async def get_websocket_clients(ctx: Context) -> Dict[str, Any]:
    """
    Get information about all connected WebSocket clients.

    Returns detailed information about each connected client.
    """
    logger.info("Received request for WebSocket clients information.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    clients_info = []
    for client in ws_server.clients.values():
        client_data = client.to_dict()
        client_data["connection_status"] = (
            "closed" if _is_websocket_closed(client.websocket) else "open"
        )
        clients_info.append(client_data)

    return {
        "status": "success",
        "clients": clients_info,
        "total_clients": len(clients_info),
        "server_info": {
            "host": ws_server.host,
            "port": ws_server.port,
            "url": f"ws://{ws_server.host}:{ws_server.port}",
        },
        "timestamp": time.time(),
    }


async def test_websocket_connection(
    ctx: Context, test_type: str = "ping", target_client: str | None = None
) -> Dict[str, Any]:
    """
    Test WebSocket connections with various test types.

    Parameters:
    - test_type: Type of test to perform (ping, echo, broadcast, stress)
    - target_client: Optional client ID for targeted tests

    Returns the result of the connection test.
    """
    logger.info(f"Received request to test WebSocket connection: {test_type}")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_clients",
            "message": "No clients connected to test",
            "timestamp": time.time(),
        }

    try:
        if test_type == "ping":
            # Send ping to all or specific client
            message = {"type": "ping", "test_id": f"test_{int(time.time())}"}
            result = await send_websocket_message(ctx, "ping", message, target_client)

        elif test_type == "echo":
            # Send echo test
            message = {
                "type": "echo",
                "test_data": "WebSocket echo test",
                "test_id": f"echo_test_{int(time.time())}",
            }
            result = await send_websocket_message(ctx, "echo", message, target_client)

        elif test_type == "broadcast":
            # Test broadcast functionality
            message = {
                "type": "broadcast",
                "message": "Test broadcast from MCP server",
                "test_id": f"broadcast_test_{int(time.time())}",
            }
            result = await send_websocket_message(ctx, "broadcast", message)

        elif test_type == "stress":
            # Send multiple messages quickly
            results = []
            for i in range(5):
                message = {
                    "type": "ping",
                    "test_id": f"stress_test_{i}_{int(time.time())}",
                }
                result = await send_websocket_message(
                    ctx, "ping", message, target_client
                )
                results.append(result)
                await asyncio.sleep(0.1)  # Small delay between messages

            return {
                "status": "stress_test_completed",
                "test_type": test_type,
                "results": results,
                "timestamp": time.time(),
            }

        else:
            return {
                "error": f"Unknown test type: {test_type}",
                "available_types": ["ping", "echo", "broadcast", "stress"],
                "timestamp": time.time(),
            }

        return {
            "status": "test_completed",
            "test_type": test_type,
            "result": result,
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error(f"Error during WebSocket connection test: {e}")
        return {
            "status": "error",
            "test_type": test_type,
            "error": f"Exception during test: {str(e)}",
            "timestamp": time.time(),
        }
