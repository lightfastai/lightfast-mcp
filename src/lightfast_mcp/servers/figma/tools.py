"""
Tool functions for the Figma MCP server.

These functions implement the actual tools that can be called via the MCP protocol
to interact with Figma plugins and execute design commands.
"""

import time
from typing import Any, Dict

from fastmcp import Context

from ...utils.logging_utils import get_logger

logger = get_logger("FigmaTools")

# Global reference to current server instance for tools to access
_current_server = None


def set_current_server(server):
    """Set the current server instance for tools to access."""
    global _current_server
    _current_server = server


async def get_figma_server_status(ctx: Context) -> Dict[str, Any]:
    """
    Get the current status of the Figma WebSocket server and connected plugins.

    Returns detailed information about the WebSocket server including:
    - Server running status
    - Connection details
    - Connected Figma plugins count
    - Server statistics
    """
    logger.info("Received request for Figma server status.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server
    server_info = ws_server.get_server_info()

    # Add MCP server information
    mcp_info = {
        "mcp_server_name": _current_server.config.name
        if _current_server.config
        else "FigmaMCP",
        "mcp_server_type": "figma",
        "mcp_server_version": getattr(_current_server, "SERVER_VERSION", "1.0.0"),
    }

    return {
        "figma_websocket_server": server_info,
        "mcp_server": mcp_info,
        "timestamp": time.time(),
    }


async def start_figma_server(ctx: Context) -> Dict[str, Any]:
    """
    Start the Figma WebSocket server if it's not already running.

    Returns the result of the start operation including server details.
    """
    logger.info("Received request to start Figma WebSocket server.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if ws_server.is_running:
        return {
            "status": "already_running",
            "message": "Figma WebSocket server is already running",
            "server_info": ws_server.get_server_info(),
            "timestamp": time.time(),
        }

    try:
        success = await ws_server.start()
        if success:
            return {
                "status": "started",
                "message": "Figma WebSocket server started successfully",
                "server_info": ws_server.get_server_info(),
                "timestamp": time.time(),
            }
        else:
            return {
                "status": "failed",
                "error": "Failed to start Figma WebSocket server",
                "timestamp": time.time(),
            }
    except Exception as e:
        logger.error(f"Error starting Figma WebSocket server: {e}")
        return {
            "status": "error",
            "error": f"Exception while starting server: {str(e)}",
            "timestamp": time.time(),
        }


async def stop_figma_server(ctx: Context) -> Dict[str, Any]:
    """
    Stop the Figma WebSocket server if it's running.

    Returns the result of the stop operation.
    """
    logger.info("Received request to stop Figma WebSocket server.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "status": "already_stopped",
            "message": "Figma WebSocket server is not running",
            "timestamp": time.time(),
        }

    try:
        await ws_server.stop()
        return {
            "status": "stopped",
            "message": "Figma WebSocket server stopped successfully",
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"Error stopping Figma WebSocket server: {e}")
        return {
            "status": "error",
            "error": f"Exception while stopping server: {str(e)}",
            "timestamp": time.time(),
        }


async def get_figma_plugins(ctx: Context) -> Dict[str, Any]:
    """
    Get information about all connected Figma plugins.

    Returns detailed information about each connected Figma plugin.
    """
    logger.info("Received request for Figma plugins information.")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "Figma WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    plugins_info = []
    for client in ws_server.clients.values():
        client_data = client.to_dict()
        plugins_info.append(client_data)

    return {
        "status": "success",
        "plugins": plugins_info,
        "total_plugins": len(plugins_info),
        "server_info": {
            "host": ws_server.host,
            "port": ws_server.port,
            "url": f"ws://{ws_server.host}:{ws_server.port}",
        },
        "timestamp": time.time(),
    }


async def ping_figma_plugin(
    ctx: Context, plugin_id: str | None = None
) -> Dict[str, Any]:
    """
    Send a ping to Figma plugins to test connectivity.

    Parameters:
    - plugin_id: Optional plugin ID to ping specific plugin (if None, pings all)

    Returns the result of the ping operation.
    """
    logger.info(f"Received request to ping Figma plugin: {plugin_id or 'all'}")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "Figma WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_plugins",
            "message": "No Figma plugins connected to ping",
            "timestamp": time.time(),
        }

    try:
        if plugin_id:
            # Ping specific plugin
            success = await ws_server.send_command_to_plugin(plugin_id, "ping")
            return {
                "status": "ping_sent" if success else "ping_failed",
                "plugin_id": plugin_id,
                "timestamp": time.time(),
            }
        else:
            # Ping all plugins
            sent_count = await ws_server.broadcast_to_plugins("ping")
            return {
                "status": "ping_broadcast",
                "sent_to_plugins": sent_count,
                "total_plugins": len(ws_server.clients),
                "timestamp": time.time(),
            }

    except Exception as e:
        logger.error(f"Error pinging Figma plugin: {e}")
        return {
            "status": "error",
            "error": f"Exception while pinging: {str(e)}",
            "timestamp": time.time(),
        }


async def get_document_state(
    ctx: Context, plugin_id: str | None = None
) -> Dict[str, Any]:
    """
    Get the current document state from Figma plugins.

    Parameters:
    - plugin_id: Optional plugin ID to get state from specific plugin (if None, gets from first available)

    Returns the current Figma document state.
    """
    logger.info(
        f"Received request to get document state from plugin: {plugin_id or 'first available'}"
    )

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "Figma WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_plugins",
            "message": "No Figma plugins connected",
            "timestamp": time.time(),
        }

    try:
        target_client = None

        if plugin_id:
            # Use specific plugin
            if plugin_id in ws_server.clients:
                target_client = ws_server.clients[plugin_id]
            else:
                return {
                    "error": f"Plugin {plugin_id} not found",
                    "status": "plugin_not_found",
                    "timestamp": time.time(),
                }
        else:
            # Use first available plugin
            target_client = next(iter(ws_server.clients.values()))

        # Check if we have cached document info
        if "last_document_info" in target_client.metadata:
            return {
                "status": "success",
                "plugin_id": target_client.id,
                "document_state": target_client.metadata["last_document_info"],
                "last_update": target_client.metadata.get("last_document_update"),
                "source": "cached",
                "timestamp": time.time(),
            }

        # Request fresh document info
        success = await ws_server.send_command_to_plugin(
            target_client.id, "get_document_info"
        )

        if success:
            return {
                "status": "request_sent",
                "plugin_id": target_client.id,
                "message": "Document info request sent to plugin",
                "note": "Use get_figma_plugins to check for updated document state",
                "timestamp": time.time(),
            }
        else:
            return {
                "status": "request_failed",
                "plugin_id": target_client.id,
                "error": "Failed to send document info request",
                "timestamp": time.time(),
            }

    except Exception as e:
        logger.error(f"Error getting document state: {e}")
        return {
            "status": "error",
            "error": f"Exception while getting document state: {str(e)}",
            "timestamp": time.time(),
        }


async def execute_design_command(
    ctx: Context, command: str, plugin_id: str | None = None
) -> Dict[str, Any]:
    """
    Execute a design command in Figma.

    Parameters:
    - command: The design command to execute (e.g., "create rectangle", "create circle")
    - plugin_id: Optional plugin ID to execute command on specific plugin (if None, uses first available)

    Returns the result of the design command execution.
    """
    logger.info(f"Received request to execute design command: {command}")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "Figma WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_plugins",
            "message": "No Figma plugins connected to execute command",
            "timestamp": time.time(),
        }

    try:
        target_client = None

        if plugin_id:
            # Use specific plugin
            if plugin_id in ws_server.clients:
                target_client = ws_server.clients[plugin_id]
            else:
                return {
                    "error": f"Plugin {plugin_id} not found",
                    "status": "plugin_not_found",
                    "timestamp": time.time(),
                }
        else:
            # Use first available plugin
            target_client = next(iter(ws_server.clients.values()))

        # Send design command to plugin
        success = await ws_server.send_command_to_plugin(
            target_client.id, "execute_design_command", {"command": command}
        )

        if success:
            return {
                "status": "command_sent",
                "plugin_id": target_client.id,
                "command": command,
                "message": "Design command sent to Figma plugin",
                "timestamp": time.time(),
            }
        else:
            return {
                "status": "command_failed",
                "plugin_id": target_client.id,
                "command": command,
                "error": "Failed to send design command to plugin",
                "timestamp": time.time(),
            }

    except Exception as e:
        logger.error(f"Error executing design command: {e}")
        return {
            "status": "error",
            "command": command,
            "error": f"Exception while executing design command: {str(e)}",
            "timestamp": time.time(),
        }


async def broadcast_design_command(ctx: Context, command: str) -> Dict[str, Any]:
    """
    Broadcast a design command to all connected Figma plugins.

    Parameters:
    - command: The design command to broadcast

    Returns the result of the broadcast operation.
    """
    logger.info(f"Received request to broadcast design command: {command}")

    if not _current_server or not hasattr(_current_server, "websocket_server"):
        return {
            "error": "Figma WebSocket server not available",
            "status": "not_initialized",
            "timestamp": time.time(),
        }

    ws_server = _current_server.websocket_server

    if not ws_server.is_running:
        return {
            "error": "Figma WebSocket server is not running",
            "status": "server_not_running",
            "timestamp": time.time(),
        }

    if not ws_server.clients:
        return {
            "status": "no_plugins",
            "message": "No Figma plugins connected to broadcast to",
            "timestamp": time.time(),
        }

    try:
        sent_count = await ws_server.broadcast_to_plugins(
            "execute_design_command", {"command": command}
        )

        return {
            "status": "broadcast_sent",
            "command": command,
            "sent_to_plugins": sent_count,
            "total_plugins": len(ws_server.clients),
            "message": f"Design command broadcasted to {sent_count} Figma plugins",
            "timestamp": time.time(),
        }

    except Exception as e:
        logger.error(f"Error broadcasting design command: {e}")
        return {
            "status": "error",
            "command": command,
            "error": f"Exception while broadcasting design command: {str(e)}",
            "timestamp": time.time(),
        }
