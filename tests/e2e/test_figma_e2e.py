"""
End-to-end tests for Figma MCP server.

These tests verify the complete workflow of the Figma server including
server startup, WebSocket connections, tool execution, and shutdown.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.figma import tools
from lightfast_mcp.servers.figma.server import FigmaMCPServer


class TestFigmaServerE2E:
    """End-to-end tests for Figma server."""

    @pytest.mark.asyncio
    async def test_figma_server_complete_lifecycle(self, sample_figma_config):
        """Test complete Figma server lifecycle from startup to shutdown."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                # Initialize server
                server = FigmaMCPServer(sample_figma_config)

                # Verify initial state
                assert server.config == sample_figma_config
                assert server.SERVER_TYPE == "figma"
                assert hasattr(server, "websocket_server")
                assert tools._current_server is server

                # Mock WebSocket server for controlled testing
                server.websocket_server.is_running = False
                server.websocket_server.start = AsyncMock(return_value=True)
                server.websocket_server.stop = AsyncMock()
                server.websocket_server.get_server_info = MagicMock(
                    return_value={
                        "is_running": True,
                        "host": "localhost",
                        "port": 9003,
                        "total_clients": 0,
                        "stats": {
                            "total_connections": 0,
                            "total_messages": 0,
                            "errors": 0,
                        },
                    }
                )

                # Test startup sequence
                await server._on_startup()

                # Simulate WebSocket server starting
                server.websocket_server.is_running = True

                # Test health check after startup
                server.info.is_running = True
                health = await server._perform_health_check()
                assert health is True

                # Test that tools are properly registered
                server_tools = server.get_tools()
                expected_tools = [
                    "get_figma_server_status",
                    "get_figma_plugins",
                    "ping_figma_plugin",
                    "get_document_state",
                    "execute_design_command",
                    "broadcast_design_command",
                ]
                for tool in expected_tools:
                    assert tool in server_tools

                # Test shutdown sequence
                await server._on_shutdown()

    @pytest.mark.asyncio
    async def test_figma_server_plugin_connection_workflow(self, sample_figma_config):
        """Test workflow with simulated Figma plugin connections."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up WebSocket server with simulated plugin connections
                server.websocket_server.is_running = True

                # Simulate multiple plugin connections
                mock_plugins = {}
                for i in range(3):
                    plugin_id = f"figma-plugin-{i}"
                    mock_client = MagicMock()
                    mock_client.to_dict.return_value = {
                        "id": plugin_id,
                        "connected_at": f"2024-01-01T00:0{i}:00",
                        "plugin_info": {
                            "name": f"Test Plugin {i}",
                            "version": "1.0.0",
                            "capabilities": ["design", "export"],
                        },
                        "metadata": {"session_id": f"session-{i}"},
                        "remote_address": f"127.0.0.1:500{i}",
                    }
                    mock_plugins[plugin_id] = mock_client

                server.websocket_server.clients = mock_plugins
                server.websocket_server.get_server_info = MagicMock(
                    return_value={
                        "is_running": True,
                        "host": "localhost",
                        "port": 9003,
                        "total_clients": len(mock_plugins),
                    }
                )

                # Test getting server status with connected plugins
                status = await tools.get_figma_server_status(None)
                assert "figma_websocket_server" in status
                assert "mcp_server" in status
                assert status["mcp_server"]["mcp_server_name"] == "test-figma"

                # Test getting plugin information
                plugins_info = await tools.get_figma_plugins(None)
                assert plugins_info["status"] == "success"
                assert plugins_info["total_plugins"] == 3
                assert len(plugins_info["plugins"]) == 3

                # Verify plugin details
                plugin_ids = [p["id"] for p in plugins_info["plugins"]]
                assert "figma-plugin-0" in plugin_ids
                assert "figma-plugin-1" in plugin_ids
                assert "figma-plugin-2" in plugin_ids

    @pytest.mark.asyncio
    async def test_figma_server_design_automation_workflow(self, sample_figma_config):
        """Test complete design automation workflow."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up WebSocket server with a connected plugin
                server.websocket_server.is_running = True

                # Create proper mock client with string ID
                mock_client = MagicMock()
                mock_client.id = "design-plugin"  # Set as string
                server.websocket_server.clients = {"design-plugin": mock_client}

                # Mock WebSocket communication methods
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                server.websocket_server.broadcast_to_plugins = AsyncMock(return_value=1)

                # Step 1: Check plugin connectivity
                ping_result = await tools.ping_figma_plugin(
                    None, plugin_id="design-plugin"
                )
                assert ping_result["status"] == "ping_sent"
                assert ping_result["plugin_id"] == "design-plugin"

                # Step 2: Get document state
                doc_state = await tools.get_document_state(
                    None, plugin_id="design-plugin"
                )
                assert doc_state["status"] == "request_sent"
                assert doc_state["plugin_id"] == "design-plugin"

                # Step 3: Execute design commands
                design_commands = [
                    "create_rectangle",
                    "set_fill_color",
                    "add_text_layer",
                    "group_elements",
                ]

                for command in design_commands:
                    result = await tools.execute_design_command(
                        None, command=command, plugin_id="design-plugin"
                    )
                    assert result["status"] == "command_sent"
                    assert result["command"] == command
                    assert result["plugin_id"] == "design-plugin"

                # Step 4: Broadcast a refresh command to all plugins
                refresh_result = await tools.broadcast_design_command(
                    None, command="refresh_canvas"
                )
                assert refresh_result["status"] == "command_broadcast"
                assert refresh_result["command"] == "refresh_canvas"
                assert refresh_result["sent_to_plugins"] == 1

                # Verify all commands were sent to WebSocket server
                assert server.websocket_server.send_command_to_plugin.call_count >= 5
                assert server.websocket_server.broadcast_to_plugins.call_count >= 1

    @pytest.mark.asyncio
    async def test_figma_server_error_recovery_workflow(self, sample_figma_config):
        """Test error recovery and resilience workflow."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Scenario 1: WebSocket server not running
                server.websocket_server.is_running = False

                # Tools should handle this gracefully
                plugins_result = await tools.get_figma_plugins(None)
                assert (
                    plugins_result["error"] == "Figma WebSocket server is not running"
                )
                assert plugins_result["status"] == "server_not_running"

                ping_result = await tools.ping_figma_plugin(None)
                assert ping_result["error"] == "Figma WebSocket server is not running"

                # Scenario 2: WebSocket server running but no plugins connected
                server.websocket_server.is_running = True
                server.websocket_server.clients = {}

                no_plugins_ping = await tools.ping_figma_plugin(None)
                assert no_plugins_ping["status"] == "no_plugins"

                # Scenario 3: Network errors during communication
                server.websocket_server.clients = {"test-plugin": MagicMock()}
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    side_effect=Exception("Network timeout")
                )

                error_ping = await tools.ping_figma_plugin(
                    None, plugin_id="test-plugin"
                )
                assert error_ping["status"] == "error"
                assert "Exception while pinging" in error_ping["error"]

                # Scenario 4: Broadcast errors
                server.websocket_server.broadcast_to_plugins = AsyncMock(
                    side_effect=Exception("Broadcast failed")
                )

                error_broadcast = await tools.broadcast_design_command(
                    None, command="test"
                )
                assert error_broadcast["status"] == "error"
                assert "Exception while broadcasting" in error_broadcast["error"]

    @pytest.mark.asyncio
    async def test_figma_server_concurrent_plugin_operations(self, sample_figma_config):
        """Test concurrent operations with multiple plugins."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up multiple plugins
                num_plugins = 5
                mock_plugins = {}
                for i in range(num_plugins):
                    plugin_id = f"concurrent-plugin-{i}"
                    mock_client = MagicMock()
                    mock_client.id = plugin_id  # Set as string
                    mock_client.to_dict.return_value = {
                        "id": plugin_id,
                        "connected_at": f"2024-01-01T00:0{i}:00",
                    }
                    mock_plugins[plugin_id] = mock_client

                server.websocket_server.is_running = True
                server.websocket_server.clients = mock_plugins
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                server.websocket_server.broadcast_to_plugins = AsyncMock(
                    return_value=num_plugins
                )

                # Execute concurrent operations
                concurrent_tasks = []

                # Ping all plugins individually
                for i in range(num_plugins):
                    plugin_id = f"concurrent-plugin-{i}"
                    task = tools.ping_figma_plugin(None, plugin_id=plugin_id)
                    concurrent_tasks.append(task)

                # Execute design commands on different plugins
                for i in range(num_plugins):
                    plugin_id = f"concurrent-plugin-{i}"
                    command = f"create_shape_{i}"
                    task = tools.execute_design_command(
                        None, command=command, plugin_id=plugin_id
                    )
                    concurrent_tasks.append(task)

                # Add some broadcast operations
                for i in range(3):
                    command = f"broadcast_command_{i}"
                    task = tools.broadcast_design_command(None, command=command)
                    concurrent_tasks.append(task)

                # Execute all tasks concurrently
                results = await asyncio.gather(
                    *concurrent_tasks, return_exceptions=True
                )

                # Verify all operations completed successfully
                successful_results = [
                    r for r in results if not isinstance(r, Exception)
                ]
                assert len(successful_results) == len(concurrent_tasks)

                # Verify ping results
                ping_results = successful_results[:num_plugins]
                for result in ping_results:
                    assert result["status"] == "ping_sent"

                # Verify execute command results
                execute_results = successful_results[num_plugins : num_plugins * 2]
                for result in execute_results:
                    assert result["status"] == "command_sent"

                # Verify broadcast results
                broadcast_results = successful_results[num_plugins * 2 :]
                for result in broadcast_results:
                    assert result["status"] == "command_broadcast"

    @pytest.mark.asyncio
    async def test_figma_server_health_monitoring_workflow(self, sample_figma_config):
        """Test health monitoring and status reporting workflow."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Test health check progression through different states
                states = [
                    # State 1: Server not running
                    {
                        "mcp_running": False,
                        "ws_running": False,
                        "expected_health": False,
                    },
                    # State 2: MCP running, WebSocket not running
                    {
                        "mcp_running": True,
                        "ws_running": False,
                        "expected_health": False,
                    },
                    # State 3: Both running, WebSocket reports not running
                    {
                        "mcp_running": True,
                        "ws_running": True,
                        "ws_reports_running": False,
                        "expected_health": False,
                    },
                    # State 4: Both running and healthy
                    {
                        "mcp_running": True,
                        "ws_running": True,
                        "ws_reports_running": True,
                        "expected_health": True,
                    },
                ]

                for i, state in enumerate(states):
                    # Set up server state
                    server.info.is_running = state["mcp_running"]
                    server.websocket_server.is_running = state["ws_running"]

                    if state.get("ws_reports_running") is not None:
                        server.websocket_server.get_server_info = MagicMock(
                            return_value={"is_running": state["ws_reports_running"]}
                        )

                    # Test health check
                    health = await server._perform_health_check()
                    assert health == state["expected_health"], f"State {i} failed"

                    # Test status reporting
                    if state["mcp_running"] and state["ws_running"]:
                        # Mock some clients for status reporting
                        server.websocket_server.clients = {
                            f"plugin-{j}": MagicMock() for j in range(2)
                        }
                        server.websocket_server.get_server_info = MagicMock(
                            return_value={
                                "is_running": state.get("ws_reports_running", True),
                                "host": "localhost",
                                "port": 9003,
                                "total_clients": 2,
                                "stats": {
                                    "total_connections": 10,
                                    "total_messages": 50,
                                    "errors": 0,
                                },
                            }
                        )

                        status = await tools.get_figma_server_status(None)
                        assert "figma_websocket_server" in status
                        assert "mcp_server" in status
                        assert "timestamp" in status

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_figma_server_performance_workflow(self, sample_figma_config):
        """Test performance characteristics under load (slow test)."""
        with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
            with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                server = FigmaMCPServer(sample_figma_config)

                # Set up server with many mock plugins
                num_plugins = 50
                mock_plugins = {}
                for i in range(num_plugins):
                    plugin_id = f"perf-plugin-{i}"
                    mock_client = MagicMock()
                    mock_client.to_dict.return_value = {
                        "id": plugin_id,
                        "connected_at": f"2024-01-01T00:{i:02d}:00",
                    }
                    mock_plugins[plugin_id] = mock_client

                server.websocket_server.is_running = True
                server.websocket_server.clients = mock_plugins

                # Mock fast WebSocket operations
                server.websocket_server.send_command_to_plugin = AsyncMock(
                    return_value=True
                )
                server.websocket_server.broadcast_to_plugins = AsyncMock(
                    return_value=num_plugins
                )
                server.websocket_server.get_server_info = MagicMock(
                    return_value={
                        "is_running": True,
                        "total_clients": num_plugins,
                    }
                )

                # Performance test: Get plugins info
                start_time = time.time()
                plugins_info = await tools.get_figma_plugins(None)
                plugins_time = time.time() - start_time

                assert plugins_info["status"] == "success"
                assert plugins_info["total_plugins"] == num_plugins
                assert plugins_time < 1.0  # Should complete within 1 second

                # Performance test: Broadcast to all plugins
                start_time = time.time()
                broadcast_result = await tools.broadcast_design_command(
                    None, command="performance_test"
                )
                broadcast_time = time.time() - start_time

                assert broadcast_result["status"] == "command_broadcast"
                assert broadcast_result["sent_to_plugins"] == num_plugins
                assert broadcast_time < 1.0  # Should complete within 1 second

                # Performance test: Multiple concurrent status checks
                start_time = time.time()
                status_tasks = [tools.get_figma_server_status(None) for _ in range(10)]
                status_results = await asyncio.gather(*status_tasks)
                status_time = time.time() - start_time

                assert len(status_results) == 10
                assert all(
                    "figma_websocket_server" in result for result in status_results
                )
                assert status_time < 2.0  # Should complete within 2 seconds

    @pytest.mark.asyncio
    async def test_figma_server_configuration_scenarios(self):
        """Test different configuration scenarios end-to-end."""
        configurations = [
            # Default configuration
            {
                "name": "default-figma",
                "config": {"type": "figma"},
                "expected_host": "localhost",
                "expected_port": 9003,
            },
            # Custom host and port
            {
                "name": "custom-figma",
                "config": {
                    "type": "figma",
                    "figma_host": "0.0.0.0",
                    "figma_port": 8888,
                },
                "expected_host": "0.0.0.0",
                "expected_port": 8888,
            },
            # Different port only
            {
                "name": "port-figma",
                "config": {"type": "figma", "figma_port": 7777},
                "expected_host": "localhost",
                "expected_port": 7777,
            },
        ]

        for config_spec in configurations:
            config = ServerConfig(
                name=config_spec["name"],
                description=f"Test {config_spec['name']}",
                config=config_spec["config"],
            )

            with patch.object(FigmaMCPServer, "_start_websocket_server_background"):
                with patch.object(FigmaMCPServer, "_register_signal_handlers"):
                    server = FigmaMCPServer(config)

                    # Verify configuration was applied correctly
                    assert server.websocket_server.host == config_spec["expected_host"]
                    assert server.websocket_server.port == config_spec["expected_port"]

                    # Verify server can be initialized and tools work
                    assert tools._current_server is server

                    # Mock WebSocket server for testing
                    server.websocket_server.is_running = True
                    server.websocket_server.get_server_info = MagicMock(
                        return_value={
                            "is_running": True,
                            "host": config_spec["expected_host"],
                            "port": config_spec["expected_port"],
                        }
                    )

                    # Test that tools work with this configuration
                    status = await tools.get_figma_server_status(None)
                    assert "figma_websocket_server" in status
                    assert (
                        status["mcp_server"]["mcp_server_name"] == config_spec["name"]
                    )
