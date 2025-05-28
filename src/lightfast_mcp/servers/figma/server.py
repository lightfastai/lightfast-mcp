"""
Figma MCP Server with socket communication for plugin integration.
Following the Blender pattern: Plugin acts as server, MCP server acts as client.
"""

import asyncio
import json
import socket
import time
from typing import Any, ClassVar

from fastmcp import Context

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaConnection:
    """Handles connection to Figma plugin socket server."""

    def __init__(self, host: str = "localhost", port: int = 9003):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self) -> bool:
        """Connect to the Figma plugin socket server."""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Figma plugin at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Figma plugin: {e}")
            self.sock = None
            return False

    def disconnect(self):
        """Disconnect from the Figma plugin."""
        if self.sock:
            try:
                self.sock.close()
                logger.info("Disconnected from Figma plugin.")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.sock = None

    def is_connected(self) -> bool:
        """Check if connected to Figma plugin."""
        return self.sock is not None

    def send_command(
        self, command_type: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command to Figma plugin and return the response."""
        if not self.sock:
            if not self.connect():
                raise ConnectionError("Failed to connect to Figma plugin")

        command = {"type": command_type, "params": params or {}}

        try:
            logger.info(f"Sending command to Figma plugin: {command_type}")
            if not self.sock:
                raise ConnectionError("Connection to Figma plugin failed")

            self.sock.sendall(json.dumps(command).encode("utf-8"))

            # Receive response
            response_data = self._receive_response()
            response = json.loads(response_data.decode("utf-8"))

            if response.get("status") == "error":
                error_message = response.get(
                    "message", "Unknown error from Figma plugin"
                )
                raise RuntimeError(error_message)

            return response.get("result", {})

        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from Figma plugin: {e}") from e
        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Error communicating with Figma plugin: {e}") from e

    def _receive_response(self, buffer_size: int = 8192) -> bytes:
        """Receive the complete response from Figma plugin."""
        if not self.sock:
            raise ConnectionError("Not connected to Figma plugin")

        chunks = []
        self.sock.settimeout(15.0)

        try:
            while True:
                chunk = self.sock.recv(buffer_size)
                if not chunk:
                    break

                chunks.append(chunk)

                # Try to parse as complete JSON
                try:
                    data_so_far = b"".join(chunks)
                    json.loads(data_so_far.decode("utf-8"))
                    return data_so_far
                except json.JSONDecodeError:
                    continue

        except TimeoutError:
            raise TimeoutError("Timeout waiting for Figma plugin response") from None
        except Exception as e:
            raise ConnectionError(f"Error receiving response: {e}") from e

        if chunks:
            return b"".join(chunks)
        else:
            raise RuntimeError("No response received from Figma plugin")


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design automation and collaborative workflows."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma-specific configuration
        figma_host = config.config.get("figma_host", "localhost")
        figma_port = config.config.get("figma_port", 9003)

        self.figma_connection = FigmaConnection(figma_host, figma_port)
        self.command_timeout = config.config.get("command_timeout", 30.0)

        logger.info(f"Figma server configured for {figma_host}:{figma_port}")

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
        """Check if Figma plugin is accessible."""
        try:
            # Quick socket check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex(
                (self.figma_connection.host, self.figma_connection.port)
            )
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # Test connection to Figma plugin
        try:
            connection_available = await self._check_figma_connection()
            if connection_available:
                logger.info("Figma plugin connection test successful")
            else:
                logger.warning(
                    "Figma plugin not accessible. Ensure Figma is running with the plugin active."
                )
        except Exception as e:
            logger.warning(f"Figma plugin connection test failed: {e}")

        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Disconnect from Figma plugin
        try:
            self.figma_connection.disconnect()
        except Exception as e:
            logger.error(f"Error during Figma plugin disconnect: {e}")

        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Figma server health check."""
        try:
            # Check if we can reach Figma plugin
            is_reachable = await self._check_figma_connection()
            if not is_reachable:
                return False

            # Try a simple ping command
            await asyncio.get_event_loop().run_in_executor(
                None, self.figma_connection.send_command, "ping"
            )
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
                "figma_connection": {
                    "host": self.figma_connection.host,
                    "port": self.figma_connection.port,
                    "is_connected": self.figma_connection.is_connected(),
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
                    "connected": self.figma_connection.is_connected(),
                    "host": self.figma_connection.host,
                    "port": self.figma_connection.port,
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
        loop = asyncio.get_event_loop()

        try:
            logger.info("Requesting document state from Figma plugin")

            # Run the Figma command in executor to avoid blocking
            result = await loop.run_in_executor(
                None, self.figma_connection.send_command, "get_document_info"
            )

            # Add diagnostic information
            result["_connection_info"] = {
                "connected": True,
                "host": self.figma_connection.host,
                "port": self.figma_connection.port,
                "server_name": self.config.name,
                "request_time": time.time(),
            }

            return json.dumps(result, indent=2)

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
        loop = asyncio.get_event_loop()

        try:
            logger.info(f"Executing design command: {design_command[:100]}...")

            # Run the Figma command in executor
            result = await loop.run_in_executor(
                None,
                self.figma_connection.send_command,
                "execute_design_command",
                {"command": design_command},
            )

            # Add server info to result
            result["_server_info"] = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "execution_time": time.time(),
            }

            return json.dumps(result, indent=2)

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
