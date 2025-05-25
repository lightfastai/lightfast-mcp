"""Multi-server manager for running multiple MCP servers simultaneously."""

import asyncio
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from lightfast_mcp.core.base_server import BaseServer, ServerConfig, ServerInfo
from lightfast_mcp.utils.logging_utils import get_logger

from .server_registry import get_registry

logger = get_logger("MultiServerManager")


@dataclass
class ServerProcess:
    """Information about a running server process."""

    server: BaseServer | None = None
    thread: threading.Thread | None = None
    process: subprocess.Popen | None = None
    process_id: int | None = None
    start_time: float = field(default_factory=time.time)
    is_background: bool = False
    config: ServerConfig | None = None


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

    def start_server(
        self,
        server_config: ServerConfig,
        background: bool = False,
        show_logs: bool = True,
    ) -> bool:
        """Start a single server."""
        if server_config.name in self._running_servers:
            logger.warning(f"Server {server_config.name} is already running")
            return False

        try:
            # Validate configuration
            server_type = server_config.config.get("type", "unknown")
            is_valid, error_msg = self.registry.validate_server_config(
                server_type, server_config
            )
            if not is_valid:
                logger.error(
                    f"Invalid configuration for {server_config.name}: {error_msg}"
                )
                return False

            # For HTTP transports, use subprocess to avoid asyncio conflicts
            if server_config.transport in ["http", "streamable-http"]:
                success = self._start_server_subprocess(
                    server_config, background, show_logs
                )
            else:
                # For stdio transport, use the traditional approach
                success = self._start_server_traditional(server_config, background)

            if success:
                logger.info(
                    f"Started server: {server_config.name} (background: {background})"
                )
            return success

        except Exception as e:
            logger.error(f"Failed to start server {server_config.name}: {e}")
            return False

    def _start_server_subprocess(
        self, server_config: ServerConfig, background: bool, show_logs: bool = True
    ) -> bool:
        """Start a server using subprocess (for HTTP transports)."""
        try:
            # Determine the correct script based on server type
            server_type = server_config.config.get("type", "unknown")

            # Validated list of trusted server modules (security: only allow known modules)
            trusted_modules = {
                "mock": "lightfast_mcp.servers.mock_server",
                "blender": "lightfast_mcp.servers.blender_mcp_server",
            }

            if server_type not in trusted_modules:
                logger.error(
                    f"Unknown or untrusted server type for subprocess: {server_type}"
                )
                return False

            script_module = trusted_modules[server_type]

            # Create environment with server config
            import json
            import os

            env = os.environ.copy()
            env["LIGHTFAST_MCP_SERVER_CONFIG"] = json.dumps(
                {
                    "name": server_config.name,
                    "description": server_config.description,
                    "host": server_config.host,
                    "port": server_config.port,
                    "transport": server_config.transport,
                    "path": server_config.path,
                    "config": server_config.config,
                }
            )

            # Start the subprocess
            # Security: Use full path to python executable and validated module name
            python_executable = (
                sys.executable or shutil.which("python3") or shutil.which("python")
            )
            if not python_executable:
                logger.error("Could not find Python executable")
                return False

            # Only capture logs if background=True AND show_logs=False
            capture_logs = background and not show_logs
            process = subprocess.Popen(
                [python_executable, "-m", script_module],  # nosec B603 - using validated module and full path
                env=env,
                stdout=subprocess.PIPE if capture_logs else None,
                stderr=subprocess.PIPE if capture_logs else None,
                text=True,
            )

            server_process = ServerProcess(
                process=process,
                process_id=process.pid,
                is_background=background,
                config=server_config,
            )

            self._running_servers[server_config.name] = server_process
            return True

        except Exception as e:
            logger.error(f"Failed to start server subprocess: {e}")
            return False

    def _start_server_traditional(
        self, server_config: ServerConfig, background: bool
    ) -> bool:
        """Start a server using the traditional approach (for stdio transport)."""
        try:
            # Create server instance
            server = self.registry.create_server(
                server_config.config.get("type"), server_config
            )

            if background:
                # Run in background thread with proper asyncio handling
                thread = threading.Thread(
                    target=self._run_server_in_thread,
                    args=(server, server_config.name),
                    daemon=True,
                )
                thread.start()

                server_process = ServerProcess(
                    server=server,
                    thread=thread,
                    is_background=True,
                    config=server_config,
                )
            else:
                # Run in foreground (blocking)
                server_process = ServerProcess(
                    server=server, is_background=False, config=server_config
                )
                # This will block
                server.run()

            self._running_servers[server_config.name] = server_process
            return True

        except Exception as e:
            logger.error(f"Failed to start server traditionally: {e}")
            return False

    def _run_server_in_thread(self, server: BaseServer, server_name: str):
        """Run a server in a background thread with proper asyncio handling."""
        try:
            logger.info(f"Running server {server_name} in background thread")

            # Create a new event loop for this thread
            # This is crucial for FastMCP servers which are asyncio-based
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the server in the new event loop
                server.run()
            finally:
                # Clean up the event loop
                loop.close()

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
            # Handle subprocess
            if server_process.process:
                try:
                    server_process.process.terminate()
                    # Wait up to 5 seconds for graceful shutdown
                    server_process.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        f"Server {server_name} didn't stop gracefully, forcing..."
                    )
                    server_process.process.kill()
                except Exception as e:
                    logger.error(f"Error stopping server process {server_name}: {e}")

            # Handle threaded server
            elif server_process.thread and server_process.thread.is_alive():
                logger.info(
                    f"Server {server_name} thread is still running, waiting for natural shutdown..."
                )

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
        config = server_process.config
        background = server_process.is_background

        if not config:
            logger.error(f"No config found for server {server_name}")
            return False

        # Stop the server
        if self.stop_server(server_name):
            # Start it again
            time.sleep(1)  # Brief delay
            return self.start_server(config, background, show_logs=True)

        return False

    def start_multiple_servers(
        self,
        server_configs: list[ServerConfig],
        background: bool = True,
        show_logs: bool = True,
    ) -> dict[str, bool]:
        """Start multiple servers."""
        results = {}

        logger.info(f"Starting {len(server_configs)} servers...")

        for config in server_configs:
            results[config.name] = self.start_server(config, background, show_logs)
            # Add a small delay between server starts to avoid port conflicts
            time.sleep(1.0)  # Increased delay for subprocess startup

        successful = sum(1 for success in results.values() if success)
        logger.info(f"Successfully started {successful}/{len(server_configs)} servers")

        return results

    def get_running_servers(self) -> dict[str, ServerInfo]:
        """Get information about all running servers."""
        info = {}
        for name, server_process in self._running_servers.items():
            if server_process.server:
                info[name] = server_process.server.info
            elif server_process.config:
                # Create ServerInfo for subprocess-based servers
                server_info = ServerInfo(config=server_process.config)
                server_info.is_running = self._is_process_running(server_process)
                if server_process.config.transport in ["http", "streamable-http"]:
                    server_info.url = (
                        f"http://{server_process.config.host}:{server_process.config.port}"
                        f"{server_process.config.path}"
                    )
                info[name] = server_info
        return info

    def _is_process_running(self, server_process: ServerProcess) -> bool:
        """Check if a subprocess is still running."""
        if server_process.process:
            return server_process.process.poll() is None
        return False

    def get_server_status(self, server_name: str) -> ServerInfo | None:
        """Get status of a specific server."""
        if server_name in self._running_servers:
            server_process = self._running_servers[server_name]
            if server_process.server:
                return server_process.server.info
            elif server_process.config:
                # Create ServerInfo for subprocess-based servers
                server_info = ServerInfo(config=server_process.config)
                server_info.is_running = self._is_process_running(server_process)
                return server_info
        return None

    async def health_check_all(self) -> dict[str, bool]:
        """Perform health checks on all running servers."""
        results = {}

        for name, server_process in self._running_servers.items():
            try:
                if server_process.server:
                    results[name] = await server_process.server.health_check()
                else:
                    # For subprocess-based servers, just check if process is running
                    results[name] = self._is_process_running(server_process)
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
            if server_process.server and server_process.server.info.url:
                urls[name] = server_process.server.info.url
            elif server_process.config and server_process.config.transport in [
                "http",
                "streamable-http",
            ]:
                urls[name] = (
                    f"http://{server_process.config.host}:{server_process.config.port}"
                    f"{server_process.config.path}"
                )
        return urls

    def is_server_running(self, server_name: str) -> bool:
        """Check if a specific server is running."""
        if server_name in self._running_servers:
            server_process = self._running_servers[server_name]
            if server_process.server:
                return server_process.server.info.is_running
            else:
                return self._is_process_running(server_process)
        return False

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
