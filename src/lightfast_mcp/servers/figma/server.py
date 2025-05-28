"""Figma MCP server implementation using the new modular architecture."""

from typing import ClassVar

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger
from . import tools
from .websocket_server import FigmaWebSocketServer

logger = get_logger("FigmaMCPServer")


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design automation and collaborative design workflows."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma WebSocket server configuration
        figma_host = config.config.get("figma_host", "localhost")
        figma_port = config.config.get("figma_port", 9003)

        # Create the WebSocket server instance
        self.websocket_server = FigmaWebSocketServer(host=figma_host, port=figma_port)

        # Auto-start configuration
        self.auto_start_websocket = config.config.get("auto_start_websocket", True)

        # Set this server instance in tools module for access
        tools.set_current_server(self)

        logger.info(
            f"Figma server configured for WebSocket server at {figma_host}:{figma_port}"
        )

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register tools from the tools module
        self.mcp.tool()(tools.get_figma_server_status)
        self.mcp.tool()(tools.start_figma_server)
        self.mcp.tool()(tools.stop_figma_server)
        self.mcp.tool()(tools.get_figma_plugins)
        self.mcp.tool()(tools.ping_figma_plugin)
        self.mcp.tool()(tools.get_document_state)
        self.mcp.tool()(tools.execute_design_command)
        self.mcp.tool()(tools.broadcast_design_command)

        # Update the server info with available tools
        self.info.tools = [
            "get_figma_server_status",
            "start_figma_server",
            "stop_figma_server",
            "get_figma_plugins",
            "ping_figma_plugin",
            "get_document_state",
            "execute_design_command",
            "broadcast_design_command",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            # For Figma, we check if the WebSocket server can start
            # (Figma plugins will connect to us)
            return True
        return True

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # Auto-start WebSocket server if configured
        if self.auto_start_websocket:
            logger.info("Auto-starting Figma WebSocket server...")
            try:
                success = await self.websocket_server.start()
                if success:
                    logger.info("✅ Figma WebSocket server auto-started successfully")
                    logger.info(
                        f"🎨 Ready for Figma plugin connections on ws://{self.websocket_server.host}:{self.websocket_server.port}"
                    )
                else:
                    logger.warning("⚠️ Failed to auto-start Figma WebSocket server")
            except Exception as e:
                logger.error(f"❌ Error auto-starting Figma WebSocket server: {e}")

        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Stop the WebSocket server
        try:
            if self.websocket_server.is_running:
                logger.info("Stopping Figma WebSocket server...")
                await self.websocket_server.stop()
                logger.info("✅ Figma WebSocket server stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping Figma WebSocket server: {e}")

        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Figma server health check."""
        try:
            # Check if the MCP server is running
            if not self.info.is_running:
                return False

            # Check WebSocket server status
            if self.auto_start_websocket and not self.websocket_server.is_running:
                return False

            # If WebSocket server is running, check if it's responsive
            if self.websocket_server.is_running:
                # Simple check - verify server object state
                server_info = self.websocket_server.get_server_info()
                return server_info.get("is_running", False)

            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design automation and collaborative design workflows",
        config={
            "type": "figma",
            "figma_host": "localhost",
            "figma_port": 9003,
            "auto_start_websocket": True,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
