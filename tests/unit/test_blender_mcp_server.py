import json
from unittest.mock import MagicMock, patch

import pytest

# Assuming your exceptions and server are structured as previously discussed
from lightfast_mcp.servers import blender_mcp_server
from lightfast_mcp.servers.blender_mcp_server import (
    BlenderCommandError,
    BlenderConnectionError,
    BlenderResponseError,
    BlenderTimeoutError,
    execute_command,
    get_state,
)

# Basic pytest marker for async functions
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_blender_connection():
    """Fixture to create a mock BlenderConnection object."""
    mock_conn = MagicMock(spec=blender_mcp_server.BlenderConnection)
    # Mock send_command to be an async function if it's called via run_in_executor
    # or a regular mock if called directly in synchronous test parts (though tools are async)
    mock_conn.send_command = MagicMock()
    return mock_conn


@pytest.fixture(autouse=True)
def patch_get_blender_connection(mock_blender_connection):
    """Autouse fixture to patch get_blender_connection globally for all tests in this module."""
    # Patch within the module where it's looked up by the tools
    with patch(
        "lightfast_mcp.servers.blender_mcp_server.get_blender_connection", return_value=mock_blender_connection
    ) as patched:
        yield patched


async def test_get_state_success(mock_blender_connection):
    """Test get_state successfully returns scene info."""
    mock_response = {"objects": 10, "active_camera": "Camera.001"}
    mock_blender_connection.send_command.return_value = mock_response

    # Call the tool function (which is async)
    ctx_mock = None  # Context is not used by this simplified tool
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    mock_blender_connection.send_command.assert_called_once_with("get_scene_info")
    assert result == mock_response


async def test_get_state_connection_error(mock_blender_connection):
    """Test get_state handles BlenderConnectionError."""
    mock_blender_connection.send_command.side_effect = BlenderConnectionError("Test connection failed")

    ctx_mock = None
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Test connection failed" in result["error"]
    assert result.get("type") == "BlenderConnectionError"


async def test_get_state_command_error(mock_blender_connection):
    """Test get_state handles BlenderCommandError."""
    mock_blender_connection.send_command.side_effect = BlenderCommandError("Blender internal error")

    ctx_mock = None
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Blender internal error" in result["error"]
    assert result.get("type") == "BlenderCommandError"


async def test_get_state_response_error(mock_blender_connection):
    """Test get_state handles BlenderResponseError (e.g. malformed JSON from underlying layers)."""
    # This might happen if send_command itself raises BlenderResponseError due to malformed JSON
    mock_blender_connection.send_command.side_effect = BlenderResponseError("Malformed JSON from Blender")

    ctx_mock = None
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Malformed JSON from Blender" in result["error"]
    assert result.get("type") == "BlenderResponseError"


async def test_get_state_timeout_error(mock_blender_connection):
    """Test get_state handles BlenderTimeoutError."""
    mock_blender_connection.send_command.side_effect = BlenderTimeoutError("Timeout waiting for Blender scene info")

    ctx_mock = None
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Interaction Error: Timeout waiting for Blender scene info" in result["error"]
    assert result.get("type") == "BlenderTimeoutError"


async def test_get_state_unexpected_error(mock_blender_connection):
    """Test get_state handles an unexpected generic error."""
    mock_blender_connection.send_command.side_effect = RuntimeError("Something totally unexpected")

    ctx_mock = None
    result_str = await get_state(ctx=ctx_mock)
    result = json.loads(result_str)

    assert "error" in result
    assert "Unexpected server error: Something totally unexpected" in result["error"]
    assert result.get("type") == "RuntimeError"  # The tool converts it to a generic error string


async def test_execute_command_success(mock_blender_connection):
    """Test execute_command successfully executes code and returns result."""
    code_to_run = "bpy.ops.mesh.primitive_cube_add()"
    mock_blender_response = {"status": "success", "message": "Cube added"}
    mock_blender_connection.send_command.return_value = mock_blender_response

    ctx_mock = None
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    mock_blender_connection.send_command.assert_called_once_with("execute_code", {"code": code_to_run})
    assert result == mock_blender_response


async def test_execute_command_connection_error(mock_blender_connection):
    """Test execute_command handles BlenderConnectionError."""
    code_to_run = "print('hello')"
    mock_blender_connection.send_command.side_effect = BlenderConnectionError("Connection lost during exec")

    ctx_mock = None
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Command Execution Error: Connection lost during exec" in result["error"]
    assert result.get("type") == "BlenderConnectionError"


async def test_execute_command_blender_side_error(mock_blender_connection):
    """Test execute_command handles errors reported by Blender (BlenderCommandError)."""
    code_to_run = "invalid.code()"
    # This error is raised by send_command if the response JSON indicates an error status
    mock_blender_connection.send_command.side_effect = BlenderCommandError(
        "bpy.context.object.data.vertices: 1-element tuple"
    )

    ctx_mock = None
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Blender Command Execution Error: bpy.context.object.data.vertices: 1-element tuple" in result["error"]
    assert result.get("type") == "BlenderCommandError"


async def test_execute_command_unexpected_error(mock_blender_connection):
    """Test execute_command handles an unexpected generic error from send_command."""
    code_to_run = "import time; time.sleep(0.1)"
    mock_blender_connection.send_command.side_effect = ValueError("Unexpected value issue")

    ctx_mock = None
    result_str = await execute_command(ctx=ctx_mock, code_to_execute=code_to_run)
    result = json.loads(result_str)

    assert "error" in result
    assert "Unexpected server error during command execution: Unexpected value issue" in result["error"]
    assert result.get("type") == "ValueError"


# It might also be useful to test the get_blender_connection logic itself,
# especially its caching and reconnection attempts, but that would involve
# more complex patching of socket.socket and the BlenderConnection methods directly.
# For tool-level tests, patching get_blender_connection as done here is often sufficient.
