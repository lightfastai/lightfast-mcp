"""Async utilities and patterns for better performance and reliability."""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional, TypeVar

from fastmcp import Client

from .errors import (
    ConnectionPoolError,
    ConnectionPoolExhaustedError,
    ServerConnectionError,
)
from .logging import get_logger, with_correlation_id
from .types import OperationStatus, Result

logger = get_logger("AsyncUtils")
T = TypeVar("T")


class ConnectionPool:
    """Manages persistent connections to MCP servers."""

    def __init__(
        self,
        max_connections_per_server: int = 5,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0,  # 5 minutes
    ):
        self.max_connections = max_connections_per_server
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout

        # Pool storage: server_name -> Queue of available connections
        self._pools: Dict[str, asyncio.Queue] = {}
        self._active_connections: Dict[str, int] = {}
        self._connection_configs: Dict[str, Dict[str, Any]] = {}
        self._last_used: Dict[str, Dict[Client, float]] = {}

        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False

    async def initialize(self):
        """Initialize the connection pool."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())

    async def register_server(
        self, server_name: str, connection_config: Dict[str, Any]
    ):
        """Register a server configuration for connection pooling."""
        self._connection_configs[server_name] = connection_config
        if server_name not in self._pools:
            self._pools[server_name] = asyncio.Queue(maxsize=self.max_connections)
            self._active_connections[server_name] = 0
            self._last_used[server_name] = {}

    @asynccontextmanager
    async def get_connection(self, server_name: str):
        """Get a connection from the pool or create a new one."""
        if server_name not in self._connection_configs:
            raise ConnectionPoolError(f"Server {server_name} not registered")

        connection = None
        try:
            connection = await self._acquire_connection(server_name)
            # Use the FastMCP client's context manager to ensure proper connection
            async with connection as connected_client:
                yield connected_client
        finally:
            if connection:
                await self._release_connection(server_name, connection)

    async def _acquire_connection(self, server_name: str) -> Client:
        """Acquire a connection from the pool."""
        pool = self._pools[server_name]

        # Try to get an existing connection from the pool
        try:
            connection = pool.get_nowait()
            self._last_used[server_name][connection] = time.time()
            logger.debug(f"Reused connection for {server_name}")
            return connection
        except asyncio.QueueEmpty:
            pass

        # Check if we can create a new connection
        if self._active_connections[server_name] >= self.max_connections:
            # Wait for a connection to become available
            try:
                connection = await asyncio.wait_for(
                    pool.get(), timeout=self.connection_timeout
                )
                self._last_used[server_name][connection] = time.time()
                logger.debug(f"Got pooled connection for {server_name}")
                return connection
            except asyncio.TimeoutError:
                raise ConnectionPoolExhaustedError(
                    f"No connections available for {server_name} within timeout"
                )

        # Create a new connection
        connection = await self._create_connection(server_name)
        self._active_connections[server_name] += 1
        self._last_used[server_name][connection] = time.time()
        logger.debug(f"Created new connection for {server_name}")
        return connection

    async def _create_connection(self, server_name: str) -> Client:
        """Create a new connection to the server."""
        config = self._connection_configs[server_name]

        try:
            if config.get("type") == "stdio":
                # For stdio connections
                import shlex
                import urllib.parse

                command = config.get("command", "")
                args = config.get("args", [])
                if args:
                    full_command = shlex.join([command] + args)
                    encoded_command = urllib.parse.quote(full_command, safe="")
                    client = Client(f"stdio://{encoded_command}")
                else:
                    encoded_command = urllib.parse.quote(command, safe="")
                    client = Client(f"stdio://{encoded_command}")
            else:
                # For HTTP/SSE connections
                url = config.get("url", "")
                client = Client(url)

            # Don't test the connection here - let the context manager handle it
            # The client will be connected when used in the context manager
            return client

        except Exception as e:
            raise ServerConnectionError(
                f"Failed to create connection to {server_name}",
                server_name=server_name,
                cause=e,
            )

    async def _release_connection(self, server_name: str, connection: Client):
        """Release a connection back to the pool."""
        pool = self._pools[server_name]

        try:
            # Put the connection back in the pool if there's space
            pool.put_nowait(connection)
            logger.debug(f"Released connection for {server_name}")
        except asyncio.QueueFull:
            # Pool is full, close the connection
            await self._close_connection(server_name, connection)

    async def _close_connection(self, server_name: str, connection: Client):
        """Close a connection and update counters."""
        try:
            # FastMCP clients don't have a direct close method
            # They are managed through context managers
            # Just clean up our tracking
            pass
        except Exception as e:
            logger.warning(f"Error closing connection for {server_name}: {e}")
        finally:
            self._active_connections[server_name] -= 1
            if connection in self._last_used[server_name]:
                del self._last_used[server_name][connection]

    async def _cleanup_idle_connections(self):
        """Periodically clean up idle connections."""
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # Check every minute
                current_time = time.time()

                for server_name, last_used_times in self._last_used.items():
                    pool = self._pools[server_name]
                    connections_to_close = []

                    # Check for idle connections
                    for connection, last_used in last_used_times.items():
                        if current_time - last_used > self.idle_timeout:
                            connections_to_close.append(connection)

                    # Close idle connections
                    for connection in connections_to_close:
                        try:
                            # Remove from pool if present
                            temp_connections = []
                            while not pool.empty():
                                try:
                                    conn = pool.get_nowait()
                                    if conn != connection:
                                        temp_connections.append(conn)
                                except asyncio.QueueEmpty:
                                    break

                            # Put back non-idle connections
                            for conn in temp_connections:
                                try:
                                    pool.put_nowait(conn)
                                except asyncio.QueueFull:
                                    await self._close_connection(server_name, conn)

                            # Close the idle connection
                            await self._close_connection(server_name, connection)
                            logger.debug(f"Closed idle connection for {server_name}")

                        except Exception as e:
                            logger.warning(
                                f"Error during cleanup for {server_name}: {e}"
                            )

            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")

    async def close_all(self):
        """Close all connections and shutdown the pool."""
        self._shutdown = True

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for server_name, pool in self._pools.items():
            connections = []
            while not pool.empty():
                try:
                    connections.append(pool.get_nowait())
                except asyncio.QueueEmpty:
                    break

            for connection in connections:
                try:
                    await self._close_connection(server_name, connection)
                except Exception as e:
                    logger.warning(f"Error closing connection for {server_name}: {e}")

        logger.info("Connection pool closed")


class RetryManager:
    """Manages retry logic with exponential backoff."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    async def execute_with_retry(
        self,
        operation: Callable[[], Any],
        retryable_exceptions: tuple = (Exception,),
        operation_name: str = "operation",
    ) -> Result[Any]:
        """Execute an operation with retry logic."""
        last_error = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.debug(
                    f"Executing {operation_name}, attempt {attempt}/{self.max_attempts}"
                )
                result = await operation()

                if attempt > 1:
                    logger.info(f"{operation_name} succeeded on attempt {attempt}")

                return Result(status=OperationStatus.SUCCESS, data=result)

            except retryable_exceptions as e:
                last_error = e

                if attempt == self.max_attempts:
                    logger.error(
                        f"{operation_name} failed after {attempt} attempts",
                        error=last_error,
                    )
                    break

                # Calculate delay with exponential backoff
                delay = min(
                    self.base_delay * (self.exponential_base ** (attempt - 1)),
                    self.max_delay,
                )

                # Add jitter to prevent thundering herd
                if self.jitter:
                    import random

                    delay *= 0.5 + random.random() * 0.5

                logger.warning(
                    f"{operation_name} failed on attempt {attempt}, retrying in {delay:.2f}s",
                    error=e,
                )

                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retryable exception
                logger.error(
                    f"{operation_name} failed with non-retryable error", error=e
                )
                return Result(
                    status=OperationStatus.FAILED,
                    error=str(e),
                    error_code=type(e).__name__,
                )

        # All retries exhausted
        return Result(
            status=OperationStatus.FAILED,
            error=f"Operation failed after {self.max_attempts} attempts: {last_error}",
            error_code="RETRY_EXHAUSTED",
        )


@with_correlation_id
async def run_concurrent_operations(
    operations: List[Callable[[], Any]],
    max_concurrent: int = 5,
    operation_names: Optional[List[str]] = None,
) -> List[Result[Any]]:
    """Run multiple operations concurrently with controlled concurrency."""
    if operation_names is None:
        operation_names = [f"operation_{i}" for i in range(len(operations))]

    # Handle edge case where max_concurrent is 0 or negative - use unlimited concurrency
    if max_concurrent <= 0:
        max_concurrent = len(operations) or 1

    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_single_operation(operation: Callable, name: str) -> Result[Any]:
        async with semaphore:
            try:
                start_time = time.time()
                result = await operation()
                duration = (time.time() - start_time) * 1000

                return Result(
                    status=OperationStatus.SUCCESS, data=result, duration_ms=duration
                )
            except Exception as e:
                logger.error(f"Operation {name} failed", error=e)
                return Result(
                    status=OperationStatus.FAILED,
                    error=str(e),
                    error_code=type(e).__name__,
                )

    tasks = [
        run_single_operation(op, name) for op, name in zip(operations, operation_names)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert any exceptions to Result objects
    final_results: List[Result[Any]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(
                Result(
                    status=OperationStatus.FAILED,
                    error=str(result),
                    error_code=type(result).__name__,
                )
            )
        elif isinstance(result, Result):
            final_results.append(result)
        else:
            # This shouldn't happen, but handle it gracefully
            final_results.append(
                Result(
                    status=OperationStatus.FAILED,
                    error=f"Unexpected result type: {type(result)}",
                    error_code="UNEXPECTED_RESULT_TYPE",
                )
            )

    return final_results


# Global connection pool instance
_connection_pool: Optional[ConnectionPool] = None


async def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
        await _connection_pool.initialize()
    return _connection_pool


async def shutdown_connection_pool():
    """Shutdown the global connection pool."""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close_all()
        _connection_pool = None
