"""Mock MCP server implementation using the new modular architecture."""

import asyncio
from typing import ClassVar

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger
from . import tools

logger = get_logger("MockMCPServer")


class MockMCPServer(BaseServer):
    """Mock MCP server for testing and development."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "mock"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = []

    def __init__(self, config: ServerConfig):
        """Initialize the mock server."""
        super().__init__(config)

        # Mock-specific configuration with validation
        delay_value = config.config.get("delay_seconds", 0.5)
        try:
            # Try to convert to float and validate
            if delay_value is None or delay_value == "":
                self.default_delay = 0.5
            else:
                self.default_delay = float(delay_value)
                if self.default_delay < 0:
                    self.default_delay = 0.5
        except (ValueError, TypeError):
            # If conversion fails, use default
            self.default_delay = 0.5

        # Set this server instance in tools module for access
        tools.set_current_server(self)

    def _register_tools(self):
        """Register mock server tools."""
        if not self.mcp:
            return

        # Register tools from the tools module
        self.mcp.tool()(tools.get_server_status)
        self.mcp.tool()(tools.fetch_mock_data)
        self.mcp.tool()(tools.execute_mock_action)

        # Update the server info with available tools
        self.info.tools = [
            "get_server_status",
            "fetch_mock_data",
            "execute_mock_action",
        ]
        logger.info(
            "Registered 3 tools: get_server_status, fetch_mock_data, execute_mock_action"
        )

    async def _on_startup(self):
        """Mock server startup logic."""
        logger.info(f"Mock server '{self.config.name}' starting up...")
        logger.info(f"Default delay configured: {self.default_delay}s")

        # Simulate some startup work
        await asyncio.sleep(0.1)

        logger.info("Mock server startup complete")

    async def _on_shutdown(self):
        """Mock server shutdown logic."""
        logger.info(f"Mock server '{self.config.name}' shutting down...")
        await asyncio.sleep(0.05)  # Simulate cleanup
        logger.info("Mock server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform mock server health check."""
        # Simple health check - just verify we're running
        return self.info.is_running


def main():
    """Run the Mock MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="MockMCP",
        description="Mock MCP Server for testing and development",
        config={"type": "mock", "delay_seconds": 0.5},
    )

    # Create and run the server
    server = MockMCPServer(config)
    logger.info(f"Starting standalone mock server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
