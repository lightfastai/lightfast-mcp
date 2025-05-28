"""Figma MCP server implementation using the new modular architecture."""

from typing import ClassVar

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger
from . import tools
from .websocket_server import FigmaWebSocketServer

logger = get_logger("FigmaMCPServer")


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design automation and collaborative design workflows."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["websockets"]
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma WebSocket server configuration
        figma_host = config.config.get("figma_host", "localhost")
        figma_port = config.config.get("figma_port", 9003)

        # Create the WebSocket server instance
        self.websocket_server = FigmaWebSocketServer(host=figma_host, port=figma_port)

        # Set this server instance in tools module for access
        tools.set_current_server(self)

        logger.info(
            f"Figma server configured for WebSocket server at {figma_host}:{figma_port}"
        )

        # Track the WebSocket thread for proper cleanup
        self._websocket_thread = None
        self._websocket_loop = None

        # Start WebSocket server immediately in a background task
        self._start_websocket_server_background()

        # Register signal handler for proper cleanup on process termination
        self._register_signal_handlers()

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register core tools - matching Blender server pattern
        self.mcp.tool()(tools.get_state)
        self.mcp.tool()(tools.execute_command)

        # Update the server info with available tools
        self.info.tools = ["get_state", "execute_command"]
        logger.info(f"Registered {len(self.info.tools)} tools: {self.info.tools}")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            # For Figma, we check if the WebSocket server can start
            # (Figma plugins will connect to us)
            return True
        return True

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")

        # WebSocket server is started in background thread during __init__
        # Just wait a moment to let it initialize
        import asyncio

        await asyncio.sleep(0.5)

        # Check if WebSocket server started successfully
        if self.websocket_server.is_running:
            logger.info("✅ WebSocket server is running and ready for connections")
        else:
            logger.warning("⚠️ WebSocket server may still be starting up")

        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""

        logger.info(f"Figma server '{self.config.name}' shutting down...")

        # Don't stop the WebSocket server during normal MCP client disconnections
        # The WebSocket server should stay running for Figma plugins
        # Only stop it during actual server shutdown (e.g., SIGTERM)
        logger.info("WebSocket server will continue running for Figma plugins")
        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform Figma server health check."""
        try:
            # Check if the MCP server is running
            if not self.info.is_running:
                return False

            # Check WebSocket server status - it should always be running
            if not self.websocket_server.is_running:
                logger.warning(
                    "Health check failed: Figma WebSocket server is not running"
                )
                return False

            # If WebSocket server is running, check if it's responsive
            server_info = self.websocket_server.get_server_info()
            return server_info.get("is_running", False)

        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def _start_websocket_server_background(self):
        """Start the WebSocket server in a background thread."""
        import asyncio
        import threading

        def start_websocket():
            """Start WebSocket server in its own event loop."""
            try:
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._websocket_loop = loop

                logger.info("Starting Figma WebSocket server in background...")

                # Run the startup logic
                success = loop.run_until_complete(self._start_websocket_with_retry())

                if success:
                    logger.info(
                        "✅ Figma WebSocket server started successfully in background"
                    )
                    # Keep the loop running to handle WebSocket connections
                    loop.run_forever()
                else:
                    logger.error(
                        "❌ Failed to start Figma WebSocket server in background"
                    )

            except Exception as e:
                logger.error(f"❌ Error starting WebSocket server in background: {e}")
                import traceback

                logger.debug(
                    f"🔍 Background startup traceback: {traceback.format_exc()}"
                )
            finally:
                try:
                    # Clean up pending tasks
                    if loop and not loop.is_closed():
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                        loop.close()
                except Exception as e:
                    logger.debug(f"Error during loop cleanup: {e}")

        # Start in daemon thread so it doesn't prevent shutdown
        self._websocket_thread = threading.Thread(target=start_websocket, daemon=True)
        self._websocket_thread.start()
        logger.info("🚀 WebSocket server startup initiated in background thread")

    async def _start_websocket_with_retry(self):
        """Start WebSocket server with retry logic."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                success = await self.websocket_server.start()
                if success:
                    logger.info(
                        f"🎨 Ready for Figma plugin connections on ws://{self.websocket_server.host}:{self.websocket_server.port}"
                    )
                    return True
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.warning(
                            f"⚠️ Failed to start Figma WebSocket server, retrying ({retry_count}/{max_retries})..."
                        )
                        # Try a different port if the default one is in use
                        self.websocket_server.port += 1
                        logger.info(f"Trying port {self.websocket_server.port}")
                    else:
                        logger.error(
                            "❌ Failed to start Figma WebSocket server after all retries"
                        )
                        return False
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logger.warning(
                        f"⚠️ Error starting Figma WebSocket server, retrying ({retry_count}/{max_retries}): {e}"
                    )
                    # Try a different port if there's a port conflict
                    self.websocket_server.port += 1
                    logger.info(f"Trying port {self.websocket_server.port}")
                else:
                    logger.error(
                        f"❌ Failed to start Figma WebSocket server after all retries: {e}"
                    )
                    return False

        return False

    def _register_signal_handlers(self):
        """Register signal handlers for proper WebSocket server cleanup."""
        import signal
        import threading

        def signal_handler(signum, frame):
            """Handle termination signals by stopping WebSocket server."""
            logger.info(f"Received signal {signum}, shutting down WebSocket server...")

            def stop_websocket_safely():
                """Stop WebSocket server in its own thread."""
                try:
                    if self._websocket_loop and not self._websocket_loop.is_closed():
                        import asyncio

                        # Stop the WebSocket server
                        future = asyncio.run_coroutine_threadsafe(
                            self.websocket_server.stop(), self._websocket_loop
                        )
                        future.result(timeout=5.0)  # Wait up to 5 seconds

                        # Stop the event loop
                        self._websocket_loop.call_soon_threadsafe(
                            self._websocket_loop.stop
                        )
                        logger.info("✅ WebSocket server stopped due to signal")
                except Exception as e:
                    logger.debug(
                        f"Error during signal-triggered WebSocket shutdown: {e}"
                    )

            # Run the shutdown in a separate thread to avoid blocking signal handler
            shutdown_thread = threading.Thread(target=stop_websocket_safely)
            shutdown_thread.start()

        # Register handlers for common termination signals
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.debug("Signal handlers registered for WebSocket server cleanup")


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design automation and collaborative design workflows",
        config={
            "type": "figma",
            "figma_host": "localhost",
            "figma_port": 9003,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
