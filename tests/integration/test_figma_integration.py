"""
Integration tests for Figma MCP server.

These tests verify the integration between different components of the Figma server
including the MCP server, WebSocket server, and tools.
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


class TestFigmaServerIntegration:
    """Integration tests for Figma server components."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_server_startup_shutdown_cycle(self, sample_figma_config):
        """Test complete startup and shutdown cycle."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server behavior
                server.websocket_server.is_running = False
                server.websocket_server.start = AsyncMock(return_value=True)
                server.websocket_server.stop = AsyncMock()
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": True}
                )

                # Test startup
                await server._on_startup()

                # Simulate WebSocket server starting
                server.websocket_server.is_running = True

                # Test health check during running state
                server.info.is_running = True
                health = await server._perform_health_check()
                assert health is True

                # Test shutdown
                await server._on_shutdown()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_tools_with_mock_websocket_server(self, sample_figma_config):
        """Test Figma tools integration with mock WebSocket server."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server with clients
                mock_client1 = MagicMock()
                mock_client1.id = "plugin-1"
                mock_client1.to_dict.return_value = {
                    "id": "plugin-1",
                    "connected_at": "2024-01-01T00:00:00",
                    "plugin_info": {"name": "Test Plugin 1"},
                }

                mock_client2 = MagicMock()
                mock_client2.id = "plugin-2"
                mock_client2.to_dict.return_value = {
                    "id": "plugin-2",
                    "connected_at": "2024-01-01T00:01:00",
                    "plugin_info": {"name": "Test Plugin 2"},
                }

                server.websocket_server.is_running = True
                server.websocket_server.clients = {
                    "plugin-1": mock_client1,
                    "plugin-2": mock_client2,
                }
                server.websocket_server.host = "localhost"
                server.websocket_server.port = 9003
                server.websocket_server.get_server_info = MagicMock(
                    return_value={
                        "is_running": True,
                        "host": "localhost",
                        "port": 9003,
                        "total_clients": 2,
                    }
                )

                # Test get_figma_server_status
                status = await tools.get_figma_server_status(None)
                assert "figma_websocket_server" in status
                assert "mcp_server" in status
                assert status["mcp_server"]["mcp_server_name"] == "test-figma"

                # Test get_figma_plugins
                plugins = await tools.get_figma_plugins(None)
                assert plugins["status"] == "success"
                assert plugins["total_plugins"] == 2
                assert len(plugins["plugins"]) == 2

                # Test ping with broadcast
                server.websocket_server.broadcast_to_plugins = AsyncMock(return_value=2)
                ping_result = await tools.ping_figma_plugin(None)
                assert ping_result["status"] == "ping_broadcast"
                assert ping_result["sent_to_plugins"] == 2

                # Test ping specific plugin
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                ping_specific = await tools.ping_figma_plugin(
                    None, plugin_id="plugin-1"
                )
                assert ping_specific["status"] == "ping_sent"
                assert ping_specific["plugin_id"] == "plugin-1"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_design_commands_integration(self, sample_figma_config):
        """Test design command execution integration."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server with clients
                server.websocket_server.is_running = True

                # Create proper mock client with string ID
                mock_client = MagicMock()
                mock_client.id = "plugin-1"  # Set as string
                server.websocket_server.clients = {"plugin-1": mock_client}

                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                server.websocket_server.broadcast_to_plugins = AsyncMock(return_value=1)

                # Test execute_design_command
                result = await tools.execute_design_command(
                    None, command="create_rectangle", plugin_id="plugin-1"
                )
                assert result["status"] == "command_sent"
                assert result["command"] == "create_rectangle"
                assert result["plugin_id"] == "plugin-1"

                # Verify the command was sent to WebSocket server
                server.websocket_server.send_command_to_plugin.assert_called_with(
                    "plugin-1",
                    "execute_design_command",
                    {"command": "create_rectangle"},
                )

                # Test broadcast_design_command
                broadcast_result = await tools.broadcast_design_command(
                    None, command="refresh_view"
                )
                assert broadcast_result["status"] == "command_broadcast"
                assert broadcast_result["command"] == "refresh_view"
                assert broadcast_result["sent_to_plugins"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_document_state_integration(self, sample_figma_config):
        """Test document state retrieval integration."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Mock WebSocket server with clients
                server.websocket_server.is_running = True

                # Create proper mock client with string ID
                mock_client = MagicMock()
                mock_client.id = "plugin-1"  # Set as string
                server.websocket_server.clients = {"plugin-1": mock_client}

                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )

                # Test get_document_state
                result = await tools.get_document_state(None, plugin_id="plugin-1")
                assert result["status"] == "request_sent"
                assert result["plugin_id"] == "plugin-1"

                # Verify the request was sent to WebSocket server
                server.websocket_server.send_command_to_plugin.assert_called_with(
                    "plugin-1", "get_document_info"
                )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_error_handling_integration(self, sample_figma_config):
        """Test error handling across components."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Test with WebSocket server not running
                server.websocket_server.is_running = False

                # All tools should handle this gracefully
                status = await tools.get_figma_server_status(None)
                assert (
                    "error" not in status
                )  # This tool works even when WS server is down

                plugins = await tools.get_figma_plugins(None)
                assert plugins["error"] == "Figma WebSocket server is not running"

                ping = await tools.ping_figma_plugin(None)
                assert ping["error"] == "Figma WebSocket server is not running"

                # Test with WebSocket server running but no clients
                server.websocket_server.is_running = True
                server.websocket_server.clients = {}

                ping_no_clients = await tools.ping_figma_plugin(None)
                assert ping_no_clients["status"] == "no_plugins"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_websocket_server_lifecycle(self):
        """Test WebSocket server lifecycle independently."""
        server = FigmaWebSocketServer(host="localhost", port=9999)

        # Test initial state
        assert server.is_running is False
        assert len(server.clients) == 0

        # Test server info when not running
        info = server.get_server_info()
        assert info["is_running"] is False
        assert info["host"] == "localhost"
        assert info["port"] == 9999

        # Test stop when not running (should not raise)
        await server.stop()

    @pytest.mark.integration
    def test_figma_client_dataclass(self):
        """Test FigmaClient dataclass functionality."""
        from datetime import datetime
        from unittest.mock import MagicMock

        mock_websocket = MagicMock()
        mock_websocket.remote_address = ("192.168.1.100", 54321)

        client = FigmaClient(id="test-client", websocket=mock_websocket)

        # Test default values
        assert client.id == "test-client"
        assert client.websocket == mock_websocket
        assert isinstance(client.connected_at, datetime)
        assert client.last_ping is None
        assert client.metadata == {}
        assert client.plugin_info == {}

        # Test to_dict conversion
        client_dict = client.to_dict()
        assert client_dict["id"] == "test-client"
        assert "connected_at" in client_dict
        assert client_dict["remote_address"] == "192.168.1.100:54321"
        assert client_dict["metadata"] == {}
        assert client_dict["plugin_info"] == {}

        # Test with metadata and plugin info
        client.metadata = {"session_id": "abc123"}
        client.plugin_info = {"name": "Test Plugin", "version": "1.0.0"}
        client.last_ping = datetime.now()

        updated_dict = client.to_dict()
        assert updated_dict["metadata"]["session_id"] == "abc123"
        assert updated_dict["plugin_info"]["name"] == "Test Plugin"
        assert updated_dict["last_ping"] is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_server_health_check_scenarios(self, sample_figma_config):
        """Test various health check scenarios."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Scenario 1: MCP server not running
                server.info.is_running = False
                health = await server._perform_health_check()
                assert health is False

                # Scenario 2: MCP server running, WebSocket server not running
                server.info.is_running = True
                server.websocket_server.is_running = False
                health = await server._perform_health_check()
                assert health is False

                # Scenario 3: Both running, but WebSocket server reports not running
                server.websocket_server.is_running = True
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": False}
                )
                health = await server._perform_health_check()
                assert health is False

                # Scenario 4: Both running and healthy
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": True}
                )
                health = await server._perform_health_check()
                assert health is True

                # Scenario 5: Exception during health check
                server.websocket_server.get_server_info = MagicMock(
                    side_effect=Exception("Connection error")
                )
                health = await server._perform_health_check()
                assert health is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_tools_error_scenarios(self, sample_figma_config):
        """Test error scenarios in tools."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up WebSocket server with error-prone behavior
                server.websocket_server.is_running = True
                server.websocket_server.clients = {"plugin-1": MagicMock()}

                # Test ping with exception
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    side_effect=Exception("Network error")
                )

                ping_result = await tools.ping_figma_plugin(None, plugin_id="plugin-1")
                assert ping_result["status"] == "error"
                assert "Exception while pinging" in ping_result["error"]

                # Test broadcast with exception
                server.websocket_server.broadcast_to_plugins = AsyncMock(
                    side_effect=Exception("Broadcast error")
                )

                broadcast_result = await tools.broadcast_design_command(
                    None, command="test"
                )
                assert broadcast_result["status"] == "error"
                assert "Exception while broadcasting" in broadcast_result["error"]

    @pytest.mark.integration
    def test_figma_server_configuration_variations(self):
        """Test server with different configuration variations."""
        # Test with minimal config
        minimal_config = ServerConfig(
            name="minimal-figma",
            description="Minimal Figma server",
            config={"type": "figma"},
        )

        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(minimal_config)
                assert server.websocket_server.host == "localhost"
                assert server.websocket_server.port == 9003

        # Test with custom config
        custom_config = ServerConfig(
            name="custom-figma",
            description="Custom Figma server",
            config={"type": "figma", "figma_host": "0.0.0.0", "figma_port": 8888},
        )

        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(custom_config)
                assert server.websocket_server.host == "0.0.0.0"
                assert server.websocket_server.port == 8888

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_figma_server_concurrent_operations(self, sample_figma_config):
        """Test concurrent operations on Figma server."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up mock clients with proper string IDs
                mock_clients = {}
                for i in range(5):
                    client_id = f"plugin-{i}"
                    mock_client = MagicMock()
                    mock_client.id = client_id  # Set as string
                    mock_clients[client_id] = mock_client

                # Mock WebSocket server
                server.websocket_server.is_running = True
                server.websocket_server.clients = mock_clients
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                server.websocket_server.broadcast_to_plugins = AsyncMock(return_value=5)
                server.websocket_server.get_server_info = MagicMock(
                    return_value={"is_running": True}
                )

                # Run multiple operations concurrently
                tasks = [
                    tools.get_figma_server_status(None),
                    tools.get_figma_plugins(None),
                    tools.ping_figma_plugin(None),
                    tools.execute_design_command(None, "test_command", "plugin-1"),
                    tools.broadcast_design_command(None, "broadcast_command"),
                ]

                results = await asyncio.gather(*tasks)

                # Verify all operations completed successfully
                assert len(results) == 5
                assert "figma_websocket_server" in results[0]  # status
                assert results[1]["status"] == "success"  # plugins
                assert results[2]["status"] == "ping_broadcast"  # ping
                assert results[3]["status"] == "command_sent"  # execute
                assert results[4]["status"] == "command_broadcast"  # broadcast
