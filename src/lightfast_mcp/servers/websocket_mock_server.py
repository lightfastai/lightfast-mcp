"""
WebSocket Mock MCP server using the new modular architecture.
This is the clean entry point for the WebSocket Mock server.
"""

import json
import os

from ..core.base_server import ServerConfig
from ..utils.logging_utils import configure_logging, get_logger
from .websocket_mock.server import WebSocketMockMCPServer

# Configure logging
configure_logging(level="INFO")
logger = get_logger("WebSocketMockMCP")

SERVER_NAME = "WebSocketMockMCP"


def main():
    """Run the WebSocket Mock MCP server."""
    logger.info("Starting WebSocket Mock MCP server")

    # Check for environment configuration (from ServerOrchestrator)
    env_config = os.getenv("LIGHTFAST_MCP_SERVER_CONFIG")

    if env_config:
        try:
            # Parse configuration from environment
            config_data = json.loads(env_config)
            config = ServerConfig(
                name=config_data.get("name", SERVER_NAME),
                description=config_data.get(
                    "description",
                    "WebSocket Mock MCP Server for testing WebSocket communications",
                ),
                host=config_data.get("host", "localhost"),
                port=config_data.get("port", 8004),
                transport=config_data.get(
                    "transport", "streamable-http"
                ),  # Default to HTTP for subprocess
                path=config_data.get("path", "/mcp"),
                config=config_data.get(
                    "config",
                    {
                        "type": "websocket_mock",
                        "websocket_host": "localhost",
                        "websocket_port": 9004,
                        "auto_start_websocket": True,
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
    server = WebSocketMockMCPServer(config)
    server.run()


def _get_default_config() -> ServerConfig:
    """Get default configuration for standalone running."""
    return ServerConfig(
        name=SERVER_NAME,
        description="WebSocket Mock MCP Server for testing WebSocket communications",
        host="localhost",
        port=8004,  # Use port 8004 by default for WebSocket mock server
        transport="streamable-http",  # Use HTTP by default for easier testing
        path="/mcp",
        config={
            "type": "websocket_mock",
            "websocket_host": "localhost",
            "websocket_port": 9004,
            "auto_start_websocket": True,
        },
    )


if __name__ == "__main__":
    main()
