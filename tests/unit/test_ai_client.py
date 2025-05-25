"""Tests for the multi-server AI client."""

from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as mcp_types
import pytest

from lightfast_mcp.clients.multi_server_ai_client import (
    ConversationState,
    MultiServerAIClient,
    Step,
    ToolCall,
    ToolCallState,
    ToolResult,
    create_multi_server_client_from_config,
    mcp_result_to_our_result,
    mcp_tool_to_claude_tool,
    mcp_tool_to_openai_tool,
)


class TestDataClasses:
    """Test the data classes and their methods."""

    def test_tool_call_creation(self):
        """Test ToolCall creation."""
        tool_call = ToolCall(
            id="test_id",
            tool_name="test_tool",
            arguments={"param": "value"},
            server_name="test_server",
        )
        assert tool_call.id == "test_id"
        assert tool_call.tool_name == "test_tool"
        assert tool_call.arguments == {"param": "value"}
        assert tool_call.server_name == "test_server"

    def test_tool_result_states(self):
        """Test ToolResult state property."""
        # Test CALL state (no result or error)
        result = ToolResult(id="test_id", tool_name="test_tool", arguments={})
        assert result.state == ToolCallState.CALL

        # Test RESULT state
        result.result = "success"
        assert result.state == ToolCallState.RESULT

        # Test ERROR state
        result.result = None
        result.error = "test error"
        assert result.state == ToolCallState.ERROR

    def test_step_functionality(self):
        """Test Step class functionality."""
        step = Step(step_number=1)

        # Test adding tool calls
        tool_call = ToolCall(id="call_1", tool_name="test_tool", arguments={})
        step.add_tool_call(tool_call)
        assert len(step.tool_calls) == 1
        assert step.has_pending_tool_calls()

        # Test adding tool results
        tool_result = ToolResult(
            id="call_1", tool_name="test_tool", arguments={}, result="success"
        )
        step.add_tool_result(tool_result)
        assert len(step.tool_results) == 1
        assert not step.has_pending_tool_calls()  # No longer pending

    def test_conversation_state(self):
        """Test ConversationState functionality."""
        state = ConversationState(max_steps=3)

        # Test creating new steps
        step1 = state.create_new_step()
        assert step1.step_number == 0
        assert len(state.steps) == 1

        step2 = state.create_new_step()
        assert step2.step_number == 1
        assert len(state.steps) == 2

        # Test current step
        current = state.get_current_step()
        assert current == step1

        # Test can_continue
        assert state.can_continue()
        state.current_step = 2  # At max
        assert not state.can_continue()


class TestMCPConversion:
    """Test MCP type conversion functions."""

    def test_mcp_tool_to_claude_tool(self):
        """Test converting MCP Tool to Claude format."""
        mcp_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool description",
            inputSchema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
            },
        )

        claude_tool = mcp_tool_to_claude_tool(mcp_tool, "test_server")

        assert claude_tool["name"] == "test_tool"
        assert claude_tool["description"] == "Test tool description"
        assert claude_tool["input_schema"] == mcp_tool.inputSchema

    def test_mcp_tool_to_openai_tool(self):
        """Test converting MCP Tool to OpenAI format."""
        mcp_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool description",
            inputSchema={
                "type": "object",
                "properties": {"param": {"type": "string"}},
            },
        )

        openai_tool = mcp_tool_to_openai_tool(mcp_tool, "test_server")

        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "test_tool"
        assert openai_tool["function"]["description"] == "Test tool description"
        assert openai_tool["function"]["parameters"] == mcp_tool.inputSchema

    def test_mcp_result_to_our_result(self):
        """Test converting MCP result to our ToolResult format."""
        tool_call = ToolCall(id="test_id", tool_name="test_tool", arguments={})

        # Test with text content
        text_content = mcp_types.TextContent(type="text", text="Hello world")
        mcp_result = [text_content]

        result = mcp_result_to_our_result(mcp_result, tool_call)
        assert result.result == "Hello world"
        assert result.error is None

        # Test with JSON content
        json_content = mcp_types.TextContent(type="text", text='{"key": "value"}')
        mcp_result = [json_content]

        result = mcp_result_to_our_result(mcp_result, tool_call)
        assert result.result == {"key": "value"}

        # Test with empty result
        result = mcp_result_to_our_result([], tool_call)
        assert result.error == "No result returned"


class TestMultiServerAIClient:
    """Test the MultiServerAIClient class."""

    @pytest.fixture
    def mock_servers(self):
        """Mock server configuration."""
        return {
            "test_server": {
                "type": "stdio",
                "command": "test-command",
                "args": [],
                "name": "Test Server",
            }
        }

    @pytest.fixture
    def client(self, mock_servers):
        """Create a test client."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
            return MultiServerAIClient(
                servers=mock_servers,
                ai_provider="claude",
                max_steps=3,
            )

    def test_client_initialization(self, client):
        """Test client initialization."""
        assert client.ai_provider == "claude"
        assert client.conversation_state.max_steps == 3
        assert len(client.servers) == 1
        assert len(client.clients) == 0  # Not connected yet
        assert len(client.tools) == 0  # No tools yet

    def test_get_api_key_claude(self):
        """Test API key retrieval for Claude."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_claude_key"}):
            client = MultiServerAIClient(servers={}, ai_provider="claude")
            assert client.api_key == "test_claude_key"

    def test_get_api_key_openai(self):
        """Test API key retrieval for OpenAI."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test_openai_key"}):
            client = MultiServerAIClient(servers={}, ai_provider="openai")
            assert client.api_key == "test_openai_key"

    def test_get_api_key_missing(self):
        """Test API key retrieval when missing."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                MultiServerAIClient(servers={}, ai_provider="claude")

    @pytest.mark.asyncio
    async def test_connect_to_servers(self, client, mock_servers):
        """Test connecting to servers."""
        mock_client = AsyncMock()
        mock_tools_result = MagicMock()
        mock_tools_result.tools = [
            mcp_types.Tool(
                name="test_tool",
                description="Test tool",
                inputSchema={"type": "object"},
            )
        ]
        mock_client.list_tools.return_value = mock_tools_result

        with patch(
            "lightfast_mcp.clients.multi_server_ai_client.Client"
        ) as mock_client_class:
            mock_client_class.return_value = mock_client

            await client.connect_to_servers()

            # Verify client was created with stdio URL format
            mock_client_class.assert_called_once_with("stdio://test-command")

            # Verify tools were loaded
            assert len(client.tools) == 1
            assert "test_tool" in client.tools

    @pytest.mark.asyncio
    async def test_execute_tool_call(self, client):
        """Test executing a tool call."""
        # Setup mock tool and client
        mock_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool",
            inputSchema={"type": "object"},
        )
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.content = [mcp_types.TextContent(type="text", text="success")]
        mock_client.call_tool.return_value = mock_result

        client.tools["test_tool"] = (mock_tool, "test_server")
        client.clients["test_server"] = mock_client

        tool_call = ToolCall(
            id="call_1", tool_name="test_tool", arguments={"param": "value"}
        )

        result = await client._execute_tool_call(tool_call)

        assert result.result == "success"
        assert result.error is None
        assert result.server_name == "test_server"
        mock_client.call_tool.assert_called_once_with("test_tool", {"param": "value"})

    @pytest.mark.asyncio
    async def test_execute_tool_call_not_found(self, client):
        """Test executing a tool call for non-existent tool."""
        tool_call = ToolCall(id="call_1", tool_name="missing_tool", arguments={})

        result = await client._execute_tool_call(tool_call)

        assert result.error == "Tool missing_tool not found"
        assert result.result is None

    @pytest.mark.asyncio
    async def test_execute_tool_calls_concurrently(self, client):
        """Test executing multiple tool calls concurrently."""
        # Setup mock tool and client
        mock_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool",
            inputSchema={"type": "object"},
        )
        mock_client = AsyncMock()
        mock_result = MagicMock()
        mock_result.content = [mcp_types.TextContent(type="text", text="success")]
        mock_client.call_tool.return_value = mock_result

        client.tools["test_tool"] = (mock_tool, "test_server")
        client.clients["test_server"] = mock_client

        tool_calls = [
            ToolCall(id="call_1", tool_name="test_tool", arguments={"param": "1"}),
            ToolCall(id="call_2", tool_name="test_tool", arguments={"param": "2"}),
        ]

        results = await client._execute_tool_calls_concurrently(tool_calls)

        assert len(results) == 2
        assert all(r.result == "success" for r in results)
        assert mock_client.call_tool.call_count == 2

    def test_parse_claude_tool_calls(self, client):
        """Test parsing tool calls from Claude response."""
        message = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "test_tool",
                    "input": {"param": "value"},
                },
                {
                    "type": "text",
                    "text": "Some text",
                },
            ]
        }

        tool_calls = client._parse_claude_tool_calls(message)

        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_1"
        assert tool_calls[0].tool_name == "test_tool"
        assert tool_calls[0].arguments == {"param": "value"}

    def test_parse_openai_tool_calls(self, client):
        """Test parsing tool calls from OpenAI response."""
        message = {
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "test_tool",
                        "arguments": '{"param": "value"}',
                    },
                }
            ]
        }

        tool_calls = client._parse_openai_tool_calls(message)

        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_1"
        assert tool_calls[0].tool_name == "test_tool"
        assert tool_calls[0].arguments == {"param": "value"}

    def test_build_claude_tools(self, client):
        """Test building tools list for Claude."""
        mock_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool",
            inputSchema={"type": "object"},
        )
        client.tools["test_tool"] = (mock_tool, "test_server")

        claude_tools = client._build_claude_tools()

        assert len(claude_tools) == 1
        assert claude_tools[0]["name"] == "test_tool"
        assert claude_tools[0]["description"] == "Test tool"

    def test_build_openai_tools(self, client):
        """Test building tools list for OpenAI."""
        mock_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool",
            inputSchema={"type": "object"},
        )
        client.tools["test_tool"] = (mock_tool, "test_server")

        openai_tools = client._build_openai_tools()

        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "test_tool"

    def test_build_tools_context(self, client):
        """Test building tools context description."""
        mock_tool = mcp_types.Tool(
            name="test_tool",
            description="Test tool description",
            inputSchema={"type": "object"},
        )
        client.tools["test_tool"] = (mock_tool, "test_server")

        context = client._build_tools_context()

        assert "test_server Server" in context
        assert "test_tool: Test tool description" in context

    def test_build_tools_context_empty(self, client):
        """Test building tools context when no tools available."""
        context = client._build_tools_context()
        assert "No connected servers or tools available" in context

    def test_get_connected_servers(self, client):
        """Test getting connected servers."""
        mock_client = AsyncMock()
        client.clients["test_server"] = mock_client

        servers = client.get_connected_servers()
        assert servers == ["test_server"]

    def test_get_all_tools(self, client):
        """Test getting all tools organized by server."""
        mock_tool1 = mcp_types.Tool(name="tool1", inputSchema={})
        mock_tool2 = mcp_types.Tool(name="tool2", inputSchema={})

        client.tools["tool1"] = (mock_tool1, "server1")
        client.tools["tool2"] = (mock_tool2, "server2")

        tools_by_server = client.get_all_tools()

        assert "server1" in tools_by_server
        assert "server2" in tools_by_server
        assert "tool1" in tools_by_server["server1"]
        assert "tool2" in tools_by_server["server2"]

    def test_find_tool_server(self, client):
        """Test finding which server has a tool."""
        mock_tool = mcp_types.Tool(name="test_tool", inputSchema={})
        client.tools["test_tool"] = (mock_tool, "test_server")

        server = client.find_tool_server("test_tool")
        assert server == "test_server"

        # Test with non-existent tool
        server = client.find_tool_server("missing_tool")
        assert server is None

    def test_get_server_status(self, client):
        """Test getting server status information."""
        mock_client = AsyncMock()
        client.clients["test_server"] = mock_client

        mock_tool = mcp_types.Tool(name="test_tool", inputSchema={})
        client.tools["test_tool"] = (mock_tool, "test_server")

        status = client.get_server_status()

        assert "test_server" in status
        assert status["test_server"]["connected"] is True
        assert status["test_server"]["tools_count"] == 1
        assert "test_tool" in status["test_server"]["tools"]

    @pytest.mark.asyncio
    async def test_chat_with_ai_legacy(self, client):
        """Test legacy chat_with_ai method."""
        with patch.object(client, "chat_with_steps") as mock_chat:
            mock_step = Step(step_number=0, text="Hello")
            mock_chat.return_value = [mock_step]

            response = await client.chat_with_ai("test message")

            assert response == "Hello"
            mock_chat.assert_called_once_with("test message", True)

    @pytest.mark.asyncio
    async def test_disconnect_from_servers(self, client):
        """Test disconnecting from servers."""
        mock_client = AsyncMock()
        client.clients["test_server"] = mock_client

        mock_tool = mcp_types.Tool(name="test_tool", inputSchema={})
        client.tools["test_tool"] = (mock_tool, "test_server")

        await client.disconnect_from_servers()

        mock_client.close.assert_called_once()
        assert len(client.clients) == 0
        assert len(client.tools) == 0


class TestClientFactory:
    """Test the client factory function."""

    @pytest.mark.asyncio
    async def test_create_multi_server_client_from_config(self):
        """Test creating client from configuration."""
        servers = {
            "test_server": {
                "type": "stdio",
                "command": "test-command",
                "args": [],
            }
        }

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test_key"}):
            with patch.object(
                MultiServerAIClient, "connect_to_servers"
            ) as mock_connect:
                client = await create_multi_server_client_from_config(
                    servers=servers,
                    ai_provider="claude",
                    max_steps=3,
                )

                assert isinstance(client, MultiServerAIClient)
                mock_connect.assert_called_once()
