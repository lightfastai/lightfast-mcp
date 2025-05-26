"""
Comprehensive tests for ServerOrchestrator - critical server lifecycle management.
"""

import asyncio
import signal
import subprocess
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from tools.common import (
    ServerInfo,
    ServerState,
)
from tools.orchestration.server_orchestrator import (
    ServerOrchestrator,
    ServerProcess,
    get_orchestrator,
)


class TestServerProcess:
    """Tests for ServerProcess dataclass."""

    def test_server_process_initialization(self):
        """Test ServerProcess initialization."""
        config = ServerConfig(
            name="test-server",
            description="Test server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        process = ServerProcess(config=config)

        assert process.server is None
        assert process.thread is None
        assert process.process is None
        assert process.process_id is None
        assert isinstance(process.start_time, datetime)
        assert process.is_background is False
        assert process.config == config

    def test_server_process_with_server(self):
        """Test ServerProcess with server instance."""
        mock_server = MagicMock()
        process = ServerProcess(server=mock_server, is_background=True)

        assert process.server == mock_server
        assert process.is_background is True

    def test_server_process_with_subprocess(self):
        """Test ServerProcess with subprocess."""
        mock_subprocess = MagicMock()
        mock_subprocess.pid = 12345
        process = ServerProcess(process=mock_subprocess, process_id=12345)

        assert process.process == mock_subprocess
        assert process.process_id == 12345

    def test_server_process_with_thread(self):
        """Test ServerProcess with thread."""
        mock_thread = MagicMock()
        process = ServerProcess(thread=mock_thread, is_background=True)

        assert process.thread == mock_thread
        assert process.is_background is True

    def test_server_process_uptime_calculation(self):
        """Test uptime calculation."""
        process = ServerProcess()

        # Small delay to ensure uptime > 0
        time.sleep(0.01)

        uptime = process.uptime_seconds
        assert uptime > 0
        assert uptime < 1  # Should be very small

    def test_server_process_uptime_with_custom_start_time(self):
        """Test uptime calculation with custom start time."""
        past_time = datetime.utcnow()
        # Simulate 1 second ago
        past_time = past_time - timedelta(seconds=1)

        process = ServerProcess()
        process.start_time = past_time

        uptime = process.uptime_seconds
        assert uptime >= 1.0


class TestServerOrchestrator:
    """Comprehensive tests for ServerOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create a ServerOrchestrator instance for testing."""
        return ServerOrchestrator(max_concurrent_startups=2)

    @pytest.fixture
    def sample_config(self):
        """Create a sample server configuration."""
        return ServerConfig(
            name="test-server",
            description="Test server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

    @pytest.fixture
    def stdio_config(self):
        """Create a stdio server configuration."""
        return ServerConfig(
            name="stdio-server",
            description="Stdio test server",
            host="localhost",
            port=0,
            transport="stdio",
            path="",
            config={"type": "mock"},
        )

    def test_orchestrator_initialization(self, orchestrator):
        """Test ServerOrchestrator initialization."""
        assert orchestrator.max_concurrent_startups == 2
        assert len(orchestrator._running_servers) == 0
        assert not orchestrator._shutdown_event.is_set()
        assert orchestrator.retry_manager.max_attempts == 3

    def test_orchestrator_initialization_defaults(self):
        """Test ServerOrchestrator initialization with defaults."""
        orchestrator = ServerOrchestrator()
        assert orchestrator.max_concurrent_startups == 3

    def test_orchestrator_singleton_pattern(self):
        """Test global orchestrator singleton pattern."""
        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()
        assert orchestrator1 is orchestrator2

    def test_setup_signal_handlers(self, orchestrator):
        """Test signal handler setup."""
        # This is hard to test directly, but we can verify the method exists
        # and doesn't raise an exception
        orchestrator._setup_signal_handlers()
        # No assertion needed - just verify it doesn't crash

    def test_setup_signal_handlers_error(self, orchestrator):
        """Test signal handler setup with error."""
        with patch("signal.signal", side_effect=ValueError("Signal error")):
            # Should not raise an exception
            orchestrator._setup_signal_handlers()

    @pytest.mark.asyncio
    async def test_start_server_already_running(self, orchestrator, sample_config):
        """Test starting a server that's already running."""
        # Add server to running list
        orchestrator._running_servers[sample_config.name] = ServerProcess()

        result = await orchestrator.start_server(sample_config)

        assert result.is_failed
        assert "already running" in result.error

    @pytest.mark.asyncio
    async def test_start_server_invalid_config(self, orchestrator):
        """Test starting server with invalid configuration."""
        invalid_config = ServerConfig(
            name="invalid-server",
            description="Invalid server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "unknown"},  # Unknown type
        )

        # Mock registry to return invalid config
        with patch.object(
            orchestrator.registry,
            "validate_server_config",
            return_value=(False, "Invalid type"),
        ):
            result = await orchestrator.start_server(invalid_config)

        assert result.is_failed
        assert "Invalid configuration" in result.error

    @pytest.mark.asyncio
    async def test_start_server_subprocess_success(self, orchestrator, sample_config):
        """Test successful server startup using subprocess."""
        # Mock registry validation
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            # Mock subprocess creation
            mock_process = MagicMock()
            mock_process.pid = 12345

            with patch("subprocess.Popen", return_value=mock_process):
                with patch("sys.executable", "/usr/bin/python"):
                    result = await orchestrator.start_server(
                        sample_config, background=True
                    )

        assert result.is_success
        server_info = result.data
        assert isinstance(server_info, ServerInfo)
        assert server_info.name == "test-server"
        assert server_info.state == ServerState.RUNNING
        assert server_info.pid == 12345
        assert sample_config.name in orchestrator._running_servers

    @pytest.mark.asyncio
    async def test_start_server_subprocess_untrusted_type(self, orchestrator):
        """Test starting server with untrusted type for subprocess."""
        untrusted_config = ServerConfig(
            name="untrusted-server",
            description="Untrusted server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "untrusted"},
        )

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            result = await orchestrator.start_server(untrusted_config)

        assert result.is_failed
        assert "Unknown or untrusted server type" in result.error

    @pytest.mark.asyncio
    async def test_start_server_subprocess_no_python(self, orchestrator, sample_config):
        """Test starting server when Python executable not found."""
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch("sys.executable", None):
                with patch("shutil.which", return_value=None):
                    result = await orchestrator.start_server(sample_config)

        assert result.is_failed
        assert "Could not find Python executable" in result.error

    @pytest.mark.asyncio
    async def test_start_server_subprocess_failure(self, orchestrator, sample_config):
        """Test server startup subprocess failure."""
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch("subprocess.Popen", side_effect=Exception("Subprocess failed")):
                result = await orchestrator.start_server(sample_config)

        assert result.is_failed
        assert "Failed to start server subprocess" in result.error

    @pytest.mark.asyncio
    async def test_start_server_traditional_success(self, orchestrator, stdio_config):
        """Test successful server startup using traditional approach."""
        mock_server = MagicMock()

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch.object(
                orchestrator.registry, "create_server", return_value=mock_server
            ):
                result = await orchestrator.start_server(stdio_config, background=False)

        assert result.is_success
        server_info = result.data
        assert server_info.name == "stdio-server"
        assert server_info.transport == "stdio"

    @pytest.mark.asyncio
    async def test_start_server_traditional_background(
        self, orchestrator, stdio_config
    ):
        """Test server startup in background using traditional approach."""
        mock_server = MagicMock()

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch.object(
                orchestrator.registry, "create_server", return_value=mock_server
            ):
                with patch("threading.Thread") as mock_thread_class:
                    mock_thread = MagicMock()
                    mock_thread_class.return_value = mock_thread

                    result = await orchestrator.start_server(
                        stdio_config, background=True
                    )

        assert result.is_success
        mock_thread.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_server_traditional_failure(self, orchestrator, stdio_config):
        """Test traditional server startup failure."""
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch.object(
                orchestrator.registry,
                "create_server",
                side_effect=Exception("Server creation failed"),
            ):
                result = await orchestrator.start_server(stdio_config)

        assert result.is_failed
        assert "Failed to start server traditionally" in result.error

    @pytest.mark.asyncio
    async def test_start_server_general_exception(self, orchestrator, sample_config):
        """Test server startup with general exception."""
        # Mock validation to pass, but then mock subprocess creation to fail
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch(
                "subprocess.Popen", side_effect=Exception("Subprocess creation failed")
            ):
                result = await orchestrator.start_server(sample_config)

        assert result.is_failed
        assert "Failed to start server test-server" in result.error

    def test_run_server_in_thread(self, orchestrator):
        """Test running server in thread."""
        mock_server = MagicMock()
        server_name = "thread-test"

        # Add server to running list
        orchestrator._running_servers[server_name] = ServerProcess(server=mock_server)

        with patch("asyncio.new_event_loop") as mock_new_loop:
            with patch("asyncio.set_event_loop") as mock_set_loop:
                mock_loop = MagicMock()
                mock_new_loop.return_value = mock_loop

                orchestrator._run_server_in_thread(mock_server, server_name)

                mock_new_loop.assert_called_once()
                mock_set_loop.assert_called_once_with(mock_loop)
                mock_server.run.assert_called_once()
                mock_loop.close.assert_called_once()

    def test_run_server_in_thread_exception(self, orchestrator):
        """Test running server in thread with exception."""
        mock_server = MagicMock()
        mock_server.run.side_effect = Exception("Server run failed")
        server_name = "thread-error-test"

        # Add server to running list
        orchestrator._running_servers[server_name] = ServerProcess(server=mock_server)

        with patch("asyncio.new_event_loop") as mock_new_loop:
            mock_loop = MagicMock()
            mock_new_loop.return_value = mock_loop

            orchestrator._run_server_in_thread(mock_server, server_name)

            # Server should be removed from running list after exception
            assert server_name not in orchestrator._running_servers

    @pytest.mark.asyncio
    async def test_start_multiple_servers_success(self, orchestrator):
        """Test starting multiple servers successfully."""
        configs = [
            ServerConfig(
                name=f"server-{i}",
                description=f"Server {i}",
                host="localhost",
                port=8000 + i,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            )
            for i in range(3)
        ]

        with patch.object(orchestrator, "start_server") as mock_start:
            mock_start.return_value = MagicMock(is_success=True)

            result = await orchestrator.start_multiple_servers(configs)

        assert result.is_success
        startup_results = result.data
        assert len(startup_results) == 3
        assert all(startup_results.values())

    @pytest.mark.asyncio
    async def test_start_multiple_servers_empty_list(self, orchestrator):
        """Test starting multiple servers with empty list."""
        result = await orchestrator.start_multiple_servers([])

        assert result.is_success
        assert result.data == {}

    @pytest.mark.asyncio
    async def test_start_multiple_servers_partial_failure(self, orchestrator):
        """Test starting multiple servers with some failures."""
        configs = [
            ServerConfig(
                name="server-1",
                description="Server 1",
                host="localhost",
                port=8001,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            ),
            ServerConfig(
                name="server-2",
                description="Server 2",
                host="localhost",
                port=8002,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            ),
        ]

        async def mock_start_server(config, *args, **kwargs):
            from tools.common import OperationStatus, Result

            if config.name == "server-1":
                return Result(status=OperationStatus.SUCCESS, data=None)
            else:
                return Result(
                    status=OperationStatus.FAILED, error="Server failed to start"
                )

        with patch.object(orchestrator, "start_server", side_effect=mock_start_server):
            result = await orchestrator.start_multiple_servers(configs)

        assert result.is_success
        startup_results = result.data
        assert startup_results["server-1"] is True
        assert startup_results["server-2"] is False

    @pytest.mark.asyncio
    async def test_start_multiple_servers_concurrency_limit(self, orchestrator):
        """Test starting multiple servers respects concurrency limit."""
        orchestrator.max_concurrent_startups = 2

        configs = [
            ServerConfig(
                name=f"server-{i}",
                description=f"Server {i}",
                host="localhost",
                port=8000 + i,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            )
            for i in range(5)
        ]

        start_times = []

        async def mock_start_server(config, *args, **kwargs):
            start_times.append(time.time())
            await asyncio.sleep(0.1)  # Simulate startup time
            return MagicMock(is_success=True)

        with patch.object(orchestrator, "start_server", side_effect=mock_start_server):
            start_time = time.time()
            result = await orchestrator.start_multiple_servers(configs)
            total_time = time.time() - start_time

        assert result.is_success
        # With concurrency limit of 2 and 5 servers, should take at least 3 batches
        assert total_time >= 0.25  # At least 3 * 0.1 - some tolerance

    def test_get_running_servers_with_server_instances(self, orchestrator):
        """Test getting running servers with server instances."""
        mock_server = MagicMock()
        mock_server.info = ServerInfo(
            name="test-server",
            server_type="mock",
            state=ServerState.RUNNING,
            host="localhost",
            port=8001,
            transport="http",
        )

        orchestrator._running_servers["test-server"] = ServerProcess(server=mock_server)

        running_servers = orchestrator.get_running_servers()

        assert len(running_servers) == 1
        assert "test-server" in running_servers
        assert running_servers["test-server"] == mock_server.info

    def test_get_running_servers_with_subprocess(self, orchestrator):
        """Test getting running servers with subprocess."""
        config = ServerConfig(
            name="subprocess-server",
            description="Subprocess server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running

        server_process = ServerProcess(
            process=mock_process,
            process_id=12345,
            config=config,
        )

        orchestrator._running_servers["subprocess-server"] = server_process

        running_servers = orchestrator.get_running_servers()

        assert len(running_servers) == 1
        server_info = running_servers["subprocess-server"]
        assert server_info.name == "subprocess-server"
        assert server_info.state == ServerState.RUNNING
        assert server_info.pid == 12345

    def test_get_running_servers_with_stopped_subprocess(self, orchestrator):
        """Test getting running servers with stopped subprocess."""
        config = ServerConfig(
            name="stopped-server",
            description="Stopped server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Stopped with exit code 1

        server_process = ServerProcess(
            process=mock_process,
            process_id=12345,
            config=config,
        )

        orchestrator._running_servers["stopped-server"] = server_process

        running_servers = orchestrator.get_running_servers()

        server_info = running_servers["stopped-server"]
        assert server_info.state == ServerState.ERROR

    def test_get_running_servers_empty(self, orchestrator):
        """Test getting running servers when none are running."""
        running_servers = orchestrator.get_running_servers()
        assert running_servers == {}

    def test_is_process_running_true(self, orchestrator):
        """Test checking if process is running (true case)."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running

        server_process = ServerProcess(process=mock_process)

        is_running = orchestrator._is_process_running(server_process)
        assert is_running is True

    def test_is_process_running_false(self, orchestrator):
        """Test checking if process is running (false case)."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Stopped

        server_process = ServerProcess(process=mock_process)

        is_running = orchestrator._is_process_running(server_process)
        assert is_running is False

    def test_is_process_running_no_process(self, orchestrator):
        """Test checking if process is running with no process."""
        server_process = ServerProcess()  # No process

        is_running = orchestrator._is_process_running(server_process)
        assert is_running is False

    def test_stop_server_success(self, orchestrator):
        """Test stopping a server successfully."""
        mock_process = MagicMock()
        mock_process.terminate.return_value = None
        mock_process.wait.return_value = None

        orchestrator._running_servers["test-server"] = ServerProcess(
            process=mock_process
        )

        result = orchestrator.stop_server("test-server")

        assert result is True
        assert "test-server" not in orchestrator._running_servers
        mock_process.terminate.assert_called_once()

    def test_stop_server_not_running(self, orchestrator):
        """Test stopping a server that's not running."""
        result = orchestrator.stop_server("nonexistent-server")

        assert result is False

    def test_stop_server_force_kill(self, orchestrator):
        """Test stopping a server that requires force kill."""
        mock_process = MagicMock()
        mock_process.terminate.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 5)
        mock_process.kill.return_value = None

        orchestrator._running_servers["stubborn-server"] = ServerProcess(
            process=mock_process
        )

        result = orchestrator.stop_server("stubborn-server")

        assert result is True
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    def test_stop_server_with_thread(self, orchestrator):
        """Test stopping a server running in thread."""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        orchestrator._running_servers["thread-server"] = ServerProcess(
            thread=mock_thread
        )

        result = orchestrator.stop_server("thread-server")

        assert result is True
        assert "thread-server" not in orchestrator._running_servers

    def test_stop_server_exception(self, orchestrator):
        """Test stopping a server with exception."""
        mock_process = MagicMock()
        mock_process.terminate.side_effect = Exception("Terminate failed")

        orchestrator._running_servers["error-server"] = ServerProcess(
            process=mock_process
        )

        result = orchestrator.stop_server("error-server")

        assert (
            result is True
        )  # Server is still removed from running list despite exception
        assert "error-server" not in orchestrator._running_servers

    def test_shutdown_all_servers(self, orchestrator):
        """Test shutting down all servers."""
        # Add multiple servers
        for i in range(3):
            mock_process = MagicMock()
            orchestrator._running_servers[f"server-{i}"] = ServerProcess(
                process=mock_process
            )

        with patch.object(orchestrator, "stop_server", return_value=True) as mock_stop:
            orchestrator.shutdown_all()

        assert mock_stop.call_count == 3
        assert orchestrator._shutdown_event.is_set()

    def test_shutdown_all_no_servers(self, orchestrator):
        """Test shutting down when no servers are running."""
        orchestrator.shutdown_all()

        assert orchestrator._shutdown_event.is_set()


class TestServerOrchestratorEdgeCases:
    """Test edge cases and error scenarios for ServerOrchestrator."""

    @pytest.mark.asyncio
    async def test_start_server_with_environment_config(self):
        """Test starting server with environment configuration."""
        orchestrator = ServerOrchestrator()

        config = ServerConfig(
            name="env-server",
            description="Environment server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch("subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                with patch("sys.executable", "/usr/bin/python"):
                    await orchestrator.start_server(config)

                # Verify environment was set
                call_args = mock_popen.call_args
                env = call_args[1]["env"]
                assert "LIGHTFAST_MCP_SERVER_CONFIG" in env

    @pytest.mark.asyncio
    async def test_start_server_with_different_concurrency_settings(self):
        """Test starting servers with different concurrency settings."""
        # Test with very high concurrency
        high_concurrency_orchestrator = ServerOrchestrator(max_concurrent_startups=100)
        assert high_concurrency_orchestrator.max_concurrent_startups == 100

        # Test with zero concurrency
        zero_concurrency_orchestrator = ServerOrchestrator(max_concurrent_startups=0)
        assert zero_concurrency_orchestrator.max_concurrent_startups == 0

    @pytest.mark.asyncio
    async def test_start_server_subprocess_with_log_capture(self):
        """Test starting server subprocess with log capture."""
        orchestrator = ServerOrchestrator()

        config = ServerConfig(
            name="log-server",
            description="Log server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch("subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                with patch("sys.executable", "/usr/bin/python"):
                    # Test with background=True and show_logs=False (should capture logs)
                    await orchestrator.start_server(
                        config, background=True, show_logs=False
                    )

                # Verify subprocess was called with log capture
                call_args = mock_popen.call_args
                assert call_args[1]["stdout"] == subprocess.PIPE
                assert call_args[1]["stderr"] == subprocess.PIPE

    @pytest.mark.asyncio
    async def test_start_server_subprocess_without_log_capture(self):
        """Test starting server subprocess without log capture."""
        orchestrator = ServerOrchestrator()

        config = ServerConfig(
            name="no-log-server",
            description="No log server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )

        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch("subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process

                with patch("sys.executable", "/usr/bin/python"):
                    # Test with background=False or show_logs=True (should not capture logs)
                    await orchestrator.start_server(
                        config, background=False, show_logs=True
                    )

                # Verify subprocess was called without log capture
                call_args = mock_popen.call_args
                assert call_args[1]["stdout"] is None
                assert call_args[1]["stderr"] is None

    def test_server_orchestrator_error_recovery(self):
        """Test server orchestrator error recovery scenarios."""
        orchestrator = ServerOrchestrator()

        # Test with invalid server in running list (with config so it shows up)
        config = ServerConfig(
            name="invalid-server",
            description="Invalid server",
            host="localhost",
            port=8001,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )
        invalid_process = ServerProcess(config=config)
        orchestrator._running_servers["invalid-server"] = invalid_process

        # Should handle gracefully when getting running servers
        running_servers = orchestrator.get_running_servers()
        assert "invalid-server" in running_servers

    @pytest.mark.asyncio
    async def test_start_multiple_servers_with_error_recovery(self):
        """Test starting multiple servers with error recovery."""
        orchestrator = ServerOrchestrator()

        configs = [
            ServerConfig(
                name="good-server",
                description="Good server",
                host="localhost",
                port=8001,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            ),
            ServerConfig(
                name="bad-server",
                description="Bad server",
                host="localhost",
                port=8002,
                transport="http",
                path="/mcp",
                config={"type": "mock"},
            ),
        ]

        async def mock_start_server(config, *args, **kwargs):
            if config.name == "good-server":
                return MagicMock(is_success=True)
            else:
                raise Exception("Server startup failed")

        with patch.object(orchestrator, "start_server", side_effect=mock_start_server):
            result = await orchestrator.start_multiple_servers(configs)

        # Should handle errors gracefully and continue with other servers
        assert result.is_success
        startup_results = result.data
        assert startup_results["good-server"] is True
        assert startup_results["bad-server"] is False

    def test_server_orchestrator_signal_handling_edge_cases(self):
        """Test signal handling edge cases."""
        orchestrator = ServerOrchestrator()

        # Test signal handler function directly
        def test_signal_handler(signum, frame):
            orchestrator.shutdown_all()

        # Should not raise an exception
        test_signal_handler(signal.SIGTERM, None)
        assert orchestrator._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_start_server_with_retry_logic(self):
        """Test server startup with retry logic integration."""
        orchestrator = ServerOrchestrator()

        # Test that retry manager is properly initialized
        assert orchestrator.retry_manager.max_attempts == 3
        assert orchestrator.retry_manager.base_delay == 2.0

    def test_server_process_edge_cases(self):
        """Test ServerProcess edge cases."""
        # Test with all None values
        process = ServerProcess()
        assert process.server is None
        assert process.thread is None
        assert process.process is None
        assert process.process_id is None

        # Test uptime calculation edge case
        uptime1 = process.uptime_seconds
        time.sleep(0.001)  # Very small delay
        uptime2 = process.uptime_seconds
        assert uptime2 > uptime1

    @pytest.mark.asyncio
    async def test_start_server_with_custom_retry_manager(self):
        """Test starting server with custom retry manager settings."""
        from tools.common import RetryManager

        custom_retry_manager = RetryManager(max_attempts=5, base_delay=1.0)
        orchestrator = ServerOrchestrator()
        orchestrator.retry_manager = custom_retry_manager

        assert orchestrator.retry_manager.max_attempts == 5
        assert orchestrator.retry_manager.base_delay == 1.0

    def test_get_running_servers_with_mixed_server_types(self):
        """Test getting running servers with mixed server types."""
        orchestrator = ServerOrchestrator()

        # Add server instance
        mock_server = MagicMock()
        mock_server.info = ServerInfo(
            name="instance-server",
            server_type="mock",
            state=ServerState.RUNNING,
            host="localhost",
            port=8001,
            transport="stdio",
        )
        orchestrator._running_servers["instance-server"] = ServerProcess(
            server=mock_server
        )

        # Add subprocess
        config = ServerConfig(
            name="subprocess-server",
            description="Subprocess server",
            host="localhost",
            port=8002,
            transport="http",
            path="/mcp",
            config={"type": "mock"},
        )
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        orchestrator._running_servers["subprocess-server"] = ServerProcess(
            process=mock_process,
            process_id=54321,
            config=config,
        )

        running_servers = orchestrator.get_running_servers()

        assert len(running_servers) == 2
        assert running_servers["instance-server"].transport == "stdio"
        assert running_servers["subprocess-server"].transport == "http"
        assert running_servers["subprocess-server"].url == "http://localhost:8002/mcp"

    @pytest.mark.asyncio
    async def test_orchestrator_integration_scenario(self):
        """Test complete orchestrator integration scenario."""
        orchestrator = ServerOrchestrator(max_concurrent_startups=2)

        # Create multiple server configs
        configs = []
        for i in range(3):
            config = ServerConfig(
                name=f"integration-server-{i}",
                description=f"Integration server {i}",
                host="localhost",
                port=8000 + i,
                transport="http" if i % 2 == 0 else "stdio",
                path="/mcp" if i % 2 == 0 else "",
                config={"type": "mock"},
            )
            configs.append(config)

        # Mock successful startup for all servers
        with patch.object(
            orchestrator.registry, "validate_server_config", return_value=(True, None)
        ):
            with patch.object(
                orchestrator.registry, "create_server", return_value=MagicMock()
            ):
                with patch("subprocess.Popen") as mock_popen:
                    with patch("threading.Thread") as mock_thread_class:
                        mock_process = MagicMock()
                        mock_process.pid = 12345
                        mock_popen.return_value = mock_process

                        mock_thread = MagicMock()
                        mock_thread_class.return_value = mock_thread

                        with patch("sys.executable", "/usr/bin/python"):
                            # Start all servers
                            result = await orchestrator.start_multiple_servers(
                                configs, background=True
                            )

        assert result.is_success
        assert len(result.data) == 3
        assert all(result.data.values())

        # Check running servers
        running_servers = orchestrator.get_running_servers()
        assert len(running_servers) == 3

        # Stop all servers
        orchestrator.shutdown_all()
        assert orchestrator._shutdown_event.is_set()


class TestGlobalOrchestrator:
    """Tests for global orchestrator management."""

    def test_global_orchestrator_singleton(self):
        """Test that global orchestrator maintains singleton pattern."""
        # Reset global state
        import tools.orchestration.server_orchestrator as orchestrator_module

        orchestrator_module._orchestrator = None

        orchestrator1 = get_orchestrator()
        orchestrator2 = get_orchestrator()

        assert orchestrator1 is orchestrator2
        assert isinstance(orchestrator1, ServerOrchestrator)

    def test_global_orchestrator_initialization(self):
        """Test global orchestrator initialization."""
        # Reset global state
        import tools.orchestration.server_orchestrator as orchestrator_module

        orchestrator_module._orchestrator = None

        orchestrator = get_orchestrator()

        assert orchestrator.max_concurrent_startups == 3  # Default value
        assert len(orchestrator._running_servers) == 0
