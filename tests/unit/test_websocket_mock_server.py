"""
Unit tests for the WebSocket Mock MCP server.

Tests cover:
- WebSocket server functionality
- MCP server integration
- Tool implementations
- Error handling
- Configuration management
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.websocket_mock import tools
from lightfast_mcp.servers.websocket_mock.server import WebSocketMockMCPServer
from lightfast_mcp.servers.websocket_mock.websocket_server import (
    WebSocketClient,
    WebSocketMockServer,
)


class TestWebSocketMockServer:
    """Test the WebSocket server component."""

    @pytest.fixture
    def websocket_server(self):
        """Create a WebSocket server instance for testing."""
        return WebSocketMockServer(host="localhost", port=9999)

    def test_websocket_server_initialization(self, websocket_server):
        """Test WebSocket server initialization."""
        assert websocket_server.host == "localhost"
        assert websocket_server.port == 9999
        assert not websocket_server.is_running
        assert websocket_server.clients == {}
        assert websocket_server.server is None
        assert "ping" in websocket_server.message_handlers
        assert "echo" in websocket_server.message_handlers

    def test_websocket_server_get_info(self, websocket_server):
        """Test getting server information."""
        info = websocket_server.get_server_info()

        assert info["host"] == "localhost"
        assert info["port"] == 9999
        assert info["is_running"] is False
        assert info["url"] == "ws://localhost:9999"
        assert info["clients_connected"] == 0
        assert "capabilities" in info
        assert "ping" in info["capabilities"]

    @pytest.mark.asyncio
    async def test_websocket_server_start_stop(self, websocket_server):
        """Test starting and stopping the WebSocket server."""
        # Mock the websockets.serve function
        with patch(
            "lightfast_mcp.servers.websocket_mock.websocket_server.websockets.serve"
        ) as mock_serve:
            mock_server = AsyncMock()

            # Make the mock_serve return an awaitable
            async def mock_serve_func(*args, **kwargs):
                return mock_server

            mock_serve.side_effect = mock_serve_func

            # Test start
            success = await websocket_server.start()
            assert success is True
            assert websocket_server.is_running is True
            assert websocket_server.server is mock_server

            # Test stop
            await websocket_server.stop()
            assert websocket_server.is_running is False
            mock_server.close.assert_called_once()
            mock_server.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_server_start_already_running(self, websocket_server):
        """Test starting server when already running."""
        websocket_server.is_running = True

        success = await websocket_server.start()
        assert success is True  # Should return True for already running

    @pytest.mark.asyncio
    async def test_websocket_server_stop_not_running(self, websocket_server):
        """Test stopping server when not running."""
        # Should not raise an exception
        await websocket_server.stop()
        assert websocket_server.is_running is False

    @pytest.mark.asyncio
    async def test_websocket_server_start_failure(self, websocket_server):
        """Test WebSocket server start failure."""
        with patch(
            "lightfast_mcp.servers.websocket_mock.websocket_server.websockets.serve"
        ) as mock_serve:
            mock_serve.side_effect = Exception("Port already in use")

            success = await websocket_server.start()
            assert success is False
            assert websocket_server.is_running is False

    @pytest.mark.asyncio
    async def test_message_handlers(self, websocket_server):
        """Test message handlers."""
        # Create a mock client
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        client = WebSocketClient(id="test_client", websocket=mock_websocket)

        # Test ping handler
        ping_response = await websocket_server._handle_ping(client, {"type": "ping"})
        assert ping_response["type"] == "pong"
        assert ping_response["client_id"] == "test_client"
        assert "timestamp" in ping_response

        # Test echo handler
        echo_data = {"type": "echo", "message": "test"}
        echo_response = await websocket_server._handle_echo(client, echo_data)
        assert echo_response["type"] == "echo_response"
        assert echo_response["client_id"] == "test_client"
        assert echo_response["original_message"] == echo_data

        # Test get_stats handler
        stats_response = await websocket_server._handle_get_stats(
            client, {"type": "get_stats"}
        )
        assert stats_response["type"] == "server_stats"
        assert stats_response["client_id"] == "test_client"
        assert "stats" in stats_response

    @pytest.mark.asyncio
    async def test_simulate_delay_handler(self, websocket_server):
        """Test simulate delay handler."""
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        client = WebSocketClient(id="test_client", websocket=mock_websocket)

        start_time = time.time()
        response = await websocket_server._handle_simulate_delay(
            client, {"type": "simulate_delay", "delay_seconds": 0.1}
        )
        end_time = time.time()

        assert response["type"] == "delay_completed"
        assert response["delay_seconds"] == 0.1
        assert (end_time - start_time) >= 0.1  # Should have actually delayed

    @pytest.mark.asyncio
    async def test_error_test_handler(self, websocket_server):
        """Test error test handler."""
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)
        client = WebSocketClient(id="test_client", websocket=mock_websocket)

        # Test generic error
        response = await websocket_server._handle_error_test(
            client, {"type": "error_test", "error_type": "generic"}
        )
        assert response["type"] == "error_test_response"
        assert response["error_type"] == "generic"

        # Test exception error
        with pytest.raises(Exception, match="Simulated exception for testing"):
            await websocket_server._handle_error_test(
                client, {"type": "error_test", "error_type": "exception"}
            )


class TestWebSocketMockMCPServer:
    """Test the WebSocket Mock MCP server."""

    @pytest.fixture
    def server_config(self):
        """Create a server configuration for testing."""
        return ServerConfig(
            name="TestWebSocketMockMCP",
            description="Test WebSocket Mock MCP Server",
            config={
                "type": "websocket_mock",
                "websocket_host": "localhost",
                "websocket_port": 9999,
                "auto_start_websocket": False,  # Don't auto-start for tests
            },
        )

    @pytest.fixture
    def mcp_server(self, server_config):
        """Create a WebSocket Mock MCP server instance for testing."""
        return WebSocketMockMCPServer(server_config)

    def test_mcp_server_initialization(self, mcp_server):
        """Test MCP server initialization."""
        assert mcp_server.SERVER_TYPE == "websocket_mock"
        assert mcp_server.SERVER_VERSION == "1.0.0"
        assert "websockets" in mcp_server.REQUIRED_DEPENDENCIES
        assert mcp_server.REQUIRED_APPS == []
        assert mcp_server.websocket_server is not None
        assert mcp_server.websocket_server.host == "localhost"
        assert mcp_server.websocket_server.port == 9999
        assert mcp_server.auto_start_websocket is False

    def test_mcp_server_tools_registration(self, mcp_server):
        """Test that tools are properly registered."""
        # Mock the MCP instance
        mcp_server.mcp = MagicMock()
        mcp_server._register_tools()

        # Check that tools were registered
        assert len(mcp_server.info.tools) == 6
        expected_tools = [
            "get_websocket_server_status",
            "start_websocket_server",
            "stop_websocket_server",
            "send_websocket_message",
            "get_websocket_clients",
            "test_websocket_connection",
        ]
        for tool in expected_tools:
            assert tool in mcp_server.info.tools

    @pytest.mark.asyncio
    async def test_mcp_server_startup_no_auto_start(self, mcp_server):
        """Test MCP server startup without auto-starting WebSocket server."""
        await mcp_server._on_startup()
        assert not mcp_server.websocket_server.is_running

    @pytest.mark.asyncio
    async def test_mcp_server_startup_with_auto_start(self, server_config):
        """Test MCP server startup with auto-starting WebSocket server."""
        server_config.config["auto_start_websocket"] = True
        mcp_server = WebSocketMockMCPServer(server_config)

        with patch.object(
            mcp_server.websocket_server, "start", return_value=True
        ) as mock_start:
            await mcp_server._on_startup()
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_server_shutdown(self, mcp_server):
        """Test MCP server shutdown."""
        # Mock running WebSocket server
        mcp_server.websocket_server.is_running = True

        with patch.object(mcp_server.websocket_server, "stop") as mock_stop:
            await mcp_server._on_shutdown()
            mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_server_health_check(self, mcp_server):
        """Test MCP server health check."""
        # Set server as running
        mcp_server.info.is_running = True

        # Test with WebSocket server not running (auto_start_websocket is False)
        health = await mcp_server._perform_health_check()
        assert health is True

        # Test with auto_start_websocket enabled but WebSocket server not running
        mcp_server.auto_start_websocket = True
        health = await mcp_server._perform_health_check()
        assert health is False

        # Test with WebSocket server running
        mcp_server.websocket_server.is_running = True
        with patch.object(
            mcp_server.websocket_server,
            "get_server_info",
            return_value={"is_running": True},
        ):
            health = await mcp_server._perform_health_check()
            assert health is True


class TestWebSocketMockTools:
    """Test the WebSocket Mock MCP tools."""

    @pytest.fixture
    def mock_server(self):
        """Create a mock server for tools testing."""
        server = MagicMock()
        server.config.name = "TestWebSocketMockMCP"
        server.SERVER_VERSION = "1.0.0"

        # Mock WebSocket server
        ws_server = MagicMock()
        ws_server.get_server_info.return_value = {
            "host": "localhost",
            "port": 9999,
            "is_running": True,
            "url": "ws://localhost:9999",
            "clients_connected": 2,
            "stats": {"total_connections": 5, "total_messages": 10},
            "capabilities": ["ping", "echo"],
        }
        server.websocket_server = ws_server

        return server

    @pytest.fixture
    def mock_context(self):
        """Create a mock context for tool calls."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_get_websocket_server_status(self, mock_server, mock_context):
        """Test get_websocket_server_status tool."""
        tools.set_current_server(mock_server)

        result = await tools.get_websocket_server_status(mock_context)

        assert "websocket_server" in result
        assert "mcp_server" in result
        assert result["mcp_server"]["mcp_server_name"] == "TestWebSocketMockMCP"
        assert result["mcp_server"]["mcp_server_type"] == "websocket_mock"

    @pytest.mark.asyncio
    async def test_get_websocket_server_status_no_server(self, mock_context):
        """Test get_websocket_server_status tool with no server."""
        tools.set_current_server(None)

        result = await tools.get_websocket_server_status(mock_context)

        assert result["error"] == "WebSocket server not available"
        assert result["status"] == "not_initialized"

    @pytest.mark.asyncio
    async def test_start_websocket_server(self, mock_server, mock_context):
        """Test start_websocket_server tool."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = False
        mock_server.websocket_server.start = AsyncMock(return_value=True)

        result = await tools.start_websocket_server(mock_context)

        assert result["status"] == "started"
        assert result["message"] == "WebSocket server started successfully"
        mock_server.websocket_server.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_websocket_server_already_running(
        self, mock_server, mock_context
    ):
        """Test start_websocket_server tool when already running."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True

        result = await tools.start_websocket_server(mock_context)

        assert result["status"] == "already_running"
        assert result["message"] == "WebSocket server is already running"

    @pytest.mark.asyncio
    async def test_stop_websocket_server(self, mock_server, mock_context):
        """Test stop_websocket_server tool."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True
        mock_server.websocket_server.stop = AsyncMock()

        result = await tools.stop_websocket_server(mock_context)

        assert result["status"] == "stopped"
        assert result["message"] == "WebSocket server stopped successfully"
        mock_server.websocket_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_websocket_server_not_running(self, mock_server, mock_context):
        """Test stop_websocket_server tool when not running."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = False

        result = await tools.stop_websocket_server(mock_context)

        assert result["status"] == "already_stopped"
        assert result["message"] == "WebSocket server is not running"

    @pytest.mark.asyncio
    async def test_send_websocket_message(self, mock_server, mock_context):
        """Test send_websocket_message tool."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True

        # Mock clients
        mock_client1 = MagicMock()
        mock_client1.websocket.closed = False
        mock_client1.websocket.send = AsyncMock()

        mock_client2 = MagicMock()
        mock_client2.websocket.closed = False
        mock_client2.websocket.send = AsyncMock()

        mock_server.websocket_server.clients = {
            "client1": mock_client1,
            "client2": mock_client2,
        }

        result = await tools.send_websocket_message(
            mock_context, message_type="test_message", payload={"data": "test"}
        )

        assert result["status"] == "sent"
        assert result["message_type"] == "test_message"
        assert result["sent_to_clients"] == 2
        assert result["total_clients"] == 2

        # Verify messages were sent
        mock_client1.websocket.send.assert_called_once()
        mock_client2.websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_websocket_message_no_clients(self, mock_server, mock_context):
        """Test send_websocket_message tool with no clients."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True
        mock_server.websocket_server.clients = {}

        result = await tools.send_websocket_message(
            mock_context, message_type="test_message"
        )

        assert result["status"] == "no_clients"
        assert result["message"] == "No clients connected to send message to"

    @pytest.mark.asyncio
    async def test_get_websocket_clients(self, mock_server, mock_context):
        """Test get_websocket_clients tool."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True

        # Mock clients
        mock_client = MagicMock()
        mock_client.to_dict.return_value = {
            "id": "client1",
            "connected_at": "2023-01-01T00:00:00",
            "remote_address": "127.0.0.1:12345",
        }
        mock_client.websocket.closed = False

        mock_server.websocket_server.clients = {"client1": mock_client}
        mock_server.websocket_server.host = "localhost"
        mock_server.websocket_server.port = 9999

        result = await tools.get_websocket_clients(mock_context)

        assert result["status"] == "success"
        assert result["total_clients"] == 1
        assert len(result["clients"]) == 1
        assert result["clients"][0]["id"] == "client1"
        assert result["clients"][0]["connection_status"] == "open"

    @pytest.mark.asyncio
    async def test_test_websocket_connection_ping(self, mock_server, mock_context):
        """Test test_websocket_connection tool with ping test."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True
        mock_server.websocket_server.clients = {"client1": MagicMock()}

        # Mock the send_websocket_message function
        with patch(
            "lightfast_mcp.servers.websocket_mock.tools.send_websocket_message"
        ) as mock_send:
            mock_send.return_value = {"status": "sent", "sent_to_clients": 1}

            result = await tools.test_websocket_connection(
                mock_context, test_type="ping"
            )

            assert result["status"] == "test_completed"
            assert result["test_type"] == "ping"
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_websocket_connection_stress(self, mock_server, mock_context):
        """Test test_websocket_connection tool with stress test."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True
        mock_server.websocket_server.clients = {"client1": MagicMock()}

        # Mock the send_websocket_message function
        with patch(
            "lightfast_mcp.servers.websocket_mock.tools.send_websocket_message"
        ) as mock_send:
            mock_send.return_value = {"status": "sent", "sent_to_clients": 1}

            result = await tools.test_websocket_connection(
                mock_context, test_type="stress"
            )

            assert result["status"] == "stress_test_completed"
            assert result["test_type"] == "stress"
            assert len(result["results"]) == 5  # Should have 5 stress test results
            assert mock_send.call_count == 5

    @pytest.mark.asyncio
    async def test_test_websocket_connection_unknown_type(
        self, mock_server, mock_context
    ):
        """Test test_websocket_connection tool with unknown test type."""
        tools.set_current_server(mock_server)
        mock_server.websocket_server.is_running = True
        mock_server.websocket_server.clients = {"client1": MagicMock()}

        result = await tools.test_websocket_connection(
            mock_context, test_type="unknown"
        )

        assert "error" in result
        assert "Unknown test type: unknown" in result["error"]
        assert "available_types" in result


class TestWebSocketClient:
    """Test the WebSocketClient dataclass."""

    def test_websocket_client_creation(self):
        """Test WebSocketClient creation and to_dict method."""
        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("127.0.0.1", 12345)

        client = WebSocketClient(id="test_client", websocket=mock_websocket)

        assert client.id == "test_client"
        assert client.websocket == mock_websocket
        assert client.last_ping is None
        assert client.metadata == {}

        # Test to_dict
        client_dict = client.to_dict()
        assert client_dict["id"] == "test_client"
        assert client_dict["remote_address"] == "127.0.0.1:12345"
        assert client_dict["last_ping"] is None

    def test_websocket_client_to_dict_no_address(self):
        """Test WebSocketClient to_dict with no remote address."""
        mock_websocket = MagicMock()
        mock_websocket.remote_address = None

        client = WebSocketClient(id="test_client", websocket=mock_websocket)
        client_dict = client.to_dict()

        assert client_dict["remote_address"] == "unknown"
