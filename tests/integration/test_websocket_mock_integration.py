"""
Integration tests for the WebSocket Mock MCP server.

These tests verify real WebSocket connections and end-to-end functionality
including actual WebSocket client connections and message handling.
"""

import asyncio
import json

import pytest
import websockets

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.websocket_mock.server import WebSocketMockMCPServer
from lightfast_mcp.servers.websocket_mock.websocket_server import WebSocketMockServer


class TestWebSocketMockIntegration:
    """Integration tests for WebSocket Mock server."""

    @pytest.fixture
    def server_config(self):
        """Create a server configuration for integration testing."""
        return ServerConfig(
            name="IntegrationTestWebSocketMockMCP",
            description="Integration Test WebSocket Mock MCP Server",
            config={
                "type": "websocket_mock",
                "websocket_host": "localhost",
                "websocket_port": 9998,  # Use different port for integration tests
                "auto_start_websocket": False,  # Manual control for tests
            },
        )

    @pytest.fixture
    async def websocket_server(self):
        """Create and start a WebSocket server for testing."""
        server = WebSocketMockServer(host="localhost", port=9998)
        await server.start()
        yield server
        await server.stop()

    @pytest.fixture
    async def mcp_server(self, server_config):
        """Create and start an MCP server for testing."""
        server = WebSocketMockMCPServer(server_config)

        # Mock the MCP instance to avoid actual server startup
        server.mcp = None
        server.info.is_running = True

        await server._on_startup()
        yield server
        await server._on_shutdown()

    @pytest.mark.asyncio
    async def test_websocket_server_real_connection(self, websocket_server):
        """Test real WebSocket client connection to the server."""
        # Connect a real WebSocket client
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Should receive welcome message
            welcome_message = await websocket.recv()
            welcome_data = json.loads(welcome_message)

            assert welcome_data["type"] == "welcome"
            assert "client_id" in welcome_data
            assert welcome_data["server_info"]["name"] == "WebSocket Mock Server"
            assert "capabilities" in welcome_data["server_info"]

            # Test ping-pong
            ping_message = {"type": "ping", "test_id": "integration_test"}
            await websocket.send(json.dumps(ping_message))

            pong_response = await websocket.recv()
            pong_data = json.loads(pong_response)

            assert pong_data["type"] == "pong"
            assert pong_data["client_id"] == welcome_data["client_id"]
            assert "timestamp" in pong_data

    @pytest.mark.asyncio
    async def test_websocket_server_multiple_clients(self, websocket_server):
        """Test multiple WebSocket clients connecting simultaneously."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        # Connect multiple clients
        async with (
            websockets.connect(uri) as client1,
            websockets.connect(uri) as client2,
        ):
            # Get welcome messages with timeout
            welcome1 = json.loads(await asyncio.wait_for(client1.recv(), timeout=5.0))
            welcome2 = json.loads(await asyncio.wait_for(client2.recv(), timeout=5.0))

            client1_id = welcome1["client_id"]
            client2_id = welcome2["client_id"]

            assert client1_id != client2_id  # Should have different IDs

            # Test broadcast from client1
            broadcast_message = {"type": "broadcast", "message": "Hello from client1"}
            await client1.send(json.dumps(broadcast_message))

            # Client1 should get confirmation with timeout
            broadcast_confirm = json.loads(
                await asyncio.wait_for(client1.recv(), timeout=5.0)
            )
            assert broadcast_confirm["type"] == "broadcast_sent"
            assert broadcast_confirm["recipients"] == 1  # Should send to 1 other client

            # Client2 should receive the broadcast with timeout
            broadcast_received = json.loads(
                await asyncio.wait_for(client2.recv(), timeout=5.0)
            )
            assert broadcast_received["type"] == "broadcast"
            assert broadcast_received["from_client"] == client1_id
            assert broadcast_received["message"] == "Hello from client1"

    @pytest.mark.asyncio
    async def test_websocket_server_echo_functionality(self, websocket_server):
        """Test echo functionality with real WebSocket connection."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()

            # Test echo
            echo_message = {
                "type": "echo",
                "test_data": "This is a test echo message",
                "additional_field": 42,
            }
            await websocket.send(json.dumps(echo_message))

            echo_response = json.loads(await websocket.recv())

            assert echo_response["type"] == "echo_response"
            assert echo_response["original_message"] == echo_message
            assert "timestamp" in echo_response

    @pytest.mark.asyncio
    async def test_websocket_server_get_clients(self, websocket_server):
        """Test getting client list with real connections."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with (
            websockets.connect(uri) as client1,
            websockets.connect(uri) as client2,
        ):
            # Skip welcome messages
            await client1.recv()
            await client2.recv()

            # Request client list from client1
            get_clients_message = {"type": "get_clients"}
            await client1.send(json.dumps(get_clients_message))

            clients_response = json.loads(await client1.recv())

            assert clients_response["type"] == "clients_list"
            assert clients_response["total_clients"] == 2
            assert len(clients_response["clients"]) == 2

            # Verify client information
            client_ids = [client["id"] for client in clients_response["clients"]]
            assert len(set(client_ids)) == 2  # Should have unique IDs

    @pytest.mark.asyncio
    async def test_websocket_server_stats(self, websocket_server):
        """Test server statistics with real connections."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()

            # Send a few messages to generate stats
            for i in range(3):
                ping_message = {"type": "ping", "test_id": f"stats_test_{i}"}
                await websocket.send(json.dumps(ping_message))
                await websocket.recv()  # Consume pong response

            # Request stats
            stats_message = {"type": "get_stats"}
            await websocket.send(json.dumps(stats_message))

            stats_response = json.loads(await websocket.recv())

            assert stats_response["type"] == "server_stats"
            assert stats_response["stats"]["total_connections"] >= 1
            assert (
                stats_response["stats"]["total_messages"] >= 4
            )  # 3 pings + 1 stats request
            assert stats_response["stats"]["current_clients"] == 1

    @pytest.mark.asyncio
    async def test_websocket_server_delay_simulation(self, websocket_server):
        """Test delay simulation with real WebSocket connection."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()

            # Test delay simulation
            import time

            start_time = time.time()

            delay_message = {"type": "simulate_delay", "delay_seconds": 0.2}
            await websocket.send(json.dumps(delay_message))

            delay_response = json.loads(await websocket.recv())
            end_time = time.time()

            assert delay_response["type"] == "delay_completed"
            assert delay_response["delay_seconds"] == 0.2
            assert (end_time - start_time) >= 0.2  # Should have actually delayed

    @pytest.mark.asyncio
    async def test_websocket_server_invalid_message(self, websocket_server):
        """Test handling of invalid messages."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()

            # Send invalid JSON
            await websocket.send("invalid json")

            error_response = json.loads(await websocket.recv())
            assert error_response["type"] == "error"
            assert "Invalid JSON" in error_response["error"]

            # Send unknown message type
            unknown_message = {"type": "unknown_message_type"}
            await websocket.send(json.dumps(unknown_message))

            error_response = json.loads(await websocket.recv())
            assert error_response["type"] == "error"
            assert "Unknown message type" in error_response["error"]
            assert "available_types" in error_response

    @pytest.mark.asyncio
    async def test_mcp_server_websocket_integration(self, mcp_server):
        """Test MCP server integration with WebSocket server."""
        # Start the WebSocket server through MCP server
        await mcp_server.websocket_server.start()

        try:
            # Verify WebSocket server is running
            assert mcp_server.websocket_server.is_running

            # Connect a WebSocket client
            uri = f"ws://{mcp_server.websocket_server.host}:{mcp_server.websocket_server.port}"

            async with websockets.connect(uri) as websocket:
                # Should receive welcome message
                welcome_message = await websocket.recv()
                welcome_data = json.loads(welcome_message)

                assert welcome_data["type"] == "welcome"
                assert "client_id" in welcome_data

                # Verify server info shows client connected
                server_info = mcp_server.websocket_server.get_server_info()
                assert server_info["clients_connected"] == 1

        finally:
            await mcp_server.websocket_server.stop()

    @pytest.mark.asyncio
    async def test_mcp_server_health_check_integration(self, mcp_server):
        """Test MCP server health check with real WebSocket server."""
        # First, stop the WebSocket server to test failure case
        if mcp_server.websocket_server.is_running:
            await mcp_server.websocket_server.stop()

        # Test health check with WebSocket server stopped
        mcp_server.auto_start_websocket = True
        health = await mcp_server._perform_health_check()
        assert health is False  # Should fail because WebSocket server is not running

        # Start WebSocket server
        await mcp_server.websocket_server.start()

        try:
            # Test health check with WebSocket server running
            health = await mcp_server._perform_health_check()
            assert health is True  # Should pass because WebSocket server is running

        finally:
            await mcp_server.websocket_server.stop()

    @pytest.mark.asyncio
    async def test_websocket_connection_cleanup(self, websocket_server):
        """Test that client connections are properly cleaned up."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        # Connect and disconnect a client
        async with websockets.connect(uri) as websocket:
            welcome_message = await websocket.recv()
            welcome_data = json.loads(welcome_message)
            client_id = welcome_data["client_id"]

            # Verify client is in server's client list
            assert client_id in websocket_server.clients
            assert len(websocket_server.clients) == 1

        # Give a moment for cleanup
        await asyncio.sleep(0.1)

        # Verify client was cleaned up after disconnection
        assert len(websocket_server.clients) == 0

    @pytest.mark.asyncio
    async def test_websocket_server_concurrent_connections(self, websocket_server):
        """Test handling of many concurrent connections."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"
        num_clients = 5  # Reduce number of clients to avoid overwhelming the test

        async def client_session(client_id):
            """Individual client session."""
            async with websockets.connect(uri) as websocket:
                # Skip welcome message with timeout
                await asyncio.wait_for(websocket.recv(), timeout=5.0)

                # Send a ping
                ping_message = {"type": "ping", "client_id": client_id}
                await websocket.send(json.dumps(ping_message))

                # Receive pong with timeout
                pong_response = json.loads(
                    await asyncio.wait_for(websocket.recv(), timeout=5.0)
                )
                assert pong_response["type"] == "pong"

                return pong_response["client_id"]

        # Run multiple clients concurrently with timeout
        tasks = [client_session(i) for i in range(num_clients)]
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=30.0)

        # Verify all clients got unique IDs
        assert len(set(results)) == num_clients

        # Verify server stats
        server_info = websocket_server.get_server_info()
        assert server_info["stats"]["total_connections"] >= num_clients

    @pytest.mark.asyncio
    async def test_websocket_server_error_handling(self, websocket_server):
        """Test error handling in WebSocket server."""
        uri = f"ws://{websocket_server.host}:{websocket_server.port}"

        async with websockets.connect(uri) as websocket:
            # Skip welcome message
            await websocket.recv()

            # Test error simulation
            error_message = {"type": "error_test", "error_type": "generic"}
            await websocket.send(json.dumps(error_message))

            error_response = json.loads(await websocket.recv())
            assert error_response["type"] == "error_test_response"
            assert error_response["error_type"] == "generic"

            # Verify server is still responsive after error
            ping_message = {"type": "ping"}
            await websocket.send(json.dumps(ping_message))

            pong_response = json.loads(await websocket.recv())
            assert pong_response["type"] == "pong"
