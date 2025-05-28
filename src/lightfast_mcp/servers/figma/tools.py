"""
Tool functions for the Figma MCP server.

These functions implement the actual tools that can be called via the MCP protocol
to interact with Figma plugins and execute JavaScript code.
"""

import json
import time

from fastmcp import Context

from ...exceptions import (
    FigmaCommandError,
    FigmaConnectionError,
    FigmaMCPError,
)
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaTools")

# Global reference to current server instance for tools to access
_current_server = None


def set_current_server(server):
    """Set the current server instance for tools to access."""
    global _current_server
    _current_server = server


async def get_state(ctx: Context) -> str:
    """
    Get detailed information about the current Figma document and connected plugins.

    Returns comprehensive state information including:
    - Current document details (name, id, type)
    - Current page information (name, id, children, selection)
    - Selection details for all selected nodes
    - Viewport state (center, zoom)
    - Plugin connection status
    - Server information
    """
    logger.info("Executing get_state command for Figma.")

    try:
        if not _current_server or not hasattr(_current_server, "websocket_server"):
            raise FigmaConnectionError("Figma WebSocket server not available")

        ws_server = _current_server.websocket_server

        if not ws_server.is_running:
            raise FigmaConnectionError("Figma WebSocket server is not running")

        if not ws_server.clients:
            raise FigmaConnectionError("No Figma plugins connected")

        # Get the first available plugin (or we could add plugin_id parameter later)
        target_client = next(iter(ws_server.clients.values()))

        # Try to get cached document info first
        document_state = None
        if "last_document_info" in target_client.metadata:
            document_state = target_client.metadata["last_document_info"]
            last_update = target_client.metadata.get("last_document_update")
        else:
            # Request fresh document info
            success = await ws_server.send_command_to_plugin(
                target_client.id, "get_document_info"
            )
            if not success:
                raise FigmaCommandError("Failed to request document info from plugin")

            # For now, return a message that fresh data was requested
            # In a real implementation, we might wait for the response
            document_state = {
                "status": "fresh_data_requested",
                "message": "Document info request sent to plugin - check again shortly",
            }
            last_update = None

        # Build comprehensive state information
        result = {
            "figma_document_state": document_state,
            "plugin_connection": {
                "plugin_id": target_client.id,
                "connected_at": target_client.connected_at.isoformat(),
                "last_ping": target_client.last_ping.isoformat()
                if target_client.last_ping
                else None,
                "plugin_info": target_client.plugin_info,
                "remote_address": f"{target_client.websocket.remote_address[0]}:{target_client.websocket.remote_address[1]}"
                if target_client.websocket.remote_address
                else "unknown",
            },
            "websocket_server": {
                "host": ws_server.host,
                "port": ws_server.port,
                "url": f"ws://{ws_server.host}:{ws_server.port}",
                "is_running": ws_server.is_running,
                "total_clients": len(ws_server.clients),
            },
            "_server_info": {
                "server_name": _current_server.config.name,
                "server_type": "figma",
                "server_version": getattr(_current_server, "SERVER_VERSION", "1.0.0"),
                "last_document_update": last_update,
                "connection_time": time.time(),
            },
        }

        return json.dumps(result, indent=2)

    except FigmaMCPError as e:
        logger.error(f"FigmaMCPError in get_state: {e}")
        return json.dumps(
            {
                "error": f"Figma Interaction Error: {str(e)}",
                "type": type(e).__name__,
                "server_name": _current_server.config.name
                if _current_server
                else "FigmaMCP",
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_state: {e}")
        return json.dumps(
            {
                "error": f"Unexpected server error: {str(e)}",
                "type": type(e).__name__,
                "server_name": _current_server.config.name
                if _current_server
                else "FigmaMCP",
            },
            indent=2,
        )


async def execute_code(ctx: Context, code_to_execute: str) -> str:
    """
    Execute arbitrary JavaScript code in Figma.
    This corresponds to the 'execute_code' command in the Figma plugin.

    Parameters:
    - code_to_execute: The JavaScript code string to execute in Figma's context.
      The code has access to the figma API, standard JavaScript, and plugin utilities.

    Example usage:
    - Create a rectangle: "const rect = figma.createRectangle(); rect.resize(100, 100); figma.currentPage.appendChild(rect);"
    - Get selected nodes: "return figma.currentPage.selection.map(n => n.name);"
    - Complex operations with loops, conditionals, and full JavaScript syntax
    """
    logger.info(f"Executing JavaScript code in Figma: {code_to_execute[:100]}...")

    try:
        if not _current_server or not hasattr(_current_server, "websocket_server"):
            raise FigmaConnectionError("Figma WebSocket server not available")

        ws_server = _current_server.websocket_server

        if not ws_server.is_running:
            raise FigmaConnectionError("Figma WebSocket server is not running")

        if not ws_server.clients:
            raise FigmaConnectionError("No Figma plugins connected to execute code")

        # Get the first available plugin (or we could add plugin_id parameter later)
        target_client = next(iter(ws_server.clients.values()))

        # Send code execution command to plugin
        success = await ws_server.send_command_to_plugin(
            target_client.id, "execute_code", {"code": code_to_execute}
        )

        if not success:
            raise FigmaCommandError("Failed to send code execution to plugin")

        # Build result information
        result = {
            "status": "code_sent",
            "code": code_to_execute,
            "plugin_id": target_client.id,
            "message": "JavaScript code sent to Figma plugin for execution",
            "note": "Check the Figma interface and console for execution results",
            "_server_info": {
                "server_name": _current_server.config.name,
                "server_type": "figma",
                "execution_time": time.time(),
            },
        }

        return json.dumps(result, indent=2)

    except FigmaMCPError as e:
        logger.error(f"FigmaMCPError in execute_code: {e}")
        return json.dumps(
            {
                "error": f"Figma Code Execution Error: {str(e)}",
                "type": type(e).__name__,
                "server_name": _current_server.config.name
                if _current_server
                else "FigmaMCP",
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Unexpected error in execute_code: {e}")
        return json.dumps(
            {
                "error": f"Unexpected server error during code execution: {str(e)}",
                "type": type(e).__name__,
                "server_name": _current_server.config.name
                if _current_server
                else "FigmaMCP",
            },
            indent=2,
        )
