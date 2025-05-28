"""
Figma MCP Server with WebSocket communication for plugin integration.
Following the Blender pattern: Plugin acts as server, MCP server acts as client.
"""

import asyncio
import json
import time
from typing import Any, ClassVar

import websockets
from fastmcp import Context

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaWebSocketConnection:
    """Handles WebSocket connection to Figma plugin server."""

    def __init__(self, host: str = "localhost", port: int = 9003):
        self.host = host
        self.port = port
        self.websocket = None
        self.is_connected = False
        self.connection_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to the Figma plugin WebSocket server."""
        if self.is_connected and self.websocket:
            return True

        async with self.connection_lock:
            try:
                uri = f"ws://{self.host}:{self.port}"
                logger.info(f"Connecting to Figma plugin WebSocket at {uri}")

                self.websocket = await websockets.connect(
                    uri, timeout=10, ping_interval=30, ping_timeout=10
                )

                self.is_connected = True
                logger.info(f"Connected to Figma plugin WebSocket at {uri}")

                # Listen for welcome message
                try:
                    welcome_msg = await asyncio.wait_for(
                        self.websocket.recv(), timeout=5.0
                    )
                    welcome_data = json.loads(welcome_msg)
                    if welcome_data.get("type") == "welcome":
                        logger.info(
                            f"Received welcome from Figma plugin: {welcome_data}"
                        )
                    else:
                        logger.warning(f"Unexpected first message: {welcome_data}")
                except asyncio.TimeoutError:
                    logger.warning("No welcome message received from Figma plugin")

                return True

            except Exception as e:
                logger.error(f"Failed to connect to Figma plugin WebSocket: {e}")
                self.websocket = None
                self.is_connected = False
                return False

    async def disconnect(self):
        """Disconnect from the Figma plugin WebSocket."""
        async with self.connection_lock:
            if self.websocket:
                try:
                    await self.websocket.close()
                    logger.info("Disconnected from Figma plugin WebSocket.")
                except Exception as e:
                    logger.error(f"Error during WebSocket disconnect: {e}")
                finally:
                    self.websocket = None
                    self.is_connected = False

    def is_websocket_connected(self) -> bool:
        """Check if connected to Figma plugin WebSocket."""
        return self.is_connected and self.websocket is not None

    async def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to Figma plugin WebSocket and return the response."""
        if not self.is_connected:
            if not await self.connect():
                raise ConnectionError("Failed to connect to Figma plugin WebSocket")

        command = {
            "type": command_type,
            "params": params or {},
            "id": int(time.time() * 1000000),  # Microsecond timestamp as ID
        }

        try:
            logger.info(f"Sending WebSocket command to Figma plugin: {command_type}")

            if not self.websocket:
                raise ConnectionError("WebSocket connection lost")

            # Send command
            await self.websocket.send(json.dumps(command))

            # Wait for response with timeout
            response_data = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)

            response = json.loads(response_data)
            logger.debug(f"Received WebSocket response: {response}")

            # Check if this is the response to our command
            if response.get("requestId") == command["id"]:
                if response.get("status") == "error":
                    error_message = response.get(
                        "error", "Unknown error from Figma plugin"
                    )
                    raise RuntimeError(error_message)

                return response.get("result", {})
            else:
                # This might be a different message, log and try again
                logger.warning(f"Received unexpected message: {response}")
                # For now, return the response anyway
                return response.get("result", response)

        except asyncio.TimeoutError:
            raise TimeoutError("Timeout waiting for Figma plugin WebSocket response")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from Figma plugin: {e}") from e
        except Exception as e:
            await self.disconnect()
            raise ConnectionError(
                f"Error communicating with Figma plugin WebSocket: {e}"
            ) from e


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design automation and collaborative workflows."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma-specific configuration
        figma_host = config.config.get("figma_host", "localhost")
        figma_port = config.config.get("figma_port", 9003)

        self.figma_connection = FigmaWebSocketConnection(figma_host, figma_port)
        self.command_timeout = config.config.get("command_timeout", 30.0)

        logger.info(
            f"Figma server configured for WebSocket at {figma_host}:{figma_port}"
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
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            return await self._check_figma_connection()
        return True

    async def _check_figma_connection(self) -> bool:
        """Check if Figma plugin WebSocket is accessible."""
        try:
            # Try to connect to WebSocket
            uri = f"ws://{self.figma_connection.host}:{self.figma_connection.port}"
            async with websockets.connect(uri, timeout=2) as websocket:
                # Send a quick ping
                await websocket.send(json.dumps({"type": "ping"}))
                # Don't wait for response, just check if connection works
                return True
        except Exception:
            return False

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # Test connection to Figma plugin WebSocket
        try:
            connection_available = await self._check_figma_connection()
            if connection_available:
                logger.info("Figma plugin WebSocket connection test successful")
            else:
                logger.warning(
                    "Figma plugin WebSocket not accessible. Ensure Figma is running with the plugin active and WebSocket server started."
                )
        except Exception as e:
            logger.warning(f"Figma plugin WebSocket connection test failed: {e}")

        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Disconnect from Figma plugin WebSocket
        try:
            await self.figma_connection.disconnect()
        except Exception as e:
            logger.error(f"Error during Figma plugin WebSocket disconnect: {e}")

        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Figma server health check."""
        try:
            # Check if we can reach Figma plugin WebSocket
            is_reachable = await self._check_figma_connection()
            if not is_reachable:
                return False

            # Try a simple ping command
            result = await self.figma_connection.send_command("ping")
            return result.get("message") == "pong"
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
                "figma_connection": {
                    "host": self.figma_connection.host,
                    "port": self.figma_connection.port,
                    "is_connected": self.figma_connection.is_websocket_connected(),
                    "connection_type": "websocket",
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
                "figma_status": {
                    "connected": self.figma_connection.is_websocket_connected(),
                    "host": self.figma_connection.host,
                    "port": self.figma_connection.port,
                    "connection_type": "websocket",
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
            logger.info("Requesting document state from Figma plugin via WebSocket")

            # Send command via WebSocket
            result = await self.figma_connection.send_command("get_document_info")

            # Add diagnostic information
            result["_connection_info"] = {
                "connected": True,
                "host": self.figma_connection.host,
                "port": self.figma_connection.port,
                "server_name": self.config.name,
                "request_time": time.time(),
                "connection_type": "websocket",
            }

            return json.dumps(result, indent=2)

        except ConnectionError as e:
            logger.error(f"WebSocket connection error getting document state: {e}")
            return json.dumps(
                {
                    "error": f"Figma plugin WebSocket not connected: {str(e)}",
                    "type": "ConnectionError",
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
            logger.info(
                f"Executing design command via WebSocket: {design_command[:100]}..."
            )

            # Send command via WebSocket
            result = await self.figma_connection.send_command(
                "execute_design_command",
                {"command": design_command},
            )

            # Add server info to result
            result["_server_info"] = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "execution_time": time.time(),
                "connection_type": "websocket",
            }

            return json.dumps(result, indent=2)

        except ConnectionError as e:
            logger.error(f"WebSocket connection error executing design command: {e}")
            return json.dumps(
                {
                    "error": f"Figma plugin WebSocket not connected: {str(e)}",
                    "type": "ConnectionError",
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Unexpected error executing design command: {e}")
            return json.dumps(
                {
                    "error": f"Unexpected server error during command execution: {str(e)}",
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
        description="Figma MCP Server for design automation",
        config={
            "type": "figma",
            "figma_host": "localhost",
            "figma_port": 9003,
            "command_timeout": 30.0,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
