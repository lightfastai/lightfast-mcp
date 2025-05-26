"""
Comprehensive tests for ConversationClient - critical AI conversation orchestration.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.ai.conversation_client import ConversationClient, create_conversation_client
from tools.common import (
    AIProviderError,
    ConversationResult,
    ConversationStep,
    OperationStatus,
    Result,
    ToolCall,
    ToolResult,
)


class MockMCPTool:
    """Mock MCP tool for testing."""

    def __init__(self, name: str, description: str = "Mock tool"):
        self.name = name
        self.description = description
        self.inputSchema = {"type": "object", "properties": {}}


class TestConversationClient:
    """Comprehensive tests for ConversationClient class."""

    @pytest.fixture
    def sample_servers(self):
        """Sample server configurations for testing."""
        return {
            "server1": {
                "type": "sse",
                "url": "http://localhost:8001/mcp",
                "name": "server1",
            },
            "server2": {
                "type": "stdio",
                "command": "python",
                "args": ["-m", "server2"],
                "name": "server2",
            },
        }

    @pytest.fixture
    def conversation_client(self, sample_servers):
        """Create a ConversationClient instance for testing."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            return ConversationClient(
                servers=sample_servers,
                ai_provider="claude",
                max_steps=3,
                max_concurrent_tools=2,
            )

    def test_conversation_client_initialization(
        self, conversation_client, sample_servers
    ):
        """Test ConversationClient initialization."""
        assert conversation_client.servers == sample_servers
        assert conversation_client.ai_provider_name == "claude"
        assert conversation_client.max_steps == 3
        assert conversation_client.max_concurrent_tools == 2
        assert conversation_client.connection_pool is None
        assert conversation_client.connected_servers == {}
        assert conversation_client.available_tools == {}
        assert conversation_client.active_sessions == {}

    def test_get_api_key_claude(self):
        """Test getting Claude API key from environment."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-claude-key"}):
            client = ConversationClient(servers={}, ai_provider="claude")
            assert client.api_key == "test-claude-key"

    def test_get_api_key_openai(self):
        """Test getting OpenAI API key from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}):
            client = ConversationClient(servers={}, ai_provider="openai")
            assert client.api_key == "test-openai-key"

    def test_get_api_key_missing_claude(self):
        """Test missing Claude API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AIProviderError, match="ANTHROPIC_API_KEY"):
                ConversationClient(servers={}, ai_provider="claude")

    def test_get_api_key_missing_openai(self):
        """Test missing OpenAI API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AIProviderError, match="OPENAI_API_KEY"):
                ConversationClient(servers={}, ai_provider="openai")

    def test_unsupported_ai_provider(self):
        """Test unsupported AI provider raises error."""
        with pytest.raises(AIProviderError, match="Unsupported AI provider"):
            ConversationClient(servers={}, ai_provider="unsupported")

    def test_create_ai_provider_claude(self, conversation_client):
        """Test creating Claude AI provider."""
        provider = conversation_client._create_ai_provider()
        assert provider.provider_name == "claude"

    def test_create_ai_provider_openai(self, sample_servers):
        """Test creating OpenAI AI provider."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = ConversationClient(servers=sample_servers, ai_provider="openai")
            provider = client._create_ai_provider()
            assert provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_connect_to_servers_success(self, conversation_client):
        """Test successful connection to servers."""
        # Mock connection pool
        mock_pool = MagicMock()
        mock_pool.register_server = AsyncMock()

        # Mock client and tools
        mock_client = MagicMock()
        mock_tools_result = MagicMock()
        mock_tools_result.tools = [
            MockMCPTool("tool1", "First tool"),
            MockMCPTool("tool2", "Second tool"),
        ]
        mock_client.list_tools = AsyncMock(return_value=mock_tools_result)

        # Mock connection context manager
        mock_connection = MagicMock()
        mock_connection.__aenter__ = AsyncMock(return_value=mock_client)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_pool.get_connection.return_value = mock_connection

        with patch(
            "tools.ai.conversation_client.get_connection_pool", return_value=mock_pool
        ):
            result = await conversation_client.connect_to_servers()

        assert result.is_success
        connection_results = result.data
        assert len(connection_results) == 2
        assert all(connection_results.values())
        assert len(conversation_client.connected_servers) == 2
        assert len(conversation_client.available_tools) == 2

    @pytest.mark.asyncio
    async def test_connect_to_servers_partial_failure(self, conversation_client):
        """Test connection with some server failures."""
        # Mock connection pool
        mock_pool = MagicMock()
        mock_pool.register_server = AsyncMock()

        # Mock successful connection for server1
        mock_client1 = MagicMock()
        mock_tools_result = MagicMock()
        mock_tools_result.tools = [MockMCPTool("tool1")]
        mock_client1.list_tools = AsyncMock(return_value=mock_tools_result)

        # Mock failed connection for server2
        def mock_get_connection(server_name):
            if server_name == "server1":
                mock_connection = MagicMock()
                mock_connection.__aenter__ = AsyncMock(return_value=mock_client1)
                mock_connection.__aexit__ = AsyncMock(return_value=None)
                return mock_connection
            else:
                raise Exception("Connection failed")

        mock_pool.get_connection.side_effect = mock_get_connection

        with patch(
            "tools.ai.conversation_client.get_connection_pool", return_value=mock_pool
        ):
            result = await conversation_client.connect_to_servers()

        assert result.is_success
        connection_results = result.data
        assert connection_results["server1"] is True
        assert connection_results["server2"] is False
        assert len(conversation_client.connected_servers) == 1

    @pytest.mark.asyncio
    async def test_connect_to_servers_tools_list_format(self, conversation_client):
        """Test connection with tools returned as list."""
        mock_pool = MagicMock()
        mock_pool.register_server = AsyncMock()

        mock_client = MagicMock()
        # Return tools as list instead of object with .tools attribute
        mock_tools_list = [MockMCPTool("tool1"), MockMCPTool("tool2")]
        mock_client.list_tools = AsyncMock(return_value=mock_tools_list)

        mock_connection = MagicMock()
        mock_connection.__aenter__ = AsyncMock(return_value=mock_client)
        mock_connection.__aexit__ = AsyncMock(return_value=None)
        mock_pool.get_connection.return_value = mock_connection

        with patch(
            "tools.ai.conversation_client.get_connection_pool", return_value=mock_pool
        ):
            result = await conversation_client.connect_to_servers()

        assert result.is_success
        assert len(conversation_client.available_tools) == 2

    @pytest.mark.asyncio
    async def test_start_conversation_success(self, conversation_client):
        """Test successful conversation start."""
        # Mock AI provider and tool executor
        conversation_client.ai_provider = MagicMock()
        conversation_client.tool_executor = MagicMock()
        conversation_client.available_tools = {
            "tool1": (MockMCPTool("tool1"), "server1")
        }

        result = await conversation_client.start_conversation()

        assert result.is_success
        session = result.data
        assert session.session_id in conversation_client.active_sessions
        assert session.max_steps == conversation_client.max_steps

    @pytest.mark.asyncio
    async def test_start_conversation_with_initial_message(self, conversation_client):
        """Test conversation start with initial message."""
        # Mock session and its process_message method
        mock_session = MagicMock()
        mock_session.session_id = "test-session"
        mock_session.process_message = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS)
        )

        with patch(
            "tools.ai.conversation_client.ConversationSession",
            return_value=mock_session,
        ):
            result = await conversation_client.start_conversation(
                initial_message="Hello", session_id="test-session"
            )

        assert result.is_success
        mock_session.process_message.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_start_conversation_duplicate_session(self, conversation_client):
        """Test starting conversation with duplicate session ID."""
        # Add existing session
        conversation_client.active_sessions["existing-session"] = MagicMock()

        result = await conversation_client.start_conversation(
            session_id="existing-session"
        )

        assert result.is_failed
        assert "already exists" in result.error

    @pytest.mark.asyncio
    async def test_chat_new_session(self, conversation_client):
        """Test chat with new session creation."""
        # Mock session creation and processing
        mock_session = MagicMock()
        mock_session.session_id = "new-session"
        mock_session.steps = [ConversationStep(step_number=0, text="Hello response")]
        mock_session.process_message = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS)
        )

        with patch.object(conversation_client, "start_conversation") as mock_start:
            mock_start.return_value = Result(
                status=OperationStatus.SUCCESS, data=mock_session
            )

            result = await conversation_client.chat("Hello")

        assert result.is_success
        conversation_result = result.data
        assert isinstance(conversation_result, ConversationResult)
        assert len(conversation_result.steps) == 1

    @pytest.mark.asyncio
    async def test_chat_existing_session(self, conversation_client):
        """Test chat with existing session."""
        # Create existing session
        mock_session = MagicMock()
        mock_session.session_id = "existing-session"
        mock_session.steps = [ConversationStep(step_number=0, text="Response")]
        mock_session.process_message = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS)
        )

        conversation_client.active_sessions["existing-session"] = mock_session

        result = await conversation_client.chat("Hello", session_id="existing-session")

        assert result.is_success
        mock_session.process_message.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_chat_session_not_found(self, conversation_client):
        """Test chat with non-existent session."""
        result = await conversation_client.chat("Hello", session_id="nonexistent")

        assert result.is_failed
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_continue_conversation(self, conversation_client):
        """Test continuing an existing conversation."""
        # Mock existing session
        mock_session = MagicMock()
        mock_session.steps = [ConversationStep(step_number=0, text="Response")]
        mock_session.process_message = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS)
        )

        conversation_client.active_sessions["test-session"] = mock_session

        result = await conversation_client.continue_conversation(
            "test-session", "Continue"
        )

        assert result.is_success
        mock_session.process_message.assert_called_once_with("Continue")

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conversation_client):
        """Test getting conversation history."""
        # Mock session with steps
        mock_session = MagicMock()
        mock_steps = [
            ConversationStep(step_number=0, text="Step 1"),
            ConversationStep(step_number=1, text="Step 2"),
        ]
        mock_session.steps = mock_steps

        conversation_client.active_sessions["test-session"] = mock_session

        result = await conversation_client.get_conversation_history("test-session")

        assert result.is_success
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_history_not_found(self, conversation_client):
        """Test getting history for non-existent session."""
        result = await conversation_client.get_conversation_history("nonexistent")

        assert result.is_failed
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_tools(self, conversation_client):
        """Test executing tool calls."""
        # Mock tool executor
        mock_tool_executor = MagicMock()
        mock_results = [
            ToolResult(id="1", tool_name="tool1", arguments={}, result="result1"),
            ToolResult(id="2", tool_name="tool2", arguments={}, result="result2"),
        ]
        mock_tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=mock_results
        )
        conversation_client.tool_executor = mock_tool_executor

        tool_calls = [
            ToolCall(id="1", tool_name="tool1", arguments={}),
            ToolCall(id="2", tool_name="tool2", arguments={}),
        ]

        result = await conversation_client.execute_tools(tool_calls)

        assert result.is_success
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_execute_tools_empty(self, conversation_client):
        """Test executing empty tool calls list."""
        result = await conversation_client.execute_tools([])

        assert result.is_success
        assert result.data == []

    def test_get_connected_servers(self, conversation_client):
        """Test getting connected servers list."""
        conversation_client.connected_servers = {
            "server1": {"type": "sse"},
            "server2": {"type": "stdio"},
        }

        servers = conversation_client.get_connected_servers()
        assert servers == ["server1", "server2"]

    def test_get_available_tools(self, conversation_client):
        """Test getting available tools by server."""
        conversation_client.available_tools = {
            "tool1": (MockMCPTool("tool1"), "server1"),
            "tool2": (MockMCPTool("tool2"), "server1"),
            "tool3": (MockMCPTool("tool3"), "server2"),
        }

        tools_by_server = conversation_client.get_available_tools()

        expected = {
            "server1": ["tool1", "tool2"],
            "server2": ["tool3"],
        }
        assert tools_by_server == expected

    def test_find_tool_server(self, conversation_client):
        """Test finding which server has a tool."""
        conversation_client.available_tools = {
            "tool1": (MockMCPTool("tool1"), "server1"),
            "tool2": (MockMCPTool("tool2"), "server2"),
        }

        assert conversation_client.find_tool_server("tool1") == "server1"
        assert conversation_client.find_tool_server("tool2") == "server2"
        assert conversation_client.find_tool_server("nonexistent") is None

    def test_get_server_status(self, conversation_client):
        """Test getting server status information."""
        conversation_client.connected_servers = {"server1": {}, "server2": {}}
        conversation_client.available_tools = {
            "tool1": (MockMCPTool("tool1"), "server1"),
            "tool2": (MockMCPTool("tool2"), "server1"),
            "tool3": (MockMCPTool("tool3"), "server2"),
        }

        status = conversation_client.get_server_status()

        assert len(status) == 2
        assert status["server1"]["connected"] is True
        assert status["server1"]["tools_count"] == 2
        assert status["server2"]["tools_count"] == 1

    def test_get_active_sessions(self, conversation_client):
        """Test getting active sessions."""
        mock_session1 = MagicMock()
        mock_session2 = MagicMock()
        conversation_client.active_sessions = {
            "session1": mock_session1,
            "session2": mock_session2,
        }

        sessions = conversation_client.get_active_sessions()

        assert len(sessions) == 2
        assert sessions["session1"] is mock_session1
        assert sessions["session2"] is mock_session2

    @pytest.mark.asyncio
    async def test_close_session(self, conversation_client):
        """Test closing a conversation session."""
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        conversation_client.active_sessions["test-session"] = mock_session

        result = await conversation_client.close_session("test-session")

        assert result.is_success
        mock_session.close.assert_called_once()
        assert "test-session" not in conversation_client.active_sessions

    @pytest.mark.asyncio
    async def test_close_session_not_found(self, conversation_client):
        """Test closing non-existent session."""
        result = await conversation_client.close_session("nonexistent")

        assert result.is_failed
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_disconnect_from_servers(self, conversation_client):
        """Test disconnecting from all servers."""
        # Mock active sessions
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        conversation_client.active_sessions["test-session"] = mock_session

        # Mock connection pool
        mock_pool = MagicMock()
        conversation_client.connection_pool = mock_pool

        with patch(
            "tools.ai.conversation_client.shutdown_connection_pool"
        ) as mock_shutdown:
            result = await conversation_client.disconnect_from_servers()

        assert result.is_success
        mock_session.close.assert_called_once()
        assert len(conversation_client.active_sessions) == 0
        assert len(conversation_client.connected_servers) == 0
        assert len(conversation_client.available_tools) == 0
        mock_shutdown.assert_called_once()


class TestCreateConversationClient:
    """Tests for the create_conversation_client factory function."""

    @pytest.fixture
    def sample_servers(self):
        """Sample server configurations."""
        return {
            "server1": {"type": "sse", "url": "http://localhost:8001/mcp"},
        }

    @pytest.mark.asyncio
    async def test_create_conversation_client_success(self, sample_servers):
        """Test successful client creation."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            # Mock the connect_to_servers method
            with patch.object(ConversationClient, "connect_to_servers") as mock_connect:
                mock_connect.return_value = Result(
                    status=OperationStatus.SUCCESS, data={"server1": True}
                )

                result = await create_conversation_client(
                    servers=sample_servers,
                    ai_provider="claude",
                    max_steps=5,
                )

        assert result.is_success
        client = result.data
        assert isinstance(client, ConversationClient)
        assert client.max_steps == 5

    @pytest.mark.asyncio
    async def test_create_conversation_client_connection_failure(self, sample_servers):
        """Test client creation with connection failure."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            # Mock connection failure
            with patch.object(ConversationClient, "connect_to_servers") as mock_connect:
                mock_connect.return_value = Result(
                    status=OperationStatus.FAILED, error="Connection failed"
                )

                result = await create_conversation_client(
                    servers=sample_servers,
                    ai_provider="claude",
                )

        assert result.is_failed
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_create_conversation_client_initialization_error(
        self, sample_servers
    ):
        """Test client creation with initialization error."""
        # Missing API key should cause initialization error
        with patch.dict(os.environ, {}, clear=True):
            result = await create_conversation_client(
                servers=sample_servers,
                ai_provider="claude",
            )

        assert result.is_failed
        assert "ANTHROPIC_API_KEY" in result.error


class TestConversationClientEdgeCases:
    """Test edge cases and error scenarios for ConversationClient."""

    @pytest.mark.asyncio
    async def test_conversation_client_with_custom_api_key(self):
        """Test client with custom API key."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        client = ConversationClient(
            servers=servers,
            ai_provider="claude",
            api_key="custom-key",
        )

        assert client.api_key == "custom-key"

    @pytest.mark.asyncio
    async def test_conversation_client_with_different_providers(self):
        """Test client with different AI providers."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        # Test Claude
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            claude_client = ConversationClient(servers=servers, ai_provider="claude")
            assert claude_client.ai_provider.provider_name == "claude"

        # Test OpenAI
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            openai_client = ConversationClient(servers=servers, ai_provider="openai")
            assert openai_client.ai_provider.provider_name == "openai"

    @pytest.mark.asyncio
    async def test_conversation_client_max_concurrent_tools(self):
        """Test client with different max concurrent tools settings."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = ConversationClient(
                servers=servers,
                ai_provider="claude",
                max_concurrent_tools=10,
            )

        assert client.max_concurrent_tools == 10
        assert client.tool_executor.max_concurrent == 10

    @pytest.mark.asyncio
    async def test_start_conversation_initial_message_failure(self):
        """Test conversation start when initial message processing fails."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = ConversationClient(servers=servers, ai_provider="claude")

        # Mock session that fails on process_message
        mock_session = MagicMock()
        mock_session.session_id = "test-session"
        mock_session.process_message = AsyncMock(
            return_value=Result(
                status=OperationStatus.FAILED, error="Processing failed"
            )
        )

        with patch(
            "tools.ai.conversation_client.ConversationSession",
            return_value=mock_session,
        ):
            result = await client.start_conversation(initial_message="Hello")

        assert result.is_failed
        assert "Processing failed" in result.error
        assert "test-session" not in client.active_sessions

    @pytest.mark.asyncio
    async def test_chat_session_creation_failure(self):
        """Test chat when session creation fails."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = ConversationClient(servers=servers, ai_provider="claude")

        # Mock failed session creation
        with patch.object(client, "start_conversation") as mock_start:
            mock_start.return_value = Result(
                status=OperationStatus.FAILED, error="Session creation failed"
            )

            result = await client.chat("Hello")

        assert result.is_failed
        assert "Session creation failed" in result.error

    @pytest.mark.asyncio
    async def test_chat_message_processing_failure(self):
        """Test chat when message processing fails."""
        servers = {"server1": {"type": "sse", "url": "http://localhost:8001"}}

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            client = ConversationClient(servers=servers, ai_provider="claude")

        # Mock session with failed processing
        mock_session = MagicMock()
        mock_session.process_message = AsyncMock(
            return_value=Result(
                status=OperationStatus.FAILED, error="Processing failed"
            )
        )
        client.active_sessions["test-session"] = mock_session

        result = await client.chat("Hello", session_id="test-session")

        assert result.is_failed
        assert "Processing failed" in result.error
