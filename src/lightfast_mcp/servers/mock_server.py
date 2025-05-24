"""
Mock MCP server using the new modular architecture.
This is now the clean entry point for the Mock server.
"""

from ..core.base_server import ServerConfig
from ..utils.logging_utils import configure_logging, get_logger
from .mock.server import MockMCPServer

# Configure logging
configure_logging(level="INFO")
logger = get_logger("MockMCP")

SERVER_NAME = "MockMCP"


def main():
    """Run the Mock MCP server."""
    logger.info("Starting Mock MCP server")

    # Create default configuration
    config = ServerConfig(
        name=SERVER_NAME,
        description="Mock MCP Server for testing and development",
        config={
            "type": "mock",
            "delay_seconds": 0.5,
        },
    )

    # Create and run server
    server = MockMCPServer(config)
    server.run()


if __name__ == "__main__":
    main()
