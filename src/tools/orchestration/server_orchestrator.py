"""Server orchestrator for managing multiple MCP servers simultaneously."""

import signal
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from lightfast_mcp.core.base_server import BaseServer, ServerConfig
from tools.common import (
    OperationStatus,
    Result,
    RetryManager,
    ServerInfo,
    ServerStartupError,
    ServerState,
    get_logger,
    run_concurrent_operations,
    with_correlation_id,
    with_operation_context,
)

from .server_registry import get_registry

logger = get_logger("ServerOrchestrator")


@dataclass
class ServerProcess:
    """Information about a running server process."""

    server: Optional[BaseServer] = None
    thread: Optional[threading.Thread] = None
    process: Optional[subprocess.Popen] = None
    process_id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    is_background: bool = False
    config: Optional[ServerConfig] = None

    @property
    def uptime_seconds(self) -> float:
        return (datetime.utcnow() - self.start_time).total_seconds()


class ServerOrchestrator:
    """Orchestrates lifecycle and coordination of multiple MCP servers."""

    def __init__(self, max_concurrent_startups: int = 3):
        """Initialize the server orchestrator."""
        self.registry = get_registry()
        self._running_servers: Dict[str, ServerProcess] = {}
        self._shutdown_event = threading.Event()
        self.max_concurrent_startups = max_concurrent_startups
        self.retry_manager = RetryManager(max_attempts=3, base_delay=2.0)

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown_all()

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Signal handling might not work in some environments (like Jupyter)
            logger.debug("Could not setup signal handlers")

    @with_correlation_id
    @with_operation_context(operation="start_server")
    async def start_server(
        self,
        server_config: ServerConfig,
        background: bool = False,
        show_logs: bool = True,
    ) -> Result[ServerInfo]:
        """Start a single server with proper error handling."""
        if server_config.name in self._running_servers:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Server {server_config.name} is already running",
                error_code="SERVER_ALREADY_RUNNING",
            )

        # Validate configuration
        server_type = server_config.config.get("type", "unknown")
        is_valid, error_msg = self.registry.validate_server_config(
            server_type, server_config
        )
        if not is_valid:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Invalid configuration: {error_msg}",
                error_code="INVALID_CONFIG",
            )

        try:
            # Choose startup method based on transport
            if server_config.transport in ["http", "streamable-http"]:
                result = await self._start_server_subprocess(
                    server_config, background, show_logs
                )
            else:
                result = await self._start_server_traditional(server_config, background)

            if result.is_success:
                logger.info(
                    f"Successfully started server: {server_config.name}",
                    server_name=server_config.name,
                    transport=server_config.transport,
                    background=background,
                )

            return result

        except Exception as e:
            error = ServerStartupError(
                f"Failed to start server {server_config.name}",
                server_name=server_config.name,
                cause=e,
            )
            logger.error("Server startup failed", error=error)
            return Result(
                status=OperationStatus.FAILED,
                error=str(error),
                error_code=error.error_code,
            )

    async def _start_server_subprocess(
        self, server_config: ServerConfig, background: bool, show_logs: bool = True
    ) -> Result[ServerInfo]:
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
                return Result(
                    status=OperationStatus.FAILED,
                    error=f"Unknown or untrusted server type for subprocess: {server_type}",
                    error_code="UNTRUSTED_SERVER_TYPE",
                )

            script_module = trusted_modules[server_type]

            # Create environment with server config
            import json
            import os
            import shutil
            import subprocess
            import sys

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
                return Result(
                    status=OperationStatus.FAILED,
                    error="Could not find Python executable",
                    error_code="PYTHON_NOT_FOUND",
                )

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

            # Create ServerInfo
            server_info = ServerInfo(
                name=server_config.name,
                server_type=server_type,
                state=ServerState.RUNNING,
                host=server_config.host,
                port=server_config.port,
                transport=server_config.transport,
                url=f"http://{server_config.host}:{server_config.port}{server_config.path}",
                pid=process.pid,
                start_time=server_process.start_time,
            )

            return Result(status=OperationStatus.SUCCESS, data=server_info)

        except Exception as e:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Failed to start server subprocess: {e}",
                error_code="SUBPROCESS_START_FAILED",
            )

    async def _start_server_traditional(
        self, server_config: ServerConfig, background: bool
    ) -> Result[ServerInfo]:
        """Start a server using the traditional approach (for stdio transport)."""
        try:
            # Create server instance
            server = self.registry.create_server(
                server_config.config.get("type"), server_config
            )

            if background:
                # Run in background thread with proper asyncio handling
                import threading

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

            # Create ServerInfo
            server_info = ServerInfo(
                name=server_config.name,
                server_type=server_config.config.get("type", "unknown"),
                state=ServerState.RUNNING,
                host=server_config.host,
                port=server_config.port,
                transport=server_config.transport,
                start_time=server_process.start_time,
            )

            return Result(status=OperationStatus.SUCCESS, data=server_info)

        except Exception as e:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Failed to start server traditionally: {e}",
                error_code="TRADITIONAL_START_FAILED",
            )

    def _run_server_in_thread(self, server: BaseServer, server_name: str):
        """Run a server in a background thread with proper asyncio handling."""
        try:
            logger.info(f"Running server {server_name} in background thread")

            # Create a new event loop for this thread
            # This is crucial for FastMCP servers which are asyncio-based
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the server in the new event loop
                server.run()
            finally:
                # Clean up the event loop
                loop.close()

        except Exception as e:
            logger.error(f"Error running server {server_name}", error=e)
        finally:
            # Clean up the server from running list when it stops
            if server_name in self._running_servers:
                logger.info(f"Server {server_name} stopped")
                del self._running_servers[server_name]

    @with_correlation_id
    async def start_multiple_servers(
        self,
        server_configs: List[ServerConfig],
        background: bool = True,
        show_logs: bool = True,
    ) -> Result[Dict[str, bool]]:
        """Start multiple servers concurrently."""
        if not server_configs:
            return Result(status=OperationStatus.SUCCESS, data={})

        logger.info(f"Starting {len(server_configs)} servers concurrently")

        # Create startup operations
        async def start_single_server(config: ServerConfig) -> bool:
            result = await self.start_server(config, background, show_logs)
            return result.is_success

        operations = [
            lambda cfg=config: start_single_server(cfg) for config in server_configs
        ]
        operation_names = [f"start_{config.name}" for config in server_configs]

        # Execute with controlled concurrency
        results = await run_concurrent_operations(
            operations,
            max_concurrent=self.max_concurrent_startups,
            operation_names=operation_names,
        )

        # Build result dictionary
        startup_results = {}
        for config, result in zip(server_configs, results):
            # If the operation succeeded, use the data (boolean result)
            # If the operation failed (exception), treat as False
            startup_results[config.name] = result.data if result.is_success else False

        successful = sum(1 for success in startup_results.values() if success)
        logger.info(
            f"Server startup completed: {successful}/{len(server_configs)} successful"
        )

        return Result(status=OperationStatus.SUCCESS, data=startup_results)

    def get_running_servers(self) -> Dict[str, ServerInfo]:
        """Get information about all running servers."""
        info = {}
        for name, server_process in self._running_servers.items():
            if server_process.server:
                info[name] = server_process.server.info
            elif server_process.config:
                # Create ServerInfo for subprocess-based servers
                server_info = ServerInfo(
                    name=server_process.config.name,
                    server_type=server_process.config.config.get("type", "unknown"),
                    state=ServerState.RUNNING
                    if self._is_process_running(server_process)
                    else ServerState.ERROR,
                    host=server_process.config.host,
                    port=server_process.config.port,
                    transport=server_process.config.transport,
                    start_time=server_process.start_time,
                    pid=server_process.process_id,
                )
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

    def shutdown_all(self):
        """Shutdown all running servers."""
        logger.info("Shutting down all servers...")

        server_names = list(self._running_servers.keys())
        for name in server_names:
            self.stop_server(name)

        self._shutdown_event.set()
        logger.info("All servers shut down")

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
                    logger.error(
                        f"Error stopping server process {server_name}", error=e
                    )

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
            logger.error(f"Error stopping server {server_name}", error=e)
            return False


# Global orchestrator instance
_orchestrator: Optional[ServerOrchestrator] = None


def get_orchestrator() -> ServerOrchestrator:
    """Get the global server orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ServerOrchestrator()
    return _orchestrator
