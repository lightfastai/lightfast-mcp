"""Tests for Blender OBJ file transfer functionality."""

from unittest.mock import Mock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.blender.server import BlenderMCPServer


@pytest.fixture
def blender_server():
    """Create a BlenderMCPServer instance for testing."""
    config = ServerConfig(
        name="test-blender",
        description="Test Blender server",
        host="localhost",
        port=8001,
        config={
            "type": "blender",
            "blender_host": "localhost",
            "blender_port": 9876,
        },
    )
    return BlenderMCPServer(config)


@pytest.fixture
def sample_obj_content():
    """Sample OBJ file content for testing."""
    return """# Simple cube
v -1.0 -1.0 -1.0
v  1.0 -1.0 -1.0
v  1.0  1.0 -1.0
v -1.0  1.0 -1.0
f 1 2 3 4
"""


class TestBlenderOBJTransfer:
    """Test OBJ file transfer functionality."""

    def test_server_has_obj_tools(self, blender_server):
        """Test that the server registers OBJ import/export tools."""
        tools = blender_server.info.tools
        assert "import_obj_file" in tools
        assert "export_obj_file" in tools

    @pytest.mark.asyncio
    async def test_import_obj_validation(self, blender_server, sample_obj_content):
        """Test OBJ import input validation."""
        from fastmcp import Context

        # Mock the Blender connection
        with patch.object(
            blender_server.blender_connection, "send_command"
        ) as mock_send:
            mock_send.return_value = {
                "imported": True,
                "object_count": 1,
                "object_names": ["TestCube"],
                "message": "Successfully imported 1 object(s) from OBJ content",
            }

            # Test valid OBJ content
            ctx = Mock(spec=Context)
            result = await blender_server.import_obj_file(
                ctx, sample_obj_content, "TestCube"
            )

            # Should call Blender with correct parameters
            mock_send.assert_called_once_with(
                "import_obj",
                {"obj_content": sample_obj_content, "object_name": "TestCube"},
            )

            # Should return JSON result
            import json

            result_data = json.loads(result)
            assert result_data["imported"] is True
            assert result_data["object_count"] == 1

    @pytest.mark.asyncio
    async def test_import_obj_empty_content(self, blender_server):
        """Test OBJ import with empty content."""
        from fastmcp import Context

        ctx = Mock(spec=Context)
        result = await blender_server.import_obj_file(ctx, "", "TestCube")

        # Should return error for empty content
        import json

        result_data = json.loads(result)
        assert "error" in result_data
        assert "empty" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_import_obj_invalid_format(self, blender_server):
        """Test OBJ import with invalid format."""
        from fastmcp import Context

        ctx = Mock(spec=Context)
        invalid_content = "This is not an OBJ file\nJust some random text"
        result = await blender_server.import_obj_file(ctx, invalid_content, "TestCube")

        # Should return error for invalid format
        import json

        result_data = json.loads(result)
        assert "error" in result_data
        assert "invalid" in result_data["error"].lower()

    @pytest.mark.asyncio
    async def test_export_obj_specific_object(self, blender_server):
        """Test OBJ export for a specific object."""
        from fastmcp import Context

        # Mock the Blender connection
        with patch.object(
            blender_server.blender_connection, "send_command"
        ) as mock_send:
            mock_send.return_value = {
                "exported": True,
                "object_names": ["TestCube"],
                "obj_content": "# Exported OBJ\nv 0 0 0\nf 1",
                "content_size": 25,
                "message": "Successfully exported 1 object(s) to OBJ format",
            }

            ctx = Mock(spec=Context)
            result = await blender_server.export_obj_file(ctx, "TestCube")

            # Should call Blender with correct parameters
            mock_send.assert_called_once_with("export_obj", {"object_name": "TestCube"})

            # Should return JSON result with OBJ content
            import json

            result_data = json.loads(result)
            assert result_data["exported"] is True
            assert "obj_content" in result_data
            assert result_data["content_size"] > 0

    @pytest.mark.asyncio
    async def test_export_obj_selected_objects(self, blender_server):
        """Test OBJ export for selected objects."""
        from fastmcp import Context

        # Mock the Blender connection
        with patch.object(
            blender_server.blender_connection, "send_command"
        ) as mock_send:
            mock_send.return_value = {
                "exported": True,
                "object_names": ["Cube1", "Cube2"],
                "obj_content": "# Exported OBJ\nv 0 0 0\nf 1",
                "content_size": 25,
                "message": "Successfully exported 2 object(s) to OBJ format",
            }

            ctx = Mock(spec=Context)
            result = await blender_server.export_obj_file(
                ctx, None
            )  # No specific object = selected objects

            # Should call Blender with None object_name
            mock_send.assert_called_once_with("export_obj", {"object_name": None})

            # Should return JSON result
            import json

            result_data = json.loads(result)
            assert result_data["exported"] is True
            assert len(result_data["object_names"]) == 2

    @pytest.mark.asyncio
    async def test_blender_connection_error_handling(
        self, blender_server, sample_obj_content
    ):
        """Test error handling when Blender connection fails."""
        from fastmcp import Context

        from lightfast_mcp.exceptions import BlenderConnectionError

        # Mock connection failure
        with patch.object(
            blender_server.blender_connection, "send_command"
        ) as mock_send:
            mock_send.side_effect = BlenderConnectionError("Connection failed")

            ctx = Mock(spec=Context)
            result = await blender_server.import_obj_file(
                ctx, sample_obj_content, "TestCube"
            )

            # Should return error response
            import json

            result_data = json.loads(result)
            assert "error" in result_data
            assert "Connection failed" in result_data["error"]
