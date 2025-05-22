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
from lightfast_mcp.servers import photoshop_mcp_server
from lightfast_mcp.servers.photoshop_mcp_server import (
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
@pytest.mark.skip(reason="TODO: Fix issue with TimeoutError mocking")
async def test_send_to_photoshop_timeout():
    """Test send_to_photoshop handles timeouts properly."""
    # Create a mock client
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Create a real exception instance
    timeout_error = TimeoutError()

    # Mock wait_for to raise the TimeoutError
    # Also mock the PhotoshopTimeoutError and logger so we can test cleanly
    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("asyncio.wait_for", side_effect=timeout_error),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
        patch("lightfast_mcp.servers.photoshop_mcp_server.PhotoshopTimeoutError") as mock_timeout_exc,
    ):
        # Configure the mock exception to be raised directly
        mock_instance = mock_timeout_exc.return_value

        # The test will now just expect an exception of type mock_timeout_exc
        with pytest.raises(Exception) as excinfo:
            await send_to_photoshop("test_command", {})

        # Verify the mock was called with the right message
        mock_timeout_exc.assert_called_once()
        assert "Timeout waiting for Photoshop response" in mock_timeout_exc.call_args[0][0]


@async_tests
@pytest.mark.skip(reason="TODO: Fix issue with ConnectionClosedError initialization")
async def test_send_to_photoshop_connection_closed():
    """Test send_to_photoshop handles connection closure properly."""
    # Create a mock client
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Use a real ConnectionClosed exception
    conn_closed = websockets.exceptions.ConnectionClosedError(1000, "Connection closed")

    # Set up the mock to raise the exception
    mock_ws.send = AsyncMock(side_effect=conn_closed)

    # Setup patching for various dependencies
    with (
        patch.object(photoshop_mcp_server, "connected_clients", {mock_ws}),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
        patch("lightfast_mcp.servers.photoshop_mcp_server.PhotoshopConnectionError") as mock_conn_exc,
    ):
        # Configure the mock exception to be raised directly
        mock_instance = mock_conn_exc.return_value

        # The test will now just expect an exception of type mock_conn_exc
        with pytest.raises(Exception) as excinfo:
            await send_to_photoshop("test_command", {})

        # Verify the mock was called with the right message
        mock_conn_exc.assert_called_once()
        assert "Connection to Photoshop lost" in mock_conn_exc.call_args[0][0]


@async_tests
@pytest.mark.skip(reason="TODO: Fix issue with await mock_handler_task not raising CancelledError")
async def test_handle_photoshop_client_successful_connection():
    """Test handle_photoshop_client handles a successful connection."""
    # Create mock objects
    mock_ws = MagicMock()
    mock_ws.remote_address = ("127.0.0.1", 54321)

    # Create a real task for the _process_incoming_messages_for_client function
    mock_handler_task = MagicMock()
    mock_handler_task.done.return_value = False

    # Create a mock coroutine for message_handler_task.wait()
    async def mock_wait():
        # This will be awaited by handle_photoshop_client
        # Raising CancelledError here will simulate cancellation
        raise asyncio.CancelledError()

    # Attach the mock coroutine to the task
    mock_handler_task.__await__ = mock_wait().__await__

    # Set up successful ping response
    ping_result = {"status": "success", "message": "pong"}

    # Empty set for connected_clients that we can modify
    connected_clients_set = set()

    with (
        patch.object(photoshop_mcp_server, "connected_clients", connected_clients_set),
        patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=ping_result),
        patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
        patch("asyncio.create_task", return_value=mock_handler_task),
    ):
        # The function should add mock_ws to the connected_clients set
        # Then it will await mock_handler_task, which will raise CancelledError
        with pytest.raises(asyncio.CancelledError):
            await handle_photoshop_client(mock_ws)

        # Verify the client was added to connected_clients
        assert mock_ws in connected_clients_set


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
