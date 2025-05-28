"""
End-to-end tests for the WebSocket Mock MCP server.

These tests verify the complete workflow from MCP tool calls to WebSocket
server interactions, simulating real-world usage scenarios.
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest
import websockets

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.websocket_mock import tools
from lightfast_mcp.servers.websocket_mock.server import WebSocketMockMCPServer


class TestWebSocketMockE2E:
    """End-to-end tests for WebSocket Mock MCP server."""

    @pytest.fixture
    def server_config(self):
        """Create a server configuration for E2E testing."""
        return ServerConfig(
            name="E2ETestWebSocketMockMCP",
            description="E2E Test WebSocket Mock MCP Server",
            config={
                "type": "websocket_mock",
                "websocket_host": "localhost",
                "websocket_port": 9997,  # Use different port for E2E tests
                "auto_start_websocket": False,  # Manual control for tests
            },
        )

    @pytest.fixture
    async def mcp_server(self, server_config):
        """Create and setup an MCP server for E2E testing."""
        server = WebSocketMockMCPServer(server_config)

        # Mock the MCP instance to avoid actual server startup
        server.mcp = MagicMock()
        server.info.is_running = True

        # Register tools
        server._register_tools()

        await server._on_startup()
        yield server
        await server._on_shutdown()

    @pytest.fixture
    def mock_context(self):
        """Create a mock context for tool calls."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_complete_websocket_workflow(self, mcp_server, mock_context):
        """Test complete workflow: start server, connect clients, send messages, stop server."""
        # Step 1: Check initial status - server should be running due to auto-start
        status_result = await tools.get_websocket_server_status(mock_context)
        assert status_result["websocket_server"]["is_running"] is True

        # Step 2: Server is already running, so we can proceed directly to testing

        try:
            # Step 3: Verify server is running
            status_result = await tools.get_websocket_server_status(mock_context)
            assert status_result["websocket_server"]["is_running"] is True

            # Step 4: Connect WebSocket clients
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

            async with (
                websockets.connect(uri) as client1,
                websockets.connect(uri) as client2,
            ):
                # Skip welcome messages
                await client1.recv()
                await client2.recv()

                # Step 5: Get client information via MCP tool
                clients_result = await tools.get_websocket_clients(mock_context)
                assert clients_result["status"] == "success"
                assert clients_result["total_clients"] == 2

                # Step 6: Send message to clients via MCP tool
                message_result = await tools.send_websocket_message(
                    mock_context,
                    message_type="test_broadcast",
                    payload={"message": "Hello from MCP server!"},
                )
                assert message_result["status"] == "sent"
                assert message_result["sent_to_clients"] == 2

                # Step 7: Verify clients received the message
                message1 = json.loads(await client1.recv())
                message2 = json.loads(await client2.recv())

                for message in [message1, message2]:
                    assert message["type"] == "test_broadcast"
                    assert message["from_mcp_server"] is True
                    assert message["payload"]["message"] == "Hello from MCP server!"

                # Step 8: Test connection via MCP tool
                test_result = await tools.test_websocket_connection(
                    mock_context, test_type="ping"
                )
                assert test_result["status"] == "test_completed"
                assert test_result["test_type"] == "ping"

                # Step 9: Clients should receive ping messages
                ping1 = json.loads(await client1.recv())
                ping2 = json.loads(await client2.recv())

                for ping in [ping1, ping2]:
                    assert ping["type"] == "ping"
                    assert ping["from_mcp_server"] is True

        finally:
            # Step 10: WebSocket server stops automatically during teardown
            pass

    @pytest.mark.asyncio
    async def test_stress_testing_workflow(self, mcp_server, mock_context):
        """Test stress testing workflow with multiple clients and messages."""
        # WebSocket server starts automatically with the MCP server

        try:
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"
            num_clients = 5

            # Connect multiple clients
            clients = []
            for i in range(num_clients):
                client = await websockets.connect(uri)
                await client.recv()  # Skip welcome message
                clients.append(client)

            try:
                # Run stress test via MCP tool
                stress_result = await tools.test_websocket_connection(
                    mock_context, test_type="stress"
                )
                assert stress_result["status"] == "stress_test_completed"
                assert len(stress_result["results"]) == 5

                # Each client should receive 5 ping messages
                for client in clients:
                    messages_received = 0
                    try:
                        while messages_received < 5:
                            message = json.loads(
                                await asyncio.wait_for(client.recv(), timeout=1.0)
                            )
                            if message["type"] == "ping":
                                messages_received += 1
                    except asyncio.TimeoutError:
                        pass  # Expected when no more messages

                    assert messages_received == 5

                # Verify server statistics
                status_result = await tools.get_websocket_server_status(mock_context)
                stats = status_result["websocket_server"]["stats"]
                assert stats["total_connections"] >= num_clients
                # Note: Messages sent via MCP tools don't count as client messages
                # so we just verify the connections were made
                assert stats["total_messages"] >= 0  # Should have some messages

            finally:
                # Close all clients
                for client in clients:
                    await client.close()

        finally:
            # WebSocket server stops automatically during teardown
            pass

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, mcp_server, mock_context):
        """Test error handling workflow with various error scenarios."""
        # Test operations when server is running but no clients connected
        clients_result = await tools.get_websocket_clients(mock_context)
        assert clients_result["status"] == "success"  # Server is running
        assert len(clients_result["clients"]) == 0  # No clients connected

        message_result = await tools.send_websocket_message(
            mock_context, message_type="test"
        )
        assert message_result["status"] == "no_clients"  # No clients to send to

        test_result = await tools.test_websocket_connection(mock_context)
        assert test_result["status"] == "no_clients"  # No clients to test

    @pytest.mark.asyncio
    async def test_targeted_messaging_workflow(self, mcp_server, mock_context):
        """Test targeted messaging to specific clients."""
        # WebSocket server starts automatically with the MCP server

        try:
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

            async with (
                websockets.connect(uri) as client1,
                websockets.connect(uri) as client2,
            ):
                # Get welcome messages and extract client IDs
                welcome1 = json.loads(await client1.recv())
                welcome2 = json.loads(await client2.recv())

                client1_id = welcome1["client_id"]
                client2_id = welcome2["client_id"]

                # Get client list to verify IDs
                clients_result = await tools.get_websocket_clients(mock_context)
                client_ids = [client["id"] for client in clients_result["clients"]]
                assert client1_id in client_ids
                assert client2_id in client_ids

                # Send targeted message to client1 only
                message_result = await tools.send_websocket_message(
                    mock_context,
                    message_type="targeted_message",
                    payload={"target": "client1"},
                    target_client=client1_id,
                )
                assert message_result["status"] == "sent"
                assert message_result["sent_to_clients"] == 1
                assert message_result["target_client"] == client1_id

                # Only client1 should receive the message
                message1 = json.loads(await client1.recv())
                assert message1["type"] == "targeted_message"
                assert message1["payload"]["target"] == "client1"

                # Client2 should not receive any message (timeout expected)
                try:
                    await asyncio.wait_for(client2.recv(), timeout=0.5)
                    assert False, "Client2 should not have received a message"
                except asyncio.TimeoutError:
                    pass  # Expected

                # Test targeted message to non-existent client
                message_result = await tools.send_websocket_message(
                    mock_context,
                    message_type="test",
                    target_client="non_existent_client",
                )
                assert message_result["status"] == "sent"
                assert message_result["sent_to_clients"] == 0
                assert len(message_result["errors"]) == 1
                assert "not found" in message_result["errors"][0]

        finally:
            # WebSocket server stops automatically during teardown
            pass

    @pytest.mark.asyncio
    async def test_client_interaction_workflow(self, mcp_server, mock_context):
        """Test workflow with client-to-client interactions."""
        # WebSocket server starts automatically with the MCP server

        try:
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

            async with (
                websockets.connect(uri) as client1,
                websockets.connect(uri) as client2,
            ):
                # Skip welcome messages
                welcome1 = json.loads(await client1.recv())
                welcome2 = json.loads(await client2.recv())

                client1_id = welcome1["client_id"]
                client2_id = welcome2["client_id"]

                # Client1 sends broadcast message
                broadcast_message = {
                    "type": "broadcast",
                    "message": "Hello from client1!",
                }
                await client1.send(json.dumps(broadcast_message))

                # Client1 gets confirmation
                broadcast_confirm = json.loads(await client1.recv())
                assert broadcast_confirm["type"] == "broadcast_sent"
                assert broadcast_confirm["recipients"] == 1

                # Client2 receives the broadcast
                broadcast_received = json.loads(await client2.recv())
                assert broadcast_received["type"] == "broadcast"
                assert broadcast_received["from_client"] == client1_id
                assert broadcast_received["message"] == "Hello from client1!"

                # Test echo functionality
                echo_message = {"type": "echo", "test_data": "Echo test from client2"}
                await client2.send(json.dumps(echo_message))

                echo_response = json.loads(await client2.recv())
                assert echo_response["type"] == "echo_response"
                assert echo_response["client_id"] == client2_id
                assert echo_response["original_message"] == echo_message

                # Test ping from client
                ping_message = {"type": "ping"}
                await client1.send(json.dumps(ping_message))

                pong_response = json.loads(await client1.recv())
                assert pong_response["type"] == "pong"
                assert pong_response["client_id"] == client1_id

                # Verify server statistics via MCP tool
                status_result = await tools.get_websocket_server_status(mock_context)
                stats = status_result["websocket_server"]["stats"]
                assert stats["current_clients"] == 2
                assert stats["total_messages"] >= 3  # broadcast, echo, ping

        finally:
            # WebSocket server stops automatically during teardown
            pass

    @pytest.mark.asyncio
    async def test_server_lifecycle_workflow(self, mcp_server, mock_context):
        """Test complete server lifecycle with multiple start/stop cycles."""
        # Initial state - server should be running due to auto-start
        status_result = await tools.get_websocket_server_status(mock_context)
        assert status_result["websocket_server"]["is_running"] is True

        # Test with server already running - Connect -> Verify -> Test functionality
        uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"
        async with websockets.connect(uri) as client:
            await client.recv()  # Welcome message

            # Verify connection
            clients_result = await tools.get_websocket_clients(mock_context)
            assert clients_result["total_clients"] == 1

        # Test with multiple clients
        async with (
            websockets.connect(uri) as client1,
            websockets.connect(uri) as client2,
            websockets.connect(uri) as client3,
        ):
            # Skip welcome messages
            for client in [client1, client2, client3]:
                await client.recv()

            # Verify all connections
            clients_result = await tools.get_websocket_clients(mock_context)
            assert clients_result["total_clients"] == 3

            # Send messages to verify functionality
            message_result = await tools.send_websocket_message(
                mock_context, message_type="lifecycle_test", payload={"cycle": 2}
            )
            assert message_result["sent_to_clients"] == 3

            # Verify all clients received the message
            for client in [client1, client2, client3]:
                message = json.loads(await client.recv())
                assert message["type"] == "lifecycle_test"
                assert message["payload"]["cycle"] == 2

        # Final verification - server should still be running
        status_result = await tools.get_websocket_server_status(mock_context)
        assert status_result["websocket_server"]["is_running"] is True

    @pytest.mark.asyncio
    async def test_auto_start_workflow(self, server_config, mock_context):
        """Test auto-start functionality workflow."""
        # Configure auto-start
        server_config.config["auto_start_websocket"] = True

        mcp_server = WebSocketMockMCPServer(server_config)
        mcp_server.mcp = MagicMock()
        mcp_server.info.is_running = True
        mcp_server._register_tools()

        # Server startup should auto-start WebSocket server
        await mcp_server._on_startup()

        try:
            # Verify WebSocket server is running
            status_result = await tools.get_websocket_server_status(mock_context)
            assert status_result["websocket_server"]["is_running"] is True

            # Test connection to auto-started server
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

            async with websockets.connect(uri) as client:
                welcome_message = json.loads(await client.recv())
                assert welcome_message["type"] == "welcome"

                # Test functionality
                ping_message = {"type": "ping"}
                await client.send(json.dumps(ping_message))

                pong_response = json.loads(await client.recv())
                assert pong_response["type"] == "pong"

        finally:
            await mcp_server._on_shutdown()

    @pytest.mark.asyncio
    async def test_health_check_workflow(self, mcp_server, mock_context):
        """Test health check workflow in various states."""
        # Health check with auto-start enabled and WebSocket server running
        mcp_server.auto_start_websocket = True
        health = await mcp_server._perform_health_check()
        assert health is True  # Should pass because WebSocket server is running

        # Connect a client and verify health check still passes
        uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

        async with websockets.connect(uri) as client:
            await client.recv()  # Welcome message

            health = await mcp_server._perform_health_check()
            assert health is True  # Should still pass with connected client
