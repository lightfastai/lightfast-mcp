"""
Test cases for modular server implementations.
"""

from unittest.mock import patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from tools.orchestration.server_registry import get_registry
from lightfast_mcp.servers.blender.server import BlenderMCPServer
from lightfast_mcp.servers.mock.server import MockMCPServer


class TestBlenderMCPServer:
    """Tests for BlenderMCPServer implementation."""

    def test_blender_server_class_attributes(self):
        """Test BlenderMCPServer class attributes."""
        assert BlenderMCPServer.SERVER_TYPE == "blender"
        assert BlenderMCPServer.SERVER_VERSION is not None
        assert isinstance(BlenderMCPServer.REQUIRED_DEPENDENCIES, list)
        assert isinstance(BlenderMCPServer.REQUIRED_APPS, list)

    def test_blender_server_initialization(self, sample_blender_config):
        """Test BlenderMCPServer initialization."""
        server = BlenderMCPServer(sample_blender_config)

        assert server.config == sample_blender_config
        assert server.SERVER_TYPE == "blender"
        assert server.mcp is not None
        # Check that config values are properly set
        assert server.config.config.get("blender_host") == "localhost"
        assert server.config.config.get("blender_port") == 9876

    def test_blender_server_default_config(self):
        """Test BlenderMCPServer with minimal config using defaults."""
        config = ServerConfig(
            name="default-test", description="Default test", config={"type": "blender"}
        )

        server = BlenderMCPServer(config)

        assert server.config.name == "default-test"
        assert server.SERVER_TYPE == "blender"

    def test_blender_server_tools(self, sample_blender_config):
        """Test that BlenderMCPServer registers tools correctly."""
        server = BlenderMCPServer(sample_blender_config)

        tools = server.get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Should have basic blender tools
        expected_tools = ["get_state", "execute_command"]
        for tool in expected_tools:
            assert tool in tools

    def test_blender_server_setup(self, sample_blender_config):
        """Test BlenderMCPServer setup process."""
        server = BlenderMCPServer(sample_blender_config)

        # Test that tools are registered during initialization
        tools = server.info.tools
        assert len(tools) > 0

    def test_blender_server_info_property(self):
        """Test BlenderMCPServer info property."""
        config = ServerConfig(
            name="info-test",
            description="Info test",
            host="localhost",
            port=8000,
            config={"type": "blender"},
        )

        server = BlenderMCPServer(config)
        info = server.info

        assert info.config.name == "info-test"
        assert info.is_running is False
        assert info.is_healthy is False
        assert isinstance(info.tools, list)

    def test_blender_server_tool_registration(self, sample_blender_config):
        """Test that BlenderMCPServer registers tools properly."""
        server = BlenderMCPServer(sample_blender_config)

        # Tools should be registered during init
        tools = server.info.tools
        assert "get_state" in tools
        assert "execute_command" in tools


class TestMockMCPServer:
    """Tests for MockMCPServer implementation."""

    def test_mock_server_class_attributes(self):
        """Test MockMCPServer class attributes."""
        assert MockMCPServer.SERVER_TYPE == "mock"
        assert MockMCPServer.SERVER_VERSION is not None
        assert isinstance(MockMCPServer.REQUIRED_DEPENDENCIES, list)
        assert isinstance(MockMCPServer.REQUIRED_APPS, list)

    def test_mock_server_initialization(self):
        """Test MockMCPServer initialization."""
        config = ServerConfig(
            name="mock-test",
            description="Mock test",
            config={"type": "mock", "delay_seconds": 1.5},
        )

        server = MockMCPServer(config)

        assert server.config == config
        assert server.SERVER_TYPE == "mock"
        assert server.mcp is not None
        assert server.default_delay == 1.5

    def test_mock_server_default_config(self):
        """Test MockMCPServer with default configuration."""
        config = ServerConfig(
            name="default-mock", description="Default mock", config={"type": "mock"}
        )

        server = MockMCPServer(config)

        assert server.config.name == "default-mock"
        assert server.default_delay == 0.5  # Default value

    def test_mock_server_tools(self, sample_mock_config):
        """Test that MockMCPServer registers tools correctly."""
        server = MockMCPServer(sample_mock_config)

        tools = server.get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Should have mock tools
        expected_tools = ["get_server_status", "fetch_mock_data", "execute_mock_action"]
        for tool in expected_tools:
            assert tool in tools

    def test_mock_server_setup(self, sample_mock_config):
        """Test MockMCPServer setup process."""
        server = MockMCPServer(sample_mock_config)

        # Test that tools are registered during initialization
        tools = server.info.tools
        assert len(tools) > 0

    def test_mock_server_info_property(self):
        """Test MockMCPServer info property."""
        config = ServerConfig(
            name="info-test",
            description="Info test",
            config={"type": "mock"},
        )

        server = MockMCPServer(config)
        info = server.info

        assert info.config.name == "info-test"
        assert info.is_running is False
        assert info.is_healthy is False
        assert isinstance(info.tools, list)

    def test_mock_server_tool_registration(self, sample_mock_config):
        """Test that MockMCPServer registers tools properly."""
        server = MockMCPServer(sample_mock_config)

        # Tools should be registered during init
        tools = server.info.tools
        assert "get_server_status" in tools
        assert "fetch_mock_data" in tools
        assert "execute_mock_action" in tools


class TestServerIntegration:
    """Integration tests for modular servers."""

    @pytest.mark.asyncio
    async def test_blender_server_full_lifecycle(self, sample_blender_config):
        """Test BlenderMCPServer full lifecycle."""
        server = BlenderMCPServer(sample_blender_config)

        # Mock the Blender connection check to return False (no connection)
        with patch.object(server, "_check_blender_connection", return_value=False):
            # Test health check when not running (and Blender not connected)
            health = await server.health_check()
            assert health is False

        # Test that server info is properly set
        info = server.info
        assert info.config == sample_blender_config
        assert info.is_running is False

    @pytest.mark.asyncio
    async def test_mock_server_full_lifecycle(self, sample_mock_config):
        """Test MockMCPServer full lifecycle."""
        server = MockMCPServer(sample_mock_config)

        # Test health check when not running
        health = await server.health_check()
        assert health is False

        # Test that server info is properly set
        info = server.info
        assert info.config == sample_mock_config
        assert info.is_running is False

    def test_server_registry_integration(self):
        """Test that servers work with the registry."""
        registry = get_registry()

        # Test creating servers through registry
        blender_config = ServerConfig(
            name="registry-blender",
            description="Registry test blender",
            config={"type": "blender"},
        )

        mock_config = ServerConfig(
            name="registry-mock",
            description="Registry test mock",
            config={"type": "mock"},
        )

        blender_server = registry.create_server("blender", blender_config)
        mock_server = registry.create_server("mock", mock_config)

        assert isinstance(blender_server, BlenderMCPServer)
        assert isinstance(mock_server, MockMCPServer)

        # Test that servers are registered in the registry
        assert registry.get_server_instance("registry-blender") is blender_server
        assert registry.get_server_instance("registry-mock") is mock_server


class TestServerConfigValidation:
    """Tests for server configuration validation."""

    def test_blender_server_invalid_port(self):
        """Test BlenderMCPServer with invalid port configuration."""
        config = ServerConfig(
            name="invalid-port",
            description="Invalid port test",
            config={"type": "blender", "blender_port": "not_a_number"},
        )

        # Should create server but use defaults for invalid values
        server = BlenderMCPServer(config)
        assert (
            server.config.config.get("blender_port") == "not_a_number"
        )  # Stored as-is

    def test_mock_server_invalid_delay(self):
        """Test MockMCPServer with invalid delay configuration."""
        config = ServerConfig(
            name="invalid-delay",
            description="Invalid delay test",
            config={"type": "mock", "delay_seconds": "not_a_number"},
        )

        # Should create server and use default for invalid delay
        server = MockMCPServer(config)
        assert server.default_delay == 0.5  # Should fallback to default

    def test_server_config_edge_cases(self):
        """Test servers with edge case configurations."""
        # Test with empty config
        empty_config = ServerConfig(
            name="empty",
            description="Empty config",
            config={"type": "mock"},
        )

        server = MockMCPServer(empty_config)
        assert server.default_delay == 0.5  # Default

        # Test with None values
        none_config = ServerConfig(
            name="none-values",
            description="None values",
            config={"type": "mock", "delay_seconds": None},
        )

        server = MockMCPServer(none_config)
        assert server.default_delay == 0.5  # Default

    def test_server_string_representations(self):
        """Test string representations of servers."""
        blender_config = ServerConfig(
            name="str-test-blender",
            description="String test blender",
            config={"type": "blender"},
        )

        mock_config = ServerConfig(
            name="str-test-mock",
            description="String test mock",
            config={"type": "mock"},
        )

        blender_server = BlenderMCPServer(blender_config)
        mock_server = MockMCPServer(mock_config)

        assert "BlenderMCPServer" in str(blender_server)
        assert "str-test-blender" in str(blender_server)

        assert "MockMCPServer" in str(mock_server)
        assert "str-test-mock" in str(mock_server)

        assert "blender" in repr(blender_server)
        assert "mock" in repr(mock_server)
