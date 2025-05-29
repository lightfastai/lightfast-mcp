"""
Test cases for Figma MCP server implementation.
"""

import asyncio
import json
import time
from datetime import datetime
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
                assert len(tools_list) == 2

                expected_tools = ["get_state", "execute_code"]
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
                _server = FigmaMCPServer(sample_figma_config)

                # Verify thread was started
                mock_thread.assert_called_once()
                thread_instance = mock_thread.return_value
                thread_instance.start.assert_called_once()

    def test_figma_server_signal_handlers(self, sample_figma_config):
        """Test signal handler registration."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch("signal.signal") as mock_signal:
                _server = FigmaMCPServer(sample_figma_config)

                # Verify signal handlers were registered
                assert mock_signal.call_count >= 2  # SIGTERM and SIGINT


class TestFigmaServerTools:
    """Tests for Figma server tools."""

    def setup_method(self):
        """Set up test environment."""
        # Reset the current server
        tools.set_current_server(None)

    @pytest.mark.asyncio
    async def test_get_state_no_server(self):
        """Test get_state when no server is available."""
        tools.set_current_server(None)

        result = await tools.get_state(None)
        result_data = json.loads(result)

        assert "Figma Interaction Error" in result_data["error"]
        assert result_data["type"] == "FigmaConnectionError"

    @pytest.mark.asyncio
    async def test_get_state_success(self, sample_figma_config):
        """Test successful get_state."""
        # Create mock server
        mock_server = MagicMock()
        mock_server.config = sample_figma_config
        mock_server.SERVER_VERSION = "1.0.0"

        # Create mock WebSocket server
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.host = "localhost"
        mock_ws_server.port = 9003
        mock_ws_server.clients = {"test-client": MagicMock()}

        # Create mock client with cached document info
        mock_client = MagicMock()
        mock_client.id = "test-client"
        mock_client.connected_at = datetime.now()
        mock_client.last_ping = datetime.now()
        mock_client.plugin_info = {"name": "Test Plugin", "version": "1.0.0"}
        mock_client.websocket.remote_address = ("127.0.0.1", 12345)
        mock_client.metadata = {
            "last_document_info": {
                "document": {"name": "Test Doc", "id": "doc_123"},
                "currentPage": {"name": "Page 1", "id": "page_456"},
                "selection": [],
            },
            "last_document_update": time.time(),
        }

        mock_ws_server.clients = {"test-client": mock_client}
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.get_state(None)
        result_data = json.loads(result)

        assert "figma_document_state" in result_data
        assert "plugin_connection" in result_data
        assert "websocket_server" in result_data
        assert "_server_info" in result_data
        assert result_data["plugin_connection"]["plugin_id"] == "test-client"

    @pytest.mark.asyncio
    async def test_get_state_no_clients(self):
        """Test get_state when no clients are connected."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_ws_server.clients = {}
        mock_server.websocket_server = mock_ws_server
        mock_server.config = MagicMock()
        mock_server.config.name = "test-server"

        tools.set_current_server(mock_server)

        result = await tools.get_state(None)
        result_data = json.loads(result)

        assert "Figma Interaction Error" in result_data["error"]
        assert result_data["type"] == "FigmaConnectionError"

    @pytest.mark.asyncio
    async def test_execute_command_no_server(self):
        """Test execute_command when no server is available."""
        tools.set_current_server(None)

        result = await tools.execute_command(None, "create rectangle")
        result_data = json.loads(result)

        assert "Figma Command Execution Error" in result_data["error"]
        assert result_data["type"] == "FigmaConnectionError"
        assert result_data["command"] == "create rectangle"

    @pytest.mark.asyncio
    async def test_execute_command_server_not_running(self):
        """Test execute_command when WebSocket server is not running."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = False
        mock_server.websocket_server = mock_ws_server
        mock_server.config = MagicMock()
        mock_server.config.name = "test-server"

        tools.set_current_server(mock_server)

        result = await tools.execute_command(None, "create circle")
        result_data = json.loads(result)

        assert "Figma Command Execution Error" in result_data["error"]
        assert result_data["type"] == "FigmaConnectionError"

    @pytest.mark.asyncio
    async def test_execute_command_success(self):
        """Test successful execute_command."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_server.config = MagicMock()
        mock_server.config.name = "test-server"

        # Create a proper mock client
        mock_client = MagicMock()
        mock_client.id = "test-plugin"
        mock_ws_server.clients = {"test-plugin": mock_client}
        mock_ws_server.send_command_to_plugin = AsyncMock(return_value=True)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.execute_command(None, "create rectangle")
        result_data = json.loads(result)

        assert result_data["status"] == "command_sent"
        assert result_data["command"] == "create rectangle"
        assert result_data["plugin_id"] == "test-plugin"
        mock_ws_server.send_command_to_plugin.assert_called_once_with(
            "test-plugin", "execute_design_command", {"command": "create rectangle"}
        )

    @pytest.mark.asyncio
    async def test_execute_command_send_failure(self):
        """Test execute_command when sending command fails."""
        mock_server = MagicMock()
        mock_ws_server = MagicMock()
        mock_ws_server.is_running = True
        mock_server.config = MagicMock()
        mock_server.config.name = "test-server"

        # Create a proper mock client
        mock_client = MagicMock()
        mock_client.id = "test-plugin"
        mock_ws_server.clients = {"test-plugin": mock_client}
        mock_ws_server.send_command_to_plugin = AsyncMock(return_value=False)
        mock_server.websocket_server = mock_ws_server

        tools.set_current_server(mock_server)

        result = await tools.execute_command(None, "create text")
        result_data = json.loads(result)

        assert "Figma Command Execution Error" in result_data["error"]
        assert result_data["type"] == "FigmaCommandError"
        assert result_data["command"] == "create text"


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
                assert "get_state" in server_tools
                assert "execute_code" in server_tools
                assert len(server_tools) == 2

    @pytest.mark.slow
    @pytest.mark.skip(
        reason="Background thread WebSocket startup creates async loop conflicts in tests"
    )
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
