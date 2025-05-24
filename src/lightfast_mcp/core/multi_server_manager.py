"""Multi-server manager for running multiple MCP servers simultaneously."""

import signal
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..utils.logging_utils import get_logger
from .base_server import BaseServer, ServerConfig, ServerInfo
from .server_registry import get_registry

logger = get_logger("MultiServerManager")


@dataclass
class ServerProcess:
    """Information about a running server process."""

    server: BaseServer
    thread: threading.Thread | None = None
    process_id: int | None = None
    start_time: float = field(default_factory=time.time)
    is_background: bool = False


class MultiServerManager:
    """Manager for running multiple MCP servers simultaneously."""

    def __init__(self):
        """Initialize the multi-server manager."""
        self.registry = get_registry()
        self._running_servers: dict[str, ServerProcess] = {}
        self._shutdown_event = threading.Event()

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down servers...")
            self.shutdown_all()

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Signal handling might not work in some environments (like Jupyter)
            logger.debug("Could not setup signal handlers")

    def start_server(self, server_config: ServerConfig, background: bool = False) -> bool:
        """Start a single server."""
        if server_config.name in self._running_servers:
            logger.warning(f"Server {server_config.name} is already running")
            return False

        try:
            # Validate configuration
            server_type = server_config.config.get("type", "unknown")
            is_valid, error_msg = self.registry.validate_server_config(server_type, server_config)
            if not is_valid:
                logger.error(f"Invalid configuration for {server_config.name}: {error_msg}")
                return False

            # Create server instance
            server = self.registry.create_server(server_type, server_config)

            if background:
                # Run in background thread
                thread = threading.Thread(
                    target=self._run_server_in_thread, args=(server, server_config.name), daemon=True
                )
                thread.start()

                server_process = ServerProcess(server=server, thread=thread, is_background=True)
            else:
                # Run in foreground (blocking)
                server_process = ServerProcess(server=server, is_background=False)
                # This will block
                server.run()

            self._running_servers[server_config.name] = server_process
            logger.info(f"Started server: {server_config.name} (background: {background})")
            return True

        except Exception as e:
            logger.error(f"Failed to start server {server_config.name}: {e}")
            return False

    def _run_server_in_thread(self, server: BaseServer, server_name: str):
        """Run a server in a background thread."""
        try:
            logger.info(f"Running server {server_name} in background thread")
            server.run()
        except Exception as e:
            logger.error(f"Error running server {server_name}: {e}")
        finally:
            # Clean up the server from running list when it stops
            if server_name in self._running_servers:
                logger.info(f"Server {server_name} stopped")
                del self._running_servers[server_name]

    def stop_server(self, server_name: str) -> bool:
        """Stop a specific server."""
        if server_name not in self._running_servers:
            logger.warning(f"Server {server_name} is not running")
            return False

        server_process = self._running_servers[server_name]

        try:
            # For now, we don't have a clean way to stop FastMCP servers
            # This would need to be implemented based on FastMCP's capabilities
            logger.warning(f"Graceful shutdown not yet implemented for {server_name}")

            # Remove from running servers
            del self._running_servers[server_name]
            logger.info(f"Stopped server: {server_name}")
            return True

        except Exception as e:
            logger.error(f"Error stopping server {server_name}: {e}")
            return False

    def restart_server(self, server_name: str) -> bool:
        """Restart a specific server."""
        if server_name not in self._running_servers:
            logger.warning(f"Server {server_name} is not running")
            return False

        server_process = self._running_servers[server_name]
        config = server_process.server.config
        background = server_process.is_background

        # Stop the server
        if self.stop_server(server_name):
            # Start it again
            time.sleep(1)  # Brief delay
            return self.start_server(config, background)

        return False

    def start_multiple_servers(self, server_configs: list[ServerConfig], background: bool = True) -> dict[str, bool]:
        """Start multiple servers."""
        results = {}

        logger.info(f"Starting {len(server_configs)} servers...")

        for config in server_configs:
            results[config.name] = self.start_server(config, background)

        successful = sum(1 for success in results.values() if success)
        logger.info(f"Successfully started {successful}/{len(server_configs)} servers")

        return results

    def get_running_servers(self) -> dict[str, ServerInfo]:
        """Get information about all running servers."""
        info = {}
        for name, server_process in self._running_servers.items():
            info[name] = server_process.server.info
        return info

    def get_server_status(self, server_name: str) -> ServerInfo | None:
        """Get status of a specific server."""
        if server_name in self._running_servers:
            return self._running_servers[server_name].server.info
        return None

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health checks on all running servers."""
        results = {}

        for name, server_process in self._running_servers.items():
            try:
                results[name] = await server_process.server.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False

        return results

    def shutdown_all(self):
        """Shutdown all running servers."""
        logger.info("Shutting down all servers...")

        server_names = list(self._running_servers.keys())
        for name in server_names:
            self.stop_server(name)

        self._shutdown_event.set()
        logger.info("All servers shut down")

    def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        self._shutdown_event.wait()

    def get_server_urls(self) -> dict[str, str]:
        """Get URLs for all HTTP servers."""
        urls = {}
        for name, server_process in self._running_servers.items():
            if server_process.server.info.url:
                urls[name] = server_process.server.info.url
        return urls

    def is_server_running(self, server_name: str) -> bool:
        """Check if a specific server is running."""
        return server_name in self._running_servers

    def get_server_count(self) -> int:
        """Get the number of running servers."""
        return len(self._running_servers)

    def list_available_server_types(self) -> list[str]:
        """List all available server types."""
        return self.registry.get_available_server_types()

    def get_server_type_info(self) -> dict[str, dict[str, Any]]:
        """Get information about all available server types."""
        return self.registry.get_server_info()


# Global manager instance
_manager: MultiServerManager | None = None


def get_manager() -> MultiServerManager:
    """Get the global multi-server manager instance."""
    global _manager
    if _manager is None:
        _manager = MultiServerManager()
    return _manager


def reset_manager():
    """Reset the global manager (mainly for testing)."""
    global _manager
    if _manager is not None:
        _manager.shutdown_all()
    _manager = None
