"""Blender MCP server implementation using the new modular architecture."""

import asyncio
import json
import socket
import time
from typing import Any, ClassVar

from fastmcp import Context

from ...core.base_server import BaseServer, ServerConfig
from ...exceptions import (
    BlenderCommandError,
    BlenderConnectionError,
    BlenderMCPError,
    BlenderResponseError,
    BlenderTimeoutError,
)
from ...utils.logging_utils import get_logger

logger = get_logger("BlenderMCPServer")


class BlenderConnection:
    """Handles connection to Blender addon."""

    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self) -> bool:
        """Connect to the Blender addon socket server."""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Blender: {e}")
            self.sock = None
            raise BlenderConnectionError(f"Failed to connect to Blender at {self.host}:{self.port}") from e

    def disconnect(self):
        """Disconnect from the Blender addon."""
        if self.sock:
            try:
                self.sock.close()
                logger.info("Disconnected from Blender.")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.sock = None

    def is_connected(self) -> bool:
        """Check if connected to Blender."""
        return self.sock is not None

    def send_command(self, command_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a command to Blender and return the response."""
        if not self.sock:
            self.connect()

        command = {"type": command_type, "params": params or {}}

        try:
            logger.info(f"Sending command to Blender: {command_type}")
            self.sock.sendall(json.dumps(command).encode("utf-8"))

            # Receive response
            response_data = self._receive_response()
            response = json.loads(response_data.decode("utf-8"))

            if response.get("status") == "error":
                error_message = response.get("message", "Unknown error from Blender")
                raise BlenderCommandError(error_message)

            return response.get("result", {})

        except json.JSONDecodeError as e:
            raise BlenderResponseError(f"Invalid JSON response from Blender: {e}") from e
        except BlenderMCPError:
            raise
        except Exception as e:
            self.disconnect()
            raise BlenderConnectionError(f"Error communicating with Blender: {e}") from e

    def _receive_response(self, buffer_size: int = 8192) -> bytes:
        """Receive the complete response from Blender."""
        if not self.sock:
            raise BlenderConnectionError("Not connected to Blender")

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
            raise BlenderTimeoutError("Timeout waiting for Blender response")
        except Exception as e:
            raise BlenderConnectionError(f"Error receiving response: {e}") from e

        if chunks:
            return b"".join(chunks)
        else:
            raise BlenderResponseError("No response received from Blender")


class BlenderMCPServer(BaseServer):
    """Blender MCP server for 3D modeling and animation control."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "blender"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = ["Blender"]

    def __init__(self, config: ServerConfig):
        """Initialize the Blender server."""
        super().__init__(config)

        # Blender-specific configuration
        blender_host = config.config.get("blender_host", "localhost")
        blender_port = config.config.get("blender_port", 9876)

        self.blender_connection = BlenderConnection(blender_host, blender_port)

        logger.info(f"Blender server configured for {blender_host}:{blender_port}")

    def _register_tools(self):
        """Register Blender server tools."""
        if not self.mcp:
            return

        # Register tools
        self.mcp.tool()(self.get_state)
        self.mcp.tool()(self.execute_command)

        # Update available tools list
        self.info.tools = ["get_state", "execute_command"]
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _check_application(self, app: str) -> bool:
        """Check if Blender is available."""
        if app.lower() == "blender":
            return await self._check_blender_connection()
        return True

    async def _check_blender_connection(self) -> bool:
        """Check if Blender is accessible."""
        try:
            # Quick socket check
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex((self.blender_connection.host, self.blender_connection.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _on_startup(self):
        """Blender server startup logic."""
        logger.info(f"Blender server '{self.config.name}' starting up...")

        # Test connection to Blender
        try:
            # Try to connect and ping
            connection_available = await self._check_blender_connection()
            if connection_available:
                logger.info("Blender connection test successful")
            else:
                logger.warning("Blender not accessible. Ensure Blender is running with the addon active.")
        except Exception as e:
            logger.warning(f"Blender connection test failed: {e}")

        logger.info("Blender server startup complete")

    async def _on_shutdown(self):
        """Blender server shutdown logic."""
        logger.info(f"Blender server '{self.config.name}' shutting down...")

        # Disconnect from Blender
        try:
            self.blender_connection.disconnect()
        except Exception as e:
            logger.error(f"Error during Blender disconnect: {e}")

        logger.info("Blender server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Blender server health check."""
        try:
            # Check if we can reach Blender
            is_reachable = await self._check_blender_connection()
            if not is_reachable:
                return False

            # Try a simple ping command
            result = await asyncio.get_event_loop().run_in_executor(None, self.blender_connection.send_command, "ping")
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    # Tool implementations
    async def get_state(self, ctx: Context) -> str:
        """
        Get detailed information about the current Blender scene.
        This corresponds to the 'get_scene_info' command in the Blender addon.
        """
        loop = asyncio.get_event_loop()

        try:
            logger.info("Executing get_state (get_scene_info) command.")

            # Run the Blender command in executor to avoid blocking
            result = await loop.run_in_executor(None, self.blender_connection.send_command, "get_scene_info")

            # Add diagnostic information
            result["_connection_info"] = {
                "connected": True,
                "host": self.blender_connection.host,
                "port": self.blender_connection.port,
                "server_name": self.config.name,
                "connection_time": time.time(),
            }

            return json.dumps(result, indent=2)

        except BlenderMCPError as e:
            logger.error(f"BlenderMCPError in get_state: {e}")
            return json.dumps(
                {
                    "error": f"Blender Interaction Error: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Unexpected error in get_state: {e}")
            return json.dumps(
                {
                    "error": f"Unexpected server error: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )

    async def execute_command(self, ctx: Context, code_to_execute: str) -> str:
        """
        Execute arbitrary Python code in Blender.
        This corresponds to the 'execute_code' command in the Blender addon.

        Parameters:
        - code_to_execute: The Python code string to execute in Blender's context.
        """
        loop = asyncio.get_event_loop()

        try:
            logger.info(f"Executing command with code: {code_to_execute[:100]}...")

            # Run the Blender command in executor
            result = await loop.run_in_executor(
                None, self.blender_connection.send_command, "execute_code", {"code": code_to_execute}
            )

            # Add server info to result
            result["_server_info"] = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "execution_time": time.time(),
            }

            return json.dumps(result, indent=2)

        except BlenderMCPError as e:
            logger.error(f"BlenderMCPError in execute_command: {e}")
            return json.dumps(
                {
                    "error": f"Blender Command Execution Error: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )
        except Exception as e:
            logger.error(f"Unexpected error in execute_command: {e}")
            return json.dumps(
                {
                    "error": f"Unexpected server error during command execution: {str(e)}",
                    "type": type(e).__name__,
                    "server_name": self.config.name,
                },
                indent=2,
            )


def main():
    """Run the Blender MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="BlenderMCP",
        description="Blender MCP Server for 3D modeling and animation",
        config={
            "type": "blender",
            "blender_host": "localhost",
            "blender_port": 9876,
        },
    )

    # Create and run the server
    server = BlenderMCPServer(config)
    logger.info(f"Starting standalone Blender server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
