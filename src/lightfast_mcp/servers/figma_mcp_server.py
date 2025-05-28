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
    # or
    uv run lightfast-figma-server --show-logs -v
"""

import argparse
import sys
from pathlib import Path

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.figma.server import FigmaMCPServer
from lightfast_mcp.utils.logging_utils import configure_logging, get_logger

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def create_default_config() -> ServerConfig:
    """Create a default configuration for the Figma server."""
    return ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design automation and collaborative design workflows",
        config={
            "type": "figma",
            "figma_host": "localhost",
            "figma_port": 9003,
        },
    )


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Figma MCP Server for design automation and collaborative design workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run lightfast-figma-server                    # Start with default settings
  uv run lightfast-figma-server --show-logs        # Show detailed logs
  uv run lightfast-figma-server -v                 # Enable verbose/debug logging
  uv run lightfast-figma-server --show-logs -v     # Show detailed logs with debug level
        """,
    )

    parser.add_argument(
        "--show-logs",
        action="store_true",
        default=False,
        help="Show detailed server logs in terminal",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose/debug logging"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Host for the MCP server (default: localhost)",
    )

    parser.add_argument(
        "--port", type=int, default=8003, help="Port for the MCP server (default: 8003)"
    )

    parser.add_argument(
        "--websocket-host",
        default="localhost",
        help="Host for the WebSocket server (default: localhost)",
    )

    parser.add_argument(
        "--websocket-port",
        type=int,
        default=9003,
        help="Port for the WebSocket server (default: 9003)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the Figma MCP server."""
    # Parse command-line arguments
    args = parse_arguments()

    # Configure logging based on arguments
    log_level = "DEBUG" if args.verbose else "INFO"
    configure_logging(level=log_level)

    # Get logger after configuring
    logger = get_logger("FigmaServerEntry")

    try:
        logger.info("🎨 Starting Figma MCP Server...")

        if args.verbose:
            logger.debug("🔧 Debug logging enabled")
            logger.debug(f"🔧 Arguments: {vars(args)}")

        # Create server configuration with command-line overrides
        config = ServerConfig(
            name="FigmaMCP",
            description="Figma MCP Server for design automation and collaborative design workflows",
            host=args.host,
            port=args.port,
            transport="streamable-http",  # Use HTTP transport for WebSocket support
            path="/mcp",
            config={
                "type": "figma",
                "figma_host": args.websocket_host,
                "figma_port": args.websocket_port,
            },
        )

        # Create and run the server
        server = FigmaMCPServer(config)

        logger.info(f"🚀 Starting Figma server: {config.name}")
        logger.info(
            f"📡 MCP server will run on http://{config.host}:{config.port}{config.path}"
        )
        logger.info(
            f"🌐 WebSocket server will run on ws://{config.config['figma_host']}:{config.config['figma_port']}"
        )
        logger.info("🔌 Figma plugins can connect to the WebSocket server")

        if args.show_logs:
            logger.info("📋 Detailed logging enabled")

        # Run the server
        server.run()

    except KeyboardInterrupt:
        logger.info("🛑 Figma server stopped by user")
    except Exception as e:
        logger.error(f"❌ Error running Figma server: {e}")
        if args.verbose:
            import traceback

            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
