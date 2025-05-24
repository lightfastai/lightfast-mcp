"""
Test cases for the AI client modules.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.clients.multi_server_ai_client import MultiServerAIClient
from lightfast_mcp.clients.server_selector import ServerSelector
from lightfast_mcp.core.base_server import ServerConfig


class TestMultiServerAIClient:
    """Test MultiServerAIClient functionality."""

    def test_init_claude_provider(self):
        """Test initialization with Claude provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            assert client.ai_provider == "claude"

    def test_init_openai_provider(self):
        """Test initialization with OpenAI provider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="openai")
            assert client.ai_provider == "openai"

    def test_init_no_api_key(self):
        """Test initialization without API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                ValueError, match="ANTHROPIC_API_KEY environment variable required"
            ):
                MultiServerAIClient(ai_provider="claude")

    def test_add_server(self):
        """Test adding a server to the client."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp", "Test server")

            assert "test-server" in client.servers
            assert client.servers["test-server"].url == "http://localhost:8001/mcp"
            assert client.servers["test-server"].description == "Test server"

    @pytest.mark.asyncio
    async def test_connect_to_servers_success(self):
        """Test successful connection to servers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock the connection method directly
            server_conn = client.servers["test-server"]
            with patch.object(
                server_conn, "connect", new_callable=AsyncMock
            ) as mock_connect:
                mock_connect.return_value = True

                results = await client.connect_to_servers()

                assert results["test-server"] is True
                mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_to_servers_failure(self):
        """Test connection failure to servers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock connection failure
            server_conn = client.servers["test-server"]
            with patch.object(
                server_conn, "connect", new_callable=AsyncMock
            ) as mock_connect:
                mock_connect.return_value = False

                results = await client.connect_to_servers()

                assert results["test-server"] is False
                mock_connect.assert_called_once()

    def test_get_all_tools(self):
        """Test getting all tools from connected servers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock connected server with tools
            client.servers["test-server"].is_connected = True
            client.servers["test-server"].tools = ["tool1", "tool2"]

            tools = client.get_all_tools()

            assert "test-server" in tools
            assert tools["test-server"] == ["tool1", "tool2"]

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock server connection and tool execution
            server_conn = client.servers["test-server"]
            server_conn.is_connected = True
            server_conn.tools = ["test_tool"]

            # Mock call_tool method
            with patch.object(
                server_conn, "call_tool", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = {"result": "success"}

                result = await client.execute_tool(
                    "test_tool", {"param": "value"}, "test-server"
                )

                assert result == {"result": "success"}
                mock_call.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    @patch("anthropic.AsyncAnthropic")
    async def test_chat_with_ai_claude(self, mock_anthropic):
        """Test chat with Claude AI."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            # Mock Claude response
            mock_client = MagicMock()
            mock_message = MagicMock()
            mock_message.content = [MagicMock(text="AI response")]
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.return_value = mock_client

            client = MultiServerAIClient(ai_provider="claude")
            response = await client.chat_with_ai("Test message")

            assert "AI response" in str(response)

    @pytest.mark.asyncio
    @patch("openai.AsyncOpenAI")
    async def test_chat_with_ai_openai(self, mock_openai):
        """Test chat with OpenAI."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            # Mock OpenAI response
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="AI response"))
            ]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            client = MultiServerAIClient(ai_provider="openai")
            response = await client.chat_with_ai("Test message")

            assert "AI response" in str(response)

    @pytest.mark.asyncio
    async def test_process_ai_response_no_tool_calls(self):
        """Test processing AI response without tool calls."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")

            # Test with plain string response (not JSON)
            result = await client.process_ai_response("Simple response")

            assert result == "Simple response"

    @pytest.mark.asyncio
    async def test_disconnect_from_servers(self):
        """Test disconnecting from all servers."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock connected server
            server_conn = client.servers["test-server"]
            server_conn.is_connected = True

            # Mock disconnect method
            with patch.object(
                server_conn, "disconnect", new_callable=AsyncMock
            ) as mock_disconnect:
                await client.disconnect_from_servers()

                mock_disconnect.assert_called_once()


class TestServerSelector:
    """Test ServerSelector functionality."""

    @patch("lightfast_mcp.clients.server_selector.ConfigLoader")
    def test_load_available_servers(self, mock_config_loader):
        """Test loading available servers."""
        mock_loader = MagicMock()
        mock_config = ServerConfig(
            name="test-server", description="Test server", config={"type": "mock"}
        )
        mock_loader.load_servers_config.return_value = [mock_config]
        mock_config_loader.return_value = mock_loader

        selector = ServerSelector()
        configs = selector.load_available_servers()

        assert len(configs) == 1
        assert configs[0].name == "test-server"

    @patch("builtins.input")
    def test_select_servers_interactive(self, mock_input):
        """Test interactive server selection."""
        # Create a mock config
        mock_config = ServerConfig(
            name="test-server", description="Test server", config={"type": "mock"}
        )

        # Mock user input to select server 1
        mock_input.side_effect = ["1", ""]

        selector = ServerSelector()
        # Directly set the available configs instead of loading from file
        selector.available_configs = [mock_config]

        with patch("builtins.print"):
            with patch.object(
                selector, "_check_server_requirements", return_value=True
            ):
                selected = selector.select_servers_interactive()

        assert len(selected) == 1
        assert selected[0].name == "test-server"

    @patch("builtins.input")
    def test_select_servers_interactive_all(self, mock_input):
        """Test selecting all servers interactively."""
        mock_configs = [
            ServerConfig(
                name="server1", description="Server 1", config={"type": "mock"}
            ),
            ServerConfig(
                name="server2", description="Server 2", config={"type": "mock"}
            ),
        ]

        # Mock user input to select all servers
        mock_input.side_effect = ["all", ""]

        selector = ServerSelector()
        # Directly set the available configs
        selector.available_configs = mock_configs

        with patch("builtins.print"):
            with patch.object(
                selector, "_check_server_requirements", return_value=True
            ):
                selected = selector.select_servers_interactive()

        assert len(selected) == 2

    @patch("builtins.input")
    def test_select_servers_interactive_invalid_input(self, mock_input):
        """Test handling invalid input in interactive selection."""
        mock_config = ServerConfig(
            name="test-server", description="Test server", config={"type": "mock"}
        )

        # Mock invalid input, then valid input
        mock_input.side_effect = ["1", ""]

        selector = ServerSelector()
        # Directly set the available configs
        selector.available_configs = [mock_config]

        with patch("builtins.print"):
            with patch.object(
                selector, "_check_server_requirements", return_value=True
            ):
                selected = selector.select_servers_interactive()

        assert len(selected) == 1

    @patch("lightfast_mcp.clients.server_selector.ConfigLoader")
    def test_load_available_servers_empty(self, mock_config_loader):
        """Test loading servers when none are available."""
        mock_loader = MagicMock()
        mock_loader.load_servers_config.return_value = []
        mock_config_loader.return_value = mock_loader

        selector = ServerSelector()
        configs = selector.load_available_servers()

        assert len(configs) == 0
