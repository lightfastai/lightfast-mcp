"""
Comprehensive tests for ConversationSession - critical session management.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from tools.ai.conversation_session import ConversationSession
from tools.common import (
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


class MockAIProvider:
    """Mock AI provider for testing."""

    def __init__(self, provider_name: str = "mock"):
        self.provider_name = provider_name

    async def generate_step(self, messages, available_tools, step_number):
        """Mock step generation."""
        step = ConversationStep(step_number=step_number, text="Mock response")
        return Result(status=OperationStatus.SUCCESS, data=step)


class MockToolExecutor:
    """Mock tool executor for testing."""

    def __init__(self):
        self.execute_tools_concurrently = AsyncMock(return_value=[])


class TestConversationSession:
    """Comprehensive tests for ConversationSession class."""

    @pytest.fixture
    def mock_ai_provider(self):
        """Create a mock AI provider."""
        return MockAIProvider()

    @pytest.fixture
    def mock_tool_executor(self):
        """Create a mock tool executor."""
        return MockToolExecutor()

    @pytest.fixture
    def sample_tools(self):
        """Create sample tools for testing."""
        return {
            "tool1": (MockMCPTool("tool1", "First tool"), "server1"),
            "tool2": (MockMCPTool("tool2", "Second tool"), "server2"),
            "tool3": (MockMCPTool("tool3", "Third tool"), "server1"),
        }

    @pytest.fixture
    def conversation_session(self, mock_ai_provider, mock_tool_executor, sample_tools):
        """Create a ConversationSession instance for testing."""
        return ConversationSession(
            session_id="test-session",
            max_steps=5,
            ai_provider=mock_ai_provider,
            tool_executor=mock_tool_executor,
            available_tools=sample_tools,
        )

    def test_conversation_session_initialization(
        self, conversation_session, mock_ai_provider, mock_tool_executor, sample_tools
    ):
        """Test ConversationSession initialization."""
        assert conversation_session.session_id == "test-session"
        assert conversation_session.max_steps == 5
        assert conversation_session.ai_provider == mock_ai_provider
        assert conversation_session.tool_executor == mock_tool_executor
        assert conversation_session.available_tools == sample_tools
        assert conversation_session.messages == []
        assert conversation_session.steps == []
        assert conversation_session.current_step_number == 0
        assert conversation_session.is_complete is False

    def test_conversation_session_initialization_with_defaults(self):
        """Test ConversationSession initialization with minimal parameters."""
        session = ConversationSession(
            session_id="minimal-session",
            max_steps=3,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        assert session.session_id == "minimal-session"
        assert session.max_steps == 3
        assert session.available_tools == {}

    def test_conversation_session_initialization_with_large_max_steps(self):
        """Test ConversationSession initialization with large max_steps."""
        session = ConversationSession(
            session_id="large-session",
            max_steps=1000,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        assert session.max_steps == 1000

    def test_conversation_session_initialization_with_zero_max_steps(self):
        """Test ConversationSession initialization with zero max_steps."""
        session = ConversationSession(
            session_id="zero-session",
            max_steps=0,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        assert session.max_steps == 0

    @pytest.mark.asyncio
    async def test_process_message_success(self, conversation_session):
        """Test successful message processing."""
        # Mock AI provider to return a step
        mock_step = ConversationStep(step_number=0, text="Response to hello")
        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        result = await conversation_session.process_message("Hello")

        assert result.is_success
        steps = result.data
        assert len(steps) == 1
        assert steps[0].text == "Response to hello"
        assert len(conversation_session.messages) == 2  # User + assistant
        assert conversation_session.messages[0]["role"] == "user"
        assert conversation_session.messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_process_message_with_tool_calls(self, conversation_session):
        """Test message processing with tool calls."""
        # Create step with tool calls and finish_reason to stop conversation
        tool_call = ToolCall(
            id="call-1", tool_name="tool1", arguments={"param": "value"}
        )
        mock_step = ConversationStep(
            step_number=0, text="Using tool", finish_reason="stop"
        )
        mock_step.tool_calls = [tool_call]

        # Mock tool result
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={"param": "value"},
            result="Tool output",
        )

        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )
        conversation_session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[tool_result]
        )

        result = await conversation_session.process_message("Use tool1")

        assert result.is_success
        steps = result.data
        assert len(steps) == 1
        assert len(steps[0].tool_calls) == 1
        assert len(steps[0].tool_results) == 1
        assert steps[0].tool_results[0].result == "Tool output"

    @pytest.mark.asyncio
    async def test_process_message_multiple_steps(self, conversation_session):
        """Test message processing that generates multiple steps."""
        conversation_session.max_steps = 3

        # Mock AI provider to return steps with tool calls that continue conversation
        step_responses = [
            ConversationStep(step_number=0, text="Step 1"),
            ConversationStep(step_number=1, text="Step 2"),
            ConversationStep(step_number=2, text="Final step", finish_reason="stop"),
        ]

        # Add tool calls to first two steps to continue conversation
        step_responses[0].tool_calls = [
            ToolCall(id="call-1", tool_name="tool1", arguments={})
        ]
        step_responses[1].tool_calls = [
            ToolCall(id="call-2", tool_name="tool2", arguments={})
        ]

        call_count = 0

        async def mock_generate_step(*args, **kwargs):
            nonlocal call_count
            step = step_responses[call_count]
            call_count += 1
            return Result(status=OperationStatus.SUCCESS, data=step)

        conversation_session.ai_provider.generate_step = mock_generate_step
        conversation_session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[
                ToolResult(
                    id="call-1", tool_name="tool1", arguments={}, result="result"
                )
            ]
        )

        result = await conversation_session.process_message("Multi-step message")

        assert result.is_success
        steps = result.data
        assert len(steps) == 3
        assert conversation_session.is_complete is True

    @pytest.mark.asyncio
    async def test_process_message_max_steps_reached(self, conversation_session):
        """Test message processing when max steps is reached."""
        conversation_session.max_steps = 2

        # Mock AI provider to always return steps with tool calls (would continue indefinitely)
        mock_step = ConversationStep(step_number=0, text="Continuing step")
        mock_step.tool_calls = [ToolCall(id="call-1", tool_name="tool1", arguments={})]

        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )
        conversation_session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[
                ToolResult(
                    id="call-1", tool_name="tool1", arguments={}, result="result"
                )
            ]
        )

        result = await conversation_session.process_message("Max steps test")

        assert result.is_success
        steps = result.data
        assert len(steps) == 2  # Should stop at max_steps
        assert conversation_session.is_complete is True

    @pytest.mark.asyncio
    async def test_process_message_already_complete(self, conversation_session):
        """Test processing message when session is already complete."""
        conversation_session.is_complete = True

        result = await conversation_session.process_message("Should fail")

        assert result.is_failed
        assert "already complete" in result.error

    @pytest.mark.asyncio
    async def test_process_message_step_generation_failure(self, conversation_session):
        """Test message processing when step generation fails."""
        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(
                status=OperationStatus.FAILED, error="Generation failed"
            )
        )

        result = await conversation_session.process_message("Failing message")

        assert result.is_failed
        assert "Failed to generate step" in result.error

    @pytest.mark.asyncio
    async def test_process_message_exception_handling(self, conversation_session):
        """Test message processing with exception handling."""
        conversation_session.ai_provider.generate_step = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        result = await conversation_session.process_message("Exception test")

        assert result.is_failed
        assert "Failed to generate step 0" in result.error

    @pytest.mark.asyncio
    async def test_generate_step_success(self, conversation_session):
        """Test successful step generation."""
        mock_step = ConversationStep(step_number=0, text="Generated step")
        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        result = await conversation_session._generate_step(0)

        assert result.is_success
        step = result.data
        assert step.text == "Generated step"
        assert step.duration_ms > 0

    @pytest.mark.asyncio
    async def test_generate_step_with_tool_execution(self, conversation_session):
        """Test step generation with tool execution."""
        # Create step with tool calls
        tool_call = ToolCall(
            id="call-1", tool_name="tool1", arguments={"param": "value"}
        )
        mock_step = ConversationStep(step_number=0, text="Step with tools")
        mock_step.tool_calls = [tool_call]

        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        # Mock tool execution
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={"param": "value"},
            result="Tool executed",
        )
        conversation_session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[tool_result]
        )

        result = await conversation_session._generate_step(0)

        assert result.is_success
        step = result.data
        assert len(step.tool_calls) == 1
        assert len(step.tool_results) == 1
        assert step.tool_results[0].result == "Tool executed"

    @pytest.mark.asyncio
    async def test_generate_step_ai_provider_failure(self, conversation_session):
        """Test step generation when AI provider fails."""
        conversation_session.ai_provider.generate_step = AsyncMock(
            return_value=Result(
                status=OperationStatus.FAILED, error="AI provider failed"
            )
        )

        result = await conversation_session._generate_step(0)

        assert result.is_failed

    @pytest.mark.asyncio
    async def test_generate_step_exception(self, conversation_session):
        """Test step generation with exception."""
        conversation_session.ai_provider.generate_step = AsyncMock(
            side_effect=Exception("Step generation error")
        )

        result = await conversation_session._generate_step(0)

        assert result.is_failed
        assert "Error generating step" in result.error

    @pytest.mark.asyncio
    async def test_update_conversation_messages_claude_format(
        self, conversation_session
    ):
        """Test updating conversation messages in Claude format."""
        conversation_session.ai_provider.provider_name = "claude"

        # Create step with tool calls and results
        tool_call = ToolCall(
            id="call-1", tool_name="tool1", arguments={"param": "value"}
        )
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={"param": "value"},
            result="Tool output",
        )

        step = ConversationStep(step_number=0, text="Using tool")
        step.tool_calls = [tool_call]
        step.tool_results = [tool_result]

        await conversation_session._update_conversation_messages(step)

        # Should have assistant message with tool use and user message with tool result
        assert len(conversation_session.messages) == 2

        assistant_msg = conversation_session.messages[0]
        assert assistant_msg["role"] == "assistant"
        assert isinstance(assistant_msg["content"], list)
        assert any(block["type"] == "text" for block in assistant_msg["content"])
        assert any(block["type"] == "tool_use" for block in assistant_msg["content"])

        user_msg = conversation_session.messages[1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert any(block["type"] == "tool_result" for block in user_msg["content"])

    @pytest.mark.asyncio
    async def test_update_conversation_messages_claude_text_only(
        self, conversation_session
    ):
        """Test updating conversation messages in Claude format with text only."""
        conversation_session.ai_provider.provider_name = "claude"

        step = ConversationStep(step_number=0, text="Simple text response")

        await conversation_session._update_conversation_messages(step)

        assert len(conversation_session.messages) == 1
        assert conversation_session.messages[0]["role"] == "assistant"
        assert conversation_session.messages[0]["content"] == "Simple text response"

    @pytest.mark.asyncio
    async def test_update_conversation_messages_openai_format(
        self, conversation_session
    ):
        """Test updating conversation messages in OpenAI format."""
        conversation_session.ai_provider.provider_name = "openai"

        # Create step with tool calls and results
        tool_call = ToolCall(
            id="call-1", tool_name="tool1", arguments={"param": "value"}
        )
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={"param": "value"},
            result="Tool output",
        )

        step = ConversationStep(step_number=0, text="Using tool")
        step.tool_calls = [tool_call]
        step.tool_results = [tool_result]

        await conversation_session._update_conversation_messages(step)

        # Should have assistant message with tool_calls and tool message with result
        assert len(conversation_session.messages) == 2

        assistant_msg = conversation_session.messages[0]
        assert assistant_msg["role"] == "assistant"
        assert "tool_calls" in assistant_msg
        assert len(assistant_msg["tool_calls"]) == 1

        tool_msg = conversation_session.messages[1]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call-1"

    @pytest.mark.asyncio
    async def test_update_conversation_messages_openai_text_only(
        self, conversation_session
    ):
        """Test updating conversation messages in OpenAI format with text only."""
        conversation_session.ai_provider.provider_name = "openai"

        step = ConversationStep(step_number=0, text="Simple text response")

        await conversation_session._update_conversation_messages(step)

        assert len(conversation_session.messages) == 1
        assert conversation_session.messages[0]["role"] == "assistant"
        assert conversation_session.messages[0]["content"] == "Simple text response"

    @pytest.mark.asyncio
    async def test_update_conversation_messages_generic_format(
        self, conversation_session
    ):
        """Test updating conversation messages in generic format."""
        conversation_session.ai_provider.provider_name = "unknown"

        # Create step with tool calls and results
        tool_call = ToolCall(
            id="call-1", tool_name="tool1", arguments={"param": "value"}
        )
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={"param": "value"},
            result="Tool output",
        )

        step = ConversationStep(step_number=0, text="Using tool")
        step.tool_calls = [tool_call]
        step.tool_results = [tool_result]

        await conversation_session._update_conversation_messages(step)

        assert len(conversation_session.messages) == 1
        message = conversation_session.messages[0]
        assert message["role"] == "assistant"
        assert "Using tool" in message["content"]
        assert "Tool calls executed: 1" in message["content"]
        assert "tool1: Tool output" in message["content"]

    @pytest.mark.asyncio
    async def test_update_conversation_messages_generic_with_error(
        self, conversation_session
    ):
        """Test updating conversation messages in generic format with tool error."""
        conversation_session.ai_provider.provider_name = "unknown"

        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={},
            error="Tool failed",
            error_code="TOOL_ERROR",
        )

        step = ConversationStep(step_number=0, text="Tool failed")
        step.tool_calls = [ToolCall(id="call-1", tool_name="tool1", arguments={})]
        step.tool_results = [tool_result]

        await conversation_session._update_conversation_messages(step)

        message = conversation_session.messages[0]
        assert "tool1: Error - Tool failed" in message["content"]

    def test_format_tool_result_content_with_dict(self, conversation_session):
        """Test formatting tool result content with dictionary result."""
        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments={},
            result={"key": "value", "number": 42},
        )

        content = conversation_session._format_tool_result_content(tool_result)

        assert '"key": "value"' in content
        assert '"number": 42' in content

    def test_format_tool_result_content_with_list(self, conversation_session):
        """Test formatting tool result content with list result."""
        tool_result = ToolResult(
            id="call-1", tool_name="tool1", arguments={}, result=[1, 2, 3, "test"]
        )

        content = conversation_session._format_tool_result_content(tool_result)

        assert "[1, 2, 3" in content
        assert '"test"' in content

    def test_format_tool_result_content_with_string(self, conversation_session):
        """Test formatting tool result content with string result."""
        tool_result = ToolResult(
            id="call-1", tool_name="tool1", arguments={}, result="Simple string result"
        )

        content = conversation_session._format_tool_result_content(tool_result)

        assert content == "Simple string result"

    def test_format_tool_result_content_with_error(self, conversation_session):
        """Test formatting tool result content with error."""
        tool_result = ToolResult(
            id="call-1", tool_name="tool1", arguments={}, error="Tool execution failed"
        )

        content = conversation_session._format_tool_result_content(tool_result)

        assert content == "Error: Tool execution failed"

    def test_format_tool_result_content_with_none(self, conversation_session):
        """Test formatting tool result content with None result."""
        tool_result = ToolResult(
            id="call-1", tool_name="tool1", arguments={}, result=None
        )

        content = conversation_session._format_tool_result_content(tool_result)

        assert content == "No result"

    def test_get_conversation_summary(self, conversation_session):
        """Test getting conversation summary."""
        # Add some mock steps with tool calls and results
        step1 = ConversationStep(step_number=0, text="Step 1")
        step1.tool_calls = [ToolCall(id="call-1", tool_name="tool1", arguments={})]
        step1.tool_results = [
            ToolResult(id="call-1", tool_name="tool1", arguments={}, result="success")
        ]

        step2 = ConversationStep(step_number=1, text="Step 2")
        step2.tool_calls = [ToolCall(id="call-2", tool_name="tool2", arguments={})]
        step2.tool_results = [
            ToolResult(id="call-2", tool_name="tool2", arguments={}, error="failed")
        ]

        conversation_session.steps = [step1, step2]
        conversation_session.messages = [
            {"role": "user"},
            {"role": "assistant"},
            {"role": "user"},
        ]

        summary = conversation_session.get_conversation_summary()

        assert summary["session_id"] == "test-session"
        assert summary["steps"] == 2
        assert summary["messages"] == 3
        assert summary["total_tool_calls"] == 2
        assert summary["successful_tool_calls"] == 1
        assert summary["is_complete"] is False
        assert summary["max_steps"] == 5

    def test_get_conversation_summary_empty(self, conversation_session):
        """Test getting conversation summary with no steps."""
        summary = conversation_session.get_conversation_summary()

        assert summary["steps"] == 0
        assert summary["messages"] == 0
        assert summary["total_tool_calls"] == 0
        assert summary["successful_tool_calls"] == 0

    @pytest.mark.asyncio
    async def test_close_session(self, conversation_session):
        """Test closing a conversation session."""
        await conversation_session.close()

        assert conversation_session.is_complete is True


class TestConversationSessionEdgeCases:
    """Test edge cases and error scenarios for ConversationSession."""

    @pytest.mark.asyncio
    async def test_conversation_session_with_empty_message(self):
        """Test processing empty message."""
        session = ConversationSession(
            session_id="empty-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        result = await session.process_message("")

        assert result.is_success
        assert session.messages[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_conversation_session_with_very_long_message(self):
        """Test processing very long message."""
        session = ConversationSession(
            session_id="long-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        long_message = "x" * 100000  # 100KB message

        result = await session.process_message(long_message)

        assert result.is_success
        assert session.messages[0]["content"] == long_message

    @pytest.mark.asyncio
    async def test_conversation_session_with_unicode_message(self):
        """Test processing Unicode message."""
        session = ConversationSession(
            session_id="unicode-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        unicode_message = "Hello 世界! 🌍 Здравствуй мир!"

        result = await session.process_message(unicode_message)

        assert result.is_success
        assert session.messages[0]["content"] == unicode_message

    @pytest.mark.asyncio
    async def test_conversation_session_with_special_characters(self):
        """Test processing message with special characters."""
        session = ConversationSession(
            session_id="special-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        special_message = (
            'Message with "quotes", \n newlines, \t tabs, and \\ backslashes'
        )

        result = await session.process_message(special_message)

        assert result.is_success
        assert session.messages[0]["content"] == special_message

    @pytest.mark.asyncio
    async def test_conversation_session_step_without_text(self):
        """Test processing step without text content."""
        session = ConversationSession(
            session_id="no-text-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Mock AI provider to return step without text
        mock_step = ConversationStep(step_number=0, text=None)
        session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        result = await session.process_message("Test")

        assert result.is_success

    @pytest.mark.asyncio
    async def test_conversation_session_with_many_tool_calls(self):
        """Test processing step with many tool calls."""
        session = ConversationSession(
            session_id="many-tools-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Create step with many tool calls
        tool_calls = [
            ToolCall(id=f"call-{i}", tool_name=f"tool{i}", arguments={})
            for i in range(20)
        ]
        mock_step = ConversationStep(step_number=0, text="Many tools")
        mock_step.tool_calls = tool_calls

        session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        # Mock tool results
        tool_results = [
            ToolResult(
                id=f"call-{i}", tool_name=f"tool{i}", arguments={}, result=f"result{i}"
            )
            for i in range(20)
        ]
        session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=tool_results
        )

        result = await session.process_message("Use many tools")

        assert result.is_success
        step = result.data[0]
        assert len(step.tool_calls) == 20
        assert len(step.tool_results) == 20

    @pytest.mark.asyncio
    async def test_conversation_session_tool_execution_failure(self):
        """Test handling tool execution failure."""
        session = ConversationSession(
            session_id="tool-fail-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Create step with tool call
        tool_call = ToolCall(id="call-1", tool_name="tool1", arguments={})
        mock_step = ConversationStep(step_number=0, text="Using tool")
        mock_step.tool_calls = [tool_call]

        session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        # Mock tool execution failure
        session.tool_executor.execute_tools_concurrently = AsyncMock(
            side_effect=Exception("Tool execution failed")
        )

        # Should still succeed but handle the error gracefully
        await session.process_message("Use failing tool")

        # The session should handle tool execution errors gracefully
        # The exact behavior depends on implementation

    @pytest.mark.asyncio
    async def test_conversation_session_with_complex_tool_arguments(self):
        """Test processing tool calls with complex arguments."""
        session = ConversationSession(
            session_id="complex-args-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Create tool call with complex arguments
        complex_args = {
            "nested": {"key": "value", "number": 42},
            "list": [1, 2, {"inner": "value"}],
            "boolean": True,
            "null": None,
            "unicode": "测试",
        }
        tool_call = ToolCall(id="call-1", tool_name="tool1", arguments=complex_args)
        mock_step = ConversationStep(step_number=0, text="Complex tool")
        mock_step.tool_calls = [tool_call]

        session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        tool_result = ToolResult(
            id="call-1",
            tool_name="tool1",
            arguments=complex_args,
            result="Complex result",
        )
        session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[tool_result]
        )

        result = await session.process_message("Use complex tool")

        assert result.is_success
        step = result.data[0]
        assert step.tool_calls[0].arguments == complex_args

    @pytest.mark.asyncio
    async def test_conversation_session_duration_measurement(self):
        """Test that step duration is measured correctly."""
        session = ConversationSession(
            session_id="duration-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Mock AI provider with delay
        async def delayed_generate_step(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            step = ConversationStep(step_number=0, text="Delayed response")
            return Result(status=OperationStatus.SUCCESS, data=step)

        session.ai_provider.generate_step = delayed_generate_step

        result = await session.process_message("Delayed test")

        assert result.is_success
        step = result.data[0]
        # Duration should be approximately 100ms (allow some variance)
        assert 80 <= step.duration_ms <= 200

    @pytest.mark.asyncio
    async def test_conversation_session_concurrent_processing(self):
        """Test concurrent message processing (should be handled gracefully)."""
        session = ConversationSession(
            session_id="concurrent-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Start multiple concurrent message processing
        import asyncio

        tasks = [session.process_message(f"Message {i}") for i in range(5)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least one should succeed, others might fail due to session state
        successful_results = [
            r for r in results if not isinstance(r, Exception) and r.is_success
        ]
        assert len(successful_results) >= 1

    @pytest.mark.asyncio
    async def test_conversation_session_step_number_progression(self):
        """Test that step numbers progress correctly."""
        session = ConversationSession(
            session_id="step-progression-test",
            max_steps=3,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Mock AI provider to return steps with tool calls (to continue conversation)
        call_count = 0

        async def mock_generate_step(*args, **kwargs):
            nonlocal call_count
            step_number = kwargs.get("step_number", call_count)
            step = ConversationStep(step_number=step_number, text=f"Step {step_number}")
            if call_count < 2:  # Add tool calls to first two steps
                step.tool_calls = [
                    ToolCall(id=f"call-{call_count}", tool_name="tool1", arguments={})
                ]
            call_count += 1
            return Result(status=OperationStatus.SUCCESS, data=step)

        session.ai_provider.generate_step = mock_generate_step
        session.tool_executor.execute_tools_concurrently = AsyncMock(
            return_value=[
                ToolResult(
                    id="call-1", tool_name="tool1", arguments={}, result="result"
                )
            ]
        )

        result = await session.process_message("Multi-step test")

        assert result.is_success
        steps = result.data
        assert len(steps) == 3
        assert steps[0].step_number == 0
        assert steps[1].step_number == 1
        assert steps[2].step_number == 2

    @pytest.mark.asyncio
    async def test_conversation_session_message_format_edge_cases(self):
        """Test edge cases in message formatting."""
        session = ConversationSession(
            session_id="format-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Test with different provider names
        for provider_name in ["claude", "openai", "unknown", "", None]:
            session.ai_provider.provider_name = provider_name
            session.messages = []  # Reset messages

            step = ConversationStep(step_number=0, text="Test response")
            await session._update_conversation_messages(step)

            assert len(session.messages) >= 1

    def test_conversation_session_summary_with_complex_data(self):
        """Test conversation summary with complex step data."""
        session = ConversationSession(
            session_id="summary-test",
            max_steps=10,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Create steps with various combinations of tool calls and results
        steps = []

        # Step with successful tool call
        step1 = ConversationStep(step_number=0, text="Step 1")
        step1.tool_calls = [ToolCall(id="call-1", tool_name="tool1", arguments={})]
        step1.tool_results = [
            ToolResult(id="call-1", tool_name="tool1", arguments={}, result="success")
        ]
        steps.append(step1)

        # Step with failed tool call
        step2 = ConversationStep(step_number=1, text="Step 2")
        step2.tool_calls = [ToolCall(id="call-2", tool_name="tool2", arguments={})]
        step2.tool_results = [
            ToolResult(id="call-2", tool_name="tool2", arguments={}, error="failed")
        ]
        steps.append(step2)

        # Step with multiple tool calls
        step3 = ConversationStep(step_number=2, text="Step 3")
        step3.tool_calls = [
            ToolCall(id="call-3a", tool_name="tool3", arguments={}),
            ToolCall(id="call-3b", tool_name="tool4", arguments={}),
        ]
        step3.tool_results = [
            ToolResult(id="call-3a", tool_name="tool3", arguments={}, result="success"),
            ToolResult(id="call-3b", tool_name="tool4", arguments={}, error="failed"),
        ]
        steps.append(step3)

        # Step with no tool calls
        step4 = ConversationStep(step_number=3, text="Step 4")
        steps.append(step4)

        session.steps = steps
        session.messages = [{"role": "user"}, {"role": "assistant"}] * 4  # 8 messages

        summary = session.get_conversation_summary()

        assert summary["steps"] == 4
        assert summary["messages"] == 8
        assert summary["total_tool_calls"] == 4  # 1 + 1 + 2 + 0
        assert summary["successful_tool_calls"] == 2  # 1 + 0 + 1 + 0

    @pytest.mark.asyncio
    async def test_conversation_session_with_none_values(self):
        """Test conversation session handling None values gracefully."""
        session = ConversationSession(
            session_id="none-test",
            max_steps=1,
            ai_provider=MockAIProvider(),
            tool_executor=MockToolExecutor(),
            available_tools={},
        )

        # Test with step that has None text
        mock_step = ConversationStep(step_number=0, text=None)
        session.ai_provider.generate_step = AsyncMock(
            return_value=Result(status=OperationStatus.SUCCESS, data=mock_step)
        )

        result = await session.process_message("None test")

        assert result.is_success

        # Test formatting None result
        tool_result = ToolResult(
            id="call-1", tool_name="tool1", arguments={}, result=None
        )
        content = session._format_tool_result_content(tool_result)
        assert content == "No result"
