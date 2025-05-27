"""
Figma MCP server using the new modular architecture.
This is the clean entry point for the Figma server.
"""

import json
import os

from ..core.base_server import ServerConfig
from ..utils.logging_utils import configure_logging, get_logger
from .figma.server import FigmaMCPServer

# Configure logging
configure_logging(level="INFO")
logger = get_logger("FigmaMCP")


def main():
    """Run the Figma MCP server."""
    logger.info("Starting Figma MCP server")

    # Check for environment configuration (from ServerOrchestrator)
    env_config = os.getenv("LIGHTFAST_MCP_SERVER_CONFIG")

    if env_config:
        try:
            # Parse configuration from environment
            config_data = json.loads(env_config)
            config = ServerConfig(
                name=config_data.get("name", "FigmaMCP"),
                description=config_data.get(
                    "description",
                    "Figma MCP Server for web design and collaborative design workflows",
                ),
                host=config_data.get("host", "localhost"),
                port=config_data.get("port", 8002),
                transport=config_data.get(
                    "transport", "streamable-http"
                ),  # Default to HTTP for subprocess
                path=config_data.get("path", "/mcp"),
                config=config_data.get(
                    "config",
                    {
                        "type": "figma",
                        "plugin_channel": "default",
                        "command_timeout": 30.0,
                        "websocket_port": config_data.get("port", 8002) + 1000,
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
    server = FigmaMCPServer(config)
    server.run()


def _get_default_config() -> ServerConfig:
    """Get default configuration for standalone running."""
    return ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for web design and collaborative design workflows",
        host="localhost",
        port=8003,  # Use port 8003 by default for figma server (matches servers.yaml)
        transport="streamable-http",  # Use HTTP by default for easier testing
        path="/mcp",
        config={
            "type": "figma",
            "plugin_channel": "default",
            "command_timeout": 30.0,
            "websocket_port": 9003,  # WebSocket on port 9003 (8003 + 1000)
        },
    )


if __name__ == "__main__":
    main()
