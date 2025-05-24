"""
Test cases for ServerRegistry and server discovery functionality.
"""

from unittest.mock import patch

import pytest

from lightfast_mcp.core.base_server import BaseServer, ServerConfig
from lightfast_mcp.core.server_registry import ServerRegistry, get_registry


class MockServerA(BaseServer):
    """Test server class A for registry testing."""

    SERVER_TYPE = "test_a"
    SERVER_VERSION = "1.0.0"

    def _register_tools(self):
        """Register test tools."""
        self.info.tools = ["test_tool_a"]


class MockServerB(BaseServer):
    """Test server class B for registry testing."""

    SERVER_TYPE = "test_b"
    SERVER_VERSION = "2.0.0"

    def _register_tools(self):
        """Register test tools."""
        self.info.tools = ["test_tool_b"]


class InvalidServerClass:
    """Invalid server class that doesn't inherit from BaseServer."""

    pass


class TestServerRegistry:
    """Tests for ServerRegistry class."""

    def test_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
        assert isinstance(registry1, ServerRegistry)

    def test_register_server_class(self):
        """Test registering a server class manually."""
        registry = ServerRegistry()

        registry.register_server_class("test_a", MockServerA)

        assert "test_a" in registry._server_classes
        assert registry._server_classes["test_a"] == MockServerA

    def test_register_duplicate_server_type(self):
        """Test that registering duplicate server types is allowed (overwrites)."""
        registry = ServerRegistry()

        registry.register_server_class("duplicate", MockServerA)
        registry.register_server_class("duplicate", MockServerB)

        # Should overwrite with the second registration
        assert registry._server_classes["duplicate"] == MockServerB

    def test_register_invalid_server_class(self):
        """Test registering an invalid server class."""
        registry = ServerRegistry()

        # Should not raise an error, just register it
        registry.register_server_class("invalid", InvalidServerClass)

        assert "invalid" in registry._server_classes
        assert registry._server_classes["invalid"] == InvalidServerClass

    def test_get_available_server_types(self):
        """Test getting list of available server types."""
        registry = get_registry()

        available_types = registry.get_available_server_types()

        assert isinstance(available_types, list)
        # Should include at least the auto-discovered servers
        assert "blender" in available_types
        assert "mock" in available_types

    def test_create_server_success(self):
        """Test successfully creating a server."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        config = ServerConfig(
            name="test", description="Test server", config={"type": "test_a"}
        )

        server = registry.create_server("test_a", config)

        assert isinstance(server, MockServerA)
        assert server.config == config
        assert "test" in registry._server_instances

    def test_create_server_unknown_type(self):
        """Test creating server with unknown type raises error."""
        registry = ServerRegistry()

        config = ServerConfig(
            name="test", description="Test server", config={"type": "unknown"}
        )

        with pytest.raises(ValueError, match="Unknown server type: unknown"):
            registry.create_server("unknown", config)

    def test_get_server_info(self):
        """Test getting server information for all types."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        info = registry.get_server_info()

        assert isinstance(info, dict)
        assert "test_a" in info
        assert info["test_a"]["class_name"] == "MockServerA"
        assert info["test_a"]["version"] == "1.0.0"

    def test_get_server_instance(self):
        """Test getting a server instance by name."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        config = ServerConfig(
            name="test-instance", description="Test server", config={"type": "test_a"}
        )
        created_server = registry.create_server("test_a", config)

        retrieved_server = registry.get_server_instance("test-instance")

        assert retrieved_server is created_server

    def test_get_server_instance_not_found(self):
        """Test getting non-existent server instance returns None."""
        registry = ServerRegistry()

        result = registry.get_server_instance("nonexistent")

        assert result is None

    def test_remove_server_instance(self):
        """Test removing a server instance."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        config = ServerConfig(
            name="test-instance", description="Test server", config={"type": "test_a"}
        )
        registry.create_server("test_a", config)

        # Verify it exists
        assert registry.get_server_instance("test-instance") is not None

        # Remove it
        result = registry.remove_server_instance("test-instance")

        assert result is True
        assert registry.get_server_instance("test-instance") is None

    def test_remove_server_instance_not_found(self):
        """Test removing non-existent server instance returns False."""
        registry = ServerRegistry()

        result = registry.remove_server_instance("nonexistent")

        assert result is False

    def test_validate_server_config_success(self):
        """Test successful server configuration validation."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        config = ServerConfig(
            name="test", description="Test server", config={"type": "test_a"}
        )

        is_valid, message = registry.validate_server_config("test_a", config)

        assert is_valid is True
        assert "valid" in message.lower()

    def test_validate_server_config_unknown_type(self):
        """Test validation with unknown server type."""
        registry = ServerRegistry()

        config = ServerConfig(
            name="test", description="Test server", config={"type": "unknown"}
        )

        is_valid, message = registry.validate_server_config("unknown", config)

        assert is_valid is False
        assert "Unknown server type" in message

    def test_validate_server_config_missing_name(self):
        """Test validation with missing server name."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        config = ServerConfig(
            name="", description="Test server", config={"type": "test_a"}
        )

        is_valid, message = registry.validate_server_config("test_a", config)

        assert is_valid is False
        assert "name is required" in message

    def test_validate_server_config_port_conflict(self):
        """Test validation with port conflict."""
        registry = ServerRegistry()
        registry.register_server_class("test_a", MockServerA)

        # Create first server with HTTP transport
        config1 = ServerConfig(
            name="server1",
            description="Server 1",
            host="localhost",
            port=8000,
            transport="http",
            config={"type": "test_a"},
        )
        registry.create_server("test_a", config1)

        # Try to create second server with same port
        config2 = ServerConfig(
            name="server2",
            description="Server 2",
            host="localhost",
            port=8000,
            transport="http",
            config={"type": "test_a"},
        )

        is_valid, message = registry.validate_server_config("test_a", config2)

        assert is_valid is False
        assert "already in use" in message


class TestServerAutoDiscovery:
    """Tests for automatic server discovery."""

    def test_discover_blender_server(self):
        """Test that Blender server is auto-discovered."""
        registry = ServerRegistry()

        # Clear and rediscover
        registry._server_classes.clear()
        registry.discover_servers()

        available_types = registry.get_available_server_types()
        assert "blender" in available_types

    def test_discover_mock_server(self):
        """Test that Mock server is auto-discovered."""
        registry = ServerRegistry()

        # Clear and rediscover
        registry._server_classes.clear()
        registry.discover_servers()

        available_types = registry.get_available_server_types()
        assert "mock" in available_types

    def test_discover_missing_module(self):
        """Test discovery with missing module."""
        registry = ServerRegistry()

        # This should not raise an error
        registry._discover_servers_in_package("nonexistent.package")

        # Should still have previously discovered servers
        available_types = registry.get_available_server_types()
        assert isinstance(available_types, list)

    def test_discover_import_error(self):
        """Test discovery with import error."""
        registry = ServerRegistry()

        # Clear servers first
        registry._server_classes.clear()

        # Mock an import error scenario
        with patch(
            "importlib.import_module", side_effect=ImportError("Mocked import error")
        ):
            registry._discover_servers_in_package("lightfast_mcp.servers")

        # Should handle gracefully
        available_types = registry.get_available_server_types()
        assert isinstance(available_types, list)

    def test_discover_missing_server_class(self):
        """Test discovery with module that has no server classes."""
        registry = ServerRegistry()

        # Create a real module-like object instead of MagicMock
        class MockModule:
            def __init__(self):
                self.SomeOtherClass = str
                self.some_function = lambda: None

        mock_module = MockModule()

        # This should not find any servers but shouldn't crash
        registry._discover_servers_in_module(mock_module)

        # Should not find any servers (this test just ensures the method doesn't crash)


class TestServerRegistryIntegration:
    """Integration tests for ServerRegistry with real servers."""

    def test_real_server_discovery(self):
        """Test that real servers are discovered correctly."""
        registry = get_registry()

        available_types = registry.get_available_server_types()

        assert "blender" in available_types
        assert "mock" in available_types
        assert len(available_types) >= 2

    def test_create_real_servers(self):
        """Test creating instances of real server types."""
        registry = get_registry()

        # Test creating a mock server
        mock_config = ServerConfig(
            name="test-mock", description="Test mock server", config={"type": "mock"}
        )

        mock_server = registry.create_server("mock", mock_config)

        assert mock_server is not None
        assert hasattr(mock_server, "SERVER_TYPE")
        assert mock_server.SERVER_TYPE == "mock"

        # Test creating a blender server
        blender_config = ServerConfig(
            name="test-blender",
            description="Test blender server",
            config={"type": "blender"},
        )

        blender_server = registry.create_server("blender", blender_config)

        assert blender_server is not None
        assert hasattr(blender_server, "SERVER_TYPE")
        assert blender_server.SERVER_TYPE == "blender"
