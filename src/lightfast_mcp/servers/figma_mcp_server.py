"""
Figma MCP server entry point with WebSocket communication.
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
    """Run the Figma MCP server with WebSocket communication."""
    logger.info("Starting Figma MCP server with WebSocket support")

    # Check for environment configuration (from ServerOrchestrator)
    env_config = os.getenv("LIGHTFAST_MCP_SERVER_CONFIG")

    if env_config:
        logger.info("Using environment configuration")
        try:
            # Parse configuration from environment
            config_data = json.loads(env_config)

            config = ServerConfig(
                name=config_data.get("name", "FigmaMCP"),
                description=config_data.get(
                    "description", "Figma MCP Server with WebSocket communication"
                ),
                host=config_data.get("host", "localhost"),
                port=config_data.get("port", 8003),
                transport=config_data.get("transport", "streamable-http"),
                path=config_data.get("path", "/mcp"),
                config=config_data.get("config", _get_default_figma_config()),
            )
            logger.info(
                f"Using environment configuration: {config.transport}://{config.host}:{config.port}"
            )
            logger.info(
                f"WebSocket client will connect to: {config.config.get('figma_host', 'localhost')}:{config.config.get('figma_port', 9003)}"
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


def _get_default_figma_config() -> dict:
    """Get default Figma-specific configuration."""
    return {
        "type": "figma",
        "figma_host": "localhost",
        "figma_port": 9003,
        "command_timeout": 30.0,
    }


def _get_default_config() -> ServerConfig:
    """Get default configuration for standalone running."""
    return ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server with WebSocket communication",
        host="localhost",
        port=8003,
        transport="streamable-http",
        path="/mcp",
        config=_get_default_figma_config(),
    )


if __name__ == "__main__":
    main()
