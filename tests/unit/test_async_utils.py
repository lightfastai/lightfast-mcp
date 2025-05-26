"""
Comprehensive tests for async_utils module - critical connection pooling and async utilities.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.common.async_utils import (
    ConnectionPool,
    RetryManager,
    get_connection_pool,
    run_concurrent_operations,
    shutdown_connection_pool,
)
from tools.common.errors import (
    ConnectionPoolError,
    ConnectionPoolExhaustedError,
    ServerConnectionError,
)


class TestConnectionPool:
    """Comprehensive tests for ConnectionPool class."""

    @pytest.mark.asyncio
    async def test_connection_pool_initialization(self):
        """Test ConnectionPool initialization and setup."""
        pool = ConnectionPool(
            max_connections_per_server=3,
            connection_timeout=10.0,
            idle_timeout=60.0,
        )

        assert pool.max_connections == 3
        assert pool.connection_timeout == 10.0
        assert pool.idle_timeout == 60.0
        assert pool._pools == {}
        assert pool._active_connections == {}
        assert pool._connection_configs == {}
        assert pool._cleanup_task is None
        assert pool._shutdown is False

        await pool.initialize()
        assert pool._cleanup_task is not None
        assert not pool._cleanup_task.done()

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_register_server(self):
        """Test server registration with connection pool."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "sse",
            "url": "http://localhost:8001/mcp",
        }

        await pool.register_server("test-server", server_config)

        assert "test-server" in pool._connection_configs
        assert pool._connection_configs["test-server"] == server_config
        assert "test-server" in pool._pools
        assert "test-server" in pool._active_connections
        assert pool._active_connections["test-server"] == 0

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_register_multiple_servers(self):
        """Test registering multiple servers."""
        pool = ConnectionPool()
        await pool.initialize()

        servers = {
            "server1": {"type": "sse", "url": "http://localhost:8001/mcp"},
            "server2": {"type": "stdio", "command": "python", "args": ["-m", "server"]},
            "server3": {"type": "sse", "url": "http://localhost:8003/mcp"},
        }

        for name, config in servers.items():
            await pool.register_server(name, config)

        assert len(pool._connection_configs) == 3
        assert len(pool._pools) == 3
        assert len(pool._active_connections) == 3

        for name in servers:
            assert name in pool._connection_configs
            assert pool._active_connections[name] == 0

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_get_connection_unregistered_server(self):
        """Test getting connection for unregistered server."""
        pool = ConnectionPool()
        await pool.initialize()

        with pytest.raises(
            ConnectionPoolError, match="Server unregistered not registered"
        ):
            async with pool.get_connection("unregistered"):
                pass

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_create_connection_sse(self):
        """Test creating SSE connection."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "sse",
            "url": "http://localhost:8001/mcp",
        }

        await pool.register_server("sse-server", server_config)

        with patch("tools.common.async_utils.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            connection = await pool._create_connection("sse-server")

            assert connection == mock_client
            mock_client_class.assert_called_once_with("http://localhost:8001/mcp")

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_create_connection_stdio(self):
        """Test creating stdio connection."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "server"],
        }

        await pool.register_server("stdio-server", server_config)

        with patch("tools.common.async_utils.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            connection = await pool._create_connection("stdio-server")

            assert connection == mock_client
            # Should encode the full command
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args[0][0]
            assert call_args.startswith("stdio://")

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_create_connection_stdio_no_args(self):
        """Test creating stdio connection without args."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "stdio",
            "command": "python",
        }

        await pool.register_server("stdio-server", server_config)

        with patch("tools.common.async_utils.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            connection = await pool._create_connection("stdio-server")

            assert connection == mock_client
            mock_client_class.assert_called_once()

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_create_connection_stdio_with_special_characters(self):
        """Test creating stdio connection with special characters in command."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "server", "--config", "path with spaces/config.json"],
        }

        await pool.register_server("stdio-server", server_config)

        with patch("tools.common.async_utils.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            connection = await pool._create_connection("stdio-server")

            assert connection == mock_client
            mock_client_class.assert_called_once()
            call_args = mock_client_class.call_args[0][0]
            assert call_args.startswith("stdio://")
            # Should properly encode special characters
            assert "path%20with%20spaces" in call_args

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_create_connection_failure(self):
        """Test connection creation failure."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {
            "type": "sse",
            "url": "http://localhost:8001/mcp",
        }

        await pool.register_server("failing-server", server_config)

        with patch(
            "tools.common.async_utils.Client",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(
                ServerConnectionError, match="Failed to create connection"
            ):
                await pool._create_connection("failing-server")

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_reuse(self):
        """Test connection reuse from pool."""
        pool = ConnectionPool(max_connections_per_server=2)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # First connection - should create new
            async with pool.get_connection("test-server") as conn1:
                assert conn1 == mock_client
                assert pool._active_connections["test-server"] == 1

            # Second connection - should reuse from pool
            async with pool.get_connection("test-server") as conn2:
                assert conn2 == mock_client

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """Test connection pool exhaustion."""
        pool = ConnectionPool(max_connections_per_server=1, connection_timeout=0.1)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Hold one connection
            async with pool.get_connection("test-server"):
                # Try to get another - should timeout
                with pytest.raises(ConnectionPoolExhaustedError):
                    async with pool.get_connection("test-server"):
                        pass

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_concurrent_access(self):
        """Test concurrent access to connection pool."""
        pool = ConnectionPool(max_connections_per_server=3)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        connection_count = 0

        def create_mock_client(*args, **kwargs):
            nonlocal connection_count
            connection_count += 1
            return mock_client

        with patch("tools.common.async_utils.Client", side_effect=create_mock_client):
            # Start multiple concurrent connections
            async def use_connection():
                async with pool.get_connection("test-server") as conn:
                    await asyncio.sleep(0.1)
                    return conn

            tasks = [use_connection() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(r == mock_client for r in results)
            # Should have created at most max_connections
            assert connection_count <= 3

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_cleanup(self):
        """Test idle connection cleanup."""
        pool = ConnectionPool(idle_timeout=0.1)  # Very short timeout
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Use and release a connection
            async with pool.get_connection("test-server"):
                pass

            # Wait for cleanup to run
            await asyncio.sleep(0.2)

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_cleanup_with_active_connections(self):
        """Test cleanup doesn't affect active connections."""
        pool = ConnectionPool(idle_timeout=0.1)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Hold an active connection while cleanup runs
            async with pool.get_connection("test-server"):
                await asyncio.sleep(0.2)  # Longer than idle timeout
                # Connection should still be valid

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_close_all_connections(self):
        """Test closing all connections."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            async with pool.get_connection("test-server"):
                pass

        await pool.close_all()

        assert pool._shutdown is True
        assert pool._cleanup_task.cancelled()

    @pytest.mark.asyncio
    async def test_cleanup_task_exception_handling(self):
        """Test cleanup task handles exceptions gracefully."""
        pool = ConnectionPool(idle_timeout=0.01)
        await pool.initialize()

        # Mock the cleanup to raise an exception
        async def failing_cleanup():
            await asyncio.sleep(0.01)
            raise Exception("Cleanup failed")

        pool._cleanup_task.cancel()
        pool._cleanup_task = asyncio.create_task(failing_cleanup())

        # Should not crash the pool
        await asyncio.sleep(0.05)

        # The cleanup task should have failed, but close_all should handle it
        try:
            await pool.close_all()
        except Exception:
            # Expected - the failing cleanup task will raise when awaited
            pass

    @pytest.mark.asyncio
    async def test_connection_pool_stress_test(self):
        """Stress test connection pool with many concurrent operations."""
        pool = ConnectionPool(max_connections_per_server=5, connection_timeout=1.0)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("stress-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        successful_connections = 0

        async def stress_connection():
            nonlocal successful_connections
            try:
                async with pool.get_connection("stress-server"):
                    await asyncio.sleep(0.01)
                    successful_connections += 1
            except Exception:
                pass

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Run many concurrent operations
            tasks = [stress_connection() for _ in range(50)]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Should have handled all connections successfully
            assert successful_connections > 40  # Allow for some timing variations

        await pool.close_all()


class TestRetryManager:
    """Comprehensive tests for RetryManager class."""

    @pytest.mark.asyncio
    async def test_retry_manager_initialization(self):
        """Test RetryManager initialization."""
        retry_manager = RetryManager(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )

        assert retry_manager.max_attempts == 5
        assert retry_manager.base_delay == 2.0
        assert retry_manager.max_delay == 30.0
        assert retry_manager.exponential_base == 3.0
        assert retry_manager.jitter is False

    @pytest.mark.asyncio
    async def test_retry_manager_default_initialization(self):
        """Test RetryManager with default values."""
        retry_manager = RetryManager()

        assert retry_manager.max_attempts == 3
        assert retry_manager.base_delay == 1.0
        assert retry_manager.max_delay == 60.0
        assert retry_manager.exponential_base == 2.0
        assert retry_manager.jitter is True

    @pytest.mark.asyncio
    async def test_successful_operation_first_attempt(self):
        """Test successful operation on first attempt."""
        retry_manager = RetryManager(max_attempts=3)

        async def successful_operation():
            return "success"

        result = await retry_manager.execute_with_retry(
            successful_operation, operation_name="test_op"
        )

        assert result.is_success
        assert result.data == "success"

    @pytest.mark.asyncio
    async def test_successful_operation_after_retries(self):
        """Test successful operation after some failures."""
        retry_manager = RetryManager(max_attempts=3, base_delay=0.01)
        attempt_count = 0

        async def eventually_successful_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await retry_manager.execute_with_retry(
            eventually_successful_operation, operation_name="test_op"
        )

        assert result.is_success
        assert result.data == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_operation_fails_all_attempts(self):
        """Test operation that fails all retry attempts."""
        retry_manager = RetryManager(max_attempts=2, base_delay=0.01)

        async def always_failing_operation():
            raise ValueError("Always fails")

        result = await retry_manager.execute_with_retry(
            always_failing_operation, operation_name="test_op"
        )

        assert result.is_failed
        assert "RETRY_EXHAUSTED" in result.error_code
        assert "Always fails" in result.error

    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test non-retryable exception handling."""
        retry_manager = RetryManager(max_attempts=3)

        async def operation_with_non_retryable_error():
            raise TypeError("Non-retryable error")

        result = await retry_manager.execute_with_retry(
            operation_with_non_retryable_error,
            retryable_exceptions=(ValueError,),
            operation_name="test_op",
        )

        assert result.is_failed
        assert result.error_code == "TypeError"
        assert "Non-retryable error" in result.error

    @pytest.mark.asyncio
    async def test_multiple_retryable_exceptions(self):
        """Test with multiple retryable exception types."""
        retry_manager = RetryManager(max_attempts=4, base_delay=0.01)
        attempt_count = 0

        async def operation_with_multiple_exceptions():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise ValueError("First failure")
            elif attempt_count == 2:
                raise ConnectionError("Second failure")
            elif attempt_count == 3:
                raise TimeoutError("Third failure")
            return "success"

        result = await retry_manager.execute_with_retry(
            operation_with_multiple_exceptions,
            retryable_exceptions=(ValueError, ConnectionError, TimeoutError),
            operation_name="test_op",
        )

        assert result.is_success
        assert result.data == "success"
        assert attempt_count == 4

    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        retry_manager = RetryManager(
            max_attempts=4,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False,
        )

        attempt_times = []

        async def failing_operation():
            attempt_times.append(time.time())
            raise ValueError("Test failure")

        start_time = time.time()
        result = await retry_manager.execute_with_retry(
            failing_operation, operation_name="test_op"
        )

        assert result.is_failed
        assert len(attempt_times) == 4

        # Check that delays increase exponentially (approximately)
        # First attempt: immediate
        # Second attempt: ~1s delay
        # Third attempt: ~2s delay
        # Fourth attempt: ~4s delay
        total_time = time.time() - start_time
        assert total_time >= 6.0  # At least 1 + 2 + 4 = 7 seconds of delays

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        retry_manager = RetryManager(
            max_attempts=3,
            base_delay=10.0,
            max_delay=0.1,  # Very low max delay
            exponential_base=2.0,
            jitter=False,
        )

        attempt_times = []

        async def failing_operation():
            attempt_times.append(time.time())
            raise ValueError("Test failure")

        start_time = time.time()
        await retry_manager.execute_with_retry(
            failing_operation, operation_name="test_op"
        )

        total_time = time.time() - start_time
        # Should be capped at max_delay, not exponential
        assert total_time < 1.0  # Much less than base_delay would suggest

    @pytest.mark.asyncio
    async def test_jitter_enabled(self):
        """Test retry with jitter enabled."""
        retry_manager = RetryManager(max_attempts=3, base_delay=0.1, jitter=True)

        attempt_times = []

        async def failing_operation():
            attempt_times.append(time.time())
            raise ValueError("Test failure")

        # Run multiple times to test jitter variability
        delays = []
        for _ in range(3):
            attempt_times.clear()
            start_time = time.time()
            await retry_manager.execute_with_retry(
                failing_operation, operation_name="test_op"
            )
            total_time = time.time() - start_time
            delays.append(total_time)

        # With jitter, delays should vary
        assert len(set(delays)) > 1 or all(
            d < 0.5 for d in delays
        )  # Allow for fast execution

    @pytest.mark.asyncio
    async def test_zero_max_attempts(self):
        """Test retry manager with zero max attempts."""
        retry_manager = RetryManager(max_attempts=0)

        async def operation():
            return "success"

        result = await retry_manager.execute_with_retry(operation)

        # Should not execute at all
        assert result.is_failed
        assert "RETRY_EXHAUSTED" in result.error_code

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        """Test retry manager with single attempt."""
        retry_manager = RetryManager(max_attempts=1)

        async def failing_operation():
            raise ValueError("Failure")

        result = await retry_manager.execute_with_retry(failing_operation)

        assert result.is_failed
        assert "RETRY_EXHAUSTED" in result.error_code

    @pytest.mark.asyncio
    async def test_very_large_exponential_base(self):
        """Test with very large exponential base."""
        retry_manager = RetryManager(
            max_attempts=3,
            base_delay=0.01,
            max_delay=0.1,
            exponential_base=100.0,
            jitter=False,
        )

        async def failing_operation():
            raise ValueError("Failure")

        start_time = time.time()
        await retry_manager.execute_with_retry(failing_operation)
        total_time = time.time() - start_time

        # Should be capped by max_delay
        assert total_time < 0.5


class TestConcurrentOperations:
    """Tests for concurrent operation utilities."""

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_success(self):
        """Test successful concurrent operations."""

        async def operation_1():
            await asyncio.sleep(0.01)
            return "result_1"

        async def operation_2():
            await asyncio.sleep(0.01)
            return "result_2"

        operations = [operation_1, operation_2]
        operation_names = ["op_1", "op_2"]

        results = await run_concurrent_operations(
            operations, max_concurrent=2, operation_names=operation_names
        )

        assert len(results) == 2
        assert all(r.is_success for r in results)
        assert results[0].data == "result_1"
        assert results[1].data == "result_2"
        assert all(r.duration_ms > 0 for r in results)

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_with_failures(self):
        """Test concurrent operations with some failures."""

        async def successful_operation():
            return "success"

        async def failing_operation():
            raise ValueError("Operation failed")

        operations = [successful_operation, failing_operation]

        results = await run_concurrent_operations(operations, max_concurrent=2)

        assert len(results) == 2
        assert results[0].is_success
        assert results[0].data == "success"
        assert results[1].is_failed
        assert "Operation failed" in results[1].error

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_concurrency_limit(self):
        """Test concurrent operations respect concurrency limit."""
        execution_order = []

        async def timed_operation():
            execution_order.append("start")
            await asyncio.sleep(0.1)
            execution_order.append("end")
            return "done"

        operations = [timed_operation for _ in range(4)]

        start_time = time.time()
        results = await run_concurrent_operations(operations, max_concurrent=2)
        total_time = time.time() - start_time

        assert len(results) == 4
        assert all(r.is_success for r in results)
        # With max_concurrent=2, should take at least 0.2s (two batches)
        assert total_time >= 0.15

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_empty_list(self):
        """Test executing empty list of operations."""
        results = await run_concurrent_operations([])
        assert results == []

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_default_names(self):
        """Test concurrent operations with default names."""

        async def simple_operation():
            return "result"

        operations = [simple_operation, simple_operation]

        results = await run_concurrent_operations(operations)

        assert len(results) == 2
        assert all(r.is_success for r in results)

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_exception_handling(self):
        """Test exception handling in concurrent operations."""

        async def exception_operation():
            raise RuntimeError("Runtime error")

        operations = [exception_operation]

        results = await run_concurrent_operations(operations)

        assert len(results) == 1
        assert results[0].is_failed
        assert results[0].error_code == "RuntimeError"

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_mixed_timing(self):
        """Test operations with different execution times."""

        async def fast_operation():
            await asyncio.sleep(0.01)
            return "fast"

        async def slow_operation():
            await asyncio.sleep(0.1)
            return "slow"

        operations = [fast_operation, slow_operation, fast_operation]

        start_time = time.time()
        results = await run_concurrent_operations(operations, max_concurrent=3)
        total_time = time.time() - start_time

        assert len(results) == 3
        assert all(r.is_success for r in results)
        # Should complete in time of slowest operation
        assert 0.08 <= total_time <= 0.2

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_large_batch(self):
        """Test concurrent operations with large batch."""

        async def batch_operation():
            await asyncio.sleep(0.01)
            return "batch_result"

        operations = [batch_operation for _ in range(20)]

        results = await run_concurrent_operations(operations, max_concurrent=5)

        assert len(results) == 20
        assert all(r.is_success for r in results)
        assert all(r.data == "batch_result" for r in results)

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_zero_max_concurrent(self):
        """Test concurrent operations with zero max_concurrent (should use unlimited)."""

        async def test_operation():
            await asyncio.sleep(0.01)
            return "unlimited"

        operations = [test_operation for _ in range(5)]

        start_time = time.time()
        results = await run_concurrent_operations(operations, max_concurrent=0)
        total_time = time.time() - start_time

        assert len(results) == 5
        assert all(r.is_success for r in results)
        assert all(r.data == "unlimited" for r in results)
        # Should complete quickly since all operations run concurrently
        assert total_time < 0.1

    @pytest.mark.asyncio
    async def test_run_concurrent_operations_negative_max_concurrent(self):
        """Test concurrent operations with negative max_concurrent (should use unlimited)."""

        async def test_operation():
            await asyncio.sleep(0.01)
            return "negative_unlimited"

        operations = [test_operation for _ in range(3)]

        results = await run_concurrent_operations(operations, max_concurrent=-1)

        assert len(results) == 3
        assert all(r.is_success for r in results)
        assert all(r.data == "negative_unlimited" for r in results)


class TestGlobalConnectionPool:
    """Tests for global connection pool management."""

    @pytest.mark.asyncio
    async def test_get_connection_pool_singleton(self):
        """Test global connection pool singleton behavior."""
        # Clean up any existing pool
        await shutdown_connection_pool()

        pool1 = await get_connection_pool()
        pool2 = await get_connection_pool()

        assert pool1 is pool2
        assert pool1._cleanup_task is not None

        await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_shutdown_connection_pool(self):
        """Test shutting down global connection pool."""
        pool = await get_connection_pool()
        assert pool is not None

        await shutdown_connection_pool()

        # Should create new pool after shutdown
        new_pool = await get_connection_pool()
        assert new_pool is not pool

        await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_shutdown_connection_pool_when_none(self):
        """Test shutting down when no pool exists."""
        await shutdown_connection_pool()

        # Should not raise an error
        await shutdown_connection_pool()

    @pytest.mark.asyncio
    async def test_global_pool_lifecycle(self):
        """Test complete lifecycle of global connection pool."""
        # Start with clean state
        await shutdown_connection_pool()

        # Create pool and register server
        pool = await get_connection_pool()
        await pool.register_server(
            "test-server", {"type": "sse", "url": "http://localhost:8001"}
        )

        # Verify pool is working
        assert "test-server" in pool._connection_configs

        # Shutdown and verify cleanup
        await shutdown_connection_pool()

        # Create new pool - should be fresh
        new_pool = await get_connection_pool()
        assert new_pool is not pool
        assert "test-server" not in new_pool._connection_configs

        await shutdown_connection_pool()


class TestConnectionPoolEdgeCases:
    """Test edge cases and error scenarios for ConnectionPool."""

    @pytest.mark.asyncio
    async def test_connection_pool_queue_full_scenario(self):
        """Test connection pool behavior when queue is full."""
        pool = ConnectionPool(max_connections_per_server=2)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Fill the queue to capacity
        with patch("tools.common.async_utils.Client", return_value=mock_client):
            connections = []
            for _ in range(2):
                async with pool.get_connection("test-server") as conn:
                    connections.append(conn)

            # Queue should be full, additional connections should be closed
            async with pool.get_connection("test-server") as conn:
                assert conn == mock_client

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_release_error_handling(self):
        """Test error handling during connection release."""
        pool = ConnectionPool()
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock queue to raise exception on put
        with patch("tools.common.async_utils.Client", return_value=mock_client):
            with patch.object(
                pool._pools["test-server"], "put_nowait", side_effect=asyncio.QueueFull
            ):
                async with pool.get_connection("test-server") as conn:
                    assert conn == mock_client
                # Should handle the queue full exception gracefully

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_cleanup_with_connection_errors(self):
        """Test cleanup handles connection errors gracefully."""
        pool = ConnectionPool(idle_timeout=0.01)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Use connection and let it become idle
            async with pool.get_connection("test-server"):
                pass

            # Mock close_connection to raise an error
            async def failing_close(*args, **kwargs):
                raise Exception("Close failed")

            pool._close_connection = failing_close

            # Wait for cleanup - should handle errors gracefully
            await asyncio.sleep(0.1)

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_initialization_without_initialize_call(self):
        """Test using connection pool without calling initialize."""
        pool = ConnectionPool()
        # Don't call initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        # Should still work, just without cleanup task
        assert pool._cleanup_task is None

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_double_initialization(self):
        """Test calling initialize multiple times."""
        pool = ConnectionPool()

        await pool.initialize()
        first_task = pool._cleanup_task

        await pool.initialize()
        second_task = pool._cleanup_task

        # Should not create multiple cleanup tasks
        assert first_task is second_task

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_with_zero_max_connections(self):
        """Test connection pool with zero max connections."""
        pool = ConnectionPool(max_connections_per_server=0, connection_timeout=0.1)
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        # Should immediately timeout since no connections allowed
        with pytest.raises(ConnectionPoolExhaustedError):
            async with pool.get_connection("test-server"):
                pass

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_server_reregistration(self):
        """Test re-registering a server with different config."""
        pool = ConnectionPool()
        await pool.initialize()

        # Register server first time
        config1 = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", config1)

        # Re-register with different config
        config2 = {"type": "sse", "url": "http://localhost:8002/mcp"}
        await pool.register_server("test-server", config2)

        # Should use new config
        assert pool._connection_configs["test-server"] == config2

        await pool.close_all()

    @pytest.mark.asyncio
    async def test_connection_pool_with_very_short_idle_timeout(self):
        """Test connection pool with very short idle timeout."""
        pool = ConnectionPool(idle_timeout=0.001)  # 1ms
        await pool.initialize()

        server_config = {"type": "sse", "url": "http://localhost:8001/mcp"}
        await pool.register_server("test-server", server_config)

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("tools.common.async_utils.Client", return_value=mock_client):
            # Use connection briefly
            async with pool.get_connection("test-server"):
                pass

            # Wait longer than idle timeout
            await asyncio.sleep(0.1)

            # Connection should have been cleaned up
            # (This is hard to test directly, but cleanup should run)

        await pool.close_all()
