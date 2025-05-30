import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets

from lightfast_mcp.exceptions import (
    BlenderConnectionError as PhotoshopConnectionError,
)
from lightfast_mcp.exceptions import (
    BlenderMCPError as PhotoshopMCPError,
)
from lightfast_mcp.exceptions import (
    BlenderTimeoutError as PhotoshopTimeoutError,
)
from lightfast_mcp.servers import photoshop_mcp_server
from lightfast_mcp.servers.photoshop_mcp_server import (
    _process_incoming_messages_for_client,
    check_photoshop_connected,
    execute_photoshop_code,
    get_document_info,
    handle_photoshop_client,
    send_to_photoshop,
)

# Mark async tests with asyncio
async_tests = pytest.mark.asyncio


@pytest.fixture
def mock_websocket():
    """Fixture to create a mock WebSocket connection."""
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.closed = False
    mock_ws.remote_address = ("127.0.0.1", 54321)
    return mock_ws


@pytest.fixture
def setup_connected_clients(mock_websocket):
    """Fixture to set up connected clients and clean up after tests."""
    # Store original connected clients and responses
    original_clients = photoshop_mcp_server.connected_clients.copy()
    original_responses = photoshop_mcp_server.responses.copy()
    original_counter = photoshop_mcp_server.command_id_counter

    # Clear the sets and add our mock client
    photoshop_mcp_server.connected_clients.clear()
    photoshop_mcp_server.connected_clients.add(mock_websocket)
    photoshop_mcp_server.responses.clear()
    photoshop_mcp_server.command_id_counter = 0

    yield

    # Restore original state
    photoshop_mcp_server.connected_clients = original_clients
    photoshop_mcp_server.responses = original_responses
    photoshop_mcp_server.command_id_counter = original_counter


@pytest.fixture
def mock_future():
    """Fixture to create a mock Future object."""
    future = asyncio.Future()
    return future


@async_tests
async def test_check_photoshop_connected_with_clients(setup_connected_clients):
    """Test check_photoshop_connected returns True when clients are connected."""
    with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
        result = await check_photoshop_connected()
        assert result is True
        mock_logger.info.assert_any_call(
            "check_photoshop_connected (simplified): connected_clients set contains 1 item(s)."
        )


@async_tests
async def test_check_photoshop_connected_no_clients():
    """Test check_photoshop_connected returns False when no clients are connected."""
    # Store original connected clients
    original_clients = photoshop_mcp_server.connected_clients.copy()

    # Clear the set for this test
    photoshop_mcp_server.connected_clients.clear()

    with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
        result = await check_photoshop_connected()
        assert result is False
        mock_logger.info.assert_called_with(
            "check_photoshop_connected (simplified): No clients in connected_clients set."
        )

    # Restore original state
    photoshop_mcp_server.connected_clients = original_clients


@async_tests
async def test_send_to_photoshop_success():
    """Test send_to_photoshop successfully sends a command and gets a response."""
    # Create a mock client and future
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    mock_future = asyncio.Future()
    mock_response = {"status": "success", "data": {"message": "Command executed"}}
    mock_future.set_result(mock_response)

    # Setup patching for various dependencies
    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch.dict(photoshop_mcp_server.responses, {"cmd_1": mock_future}),
        patch("lightfast_mcp.servers.photoshop_mcp_server.command_id_counter", 0),
        patch("asyncio.wait_for", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
    ):
        # Call the function
        result = await send_to_photoshop("test_command", {"param": "value"})

        # Verify the command was sent correctly
        mock_ws.send.assert_called_once()

        # Verify the result is as expected
        assert result == mock_response


@async_tests
async def test_send_to_photoshop_no_clients():
    """Test send_to_photoshop raises an error when no clients are connected."""
    with patch.object(photoshop_mcp_server, "connected_clients", set()):
        with pytest.raises(PhotoshopConnectionError) as excinfo:
            await send_to_photoshop("test_command", {})

        assert "No Photoshop clients connected" in str(excinfo.value)


@async_tests
async def test_send_to_photoshop_timeout():
    """Test send_to_photoshop handles timeouts properly."""
    # Create a mock client
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("asyncio.wait_for", side_effect=asyncio.TimeoutError("Timeout")),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        with pytest.raises(PhotoshopTimeoutError) as excinfo:
            await send_to_photoshop("test_command", {})

        assert "Timeout waiting for Photoshop response" in str(excinfo.value)
        mock_logger.error.assert_called()


@async_tests
async def test_send_to_photoshop_connection_closed():
    """Test send_to_photoshop handles connection closure properly."""
    # Create a mock client
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Create a real ConnectionClosed exception
    conn_closed = websockets.exceptions.ConnectionClosedError(1000, "Connection closed")
    mock_ws.send = AsyncMock(side_effect=conn_closed)

    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        with pytest.raises(PhotoshopConnectionError) as excinfo:
            await send_to_photoshop("test_command", {})

        assert "Connection to Photoshop lost" in str(excinfo.value)
        mock_logger.error.assert_called()


@async_tests
async def test_send_to_photoshop_multiple_clients():
    """Test send_to_photoshop works with multiple connected clients."""
    # Create multiple mock clients
    mock_ws1 = MagicMock()
    mock_ws1.send = AsyncMock()
    mock_ws1.remote_address = ("127.0.0.1", 54321)

    mock_ws2 = MagicMock()
    mock_ws2.send = AsyncMock()
    mock_ws2.remote_address = ("127.0.0.1", 54322)

    mock_response = {"status": "success", "data": {"message": "Command executed"}}

    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws1, mock_ws2}),
        patch("asyncio.wait_for", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
    ):
        result = await send_to_photoshop("test_command", {"param": "value"})

        # Should use the first client in the set
        assert mock_ws1.send.called or mock_ws2.send.called
        assert result == mock_response


@async_tests
async def test_handle_photoshop_client_successful_connection():
    """Test handle_photoshop_client handles a successful connection."""
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Mock the ping response
    ping_result = {"status": "success", "message": "pong"}

    # Create a mock task that will be cancelled
    mock_task = MagicMock()

    # Mock the task creation and cancellation
    async def mock_create_task(coro):
        """Mock create_task that returns a cancellable task."""
        task = MagicMock()
        task.cancel = MagicMock()
        task.done.return_value = False
        # Simulate waiting on the task and then cancelling
        await asyncio.sleep(0)  # Allow other coroutines to run
        task.cancel()
        raise asyncio.CancelledError()

    connected_clients_set = set()

    with (
        patch.object(photoshop_mcp_server, "connected_clients", connected_clients_set),
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=ping_result),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
        patch("asyncio.create_task", side_effect=mock_create_task),
    ):
        try:
            await handle_photoshop_client(mock_ws)
        except asyncio.CancelledError:
            pass  # Expected when task is cancelled

        # Verify the client was added to connected_clients
        assert mock_ws in connected_clients_set


@async_tests
async def test_handle_photoshop_client_ping_failure():
    """Test handle_photoshop_client handles ping failure."""
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)
    mock_ws.close = AsyncMock()

    # Mock ping to raise an exception
    ping_error = PhotoshopConnectionError("Ping failed")

    connected_clients_set = set()

    with (
        patch.object(photoshop_mcp_server, "connected_clients", connected_clients_set),
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", side_effect=ping_error),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        await handle_photoshop_client(mock_ws)

        # Verify the client was removed from connected_clients
        assert mock_ws not in connected_clients_set
        mock_ws.close.assert_called_once()
        mock_logger.error.assert_called()


@async_tests
async def test_process_incoming_messages_for_client():
    """Test _process_incoming_messages_for_client processes messages correctly."""
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Mock receiving a response message
    response_message = {"command_id": "cmd_1", "status": "success", "data": {"result": "test"}}

    # Set up recv to return the message once, then raise ConnectionClosed
    mock_ws.recv = AsyncMock(
        side_effect=[json.dumps(response_message), websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
    )

    # Create a future for the response
    future = asyncio.Future()
    responses = {"cmd_1": future}

    with (
        patch.dict(photoshop_mcp_server.responses, responses),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

        # Verify the future was resolved with the response
        assert future.done()
        assert future.result() == response_message


@async_tests
async def test_process_incoming_messages_invalid_json():
    """Test _process_incoming_messages_for_client handles invalid JSON."""
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Mock receiving invalid JSON
    mock_ws.recv = AsyncMock(
        side_effect=["invalid json {", websockets.exceptions.ConnectionClosedOK(1000, "Normal closure")]
    )

    with patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger:
        await _process_incoming_messages_for_client(mock_ws, "127.0.0.1:54321")

        # Verify error was logged
        mock_logger.error.assert_called()


@async_tests
async def test_get_document_info_success(setup_connected_clients):
    """Test get_document_info successfully returns document information."""
    # Mock the response from send_to_photoshop
    mock_response = {
        "status": "success",
        "title": "Test Document",
        "width": 800,
        "height": 600,
        "resolution": 72,
        "layerCount": 3,
    }

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
    ):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await get_document_info(ctx=ctx_mock)
        result = json.loads(result_str)

        # Verify the result contains the expected information
        assert result["status"] == "success"
        assert result["title"] == "Test Document"
        assert result["width"] == 800
        assert result["height"] == 600
        assert result["resolution"] == 72
        assert result["layerCount"] == 3
        assert "_connection_info" in result
        assert result["_connection_info"]["connected_clients"] == 1


@async_tests
async def test_get_document_info_no_connection():
    """Test get_document_info handles case when Photoshop is not connected."""
    with patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=False):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await get_document_info(ctx=ctx_mock)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "No Photoshop clients connected" in result["message"]
        assert result["error_type"] == "PhotoshopConnectionError"


@async_tests
async def test_get_document_info_connection_error(setup_connected_clients):
    """Test get_document_info handles connection errors."""
    # Mock send_to_photoshop to raise a connection error
    error = PhotoshopConnectionError("Connection lost")

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", side_effect=error),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await get_document_info(ctx=ctx_mock)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "Connection lost" in result["message"]
        # The error_type in the response is the class name, not the alias
        assert result["error_type"] == "BlenderConnectionError"
        mock_logger.error.assert_called_with("Error getting document info: Connection lost")


@async_tests
async def test_execute_photoshop_code_success(setup_connected_clients):
    """Test execute_photoshop_code successfully executes code and returns result."""
    # JavaScript code to execute
    js_code = "return { layers: app.activeDocument.layers.length };"

    # Mock response from Photoshop
    mock_response = {"status": "success", "data": {"layers": 5}}

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
    ):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=js_code)
        result = json.loads(result_str)

        # Verify the result
        assert result == mock_response


@async_tests
async def test_execute_photoshop_code_no_connection():
    """Test execute_photoshop_code handles case when Photoshop is not connected."""
    js_code = "return { success: true };"

    with patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=False):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=js_code)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "No Photoshop clients connected" in result["message"]
        assert result["error_type"] == "PhotoshopConnectionError"


@async_tests
async def test_execute_photoshop_code_execution_error(setup_connected_clients):
    """Test execute_photoshop_code handles execution errors in Photoshop."""
    # JavaScript code with an error
    js_code = "invalid.syntax.that.will.fail();"

    # Mock an error response from send_to_photoshop
    error = PhotoshopMCPError("JavaScript execution error")

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", side_effect=error),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        # Call the function
        ctx_mock = MagicMock()
        result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=js_code)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "JavaScript execution error" in result["message"]
        # The error_type in the response is the class name, not the alias
        assert result["error_type"] == "BlenderMCPError"
        mock_logger.error.assert_called_with("Error executing Photoshop UXP code: JavaScript execution error")


@async_tests
async def test_execute_jsx_success(setup_connected_clients):
    """Test execute_jsx successfully executes JSX code and returns result."""
    # JSX code to execute
    jsx_code = "app.activeDocument.layers.length"

    # Mock response from Photoshop
    mock_response = {"status": "success", "result": 5}

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        # Call the function
        from lightfast_mcp.servers.photoshop_mcp_server import execute_jsx

        ctx_mock = MagicMock()
        result_str = await execute_jsx(ctx=ctx_mock, jsx_code=jsx_code)
        result = json.loads(result_str)

        # Verify the result
        assert result == mock_response

        # Verify the correct command was sent
        mock_logger.info.assert_any_call(f"Executing execute_jsx command (deprecated): {jsx_code[:100]}...")


@async_tests
async def test_execute_jsx_no_connection():
    """Test execute_jsx handles case when Photoshop is not connected."""
    jsx_code = "app.activeDocument.artLayers.add()"

    with patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=False):
        # Call the function
        from lightfast_mcp.servers.photoshop_mcp_server import execute_jsx

        ctx_mock = MagicMock()
        result_str = await execute_jsx(ctx=ctx_mock, jsx_code=jsx_code)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "No Photoshop clients connected" in result["message"]
        assert result["error_type"] == "PhotoshopConnectionError"


@async_tests
async def test_execute_jsx_execution_error(setup_connected_clients):
    """Test execute_jsx handles execution errors in Photoshop."""
    # JSX code with an error
    jsx_code = "invalidCommand()"

    # Mock an error response from send_to_photoshop
    error = PhotoshopMCPError("JSX execution error")

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", side_effect=error),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger") as mock_logger,
    ):
        # Call the function
        from lightfast_mcp.servers.photoshop_mcp_server import execute_jsx

        ctx_mock = MagicMock()
        result_str = await execute_jsx(ctx=ctx_mock, jsx_code=jsx_code)
        result = json.loads(result_str)

        # Verify the error response
        assert result["status"] == "error"
        assert "JSX execution error" in result["message"]
        # The error_type in the response is the class name, not the alias
        assert result["error_type"] == "BlenderMCPError"
        mock_logger.error.assert_called_with("Error executing JSX code: JSX execution error")


# Additional comprehensive tests for better coverage


@async_tests
async def test_send_to_photoshop_with_empty_params():
    """Test send_to_photoshop works with empty or None parameters."""
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    mock_response = {"status": "success"}

    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("asyncio.wait_for", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
    ):
        # Test with None params
        result = await send_to_photoshop("test_command", None)
        assert result == mock_response

        # Test with empty dict params
        result = await send_to_photoshop("test_command", {})
        assert result == mock_response


@async_tests
async def test_command_id_counter_increment():
    """Test that command_id_counter increments properly."""
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    original_counter = photoshop_mcp_server.command_id_counter

    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("asyncio.wait_for", return_value={"status": "success"}),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
    ):
        # Send multiple commands
        await send_to_photoshop("command1", {})
        await send_to_photoshop("command2", {})

        # Verify counter incremented
        assert photoshop_mcp_server.command_id_counter > original_counter


@async_tests
async def test_execute_photoshop_code_with_complex_js():
    """Test execute_photoshop_code with complex JavaScript code."""
    complex_js = """
    const doc = app.activeDocument;
    const layers = doc.layers;
    const result = {
        layerCount: layers.length,
        documentName: doc.name,
        width: doc.width.value,
        height: doc.height.value
    };
    return result;
    """

    mock_response = {
        "status": "success",
        "data": {"layerCount": 10, "documentName": "test.psd", "width": 1920, "height": 1080},
    }

    with (
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
        patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
    ):
        ctx_mock = MagicMock()
        result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=complex_js)
        result = json.loads(result_str)

        assert result == mock_response
        assert result["data"]["layerCount"] == 10
        assert result["data"]["documentName"] == "test.psd"
