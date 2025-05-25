"""
Extended test cases for MultiServerAIClient to improve coverage.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.clients.multi_server_ai_client import (
    MultiServerAIClient,
    ToolCall,
    ToolCallState,
    create_multi_server_client_from_config,
)


class TestMultiServerAIClientExtended:
    """Extended tests for MultiServerAIClient functionality."""

    @pytest.mark.asyncio
    async def test_connect_to_servers_stdio_error(self):
        """Test connection error handling for stdio servers."""
        servers = {
            "test_server": {
                "type": "stdio",
                "command": "",  # Empty command should cause error
                "args": [],
            }
        }

        client = MultiServerAIClient(
            servers=servers, ai_provider="claude", api_key="test-key"
        )

        # Should handle the error gracefully
        await client.connect_to_servers()

        # Server should not be in clients due to error
        assert "test_server" not in client.clients

    @pytest.mark.asyncio
    async def test_connect_to_servers_unsupported_transport(self):
        """Test connection with unsupported transport type."""
        servers = {
            "test_server": {
                "type": "unsupported_transport",
                "url": "http://localhost:8000",
            }
        }

        client = MultiServerAIClient(
            servers=servers, ai_provider="claude", api_key="test-key"
        )
        await client.connect_to_servers()

        # Server should not be in clients due to unsupported transport
        assert "test_server" not in client.clients

    @pytest.mark.asyncio
    async def test_get_available_tools_error(self):
        """Test error handling in _get_available_tools."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        # Add a mock client that raises an exception
        mock_client = AsyncMock()
        mock_client.list_tools.side_effect = Exception("Tools listing failed")
        client.clients["error_server"] = mock_client

        # Should handle the error gracefully
        await client._get_available_tools()

        # Tools should be empty due to error
        assert client.tools == {}

    @pytest.mark.asyncio
    async def test_execute_tool_call_tool_not_found(self):
        """Test executing tool call when tool is not found."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        tool_call = ToolCall(
            id="test-id", tool_name="nonexistent_tool", arguments={"param": "value"}
        )

        result = await client._execute_tool_call(tool_call)

        assert result.state == ToolCallState.ERROR
        assert "Tool nonexistent_tool not found" in result.error

    def test_get_server_status(self):
        """Test get_server_status method."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        # Add mock clients
        client.clients["server1"] = MagicMock()
        client.clients["server2"] = MagicMock()

        status = client.get_server_status()

        # The actual implementation returns a dict with server names as keys
        assert "server1" in status
        assert "server2" in status
        assert status["server1"]["connected"] is True
        assert status["server2"]["connected"] is True

    def test_find_tool_server(self):
        """Test find_tool_server method."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        # Add tools
        mock_tool = MagicMock()
        client.tools = {
            "tool1": (mock_tool, "server1"),
            "tool2": (mock_tool, "server2"),
        }

        assert client.find_tool_server("tool1") == "server1"
        assert client.find_tool_server("tool2") == "server2"
        assert client.find_tool_server("nonexistent") is None

    def test_get_all_tools(self):
        """Test get_all_tools method."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        # Add tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        mock_tool3 = MagicMock()
        mock_tool3.name = "tool3"

        client.tools = {
            "tool1": (mock_tool1, "server1"),
            "tool2": (mock_tool2, "server1"),
            "tool3": (mock_tool3, "server2"),
        }

        tools_by_server = client.get_all_tools()

        assert "server1" in tools_by_server
        assert "server2" in tools_by_server
        assert len(tools_by_server["server1"]) == 2
        assert len(tools_by_server["server2"]) == 1

    def test_get_connected_servers(self):
        """Test get_connected_servers method."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        client.clients["server1"] = MagicMock()
        client.clients["server2"] = MagicMock()

        connected = client.get_connected_servers()

        assert "server1" in connected
        assert "server2" in connected
        assert len(connected) == 2

    @pytest.mark.asyncio
    async def test_disconnect_from_servers(self):
        """Test disconnecting from servers."""
        client = MultiServerAIClient(
            servers={}, ai_provider="claude", api_key="test-key"
        )

        # Add mock clients
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        client.clients["server1"] = mock_client1
        client.clients["server2"] = mock_client2

        await client.disconnect_from_servers()

        # Clients should be cleared
        assert client.clients == {}


class TestClientFactory:
    """Test the client factory function."""

    @pytest.mark.asyncio
    async def test_create_multi_server_client_from_config_missing_api_key(self):
        """Test creating client with missing API key."""
        servers = {"test_server": {"type": "sse", "url": "http://localhost:8000"}}

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="ANTHROPIC_API_KEY environment variable required"
            ):
                await create_multi_server_client_from_config(
                    servers=servers, ai_provider="claude"
                )
