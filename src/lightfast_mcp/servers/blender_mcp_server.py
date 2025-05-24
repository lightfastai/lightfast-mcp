"""
Blender MCP server using the new modular architecture.
This is now the clean entry point for the Blender server.
"""

import json
import os

from ..core.base_server import ServerConfig
from ..utils.logging_utils import configure_logging, get_logger
from .blender.server import BlenderMCPServer

# Configure logging
configure_logging(level="INFO")
logger = get_logger("BlenderMCP")


def main():
    """Run the Blender MCP server."""
    logger.info("Starting Blender MCP server")

    # Check for environment configuration (from MultiServerManager)
    env_config = os.getenv("LIGHTFAST_MCP_SERVER_CONFIG")

    if env_config:
        try:
            # Parse configuration from environment
            config_data = json.loads(env_config)
            config = ServerConfig(
                name=config_data.get("name", "BlenderMCP"),
                description=config_data.get(
                    "description", "Blender MCP Server for 3D modeling and animation"
                ),
                host=config_data.get("host", "localhost"),
                port=config_data.get("port", 8001),
                transport=config_data.get(
                    "transport", "streamable-http"
                ),  # Default to HTTP for subprocess
                path=config_data.get("path", "/mcp"),
                config=config_data.get(
                    "config",
                    {
                        "type": "blender",
                        "blender_host": "localhost",
                        "blender_port": 9876,
                    },
                ),
            )
            logger.info(
                f"Using environment configuration: {config.transport}://{config.host}:{config.port}"
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid environment configuration: {e}, using defaults")
            config = _get_default_config()
    else:
        # Use default configuration for standalone running
        config = _get_default_config()

    # Create and run server
    server = BlenderMCPServer(config)
    server.run()


def _get_default_config() -> ServerConfig:
    """Get default configuration for standalone running."""
    return ServerConfig(
        name="BlenderMCP",
        description="Blender MCP Server for 3D modeling and animation",
        host="localhost",
        port=8001,  # Use port 8001 by default for blender server
        transport="streamable-http",  # Use HTTP by default for easier testing
        path="/mcp",
        config={
            "type": "blender",
            "blender_host": "localhost",
            "blender_port": 9876,
        },
    )


if __name__ == "__main__":
    main()
