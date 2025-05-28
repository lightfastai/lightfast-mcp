#!/usr/bin/env python3
"""
Figma MCP Server Entry Point

This script provides a direct entry point for running the Figma MCP server.
The server acts as a WebSocket server that Figma plugins can connect to for
real-time design automation and AI integration.

Usage:
    python -m lightfast_mcp.servers.figma_mcp_server
    # or
    uv run lightfast-figma-server
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.figma.server import FigmaMCPServer
from lightfast_mcp.utils.logging_utils import get_logger

logger = get_logger("FigmaServerEntry")


def create_default_config() -> ServerConfig:
    """Create a default configuration for the Figma server."""
    return ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design automation and collaborative design workflows",
        config={
            "type": "figma",
            "figma_host": "localhost",
            "figma_port": 9003,
            "auto_start_websocket": True,
        },
    )


def main():
    """Main entry point for the Figma MCP server."""
    try:
        logger.info("🎨 Starting Figma MCP Server...")

        # Create server configuration
        config = create_default_config()

        # Create and run the server
        server = FigmaMCPServer(config)

        logger.info(f"🚀 Starting Figma server: {config.name}")
        logger.info(
            f"📡 WebSocket server will run on ws://{config.config['figma_host']}:{config.config['figma_port']}"
        )
        logger.info("🔌 Figma plugins can connect to this WebSocket server")

        # Run the server
        server.run()

    except KeyboardInterrupt:
        logger.info("🛑 Figma server stopped by user")
    except Exception as e:
        logger.error(f"❌ Error running Figma server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
