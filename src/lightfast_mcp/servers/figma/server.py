"""
Simplified Figma MCP Server for basic design operations.
"""

import json
from typing import ClassVar

from fastmcp import Context

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaMCPServer(BaseServer):
    """Simplified Figma MCP server for basic design operations."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)
        logger.info(f"Figma server '{self.config.name}' initialized")

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register basic tools
        self.mcp.tool()(self.get_server_info)
        self.mcp.tool()(self.ping)

        # Update available tools list
        self.info.tools = [
            "get_server_info",
            "ping",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            # For now, we assume Figma is available
            return True
        return True

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up")
        logger.info("Simplified Figma server ready for MCP communication")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down")

    async def _perform_health_check(self) -> bool:
        """Perform health check."""
        return True

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
                "message": "Simplified Figma MCP server ready",
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
            }
            return json.dumps(response, indent=2)
        except Exception as e:
            logger.error(f"Error in ping: {e}")
            return json.dumps({"error": str(e)}, indent=2)


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Simplified Figma MCP Server",
        config={
            "type": "figma",
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
