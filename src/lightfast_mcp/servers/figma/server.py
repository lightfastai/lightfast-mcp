"""
Figma MCP Server for design manipulation through Figma plugin integration.
Uses direct API communication with WebSocket support for real-time bidirectional communication.
"""

import asyncio
import json
import time
from typing import ClassVar

import websockets
from fastmcp import Context
from websockets.server import WebSocketServerProtocol

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaWebSocketHandler:
    """Handles WebSocket connections for real-time communication with Figma plugin."""

    def __init__(self, server_instance):
        self.server = server_instance
        self.clients = set()
        self.message_handlers = {}
        self.websocket_server = None

    async def register_client(self, websocket: WebSocketServerProtocol):
        """Register a new WebSocket client."""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

        # Send welcome message
        await websocket.send(
            json.dumps(
                {
                    "type": "connected",
                    "server_info": {
                        "name": self.server.config.name,
                        "version": self.server.SERVER_VERSION,
                        "channel": self.server.plugin_channel,
                    },
                }
            )
        )

    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """Unregister a WebSocket client."""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            message_id = data.get("id")

            logger.info(f"Received message: {message_type} (id: {message_id})")

            response = None

            if message_type == "ping":
                response = {
                    "type": "pong",
                    "id": message_id,
                    "timestamp": data.get("timestamp", time.time()),
                }
            elif message_type == "plugin_status_request":
                try:
                    # Directly get status without full tool machinery for plugin
                    status_info = await self.server.get_server_status_for_plugin()
                    response = {
                        "type": "plugin_status_response",
                        "id": message_id,
                        "success": True,
                        "data": status_info,
                    }
                except Exception as e:
                    logger.error(f"Error getting plugin status: {e}")
                    response = {
                        "type": "plugin_status_response",
                        "id": message_id,
                        "success": False,
                        "error": str(e),
                    }
            elif message_type == "tool_call":
                tool_name = data.get("tool")
                params = data.get("params", {})

                # Execute the MCP tool
                try:
                    result = await self.execute_mcp_tool(tool_name, params)
                    response = {
                        "type": "tool_response",
                        "id": message_id,
                        "tool": tool_name,
                        "success": True,
                        "data": result,
                    }
                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    response = {
                        "type": "tool_response",
                        "id": message_id,
                        "tool": tool_name,
                        "success": False,
                        "error": str(e),
                    }

            else:
                response = {
                    "type": "error",
                    "id": message_id,
                    "error": f"Unknown message type: {message_type}",
                }

            if response:
                await websocket.send(json.dumps(response))

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON message: {e}")
            await websocket.send(
                json.dumps({"type": "error", "error": "Invalid JSON message"})
            )
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await websocket.send(json.dumps({"type": "error", "error": str(e)}))

    async def execute_mcp_tool(self, tool_name: str, params: dict):
        """Execute an MCP tool and return the result."""
        # Create a context for the tool execution
        context = Context(self.server.mcp)

        # Map tool names to server methods
        tool_methods = {
            "get_document_info": self.server.get_document_info,
            "get_selection": self.server.get_selection,
            "get_node_info": self.server.get_node_info,
            "create_rectangle": self.server.create_rectangle,
            "create_frame": self.server.create_frame,
            "create_text": self.server.create_text,
            "set_text_content": self.server.set_text_content,
            "move_node": self.server.move_node,
            "resize_node": self.server.resize_node,
            "delete_node": self.server.delete_node,
            "set_fill_color": self.server.set_fill_color,
            "get_server_status": self.server.get_server_status,
        }

        if tool_name not in tool_methods:
            raise ValueError(f"Unknown tool: {tool_name}")

        method = tool_methods[tool_name]

        # Call the method with appropriate parameters
        if tool_name == "get_node_info":
            return await method(context, params.get("node_id"))
        elif tool_name == "create_rectangle":
            return await method(context, **params)
        elif tool_name == "create_frame":
            return await method(context, **params)
        elif tool_name == "create_text":
            return await method(context, **params)
        elif tool_name == "set_text_content":
            return await method(context, params.get("node_id"), params.get("text"))
        elif tool_name == "move_node":
            return await method(
                context, params.get("node_id"), params.get("x"), params.get("y")
            )
        elif tool_name == "resize_node":
            return await method(
                context,
                params.get("node_id"),
                params.get("width"),
                params.get("height"),
            )
        elif tool_name == "delete_node":
            return await method(context, params.get("node_id"))
        elif tool_name == "set_fill_color":
            return await method(context, **params)
        else:
            return await method(context)

    async def broadcast_message(self, message: dict):
        """Broadcast a message to all connected clients."""
        if self.clients:
            message_str = json.dumps(message)
            disconnected = set()

            for client in self.clients:
                try:
                    await client.send(message_str)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    disconnected.add(client)

            # Remove disconnected clients
            for client in disconnected:
                self.clients.discard(client)

    async def client_handler(self, websocket: WebSocketServerProtocol):
        """Handle a WebSocket client connection."""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client connection closed")
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            await self.unregister_client(websocket)

    async def start_websocket_server(self, host: str, port: int):
        """Start the WebSocket server."""
        try:
            self.websocket_server = await websockets.serve(
                self.client_handler, host, port, ping_interval=20, ping_timeout=10
            )
            logger.info(f"WebSocket server started on ws://{host}:{port}")
            # Server is now running and will accept connections
            # Don't block here - let the server run in the background
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def stop_websocket_server(self):
        """Stop the WebSocket server."""
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            logger.info("WebSocket server stopped")


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design manipulation via plugin communication."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma-specific configuration
        self.plugin_channel = config.config.get("plugin_channel", "default")
        self.command_timeout = config.config.get("command_timeout", 30.0)
        self.websocket_port = config.config.get(
            "websocket_port", config.port + 1000
        )  # Default: MCP port + 1000

        # WebSocket handler
        self.websocket_handler = FigmaWebSocketHandler(self)
        self.websocket_task = None

        logger.info(f"Figma server configured with channel: {self.plugin_channel}")
        logger.info(f"WebSocket will run on port: {self.websocket_port}")

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register core design tools
        self.mcp.tool()(self.get_document_info)
        self.mcp.tool()(self.get_selection)
        self.mcp.tool()(self.get_node_info)
        self.mcp.tool()(self.create_rectangle)
        self.mcp.tool()(self.create_frame)
        self.mcp.tool()(self.create_text)
        self.mcp.tool()(self.set_text_content)
        self.mcp.tool()(self.move_node)
        self.mcp.tool()(self.resize_node)
        self.mcp.tool()(self.delete_node)
        self.mcp.tool()(self.set_fill_color)
        self.mcp.tool()(self.get_server_status)

        # Update available tools list
        self.info.tools = [
            "get_document_info",
            "get_selection",
            "get_node_info",
            "create_rectangle",
            "create_frame",
            "create_text",
            "set_text_content",
            "move_node",
            "resize_node",
            "delete_node",
            "set_fill_color",
            "get_server_status",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            # For plugin-based integration, we assume Figma is available
            # The actual check happens when the plugin connects
            return True
        return True

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # Start WebSocket server
        try:
            await self.websocket_handler.start_websocket_server(
                self.config.host, self.websocket_port
            )

            # Check if the server is actually running
            if self.websocket_handler.websocket_server:
                logger.info("WebSocket server started successfully")

                # Create a task to keep the server alive
                self.websocket_task = asyncio.create_task(
                    self.websocket_handler.websocket_server.wait_closed()
                )
            else:
                logger.warning("WebSocket server may not have started properly")

        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")

        logger.info("Plugin-based Figma server ready for MCP communication")
        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Stop WebSocket server
        if self.websocket_task:
            self.websocket_task.cancel()
            try:
                await self.websocket_task
            except asyncio.CancelledError:
                pass

        await self.websocket_handler.stop_websocket_server()
        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform health check."""
        try:
            # Check if WebSocket server is running and we have some basic state
            return (
                self.websocket_handler.websocket_server is not None
                or len(self.websocket_handler.clients) > 0
            )
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    # Tool implementations
    async def get_document_info(self, ctx: Context) -> str:
        """Get information about the current Figma document.

        Returns:
            JSON string with document information
        """
        try:
            # Check if we have connected clients
            if self.websocket_handler.clients:
                # Broadcast request to connected plugins
                await self.websocket_handler.broadcast_message(
                    {"type": "figma_command", "command": "get_current_document"}
                )

                result = {
                    "message": "Document info request sent to connected Figma plugins",
                    "status": "requested",
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting document info: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_selection(self, ctx: Context) -> str:
        """Get information about currently selected elements.

        Returns:
            JSON string with selection information
        """
        try:
            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {"type": "figma_command", "command": "get_current_selection"}
                )

                result = {
                    "message": "Selection info request sent to connected Figma plugins",
                    "status": "requested",
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting selection: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_node_info(self, ctx: Context, node_id: str) -> str:
        """Get detailed information about a specific node.

        Args:
            node_id: The ID of the node to get information about

        Returns:
            JSON string with node information
        """
        try:
            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {
                            "tool": "get_node_info",
                            "params": {"node_id": node_id},
                        },
                    }
                )

                result = {
                    "message": "Node info request sent to connected Figma plugins",
                    "status": "requested",
                    "node_id": node_id,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "node_id": node_id,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting node info for {node_id}: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_rectangle(
        self,
        ctx: Context,
        x: float = 0,
        y: float = 0,
        width: float = 100,
        height: float = 100,
        name: str = "Rectangle",
    ) -> str:
        """Create a new rectangle in Figma.

        Args:
            x: X position
            y: Y position
            width: Width of rectangle
            height: Height of rectangle
            name: Name for the rectangle

        Returns:
            JSON string with created rectangle information
        """
        try:
            params = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "name": name,
            }

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "create_rectangle", "params": params},
                    }
                )

                result = {
                    "message": "Rectangle creation request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "create_rectangle",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "create_rectangle",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating rectangle: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_frame(
        self,
        ctx: Context,
        x: float = 0,
        y: float = 0,
        width: float = 200,
        height: float = 200,
        name: str = "Frame",
    ) -> str:
        """Create a new frame in Figma.

        Args:
            x: X position
            y: Y position
            width: Width of frame
            height: Height of frame
            name: Name for the frame

        Returns:
            JSON string with created frame information
        """
        try:
            params = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "name": name,
            }

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "create_frame", "params": params},
                    }
                )

                result = {
                    "message": "Frame creation request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "create_frame",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "create_frame",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating frame: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_text(
        self,
        ctx: Context,
        text: str,
        x: float = 0,
        y: float = 0,
        font_size: float = 16,
        font_family: str = "Inter",
        name: str = "Text",
    ) -> str:
        """Create a new text node in Figma.

        Args:
            text: Text content
            x: X position
            y: Y position
            font_size: Font size
            font_family: Font family name
            name: Name for the text node

        Returns:
            JSON string with created text node information
        """
        try:
            params = {
                "text": text,
                "x": x,
                "y": y,
                "fontSize": font_size,
                "fontFamily": font_family,
                "name": name,
            }

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "create_text", "params": params},
                    }
                )

                result = {
                    "message": "Text creation request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "create_text",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "create_text",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating text: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def set_text_content(self, ctx: Context, node_id: str, text: str) -> str:
        """Set the text content of a text node.

        Args:
            node_id: ID of the text node
            text: New text content

        Returns:
            JSON string with update result
        """
        try:
            params = {"nodeId": node_id, "text": text}

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "set_text_content", "params": params},
                    }
                )

                result = {
                    "message": "Text content update request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "set_text_content",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "set_text_content",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error setting text content: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def move_node(self, ctx: Context, node_id: str, x: float, y: float) -> str:
        """Move a node to a new position.

        Args:
            node_id: ID of the node to move
            x: New X position
            y: New Y position

        Returns:
            JSON string with move result
        """
        try:
            params = {"nodeId": node_id, "x": x, "y": y}

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "move_node", "params": params},
                    }
                )

                result = {
                    "message": "Node move request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "move_node",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "move_node",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error moving node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def resize_node(
        self, ctx: Context, node_id: str, width: float, height: float
    ) -> str:
        """Resize a node.

        Args:
            node_id: ID of the node to resize
            width: New width
            height: New height

        Returns:
            JSON string with resize result
        """
        try:
            params = {"nodeId": node_id, "width": width, "height": height}

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "resize_node", "params": params},
                    }
                )

                result = {
                    "message": "Node resize request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "resize_node",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "resize_node",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error resizing node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def delete_node(self, ctx: Context, node_id: str) -> str:
        """Delete a node.

        Args:
            node_id: ID of the node to delete

        Returns:
            JSON string with deletion result
        """
        try:
            params = {"nodeId": node_id}

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "delete_node", "params": params},
                    }
                )

                result = {
                    "message": "Node deletion request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "delete_node",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "delete_node",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def set_fill_color(
        self,
        ctx: Context,
        node_id: str,
        r: int,
        g: int,
        b: int,
        a: float = 1.0,
    ) -> str:
        """Set the fill color of a node.

        Args:
            node_id: ID of the node
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            a: Alpha value (0.0-1.0)

        Returns:
            JSON string with color change result
        """
        try:
            params = {"nodeId": node_id, "r": r, "g": g, "b": b, "a": a}

            if self.websocket_handler.clients:
                await self.websocket_handler.broadcast_message(
                    {
                        "type": "figma_command",
                        "command": "execute_tool",
                        "params": {"tool": "set_fill_color", "params": params},
                    }
                )

                result = {
                    "message": "Fill color change request sent to connected Figma plugins",
                    "status": "requested",
                    "command": "set_fill_color",
                    "params": params,
                    "connected_clients": len(self.websocket_handler.clients),
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            else:
                result = {
                    "message": "No Figma plugins currently connected",
                    "status": "no_clients",
                    "command": "set_fill_color",
                    "params": params,
                    "server_info": {
                        "name": self.config.name,
                        "type": self.SERVER_TYPE,
                        "channel": self.plugin_channel,
                    },
                }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error setting fill color: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_server_status(self, ctx: Context) -> str:
        """Get server status and configuration information.

        Returns:
            JSON string with server status
        """
        try:
            status = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "server_version": self.SERVER_VERSION,
                "plugin_channel": self.plugin_channel,
                "command_timeout": self.command_timeout,
                "websocket_port": self.websocket_port,
                "connected_clients": len(self.websocket_handler.clients),
                "status": "running",
                "message": "WebSocket-enabled Figma MCP server ready for real-time communication",
                "websocket_url": f"ws://{self.config.host}:{self.websocket_port}",
            }
            return json.dumps(status, indent=2)
        except Exception as e:
            logger.error(f"Error getting server status: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_server_status_for_plugin(self) -> dict:
        """Get essential server status for the plugin."""
        return {
            "server_name": self.config.name,
            "server_type": self.SERVER_TYPE,
            "server_version": self.SERVER_VERSION,
            "plugin_channel": self.plugin_channel,
            "websocket_port": self.websocket_port,
            "connected_clients": len(self.websocket_handler.clients),
            "status": "running",
            "message": "WebSocket-enabled Figma MCP server ready for real-time communication",
            "websocket_url": f"ws://{self.config.host}:{self.websocket_port}",
        }


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design manipulation",
        config={
            "type": "figma",
            "plugin_channel": "default",
            "command_timeout": 30.0,
            "websocket_port": 9003,  # WebSocket on port 9003
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
