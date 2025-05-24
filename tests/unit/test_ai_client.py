"""
Test cases for the AI client modules.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.clients.multi_server_ai_client import (
    ConversationState,
    MultiServerAIClient,
    Step,
    ToolCall,
    ToolResult,
)
from lightfast_mcp.clients.server_selector import ServerSelector
from lightfast_mcp.core.base_server import ServerConfig


class TestMultiServerAIClient:
    """Test MultiServerAIClient functionality."""

    def test_init_claude_provider(self):
        """Test initialization with Claude provider."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude", max_steps=5)
            assert client.ai_provider == "claude"
            assert client.conversation_state.max_steps == 5

    def test_init_openai_provider(self):
        """Test initialization with OpenAI provider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="openai", max_steps=3)
            assert client.ai_provider == "openai"
            assert client.conversation_state.max_steps == 3

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
    async def test_execute_tool_call_success(self):
        """Test successful tool call execution."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock server connection and tool execution
            server_conn = client.servers["test-server"]
            server_conn.is_connected = True
            server_conn.tools = ["test_tool"]

            # Create a tool call
            tool_call = ToolCall(
                id="test_call_1",
                tool_name="test_tool",
                arguments={"param": "value"},
                server_name="test-server",
            )

            # Mock call_tool method
            with patch.object(
                server_conn, "call_tool", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = {"result": "success"}

                result = await client.execute_tool_call(tool_call)

                assert isinstance(result, ToolResult)
                assert result.result == {"result": "success"}
                assert result.error is None
                mock_call.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_call_failure(self):
        """Test tool call execution failure."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")
            client.add_server("test-server", "http://localhost:8001/mcp")

            # Mock server connection and client properly
            server_conn = client.servers["test-server"]
            server_conn.is_connected = True
            server_conn.client = MagicMock()  # Mock the MCP client
            server_conn.tools = [
                "test_tool"
            ]  # Available tools (missing the one we'll request)

            # Create a tool call with nonexistent tool
            tool_call = ToolCall(
                id="test_call_1",
                tool_name="nonexistent_tool",
                arguments={},
                server_name="test-server",
            )

            result = await client.execute_tool_call(tool_call)

            assert isinstance(result, ToolResult)
            assert result.error is not None
            # The error should be about the tool not being available
            assert "not available" in result.error
            assert "nonexistent_tool" in result.error

    @pytest.mark.asyncio
    async def test_chat_with_steps(self):
        """Test chat with steps functionality."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude", max_steps=2)

            # Mock the generate_with_steps method
            mock_step1 = Step(
                step_number=0, text="Step 1 response", finish_reason="continue"
            )
            mock_step2 = Step(
                step_number=1, text="Step 2 response", finish_reason="stop"
            )

            async def mock_generate(message, include_context=True):
                yield mock_step1
                yield mock_step2

            with patch.object(client, "generate_with_steps", side_effect=mock_generate):
                steps = await client.chat_with_steps("Test message")

                assert len(steps) == 2
                assert steps[0].text == "Step 1 response"
                assert steps[1].text == "Step 2 response"

    @pytest.mark.asyncio
    @patch("anthropic.AsyncAnthropic")
    async def test_chat_with_ai_claude_legacy(self, mock_anthropic):
        """Test legacy chat with Claude AI (backward compatibility)."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude")

            # Mock chat_with_steps to return simple steps
            mock_steps = [Step(step_number=0, text="AI response", finish_reason="stop")]

            with patch.object(
                client, "chat_with_steps", new_callable=AsyncMock
            ) as mock_chat:
                mock_chat.return_value = mock_steps

                response = await client.chat_with_ai("Test message")

                assert "AI response" in response
                mock_chat.assert_called_once()

    def test_conversation_state(self):
        """Test conversation state management."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = MultiServerAIClient(ai_provider="claude", max_steps=3)

            conv_state = client.get_conversation_state()
            assert isinstance(conv_state, ConversationState)
            assert conv_state.max_steps == 3
            assert conv_state.current_step == 0
            assert not conv_state.is_complete

    def test_step_functionality(self):
        """Test Step class functionality."""
        step = Step(step_number=1)

        # Test adding tool calls
        tool_call = ToolCall(id="test_1", tool_name="test_tool", arguments={})
        step.add_tool_call(tool_call)
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0].id == "test_1"

        # Test adding tool results
        tool_result = ToolResult(
            id="test_1", tool_name="test_tool", arguments={}, result="success"
        )
        step.add_tool_result(tool_result)
        assert len(step.tool_results) == 1
        assert step.tool_results[0].result == "success"

        # Test pending tool calls
        assert not step.has_pending_tool_calls()  # result matches call

        # Add another call without result
        tool_call2 = ToolCall(id="test_2", tool_name="test_tool2", arguments={})
        step.add_tool_call(tool_call2)
        assert step.has_pending_tool_calls()  # now has pending call

    def test_tool_result_states(self):
        """Test ToolResult state property."""
        # Test CALL state (no result or error)
        result = ToolResult(id="test", tool_name="test", arguments={})
        assert result.state.value == "call"

        # Test RESULT state
        result.result = {"success": True}
        assert result.state.value == "result"

        # Test ERROR state
        result.error = "Something went wrong"
        assert result.state.value == "error"

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
