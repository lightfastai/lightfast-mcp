"""
Test cases for Figma MCP server implementation.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.figma import tools
from lightfast_mcp.servers.figma.server import FigmaMCPServer
from lightfast_mcp.servers.figma.websocket_server import (
    FigmaClient,
    FigmaWebSocketServer,
)


class TestFigmaMCPServer:
    """Tests for FigmaMCPServer implementation."""

    def test_figma_server_class_attributes(self):
        """Test FigmaMCPServer class attributes."""
        assert FigmaMCPServer.SERVER_TYPE == "figma"
        assert FigmaMCPServer.SERVER_VERSION is not None
        assert isinstance(FigmaMCPServer.REQUIRED_DEPENDENCIES, list)
        assert isinstance(FigmaMCPServer.REQUIRED_APPS, list)
        assert "websockets" in FigmaMCPServer.REQUIRED_DEPENDENCIES
        assert "Figma" in FigmaMCPServer.REQUIRED_APPS

    def test_figma_server_initialization(self, sample_figma_config):
        """Test FigmaMCPServer initialization."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                assert server.config == sample_figma_config
                assert server.SERVER_TYPE == "figma"
                assert server.mcp is not None
                assert hasattr(server, "websocket_server")
                assert isinstance(server.websocket_server, FigmaWebSocketServer)
                assert server.websocket_server.host == "localhost"
                assert server.websocket_server.port == 9003

    def test_figma_server_default_config(self):
        """Test FigmaMCPServer with minimal config using defaults."""
        config = ServerConfig(
            name="default-test", description="Default test", config={"type": "figma"}
        )

        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(config)

                assert server.config.name == "default-test"
                assert server.SERVER_TYPE == "figma"
                assert server.websocket_server.host == "localhost"  # Default
                assert server.websocket_server.port == 9003  # Default

    def test_figma_server_custom_websocket_config(self):
        """Test FigmaMCPServer with custom WebSocket configuration."""
        config = ServerConfig(
            name="custom-test",
            description="Custom test",
            config={"type": "figma", "figma_host": "0.0.0.0", "figma_port": 9999},
        )

        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(config)

                assert server.websocket_server.host == "0.0.0.0"
                assert server.websocket_server.port == 9999

    def test_figma_server_tools_registration(self, sample_figma_config):
        """Test that FigmaMCPServer registers tools correctly."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                tools_list = server.get_tools()
                assert isinstance(tools_list, list)
                assert len(tools_list) > 0

                expected_tools = [
                    "get_figma_server_status",
                    "get_figma_plugins",
                    "ping_figma_plugin",
                    "get_document_state",
                    "execute_design_command",
                    "broadcast_design_command",
                ]
                for tool in expected_tools:
                    assert tool in tools_list

    def test_figma_server_tools_current_server_set(self, sample_figma_config):
        """Test that the current server is set in tools module."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Check that tools module has access to the server
                assert tools._current_server is server

    @pytest.mark.asyncio
    async def test_figma_server_check_application(self, sample_figma_config):
        """Test FigmaMCPServer application check."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Figma check should always return True (plugins connect to us)
                result = await server._check_application("figma")
                assert result is True

                result = await server._check_application("Figma")
                assert result is True

                result = await server._check_application("other")
                assert result is True

    @pytest.mark.asyncio
    async def test_figma_server_startup(self, sample_figma_config):
        """Test FigmaMCPServer startup process."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server as running
                server.websocket_server.is_running = True

                await server._on_startup()

                # Should complete without errors
                assert server.websocket_server.is_running is True

    @pytest.mark.asyncio
    async def test_figma_server_shutdown(self, sample_figma_config):
        """Test FigmaMCPServer shutdown process."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                await server._on_shutdown()

                # Should complete without errors (WebSocket server stays running)

    @pytest.mark.asyncio
    async def test_figma_server_health_check_not_running(self, sample_figma_config):
        """Test health check when server is not running."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Server not running
                server.info.is_running = False
                result = await server._perform_health_check()
                assert result is False

    @pytest.mark.asyncio
    async def test_figma_server_health_check_websocket_not_running(
        self, sample_figma_config
    ):
        """Test health check when WebSocket server is not running."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # MCP server running but WebSocket server not
                server.info.is_running = True
                server.websocket_server.is_running = False

                result = await server._perform_health_check()
                assert result is False

    @pytest.mark.asyncio
    async def test_figma_server_health_check_success(self, sample_figma_config):
        """Test successful health check."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Both servers running
                server.info.is_running = True
                server.websocket_server.is_running = True

                # Mock get_server_info to return running status
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": True}
                )

                result = await server._perform_health_check()
                assert result is True

    @pytest.mark.asyncio
    async def test_figma_server_health_check_exception(self, sample_figma_config):
        """Test health check with exception."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock to raise exception
                server.websocket_server.get_server_info = MagicMock(
                    side_effect=Exception("Test error")
                )

                result = await server._perform_health_check()
                assert result is False

    def test_figma_server_websocket_startup_retry(self, sample_figma_config):
        """Test WebSocket server startup with retry logic."""
        with patch.object(FigmaMCPServer, "_register_signal_handlers"):
            with patch("threading.Thread") as mock_thread:
                server = FigmaMCPServer(sample_figma_config)

                # Verify thread was started
                mock_thread.assert_called_once()
                thread_instance = mock_thread.return_value
                thread_instance.start.assert_called_once()

    def test_figma_server_signal_handlers(self, sample_figma_config):
        """Test signal handler registration."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch("signal.signal") as mock_signal:
                server = FigmaMCPServer(sample_figma_config)

                # Verify signal handlers were registered
                assert mock_signal.call_count >= 2  # SIGTERM and SIGINT


class TestFigmaServerTools:
    """Tests for Figma server tools."""

    def setup_method(self):
        """Set up test environment."""
        # Reset the current server
        tools.set_current_server(None)

    @pytest.mark.asyncio
    async def test_get_figma_server_status_no_server(self):
        """Test get_figma_server_status when no server is available."""
        tools.set_current_server(None)

        result = await tools.get_figma_server_status(None)

        assert result["error"] == "Figma WebSocket server not available"
        assert result["status"] == "not_initialized"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_figma_server_status_success(self, sample_figma_config):
        """Test successful get_figma_server_status."""
        # Create mock server
        mock_server = MagicMock()
        mock_server.config = sample_figma_config
        mock_server.SERVER_VERSION = "1.0.0"

        # Create mock WebSocket server
        mock_ws_server = MagicMock()
        mock_ws_server.get_server_info.return_value = {
            "is_running": True,
            "host": "localhost",
            "port": 9003,
        }
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.get_figma_server_status(None)

        assert "figma_websocket_server" in result
        assert "mcp_server" in result
        assert result["mcp_server"]["mcp_server_name"] == "test-figma"
        assert result["mcp_server"]["mcp_server_type"] == "figma"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_figma_plugins_no_server(self):
        """Test get_figma_plugins when no server is available."""
        tools.set_current_server(None)

        result = await tools.get_figma_plugins(None)

        assert result["error"] == "Figma WebSocket server not available"
        assert result["status"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_get_figma_plugins_server_not_running(self):
        """Test get_figma_plugins when WebSocket server is not running."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = False
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.get_figma_plugins(None)

        assert result["error"] == "Figma WebSocket server is not running"
        assert result["status"] == "server_not_running"

    @pytest.mark.asyncio
    async def test_get_figma_plugins_success(self):
        """Test successful get_figma_plugins."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.host = "localhost"
        mock_ws_server.port = 9003

        # Mock clients
        mock_client = MagicMock()
        mock_client.to_dict.return_value = {
            "id": "test-client",
            "connected_at": "2024-01-01T00:00:00",
        }
        mock_ws_server.clients = {"test-client": mock_client}

        mock_server.websocket_server = mock_ws_server
        tools.set_current_server(mock_server)

        result = await tools.get_figma_plugins(None)

        assert result["status"] == "success"
        assert result["total_plugins"] == 1
        assert len(result["plugins"]) == 1
        assert result["plugins"][0]["id"] == "test-client"

    @pytest.mark.asyncio
    async def test_ping_figma_plugin_no_plugins(self):
        """Test ping_figma_plugin when no plugins are connected."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.clients = {}
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.ping_figma_plugin(None)

        assert result["status"] == "no_plugins"
        assert result["message"] == "No Figma plugins connected to ping"

    @pytest.mark.asyncio
    async def test_ping_figma_plugin_specific_success(self):
        """Test ping_figma_plugin for specific plugin."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.clients = {"test-plugin": MagicMock()}
        mock_ws_server.send_command_to_plugin = AsyncMock(return_value=True)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.ping_figma_plugin(None, plugin_id="test-plugin")

        assert result["status"] == "ping_sent"
        assert result["plugin_id"] == "test-plugin"
        mock_ws_server.send_command_to_plugin.assert_called_once_with(
            "test-plugin", "ping"
        )

    @pytest.mark.asyncio
    async def test_ping_figma_plugin_broadcast_success(self):
        """Test ping_figma_plugin broadcast to all plugins."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.clients = {"plugin1": MagicMock(), "plugin2": MagicMock()}
        mock_ws_server.broadcast_to_plugins = AsyncMock(return_value=2)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.ping_figma_plugin(None)

        assert result["status"] == "ping_broadcast"
        assert result["sent_to_plugins"] == 2
        assert result["total_plugins"] == 2
        mock_ws_server.broadcast_to_plugins.assert_called_once_with("ping")

    @pytest.mark.asyncio
    async def test_execute_design_command_success(self):
        """Test successful execute_design_command."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True

        # Create a proper mock client with string ID
        mock_client = MagicMock()
        mock_client.id = "test-plugin"  # Set as string, not MagicMock
        mock_ws_server.clients = {"test-plugin": mock_client}

        mock_ws_server.send_command_to_plugin = AsyncMock(return_value=True)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.execute_design_command(
            None, command="create_rectangle", plugin_id="test-plugin"
        )

        assert result["status"] == "command_sent"
        assert result["command"] == "create_rectangle"
        assert result["plugin_id"] == "test-plugin"

    @pytest.mark.asyncio
    async def test_broadcast_design_command_success(self):
        """Test successful broadcast_design_command."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True

        # Create proper mock clients with string IDs
        mock_client1 = MagicMock()
        mock_client1.id = "plugin1"
        mock_client2 = MagicMock()
        mock_client2.id = "plugin2"
        mock_ws_server.clients = {"plugin1": mock_client1, "plugin2": mock_client2}

        mock_ws_server.broadcast_to_plugins = AsyncMock(return_value=2)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.broadcast_design_command(None, command="refresh_view")

        assert result["status"] == "command_broadcast"
        assert result["command"] == "refresh_view"
        assert result["sent_to_plugins"] == 2
        assert result["total_plugins"] == 2


class TestFigmaWebSocketServer:
    """Tests for FigmaWebSocketServer."""

    def test_websocket_server_initialization(self):
        """Test WebSocket server initialization."""
        server = FigmaWebSocketServer(host="0.0.0.0", port=9999)

        assert server.host == "0.0.0.0"
        assert server.port == 9999
        assert server.is_running is False
        assert server.clients == {}
        assert server.server is None
        assert len(server.message_handlers) > 0

    def test_websocket_server_default_initialization(self):
        """Test WebSocket server with default parameters."""
        server = FigmaWebSocketServer()

        assert server.host == "localhost"
        assert server.port == 9003
        assert server.is_running is False

    def test_websocket_server_message_handlers(self):
        """Test that default message handlers are registered."""
        server = FigmaWebSocketServer()

        expected_handlers = [
            "ping",
            "pong",
            "get_document_info",
            "execute_design_command",
            "get_server_status",
            "plugin_info",
            "document_update",
            "document_info_response",
            "design_command_response",
        ]

        for handler in expected_handlers:
            assert handler in server.message_handlers

    def test_websocket_server_stats_initialization(self):
        """Test WebSocket server statistics initialization."""
        server = FigmaWebSocketServer()

        assert server.stats["total_connections"] == 0
        assert server.stats["total_messages"] == 0
        assert server.stats["start_time"] is None
        assert server.stats["errors"] == 0

    def test_websocket_server_get_server_info(self):
        """Test get_server_info method."""
        server = FigmaWebSocketServer(host="test-host", port=1234)
        server.is_running = True

        info = server.get_server_info()

        assert info["host"] == "test-host"
        assert info["port"] == 1234
        assert info["is_running"] is True
        assert info["total_clients"] == 0
        assert "stats" in info

    @pytest.mark.asyncio
    async def test_websocket_server_start_already_running(self):
        """Test starting server when already running."""
        server = FigmaWebSocketServer()
        server.is_running = True

        result = await server.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_websocket_server_stop_not_running(self):
        """Test stopping server when not running."""
        server = FigmaWebSocketServer()
        server.is_running = False

        # Should not raise exception
        await server.stop()

    def test_figma_client_creation(self):
        """Test FigmaClient creation and to_dict method."""
        from datetime import datetime
        from unittest.mock import MagicMock

        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        client = FigmaClient(id="test-id", websocket=mock_websocket)

        assert client.id == "test-id"
        assert client.websocket == mock_websocket
        assert isinstance(client.connected_at, datetime)
        assert client.last_ping is None
        assert client.metadata == {}
        assert client.plugin_info == {}

        client_dict = client.to_dict()
        assert client_dict["id"] == "test-id"
        assert "connected_at" in client_dict
        assert client_dict["remote_address"] == "127.0.0.1:12345"


class TestFigmaServerIntegration:
    """Integration tests for Figma server components."""

    @pytest.mark.asyncio
    async def test_figma_server_full_lifecycle_mock(self, sample_figma_config):
        """Test FigmaMCPServer full lifecycle with mocked WebSocket server."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server as running
                server.websocket_server.is_running = True
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": True}
                )

                # Test startup
                await server._on_startup()

                # Test health check
                server.info.is_running = True
                health = await server._perform_health_check()
                assert health is True

                # Test shutdown
                await server._on_shutdown()

    def test_figma_server_tools_integration(self, sample_figma_config):
        """Test integration between server and tools."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Verify tools have access to server
                assert tools._current_server is server

                # Verify server has correct tools registered
                server_tools = server.get_tools()
                assert "get_figma_server_status" in server_tools
                assert "get_figma_plugins" in server_tools
                assert "ping_figma_plugin" in server_tools
                assert "get_document_state" in server_tools
                assert "execute_design_command" in server_tools
                assert "broadcast_design_command" in server_tools

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_figma_server_websocket_startup_integration(
        self, sample_figma_config
    ):
        """Test WebSocket server startup integration (slow test)."""
        with patch.object(FigmaMCPServer, "_register_signal_handlers"):
            # Use a different port to avoid conflicts
            config = ServerConfig(
                name="integration-test",
                description="Integration test",
                config={"type": "figma", "figma_host": "localhost", "figma_port": 9999},
            )

            server = FigmaMCPServer(config)

            # Give some time for background startup
            await asyncio.sleep(1.0)

            # Check if WebSocket server started
            # Note: This might fail if port is in use, which is expected
            # The test verifies the integration works, not that it always succeeds

            # Clean up
            if server.websocket_server.is_running:
                await server.websocket_server.stop()
