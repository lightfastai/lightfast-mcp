"""
Test cases for MultiServerManager.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import BaseServer, ServerConfig
from lightfast_mcp.core.multi_server_manager import MultiServerManager, get_manager


class MockTestServer(BaseServer):
    """Mock test server for testing."""

    SERVER_TYPE = "mock_test"
    SERVER_VERSION = "1.0.0"

    def _register_tools(self):
        """Register test tools."""
        self.info.tools = ["mock_tool"]

    async def _on_startup(self):
        """Mock startup."""
        pass

    async def _on_shutdown(self):
        """Mock shutdown."""
        pass


class FailingMockServer(BaseServer):
    """Mock server that fails during startup."""

    SERVER_TYPE = "failing_mock"
    SERVER_VERSION = "1.0.0"

    def _register_tools(self):
        """Register test tools."""
        self.info.tools = ["failing_tool"]

    async def _on_startup(self):
        """Fail during startup."""
        raise RuntimeError("Mock startup failure")


class TestMultiServerManager:
    """Tests for MultiServerManager class."""

    def test_manager_singleton(self):
        """Test that get_manager returns the same instance."""
        manager1 = get_manager()
        manager2 = get_manager()

        assert manager1 is manager2
        assert isinstance(manager1, MultiServerManager)

    def test_manager_initialization(self):
        """Test MultiServerManager initialization."""
        manager = MultiServerManager()

        assert manager.registry is not None
        assert manager._running_servers == {}
        assert hasattr(manager, "_shutdown_event")

    def test_start_single_server(self):
        """Test starting a single server."""
        manager = MultiServerManager()

        # Mock the registry to return our test server
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                mock_validate.return_value = (True, "Valid")
                server = MockTestServer(
                    ServerConfig(
                        name="test", description="Test", config={"type": "mock_test"}
                    )
                )
                mock_create.return_value = server

                config = ServerConfig(
                    name="test-server",
                    description="Test server",
                    config={"type": "mock_test"},
                )

                # Mock the server.run method to avoid actual execution
                with patch.object(server, "run"):
                    result = manager.start_server(config, background=False)

                assert result is True
                assert "test-server" in manager._running_servers

    def test_start_server_background(self):
        """Test starting a server in background mode."""
        manager = MultiServerManager()

        # Mock the registry
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                mock_validate.return_value = (True, "Valid")
                server = MockTestServer(
                    ServerConfig(
                        name="test", description="Test", config={"type": "mock_test"}
                    )
                )
                mock_create.return_value = server

                config = ServerConfig(
                    name="bg-server",
                    description="Background server",
                    config={"type": "mock_test"},
                )

                # Mock threading
                with patch("threading.Thread") as mock_thread:
                    mock_thread_instance = MagicMock()
                    mock_thread.return_value = mock_thread_instance

                    result = manager.start_server(config, background=True)

                    assert result is True
                    assert "bg-server" in manager._running_servers
                    assert manager._running_servers["bg-server"].is_background is True
                    mock_thread_instance.start.assert_called_once()

    def test_start_server_already_running(self):
        """Test starting a server that's already running."""
        manager = MultiServerManager()

        config = ServerConfig(
            name="existing", description="Existing server", config={"type": "mock_test"}
        )

        # Manually add server to running servers
        server = MockTestServer(config)
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["existing"] = ServerProcess(server=server)

        result = manager.start_server(config, background=False)

        assert result is False

    def test_start_server_failure(self):
        """Test handling server startup failure."""
        manager = MultiServerManager()

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                mock_validate.return_value = (True, "Valid")
                mock_create.side_effect = Exception("Creation failed")

                config = ServerConfig(
                    name="fail-server",
                    description="Failing server",
                    config={"type": "mock_test"},
                )

                result = manager.start_server(config, background=False)

                assert result is False
                assert "fail-server" not in manager._running_servers

    def test_stop_server(self):
        """Test stopping a server."""
        manager = MultiServerManager()

        # Manually add server to running servers
        config = ServerConfig(
            name="stop-test", description="Stop test", config={"type": "mock_test"}
        )
        server = MockTestServer(config)
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["stop-test"] = ServerProcess(server=server)

        result = manager.stop_server("stop-test")

        assert result is True
        assert "stop-test" not in manager._running_servers

    def test_stop_server_not_found(self):
        """Test stopping a server that's not running."""
        manager = MultiServerManager()

        result = manager.stop_server("nonexistent")

        assert result is False

    def test_stop_server_with_background_task(self):
        """Test stopping a server with background task."""
        manager = MultiServerManager()

        # Create a mock thread
        mock_thread = MagicMock()

        # Manually add server with background thread
        config = ServerConfig(
            name="bg-stop", description="Background stop", config={"type": "mock_test"}
        )
        server = MockTestServer(config)
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["bg-stop"] = ServerProcess(
            server=server, thread=mock_thread, is_background=True
        )

        result = manager.stop_server("bg-stop")

        assert result is True
        assert "bg-stop" not in manager._running_servers

    def test_start_multiple_servers(self):
        """Test starting multiple servers."""
        manager = MultiServerManager()

        configs = [
            ServerConfig(
                name="multi-server-0",
                description="Multi 0",
                config={"type": "mock_test"},
            ),
            ServerConfig(
                name="multi-server-1",
                description="Multi 1",
                config={"type": "mock_test"},
            ),
            ServerConfig(
                name="multi-server-2",
                description="Multi 2",
                config={"type": "mock_test"},
            ),
        ]

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            # Mock validation to fail for unknown server type
            mock_validate.return_value = (False, "Unknown server type: mock_test")

            results = manager.start_multiple_servers(configs, background=True)

            assert isinstance(results, dict)
            assert len(results) == 3
            # All should fail due to validation
            for _name, result in results.items():
                assert result is False

    def test_stop_all_servers(self):
        """Test stopping all servers."""
        manager = MultiServerManager()

        # Add multiple servers manually
        for i in range(3):
            config = ServerConfig(
                name=f"stop-all-{i}",
                description=f"Stop all {i}",
                config={"type": "mock_test"},
            )
            server = MockTestServer(config)
            from lightfast_mcp.core.multi_server_manager import ServerProcess

            manager._running_servers[f"stop-all-{i}"] = ServerProcess(server=server)

        manager.shutdown_all()

        assert len(manager._running_servers) == 0

    def test_get_running_servers(self):
        """Test getting information about running servers."""
        manager = MultiServerManager()

        # Add a server
        config = ServerConfig(
            name="info-server", description="Info server", config={"type": "mock_test"}
        )
        server = MockTestServer(config)
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["info-server"] = ServerProcess(server=server)

        running_servers = manager.get_running_servers()

        assert isinstance(running_servers, dict)
        assert "info-server" in running_servers
        assert running_servers["info-server"] == server.info

    def test_get_server_status(self):
        """Test getting status of a specific server."""
        manager = MultiServerManager()

        # Add a server
        config = ServerConfig(
            name="status-server",
            description="Status server",
            config={"type": "mock_test"},
        )
        server = MockTestServer(config)
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["status-server"] = ServerProcess(server=server)

        status = manager.get_server_status("status-server")

        assert status is not None
        assert status == server.info

    def test_get_server_status_not_found(self):
        """Test getting status of non-existent server."""
        manager = MultiServerManager()

        status = manager.get_server_status("nonexistent")

        assert status is None

    def test_is_server_running(self):
        """Test checking if a server is running."""
        manager = MultiServerManager()

        # Add a server
        config = ServerConfig(
            name="running-check",
            description="Running check",
            config={"type": "mock_test"},
        )
        server = MockTestServer(config)
        # Set the server as running
        server.info.is_running = True
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["running-check"] = ServerProcess(server=server)

        assert manager.is_server_running("running-check") is True
        assert manager.is_server_running("nonexistent") is False

    def test_get_server_count(self):
        """Test getting the number of running servers."""
        manager = MultiServerManager()

        assert manager.get_server_count() == 0

        # Add servers
        for i in range(3):
            config = ServerConfig(
                name=f"count-{i}",
                description=f"Count {i}",
                config={"type": "mock_test"},
            )
            server = MockTestServer(config)
            from lightfast_mcp.core.multi_server_manager import ServerProcess

            manager._running_servers[f"count-{i}"] = ServerProcess(server=server)

        assert manager.get_server_count() == 3

    def test_get_server_urls(self):
        """Test getting server URLs."""
        manager = MultiServerManager()

        # Add a server with URL
        config = ServerConfig(
            name="url-server", description="URL server", config={"type": "mock_test"}
        )
        server = MockTestServer(config)
        server.info.url = "http://localhost:8000/mcp"
        from lightfast_mcp.core.multi_server_manager import ServerProcess

        manager._running_servers["url-server"] = ServerProcess(server=server)

        urls = manager.get_server_urls()

        assert isinstance(urls, dict)
        assert "url-server" in urls
        assert urls["url-server"] == "http://localhost:8000/mcp"

    def test_list_available_server_types(self):
        """Test listing available server types."""
        manager = MultiServerManager()

        with patch.object(
            manager.registry, "get_available_server_types"
        ) as mock_get_types:
            mock_get_types.return_value = ["blender", "mock"]

            types = manager.list_available_server_types()

            assert types == ["blender", "mock"]
            mock_get_types.assert_called_once()

    def test_get_server_type_info(self):
        """Test getting server type information."""
        manager = MultiServerManager()

        with patch.object(manager.registry, "get_server_info") as mock_get_info:
            mock_info = {"blender": {"version": "1.0.0"}, "mock": {"version": "1.0.0"}}
            mock_get_info.return_value = mock_info

            info = manager.get_server_type_info()

            assert info == mock_info
            mock_get_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all_servers(self):
        """Test performing health checks on all servers."""
        manager = MultiServerManager()

        # Add servers
        for i in range(2):
            config = ServerConfig(
                name=f"health-{i}",
                description=f"Health {i}",
                config={"type": "mock_test"},
            )
            server = MockTestServer(config)
            from lightfast_mcp.core.multi_server_manager import ServerProcess

            manager._running_servers[f"health-{i}"] = ServerProcess(server=server)

        with patch.object(
            MockTestServer, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True

            results = await manager.health_check_all()

            assert isinstance(results, dict)
            assert len(results) == 2
            assert all(result is True for result in results.values())


class TestMultiServerManagerErrorHandling:
    """Tests for MultiServerManager error handling."""

    def test_start_multiple_with_failures(self):
        """Test starting multiple servers with some failures."""
        manager = MultiServerManager()

        configs = [
            ServerConfig(
                name="success-server",
                description="Success",
                config={"type": "mock_test"},
            ),
            ServerConfig(
                name="fail-server", description="Fail", config={"type": "failing_mock"}
            ),
        ]

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            # Mock validation to fail for both (unknown server types)
            mock_validate.return_value = (False, "Unknown server type")

            results = manager.start_multiple_servers(configs, background=False)

            assert isinstance(results, dict)
            assert len(results) == 2
            # Both should fail due to validation
            assert all(result is False for result in results.values())

    def test_validation_failure_handling(self):
        """Test handling of configuration validation failures."""
        manager = MultiServerManager()

        config = ServerConfig(
            name="invalid-config", description="Invalid", config={"type": "unknown"}
        )

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            mock_validate.return_value = (False, "Invalid configuration")

            result = manager.start_server(config, background=False)

            assert result is False
            assert "invalid-config" not in manager._running_servers

    def test_graceful_shutdown_handling(self):
        """Test graceful shutdown of the manager."""
        manager = MultiServerManager()

        # Add some servers
        for i in range(2):
            config = ServerConfig(
                name=f"shutdown-{i}",
                description=f"Shutdown {i}",
                config={"type": "mock_test"},
            )
            server = MockTestServer(config)
            from lightfast_mcp.core.multi_server_manager import ServerProcess

            manager._running_servers[f"shutdown-{i}"] = ServerProcess(server=server)

        # Test shutdown
        manager.shutdown_all()

        assert len(manager._running_servers) == 0
        assert manager._shutdown_event.is_set() is True
