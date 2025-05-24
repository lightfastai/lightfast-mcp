"""
Blender MCP server using the new modular architecture.
This is now the clean entry point for the Blender server.
"""

from ..core.base_server import ServerConfig
from ..utils.logging_utils import configure_logging, get_logger
from .blender.server import BlenderMCPServer

# Configure logging
configure_logging(level="INFO")
logger = get_logger("BlenderMCP")


def main():
    """Run the Blender MCP server."""
    logger.info("Starting Blender MCP server")

    # Create default configuration
    config = ServerConfig(
        name="BlenderMCP",
        description="A simplified MCP server for basic Blender interaction.",
        config={
            "type": "blender",
            "blender_host": "localhost",
            "blender_port": 9876,
        },
    )

    # Create and run server
    server = BlenderMCPServer(config)
    server.run()


if __name__ == "__main__":
    main()
