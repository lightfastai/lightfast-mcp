"""WebSocket Mock MCP server implementation using the new modular architecture."""

from typing import ClassVar

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger
from . import tools
from .websocket_server import WebSocketMockServer

logger = get_logger("WebSocketMockMCPServer")


class WebSocketMockMCPServer(BaseServer):
    """WebSocket Mock MCP server for testing WebSocket communications."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "websocket_mock"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = []

    def __init__(self, config: ServerConfig):
        """Initialize the WebSocket mock server."""
        super().__init__(config)

        # WebSocket server configuration
        ws_host = config.config.get("websocket_host", "localhost")
        ws_port = config.config.get("websocket_port", 9004)

        # Create the WebSocket server instance
        self.websocket_server = WebSocketMockServer(host=ws_host, port=ws_port)

        # Set this server instance in tools module for access
        tools.set_current_server(self)

        logger.info(
            f"WebSocket Mock server configured for WebSocket server at {ws_host}:{ws_port}"
        )

    def _register_tools(self):
        """Register WebSocket mock server tools."""
        if not self.mcp:
            return

        # Register tools from the tools module
        self.mcp.tool()(tools.get_websocket_server_status)
        self.mcp.tool()(tools.send_websocket_message)
        self.mcp.tool()(tools.get_websocket_clients)
        self.mcp.tool()(tools.test_websocket_connection)

        # Update the server info with available tools
        self.info.tools = [
            "get_websocket_server_status",
            "send_websocket_message",
            "get_websocket_clients",
            "test_websocket_connection",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _on_startup(self):
        """WebSocket mock server startup logic."""
        logger.info(f"WebSocket Mock server '{self.config.name}' starting up...")

        # Always start the WebSocket server
        logger.info("Starting WebSocket server...")
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                success = await self.websocket_server.start()
                if success:
                    logger.info("✅ WebSocket server started successfully")
                    break
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(
                            f"⚠️ Failed to start WebSocket server, retrying ({retry_count}/{max_retries})..."
                        )
                        # Try a different port if the default one is in use
                        self.websocket_server.port += 1
                        logger.info(f"Trying port {self.websocket_server.port}")
                    else:
                        logger.error(
                            "❌ Failed to start WebSocket server after all retries"
                        )
                        raise RuntimeError("Could not start WebSocket server")
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(
                        f"⚠️ Error starting WebSocket server, retrying ({retry_count}/{max_retries}): {e}"
                    )
                    # Try a different port if there's a port conflict
                    self.websocket_server.port += 1
                    logger.info(f"Trying port {self.websocket_server.port}")
                else:
                    logger.error(
                        f"❌ Failed to start WebSocket server after all retries: {e}"
                    )
                    raise RuntimeError(f"Could not start WebSocket server: {e}")

        logger.info("WebSocket Mock server startup complete")

    async def _on_shutdown(self):
        """WebSocket mock server shutdown logic."""
        logger.info(f"WebSocket Mock server '{self.config.name}' shutting down...")

        # Stop the WebSocket server
        try:
            if self.websocket_server.is_running:
                logger.info("Stopping WebSocket server...")
                await self.websocket_server.stop()
                logger.info("✅ WebSocket server stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping WebSocket server: {e}")

        logger.info("WebSocket Mock server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform WebSocket mock server health check."""
        try:
            # Check if the MCP server is running
            if not self.info.is_running:
                return False

            # Check WebSocket server status - it should always be running
            if not self.websocket_server.is_running:
                logger.warning("Health check failed: WebSocket server is not running")
                return False

            # If WebSocket server is running, check if it's responsive
            server_info = self.websocket_server.get_server_info()
            return server_info.get("is_running", False)

        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False


def main():
    """Run the WebSocket Mock MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="WebSocketMockMCP",
        description="WebSocket Mock MCP Server for testing WebSocket communications",
        config={
            "type": "websocket_mock",
            "websocket_host": "localhost",
            "websocket_port": 9004,
        },
    )

    # Create and run the server
    server = WebSocketMockMCPServer(config)
    logger.info(f"Starting standalone WebSocket Mock server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
