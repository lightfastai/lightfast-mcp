import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from lightfast_mcp.servers import photoshop_mcp_server
from lightfast_mcp.servers.photoshop_mcp_server import (
    handle_photoshop_client,
    server_lifespan,
    start_websocket_server,
)

# Mark async tests with asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def mock_fastmcp_server():
    """Fixture to create a mock FastMCP server."""
    mock_server = MagicMock()
    mock_server.name = "PhotoshopMCPServer"
    return mock_server


class TestPhotoshopIntegration:
    """Integration tests for the Photoshop MCP server."""

    async def test_server_lifespan_context_manager(self, mock_fastmcp_server):
        """Test that server_lifespan properly manages WebSocket server lifecycle."""
        mock_ws_server = MagicMock()
        mock_ws_server.close = AsyncMock()
        mock_ws_server.wait_closed = AsyncMock()

        with patch("lightfast_mcp.servers.photoshop_mcp_server.start_websocket_server", return_value=mock_ws_server):
            async with server_lifespan(mock_fastmcp_server) as context:
                # Verify context contains server info
                assert "websocket_server" in context
                assert "port" in context
                assert "host" in context
                assert context["port"] == 8765
                assert context["host"] == "localhost"

            # Verify cleanup was called
            mock_ws_server.close.assert_called_once()
            mock_ws_server.wait_closed.assert_called_once()

    async def test_websocket_server_start_and_stop(self):
        """Test WebSocket server can start and stop properly."""
        # Mock websockets.serve to return a mock server
        mock_server = MagicMock()
        mock_server.close = AsyncMock()
        mock_server.wait_closed = AsyncMock()

        with patch("websockets.serve", return_value=mock_server) as mock_serve:
            server = await start_websocket_server()

            # Verify websockets.serve was called with correct parameters
            mock_serve.assert_called_once_with(handle_photoshop_client, "localhost", 8765)

            # Verify returned server
            assert server == mock_server

    async def test_concurrent_client_connections(self):
        """Test handling multiple concurrent client connections."""
        # Create multiple mock clients
        mock_clients = []
        for i in range(3):
            mock_ws = MagicMock()
            mock_ws.remote_address = ("127.0.0.1", 54321 + i)
            mock_ws.send = AsyncMock()
            mock_ws.close = AsyncMock()
            mock_clients.append(mock_ws)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()

        try:
            # Clear connected clients
            photoshop_mcp_server.connected_clients.clear()

            # Mock successful ping for all clients
            ping_response = {"status": "success", "message": "pong"}

            # Mock create_task to simulate message processing tasks
            async def mock_create_task(coro):
                # Just let the coroutine run briefly then cancel
                task = MagicMock()
                task.cancel = MagicMock()
                await asyncio.sleep(0.01)  # Brief delay
                raise asyncio.CancelledError()

            with (
                patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=ping_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
                patch("asyncio.create_task", side_effect=mock_create_task),
            ):
                # Start handling clients concurrently
                tasks = []
                for client in mock_clients:
                    task = asyncio.create_task(handle_photoshop_client(client))
                    tasks.append(task)

                # Wait for all tasks to complete (they should be cancelled)
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All should have been cancelled
                for result in results:
                    assert isinstance(result, asyncio.CancelledError) or result is None

                # Verify all clients were added to connected_clients
                assert len(photoshop_mcp_server.connected_clients) == len(mock_clients)
                for client in mock_clients:
                    assert client in photoshop_mcp_server.connected_clients

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients

    async def test_client_connection_and_disconnection_lifecycle(self):
        """Test the full lifecycle of client connection and disconnection."""
        mock_ws = MagicMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)
        mock_ws.send = AsyncMock()
        mock_ws.recv = AsyncMock()
        mock_ws.close = AsyncMock()

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()

        try:
            # Clear state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.responses.clear()

            # Mock successful ping
            ping_response = {"status": "success", "message": "pong"}

            # Mock receiving a message then disconnection
            response_message = {"command_id": "cmd_1", "status": "success", "data": {"result": "test"}}

            mock_ws.recv.side_effect = [
                json.dumps(response_message),
                websockets.exceptions.ConnectionClosedOK(1000, "Normal closure"),
            ]

            with (
                patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=ping_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Create a future to resolve
                future = asyncio.Future()
                photoshop_mcp_server.responses["cmd_1"] = future

                # Handle the client (this will process the message and then disconnect)
                try:
                    await handle_photoshop_client(mock_ws)
                except asyncio.CancelledError:
                    pass  # Expected

                # Verify the future was resolved
                assert future.done()
                assert future.result() == response_message

                # Verify client was initially added
                assert mock_ws in photoshop_mcp_server.connected_clients

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses

    async def test_command_response_correlation(self):
        """Test that commands are properly correlated with their responses."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()
            photoshop_mcp_server.command_id_counter = 0

            # Mock multiple responses
            responses = [
                {"command_id": "cmd_1", "status": "success", "data": {"result": "first"}},
                {"command_id": "cmd_2", "status": "success", "data": {"result": "second"}},
                {"command_id": "cmd_3", "status": "success", "data": {"result": "third"}},
            ]

            # Use separate mock for asyncio.wait_for to return different responses
            async def mock_wait_for(future, timeout):
                # Return the appropriate response based on the command_id
                command_id = None
                for cmd_id, fut in photoshop_mcp_server.responses.items():
                    if fut == future:
                        command_id = cmd_id
                        break

                if command_id == "cmd_1":
                    return responses[0]
                elif command_id == "cmd_2":
                    return responses[1]
                elif command_id == "cmd_3":
                    return responses[2]
                else:
                    return {"status": "success"}

            with (
                patch("asyncio.wait_for", side_effect=mock_wait_for),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Send multiple commands
                from lightfast_mcp.servers.photoshop_mcp_server import send_to_photoshop

                results = await asyncio.gather(
                    send_to_photoshop("command1", {"param": "value1"}),
                    send_to_photoshop("command2", {"param": "value2"}),
                    send_to_photoshop("command3", {"param": "value3"}),
                )

                # Verify all commands were sent
                assert mock_ws.send.call_count == 3

                # Verify responses are correctly correlated
                assert len(results) == 3
                for i, result in enumerate(results):
                    assert result["status"] == "success"

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_stress_multiple_commands(self):
        """Test handling multiple rapid commands."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()
            photoshop_mcp_server.command_id_counter = 0

            command_count = 10
            mock_response = {"status": "success", "data": {"result": "test"}}

            with (
                patch("asyncio.wait_for", return_value=mock_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Send many commands concurrently
                from lightfast_mcp.servers.photoshop_mcp_server import send_to_photoshop

                start_time = time.time()
                tasks = [send_to_photoshop(f"command{i}", {"param": f"value{i}"}) for i in range(command_count)]

                results = await asyncio.gather(*tasks)
                end_time = time.time()

                # Verify all commands completed successfully
                assert len(results) == command_count
                for result in results:
                    assert result["status"] == "success"

                # Verify performance (should complete quickly)
                duration = end_time - start_time
                assert duration < 1.0  # Should complete within 1 second

                # Verify all commands were sent
                assert mock_ws.send.call_count == command_count

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_error_recovery_after_client_disconnect(self):
        """Test that the server can recover after a client disconnects."""
        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()

        try:
            # Clear connected clients
            photoshop_mcp_server.connected_clients.clear()

            # Create first client that will disconnect
            mock_ws1 = MagicMock()
            mock_ws1.remote_address = ("127.0.0.1", 54321)
            mock_ws1.send = AsyncMock(side_effect=websockets.exceptions.ConnectionClosedError(1000, "Disconnected"))

            # Add to connected clients
            photoshop_mcp_server.connected_clients.add(mock_ws1)

            # Try to send command to disconnected client
            from lightfast_mcp.exceptions import BlenderConnectionError as PhotoshopConnectionError
            from lightfast_mcp.servers.photoshop_mcp_server import send_to_photoshop

            with pytest.raises(PhotoshopConnectionError):
                await send_to_photoshop("test_command", {})

            # Now add a new working client
            mock_ws2 = MagicMock()
            mock_ws2.remote_address = ("127.0.0.1", 54322)
            mock_ws2.send = AsyncMock()

            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws2)

            # Mock successful response
            mock_response = {"status": "success", "data": {"result": "recovered"}}

            with (
                patch("asyncio.wait_for", return_value=mock_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Should work with new client
                result = await send_to_photoshop("recovery_command", {})
                assert result["status"] == "success"
                assert result["data"]["result"] == "recovered"

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
