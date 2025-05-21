import json
import socket
from unittest.mock import MagicMock, patch

import pytest

# Assuming your exceptions and server are structured as previously discussed
from lightfast_mcp.servers import blender_mcp_server
from lightfast_mcp.servers.blender_mcp_server import (
    BlenderCommandError,
    BlenderConnection,
    BlenderConnectionError,
    BlenderResponseError,
    BlenderTimeoutError,
    execute_command,
    get_state,
)

# Only mark async tests with asyncio
async_tests = pytest.mark.asyncio


@pytest.fixture
def mock_blender_connection():
    """Fixture to create a mock BlenderConnection object."""
    mock_conn = MagicMock(spec=BlenderConnection)
    # Mock send_command to be an async function if it's called via run_in_executor
    # or a regular mock if called directly in synchronous test parts (though tools are async)
    mock_conn.send_command = MagicMock()

    # Add additional properties needed for the connection info in get_state
    mock_conn.host = "localhost"
    mock_conn.port = 9876
    mock_conn.sock = MagicMock(spec=socket.socket)

    # Set up _is_ping_check attribute to avoid AttributeError
    mock_conn._is_ping_check = False

    return mock_conn


@pytest.fixture(autouse=True)
def patch_get_blender_connection(mock_blender_connection):
    """Autouse fixture to patch get_blender_connection globally for all tests in this module."""
    # Patch within the module where it's looked up by the tools
    with patch(
        "lightfast_mcp.servers.blender_mcp_server.get_blender_connection", return_value=mock_blender_connection
    ) as patched:
        yield patched


@pytest.fixture
def patch_time():
    """Fixture to patch time.time() for consistent timestamps."""
    with patch("time.time", return_value=12345.0) as mock_time:
        yield mock_time


@async_tests
async def test_get_state_success(mock_blender_connection, patch_time):
    """Test get_state successfully returns scene info."""
    mock_response = {"objects": 10, "active_camera": "Camera.001"}
    mock_blender_connection.send_command.return_value = mock_response

    # Call the tool function (which is async)
    ctx_mock = MagicMock()  # Create a basic context mock
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    # Verify the correct command was sent
    mock_blender_connection.send_command.assert_called_once_with("get_scene_info")

    # Check for connection info in the result
    assert "_connection_info" in result
    connection_info = result["_connection_info"]
    assert connection_info["connected"] is True
    assert connection_info["host"] == "localhost"
    assert connection_info["port"] == 9876
    assert connection_info["connection_time"] == 12345.0

    # Also check for the original response fields
    assert result["objects"] == 10
    assert result["active_camera"] == "Camera.001"


@async_tests
async def test_get_state_connection_error(mock_blender_connection):
    """Test get_state handles BlenderConnectionError."""
    mock_blender_connection.send_command.side_effect = BlenderConnectionError("Test connection failed")

    ctx_mock = MagicMock()
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Test connection failed" in result["error"]
    assert result.get("type") == "BlenderConnectionError"


@async_tests
async def test_get_state_command_error(mock_blender_connection):
    """Test get_state handles BlenderCommandError."""
    mock_blender_connection.send_command.side_effect = BlenderCommandError("Blender internal error")

    ctx_mock = MagicMock()
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Blender internal error" in result["error"]
    assert result.get("type") == "BlenderCommandError"


@async_tests
async def test_get_state_response_error(mock_blender_connection):
    """Test get_state handles BlenderResponseError (e.g. malformed JSON from underlying layers)."""
    # This might happen if send_command itself raises BlenderResponseError due to malformed JSON
    mock_blender_connection.send_command.side_effect = BlenderResponseError("Malformed JSON from Blender")

    ctx_mock = MagicMock()
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Malformed JSON from Blender" in result["error"]
    assert result.get("type") == "BlenderResponseError"


@async_tests
async def test_get_state_timeout_error(mock_blender_connection):
    """Test get_state handles BlenderTimeoutError."""
    mock_blender_connection.send_command.side_effect = BlenderTimeoutError("Timeout waiting for Blender scene info")

    ctx_mock = MagicMock()
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Timeout waiting for Blender scene info" in result["error"]
    assert result.get("type") == "BlenderTimeoutError"


@async_tests
async def test_get_state_unexpected_error(mock_blender_connection):
    """Test get_state handles an unexpected generic error."""
    mock_blender_connection.send_command.side_effect = RuntimeError("Something totally unexpected")

    ctx_mock = MagicMock()
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Unexpected server error: Something totally unexpected" in result["error"]
    assert result.get("type") == "RuntimeError"  # The tool converts it to a generic error string


@async_tests
async def test_execute_command_success(mock_blender_connection):
    """Test execute_command successfully executes code and returns result."""
    code_to_run = "bpy.ops.mesh.primitive_cube_add()"
    mock_blender_response = {"executed": True, "result": "Cube added"}
    mock_blender_connection.send_command.return_value = mock_blender_response

    ctx_mock = MagicMock()
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    mock_blender_connection.send_command.assert_called_once_with("execute_code", {"code": code_to_run})
    assert result == mock_blender_response


@async_tests
async def test_execute_command_connection_error(mock_blender_connection):
    """Test execute_command handles BlenderConnectionError."""
    code_to_run = "print('hello')"
    mock_blender_connection.send_command.side_effect = BlenderConnectionError("Connection lost during exec")

    ctx_mock = MagicMock()
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Command Execution Error: Connection lost during exec" in result["error"]
    assert result.get("type") == "BlenderConnectionError"


@async_tests
async def test_execute_command_blender_side_error(mock_blender_connection):
    """Test execute_command handles errors reported by Blender (BlenderCommandError)."""
    code_to_run = "invalid.code()"
    # This error is raised by send_command if the response JSON indicates an error status
    mock_blender_connection.send_command.side_effect = BlenderCommandError(
        "bpy.context.object.data.vertices: 1-element tuple"
    )

    ctx_mock = MagicMock()
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Command Execution Error: bpy.context.object.data.vertices: 1-element tuple" in result["error"]
    assert result.get("type") == "BlenderCommandError"


@async_tests
async def test_execute_command_unexpected_error(mock_blender_connection):
    """Test execute_command handles an unexpected generic error from send_command."""
    code_to_run = "import time; time.sleep(0.1)"
    mock_blender_connection.send_command.side_effect = ValueError("Unexpected value issue")

    ctx_mock = MagicMock()
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Unexpected server error during command execution: Unexpected value issue" in result["error"]
    assert result.get("type") == "ValueError"


# Additional tests for new functionality


@pytest.fixture
def mock_socket():
    """Fixture to mock socket operations"""
    with patch("socket.socket") as mock_socket_cls:
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        yield mock_sock


def test_check_blender_running_success(mock_socket):
    """Test check_blender_running when Blender is available"""
    # Configure the socket mock to simulate successful connection
    with patch("lightfast_mcp.servers.blender_mcp_server.logger") as mock_logger:
        result = blender_mcp_server.check_blender_running()
        assert result is True
        mock_logger.info.assert_any_call("Checking if Blender is running on localhost:9876...")
        mock_logger.info.assert_any_call("Successfully connected to Blender on localhost:9876")


def test_check_blender_running_connection_refused(mock_socket):
    """Test check_blender_running when connection is refused"""
    # Configure the socket mock to simulate connection refused
    mock_socket.connect.side_effect = ConnectionRefusedError("Connection refused")

    with patch("lightfast_mcp.servers.blender_mcp_server.logger") as mock_logger:
        result = blender_mcp_server.check_blender_running()
        assert result is False
        mock_logger.warning.assert_any_call("Could not connect to Blender: ConnectionRefusedError: Connection refused")


def test_find_blender_port_success(mock_socket):
    """Test find_blender_port when it successfully finds Blender"""
    # Configure connect_ex to return 0 (success) for port 9876
    mock_socket.connect_ex.return_value = 0

    # Configure the second connection (for verification) to successfully return a valid response
    mock_socket.recv.return_value = b'{"status": "success", "result": {"message": "pong"}}'

    with patch("lightfast_mcp.servers.blender_mcp_server.logger") as mock_logger:
        result = blender_mcp_server.find_blender_port()
        assert result == 9876
        mock_logger.info.assert_any_call("Verified Blender running on port 9876")


def test_find_blender_port_failure(mock_socket):
    """Test find_blender_port when it cannot find Blender"""
    # Configure connect_ex to return non-zero (failure) for all ports
    mock_socket.connect_ex.return_value = 1

    with patch("lightfast_mcp.servers.blender_mcp_server.logger") as mock_logger:
        result = blender_mcp_server.find_blender_port(start_port=9876, end_port=9878)
        assert result is None
        mock_logger.warning.assert_called_with("No Blender server found on ports 9876-9878")
