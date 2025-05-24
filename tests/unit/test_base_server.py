"""
Test cases for BaseServer and related classes.
"""

from unittest.mock import AsyncMock, patch

import pytest

from lightfast_mcp.core.base_server import BaseServer, ServerConfig, ServerInfo


class TestServerConfig:
    """Tests for ServerConfig class."""

    def test_server_config_creation(self):
        """Test creating a ServerConfig with all parameters."""
        config = ServerConfig(
            name="test-server",
            description="A test server",
            version="1.0.0",
            host="localhost",
            port=8000,
            transport="stdio",
            path="/mcp",
            config={"type": "test", "param": "value"},
            dependencies=["pytest"],
            required_apps=["TestApp"],
        )

        assert config.name == "test-server"
        assert config.description == "A test server"
        assert config.version == "1.0.0"
        assert config.host == "localhost"
        assert config.port == 8000
        assert config.transport == "stdio"
        assert config.path == "/mcp"
        assert config.config == {"type": "test", "param": "value"}
        assert config.dependencies == ["pytest"]
        assert config.required_apps == ["TestApp"]

    def test_server_config_minimal(self):
        """Test creating a ServerConfig with minimal parameters."""
        config = ServerConfig(name="minimal", description="Minimal config")

        assert config.name == "minimal"
        assert config.description == "Minimal config"
        assert config.version == "1.0.0"  # Default
        assert config.host == "localhost"  # Default
        assert config.port == 8000  # Default
        assert config.transport == "stdio"  # Default
        assert config.path == "/mcp"  # Default
        assert config.config == {}  # Default
        assert config.dependencies == []  # Default
        assert config.required_apps == []  # Default


class TestServerInfo:
    """Tests for ServerInfo class."""

    def test_server_info_creation(self, sample_server_config):
        """Test creating ServerInfo."""
        info = ServerInfo(
            config=sample_server_config,
            is_running=True,
            is_healthy=True,
            last_health_check=123.456,
            error_message="",
            tools=["tool1", "tool2"],
            url="http://localhost:8000/mcp",
        )

        assert info.config == sample_server_config
        assert info.is_running is True
        assert info.is_healthy is True
        assert info.last_health_check == 123.456
        assert info.error_message == ""
        assert info.tools == ["tool1", "tool2"]
        assert info.url == "http://localhost:8000/mcp"


class ConcreteTestServer(BaseServer):
    """Concrete test server implementation."""

    SERVER_TYPE = "test"
    SERVER_VERSION = "1.0.0"

    def _register_tools(self):
        """Register test tools."""
        self.info.tools = ["test_tool"]


class FailingTestServer(BaseServer):
    """Test server that fails during startup."""

    SERVER_TYPE = "failing"
    SERVER_VERSION = "1.0.0"

    def _register_tools(self):
        """Register tools."""
        self.info.tools = ["failing_tool"]

    async def _on_startup(self):
        """Fail during startup."""
        raise RuntimeError("Startup failed")


class TestBaseServer:
    """Tests for BaseServer class."""

    def test_base_server_init(self, sample_server_config):
        """Test BaseServer initialization."""
        server = ConcreteTestServer(sample_server_config)

        assert server.config == sample_server_config
        assert server.mcp is not None
        assert server.info.config == sample_server_config
        assert server.info.is_running is False
        assert server.info.is_healthy is False

    def test_base_server_info_property(self, sample_server_config):
        """Test BaseServer info property."""
        server = ConcreteTestServer(sample_server_config)
        info = server.info

        assert isinstance(info, ServerInfo)
        assert info.config == sample_server_config

    @pytest.mark.asyncio
    async def test_health_check_stopped(self, sample_server_config):
        """Test health check when server is stopped."""
        server = ConcreteTestServer(sample_server_config)

        # Server is not running by default
        result = await server.health_check()
        assert result is False
        assert server.info.is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_running(self, sample_server_config):
        """Test health check when server is running."""
        server = ConcreteTestServer(sample_server_config)

        # Manually set server as running for test
        server.info.is_running = True

        result = await server.health_check()
        assert result is True
        assert server.info.is_healthy is True

    @pytest.mark.asyncio
    async def test_startup_lifecycle(self, sample_server_config):
        """Test server startup lifecycle using lifespan context."""
        server = ConcreteTestServer(sample_server_config)

        # Mock the _on_startup method to avoid actual startup logic
        with patch.object(server, "_on_startup", new_callable=AsyncMock) as mock_startup:
            with patch.object(server, "_on_shutdown", new_callable=AsyncMock) as mock_shutdown:
                # Test the lifespan context manager
                async with server._server_lifespan(server.mcp):
                    assert server.info.is_running is True
                    assert server.info.is_healthy is True
                    mock_startup.assert_called_once()

                # After context, shutdown should have been called
                mock_shutdown.assert_called_once()
                assert server.info.is_running is False

    @pytest.mark.asyncio
    async def test_shutdown_lifecycle(self, sample_server_config):
        """Test server shutdown lifecycle."""
        server = ConcreteTestServer(sample_server_config)

        # Mock shutdown method
        with patch.object(server, "_on_shutdown", new_callable=AsyncMock) as mock_shutdown:
            # Manually set server as running
            server.info.is_running = True

            # Test the lifespan context manager
            async with server._server_lifespan(server.mcp):
                pass

            # Verify shutdown was called
            mock_shutdown.assert_called_once()
            assert server.info.is_running is False

    @pytest.mark.asyncio
    async def test_startup_already_running(self, sample_server_config):
        """Test behavior when server is already running."""
        server = ConcreteTestServer(sample_server_config)

        # Set server as already running
        server.info.is_running = True

        # Health check should still work
        result = await server.health_check()
        assert result is True

    def test_run_sync_mode(self, sample_server_config):
        """Test run method validation."""
        server = ConcreteTestServer(sample_server_config)

        # Test that run raises error with unsupported transport
        server.config.transport = "invalid"
        with pytest.raises(ValueError, match="Unsupported transport"):
            server.run()

    def test_get_tools(self, sample_server_config):
        """Test get_tools method."""
        server = ConcreteTestServer(sample_server_config)
        tools = server.get_tools()
        assert tools == ["test_tool"]

    def test_create_from_config(self, sample_server_config):
        """Test creating server from config."""
        server = ConcreteTestServer.create_from_config(sample_server_config)
        assert isinstance(server, ConcreteTestServer)
        assert server.config == sample_server_config

    def test_string_representation(self, sample_server_config):
        """Test string representation of server."""
        server = ConcreteTestServer(sample_server_config)
        assert str(server) == f"ConcreteTestServer({sample_server_config.name})"
        assert repr(server) == f"ConcreteTestServer(name='{sample_server_config.name}', type='test')"


class TestBaseServerErrorHandling:
    """Tests for BaseServer error handling."""

    @pytest.mark.asyncio
    async def test_startup_failure_handling(self, sample_server_config):
        """Test handling of startup failures."""
        server = FailingTestServer(sample_server_config)

        # Test that startup failure is handled properly
        with pytest.raises(RuntimeError, match="Startup failed"):
            async with server._server_lifespan(server.mcp):
                pass

        # Server should not be marked as healthy after failure
        assert server.info.is_healthy is False
        assert "Startup failed" in server.info.error_message

    @pytest.mark.asyncio
    async def test_health_check_exception(self, sample_server_config):
        """Test health check with exception."""
        server = ConcreteTestServer(sample_server_config)

        # Mock _perform_health_check to raise exception
        with patch.object(server, "_perform_health_check", side_effect=Exception("Health check failed")):
            result = await server.health_check()

            assert result is False
            assert server.info.is_healthy is False
            assert "Health check failed" in server.info.error_message

    @pytest.mark.asyncio
    async def test_dependency_check(self, sample_server_config):
        """Test dependency checking."""
        server = ConcreteTestServer(sample_server_config)

        # Test successful dependency check
        result = await server._check_dependency("sys")  # sys is always available
        assert result is True

        # Test failed dependency check
        result = await server._check_dependency("nonexistent_module")
        assert result is False
