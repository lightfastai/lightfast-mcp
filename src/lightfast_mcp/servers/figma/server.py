"""
Figma MCP Server with WebSocket communication for plugin integration.
"""

import asyncio
import json
import time
from typing import Any, ClassVar

import websockets
from fastmcp import Context
from websockets.server import WebSocketServerProtocol

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaWebSocketServer:
    """Handles WebSocket communication with Figma plugin."""

    def __init__(self, host: str = "localhost", port: int = 9003):
        self.host = host
        self.port = port
        self.server = None
        self.clients: set[WebSocketServerProtocol] = set()
        self.is_running = False

    async def start(self):
        """Start the WebSocket server."""
        try:
            # Start the WebSocket server directly
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
            )
            self.is_running = True
            logger.info(f"WebSocket server started on {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.is_running = False
            logger.info("WebSocket server stopped")

        # Cancel the background task if it exists
        if hasattr(self, "_server_task") and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket client connection."""
        self.clients.add(websocket)
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Figma plugin connected: {client_info}")

        try:
            async for message in websocket:
                try:
                    # Handle both text and JSON messages
                    if isinstance(message, str):
                        if message.strip().startswith("{"):
                            # Try to parse as JSON
                            data = json.loads(message)
                            response = await self.process_command(data)
                            await websocket.send(json.dumps(response))
                        else:
                            # Simple text message - echo back
                            await websocket.send(f"Echo: {message}")
                    else:
                        # Binary message - not supported
                        error_response = {
                            "status": "error",
                            "message": "Binary messages not supported",
                            "timestamp": time.time(),
                        }
                        await websocket.send(json.dumps(error_response))

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    error_response = {
                        "status": "error",
                        "message": "Invalid JSON format",
                        "timestamp": time.time(),
                    }
                    await websocket.send(json.dumps(error_response))
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_response = {
                        "status": "error",
                        "message": f"Error processing command: {str(e)}",
                        "timestamp": time.time(),
                    }
                    await websocket.send(json.dumps(error_response))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Figma plugin disconnected: {client_info}")
        except Exception as e:
            logger.error(f"Error handling client {client_info}: {e}")
        finally:
            self.clients.discard(websocket)

    async def process_command(self, command: dict[str, Any]) -> dict[str, Any]:
        """Process command from Figma plugin."""
        command_type = command.get("type")
        params = command.get("params", {})

        logger.info(f"Processing Figma command: {command_type}")

        try:
            if command_type == "ping":
                return {
                    "status": "success",
                    "result": {
                        "message": "pong",
                        "timestamp": time.time(),
                        "server": "figma-mcp",
                    },
                }

            elif command_type == "get_document_info":
                # This would be populated by the Figma plugin
                document_info = params.get("document_info", {})
                return {
                    "status": "success",
                    "result": {
                        "document": document_info,
                        "processed_at": time.time(),
                        "server": "figma-mcp",
                    },
                }

            elif command_type == "execute_design_command":
                # Handle design commands from AI
                design_command = params.get("command", "")
                return {
                    "status": "success",
                    "result": {
                        "command": design_command,
                        "message": "Design command received",
                        "timestamp": time.time(),
                    },
                }

            else:
                return {
                    "status": "error",
                    "message": f"Unknown command type: {command_type}",
                    "timestamp": time.time(),
                }

        except Exception as e:
            logger.error(f"Error processing command {command_type}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": time.time(),
            }

    async def send_to_figma(self, command: dict[str, Any]) -> dict[str, Any]:
        """Send command to Figma plugin and wait for response."""
        if not self.clients:
            raise ConnectionError("No Figma plugin connected")

        # For now, send to the first connected client
        # In a production system, you might want to manage multiple clients
        client = next(iter(self.clients))

        try:
            await client.send(json.dumps(command))

            # Wait for response (simplified - in production you'd want proper request/response matching)
            response_message = await asyncio.wait_for(client.recv(), timeout=10.0)
            return json.loads(response_message)
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout waiting for Figma plugin response")
        except Exception as e:
            raise ConnectionError(f"Error communicating with Figma plugin: {e}")


class FigmaMCPServer(BaseServer):
    """Figma MCP server with WebSocket communication for plugin integration."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # WebSocket server configuration
        websocket_port = config.config.get("websocket_port", 9003)
        websocket_host = config.config.get("websocket_host", "localhost")

        self.websocket_server = FigmaWebSocketServer(websocket_host, websocket_port)
        self.command_timeout = config.config.get("command_timeout", 30.0)

        logger.info(
            f"Figma server configured for WebSocket on {websocket_host}:{websocket_port}"
        )

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register basic tools
        self.mcp.tool()(self.get_server_info)
        self.mcp.tool()(self.ping)

        # Register Figma-specific tools
        self.mcp.tool()(self.get_document_state)
        self.mcp.tool()(self.execute_design_command)

        # Update available tools list
        self.info.tools = [
            "get_server_info",
            "ping",
            "get_document_state",
            "execute_design_command",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            return await self._check_figma_connection()
        return True

    async def _check_figma_connection(self) -> bool:
        """Check if Figma plugin is connected via WebSocket."""
        return (
            self.websocket_server.is_running and len(self.websocket_server.clients) > 0
        )

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # Start WebSocket server
        try:
            await self.websocket_server.start()
            logger.info("WebSocket server started successfully")
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise

        logger.info("Figma server startup complete - waiting for plugin connection")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Stop WebSocket server
        try:
            await self.websocket_server.stop()
        except Exception as e:
            logger.error(f"Error stopping WebSocket server: {e}")

        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Figma server health check."""
        try:
            # Check if WebSocket server is running
            if not self.websocket_server.is_running:
                return False

            # If there are connected clients, try a ping
            if self.websocket_server.clients:
                command = {"type": "ping", "params": {}}
                response = await self.websocket_server.send_to_figma(command)
                return response.get("status") == "success"

            # WebSocket server is running but no clients connected
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    # Tool implementations
    async def get_server_info(self, ctx: Context) -> str:
        """Get basic server information.

        Returns:
            JSON string with server information
        """
        try:
            info = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "server_version": self.SERVER_VERSION,
                "status": "running",
                "websocket_info": {
                    "host": self.websocket_server.host,
                    "port": self.websocket_server.port,
                    "is_running": self.websocket_server.is_running,
                    "connected_clients": len(self.websocket_server.clients),
                },
                "tools": self.info.tools,
            }
            return json.dumps(info, indent=2)
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def ping(self, ctx: Context) -> str:
        """Simple ping tool for testing connectivity.

        Returns:
            JSON string with pong response
        """
        try:
            response = {
                "message": "pong",
                "server": self.config.name,
                "timestamp": ctx.session.request_id
                if hasattr(ctx, "session")
                else "unknown",
                "websocket_status": {
                    "running": self.websocket_server.is_running,
                    "clients": len(self.websocket_server.clients),
                },
            }
            return json.dumps(response, indent=2)
        except Exception as e:
            logger.error(f"Error in ping: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_document_state(self, ctx: Context) -> str:
        """Get current Figma document state from the plugin.

        Returns:
            JSON string with document information
        """
        try:
            logger.info("Requesting document state from Figma plugin")

            # Send command to Figma plugin
            command = {
                "type": "get_document_info",
                "params": {"detailed": True},
            }

            response = await asyncio.wait_for(
                self.websocket_server.send_to_figma(command),
                timeout=self.command_timeout,
            )

            # Add server metadata
            response["_server_info"] = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "request_time": time.time(),
            }

            return json.dumps(response, indent=2)

        except ConnectionError as e:
            logger.error(f"Connection error getting document state: {e}")
            return json.dumps(
                {
                    "error": f"Figma plugin not connected: {str(e)}",
                    "type": "ConnectionError",
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except asyncio.TimeoutError:
            logger.error("Timeout getting document state from Figma")
            return json.dumps(
                {
                    "error": "Timeout waiting for Figma plugin response",
                    "type": "TimeoutError",
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Unexpected error getting document state: {e}")
            return json.dumps(
                {
                    "error": f"Unexpected server error: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )

    async def execute_design_command(self, ctx: Context, design_command: str) -> str:
        """Execute a design command in Figma through the plugin.

        Parameters:
        - design_command: The design command to execute in Figma

        Returns:
            JSON string with execution result
        """
        try:
            logger.info(f"Executing design command: {design_command[:100]}...")

            # Send command to Figma plugin
            command = {
                "type": "execute_design_command",
                "params": {"command": design_command},
            }

            response = await asyncio.wait_for(
                self.websocket_server.send_to_figma(command),
                timeout=self.command_timeout,
            )

            # Add server metadata
            response["_server_info"] = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "execution_time": time.time(),
            }

            return json.dumps(response, indent=2)

        except ConnectionError as e:
            logger.error(f"Connection error executing design command: {e}")
            return json.dumps(
                {
                    "error": f"Figma plugin not connected: {str(e)}",
                    "type": "ConnectionError",
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except asyncio.TimeoutError:
            logger.error("Timeout executing design command in Figma")
            return json.dumps(
                {
                    "error": "Timeout waiting for Figma plugin response",
                    "type": "TimeoutError",
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Unexpected error executing design command: {e}")
            return json.dumps(
                {
                    "error": f"Unexpected server error: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server with WebSocket communication",
        config={
            "type": "figma",
            "websocket_host": "localhost",
            "websocket_port": 9003,
            "command_timeout": 30.0,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
