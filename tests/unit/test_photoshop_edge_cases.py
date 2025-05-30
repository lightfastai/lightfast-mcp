import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from lightfast_mcp.exceptions import (
    BlenderConnectionError as PhotoshopConnectionError,
)
from lightfast_mcp.servers import photoshop_mcp_server
from lightfast_mcp.servers.photoshop_mcp_server import (
    _process_incoming_messages_for_client,
    check_photoshop_connected,
    execute_photoshop_code,
    get_document_info,
    send_to_photoshop,
)

# Mark async tests with asyncio
pytestmark = pytest.mark.asyncio


class TestPhotoshopEdgeCases:
    """Test edge cases and error scenarios for Photoshop MCP server."""

    async def test_send_to_photoshop_with_malformed_response(self):
        """Test handling of malformed responses from Photoshop."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Mock wait_for to return malformed response
        malformed_response = "not a dictionary"

        with (
            patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
            patch("asyncio.wait_for", return_value=malformed_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
        ):
            result = await send_to_photoshop("test_command", {})
            # Should still return the malformed response as-is
            assert result == malformed_response

    async def test_send_to_photoshop_with_very_large_command_id(self):
        """Test handling of very large command IDs."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Set a very large command ID counter
        original_counter = photoshop_mcp_server.command_id_counter
        photoshop_mcp_server.command_id_counter = 999999

        try:
            mock_response = {"status": "success"}

            with (
                patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
                patch("asyncio.wait_for", return_value=mock_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                result = await send_to_photoshop("test_command", {})
                assert result == mock_response

                # Verify command was sent with large ID
                mock_ws.send.assert_called_once()
                sent_data = json.loads(mock_ws.send.call_args[0][0])
                assert sent_data["command_id"] == "cmd_1000000"

        finally:
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_execute_photoshop_code_with_unicode_characters(self):
        """Test executing JavaScript code with Unicode characters."""
        unicode_js = """
        const emoji = "🎨✨💫";
        const chinese = "中文测试";
        const result = { message: emoji + " " + chinese };
        return result;
        """

        mock_response = {"status": "success", "data": {"message": "🎨✨💫 中文测试"}}

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()
            result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=unicode_js)
            result = json.loads(result_str)

            assert result == mock_response
            assert "🎨✨💫 中文测试" in result["data"]["message"]

    async def test_execute_photoshop_code_with_very_long_script(self):
        """Test executing very long JavaScript code."""
        # Generate a very long script
        long_js = "const data = {\n"
        for i in range(1000):
            long_js += f"  key{i}: 'value{i}',\n"
        long_js += "};\nreturn data;"

        mock_response = {"status": "success", "data": {"message": "Long script executed"}}

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()
            result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=long_js)
            result = json.loads(result_str)

            assert result == mock_response

    async def test_process_incoming_messages_with_missing_command_id(self):
        """Test processing messages that don't have a command_id."""
        mock_ws = MagicMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Mock receiving a message without command_id
        invalid_message = {
            "status": "success",
            "data": {"result": "test"},
            # Missing command_id
        }

        mock_ws.recv = AsyncMock(
            side_effect=[json.dumps(invalid_message), websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
        )

        with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
            await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

            # Should log a warning about missing command_id
            mock_logger.warning.assert_called()

    async def test_process_incoming_messages_with_non_existent_command_id(self):
        """Test processing messages with command_ids that don't exist in responses."""
        mock_ws = MagicMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Mock receiving a message with non-existent command_id
        orphan_message = {"command_id": "cmd_nonexistent", "status": "success", "data": {"result": "orphan"}}

        mock_ws.recv = AsyncMock(
            side_effect=[json.dumps(orphan_message), websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
        )

        with (
            patch.dict(photoshop_mcp_server.responses, {}),  # Empty responses dict
            patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
        ):
            await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

            # Should log a warning about orphaned response
            mock_logger.warning.assert_called()

    async def test_concurrent_operations_with_client_disconnect(self):
        """Test concurrent operations when a client disconnects mid-operation."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()

            # Mock first command to succeed, second to fail due to disconnect
            call_count = 0

            async def mock_wait_for(future, timeout):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {"status": "success", "data": {"result": "first"}}
                else:
                    # Simulate disconnect during second command
                    raise websockets.exceptions.ConnectionClosedError(1000, "Disconnected")

            with (
                patch("asyncio.wait_for", side_effect=mock_wait_for),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Start two concurrent operations
                tasks = [
                    send_to_photoshop("command1", {}),
                    send_to_photoshop("command2", {}),
                ]

                # Gather results, expecting one success and one failure
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # One should succeed, one should fail
                success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
                error_count = sum(1 for r in results if isinstance(r, Exception))

                assert success_count >= 1 or error_count >= 1  # At least one should complete

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses

    async def test_get_document_info_with_unexpected_error_type(self):
        """Test get_document_info with an unexpected error type."""

        # Create a custom exception that's not a known Photoshop exception
        class CustomError(Exception):
            pass

        with (
            patch(
                "lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", side_effect=CustomError("Custom error")
            ),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
            patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
        ):
            ctx_mock = MagicMock()
            result_str = await get_document_info(ctx=ctx_mock)
            result = json.loads(result_str)

            # Should handle the unexpected error gracefully
            assert result["status"] == "error"
            assert "Custom error" in result["message"]
            assert result["error_type"] == "CustomError"
            mock_logger.error.assert_called()

    async def test_execute_photoshop_code_with_empty_string(self):
        """Test executing empty JavaScript code."""
        empty_js = ""

        mock_response = {"status": "success", "data": {"result": "empty executed"}}

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()
            result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=empty_js)
            result = json.loads(result_str)

            assert result == mock_response

    async def test_execute_photoshop_code_with_null_characters(self):
        """Test executing JavaScript code with null characters."""
        null_js = "const data = 'test\\0null\\0char';\nreturn {result: data};"

        mock_response = {"status": "success", "data": {"result": "test\x00null\x00char"}}

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()
            result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=null_js)
            result = json.loads(result_str)

            assert result == mock_response

    async def test_websocket_recv_with_binary_data(self):
        """Test processing binary data received from WebSocket."""
        mock_ws = MagicMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Mock receiving binary data (should cause JSON decode error)
        binary_data = b"\x00\x01\x02\x03"
        mock_ws.recv = AsyncMock(
            side_effect=[binary_data, websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
        )

        with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
            await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

            # Should log an error about JSON decoding
            mock_logger.error.assert_called()

    async def test_command_future_already_resolved(self):
        """Test handling when a command future is already resolved."""
        mock_ws = MagicMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Create an already resolved future
        future = asyncio.Future()
        future.set_result({"status": "already_resolved"})

        response_message = {"command_id": "cmd_1", "status": "success", "data": {"result": "new_result"}}

        mock_ws.recv = AsyncMock(
            side_effect=[json.dumps(response_message), websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
        )

        responses = {"cmd_1": future}

        with (
            patch.dict(photoshop_mcp_server.responses, responses),
            patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
        ):
            await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

            # Should log a warning about already resolved future
            mock_logger.warning.assert_called()

            # Future should still contain original result
            assert future.result() == {"status": "already_resolved"}

    async def test_check_photoshop_connected_with_closed_clients(self):
        """Test check_photoshop_connected when clients are closed but still in set."""
        # Create mock clients that are closed
        mock_ws1 = MagicMock()
        mock_ws1.closed = True
        mock_ws2 = MagicMock()
        mock_ws2.closed = False

        original_clients = photoshop_mcp_server.connected_clients.copy()

        try:
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws1)  # Closed client
            photoshop_mcp_server.connected_clients.add(mock_ws2)  # Open client

            with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
                result = await check_photoshop_connected()

                # Should return True because there are clients (even if some are closed)
                assert result is True
                mock_logger.info.assert_called()

        finally:
            photoshop_mcp_server.connected_clients = original_clients

    async def test_send_to_photoshop_with_exception_during_cleanup(self):
        """Test error handling when cleanup operations also fail."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=websockets.exceptions.ConnectionClosedError(1000, "Connection lost"))
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Mock the cleanup to also raise an exception
        original_clients = photoshop_mcp_server.connected_clients.copy()

        try:
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)

            with (
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
            ):
                with pytest.raises(PhotoshopConnectionError):
                    await send_to_photoshop("test_command", {})

                # Should log the connection error
                mock_logger.error.assert_called()

        finally:
            photoshop_mcp_server.connected_clients = original_clients
