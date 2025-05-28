"""
Simplified Figma MCP server entry point.
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
    """Run the simplified Figma MCP server."""
    logger.info("Starting simplified Figma MCP server")

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
                    "description", "Simplified Figma MCP Server"
                ),
                host=config_data.get("host", "localhost"),
                port=config_data.get("port", 8003),
                transport=config_data.get("transport", "streamable-http"),
                path=config_data.get("path", "/mcp"),
                config=config_data.get("config", {"type": "figma"}),
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
        description="Simplified Figma MCP Server",
        host="localhost",
        port=8003,
        transport="streamable-http",
        path="/mcp",
        config={"type": "figma"},
    )


if __name__ == "__main__":
    main()
