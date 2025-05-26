"""
Comprehensive tests for ToolExecutor - critical tool execution logic.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.ai.tool_executor import ToolExecutor
from tools.common import (
    ToolCall,
    ToolResult,
)
from tools.common.async_utils import ConnectionPool


class MockMCPTool:
    """Mock MCP tool for testing."""

    def __init__(self, name: str, description: str = "Mock tool"):
        self.name = name
        self.description = description
        self.inputSchema = {"type": "object", "properties": {}}


class TestToolExecutor:
    """Comprehensive tests for ToolExecutor class."""

    @pytest.fixture
    async def connection_pool(self):
        """Create a mock connection pool for testing."""
        pool = ConnectionPool()
        await pool.initialize()
        yield pool
        await pool.close_all()

    @pytest.fixture
    def tool_executor(self):
        """Create a ToolExecutor instance for testing."""
        return ToolExecutor(max_concurrent=3, tool_timeout=5.0)

    @pytest.fixture
    def sample_tools(self):
        """Create sample tools for testing."""
        return {
            "test_tool_1": (MockMCPTool("test_tool_1", "First test tool"), "server1"),
            "test_tool_2": (MockMCPTool("test_tool_2", "Second test tool"), "server2"),
            "slow_tool": (MockMCPTool("slow_tool", "Slow test tool"), "server1"),
            "json_tool": (MockMCPTool("json_tool", "JSON returning tool"), "server1"),
            "error_tool": (MockMCPTool("error_tool", "Error prone tool"), "server2"),
        }

    def test_tool_executor_initialization(self, tool_executor):
        """Test ToolExecutor initialization."""
        assert tool_executor.max_concurrent == 3
        assert tool_executor.tool_timeout == 5.0
        assert tool_executor.available_tools == {}
        assert tool_executor.connection_pool is None

    def test_tool_executor_initialization_with_defaults(self):
        """Test ToolExecutor initialization with default values."""
        executor = ToolExecutor()
        assert executor.max_concurrent == 5
        assert executor.tool_timeout == 30.0
        assert executor.available_tools == {}
        assert executor.connection_pool is None

    def test_tool_executor_initialization_with_custom_values(self):
        """Test ToolExecutor initialization with custom values."""
        executor = ToolExecutor(max_concurrent=10, tool_timeout=60.0)
        assert executor.max_concurrent == 10
        assert executor.tool_timeout == 60.0

    @pytest.mark.asyncio
    async def test_update_tools(self, tool_executor, connection_pool, sample_tools):
        """Test updating tools and connection pool."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        assert tool_executor.available_tools == sample_tools
        assert tool_executor.connection_pool == connection_pool

    @pytest.mark.asyncio
    async def test_update_tools_empty_dict(self, tool_executor, connection_pool):
        """Test updating with empty tools dictionary."""
        await tool_executor.update_tools({}, connection_pool)

        assert tool_executor.available_tools == {}
        assert tool_executor.connection_pool == connection_pool

    @pytest.mark.asyncio
    async def test_update_tools_multiple_times(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test updating tools multiple times."""
        # First update
        await tool_executor.update_tools(sample_tools, connection_pool)
        assert len(tool_executor.available_tools) == 5

        # Second update with different tools
        new_tools = {
            "new_tool": (MockMCPTool("new_tool"), "new_server"),
        }
        await tool_executor.update_tools(new_tools, connection_pool)
        assert len(tool_executor.available_tools) == 1
        assert "new_tool" in tool_executor.available_tools

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, tool_executor):
        """Test executing a tool that doesn't exist."""
        tool_call = ToolCall(
            id="test-1", tool_name="nonexistent_tool", arguments={"param": "value"}
        )

        result = await tool_executor.execute_tool(tool_call)

        assert isinstance(result, ToolResult)
        assert result.id == "test-1"
        assert result.tool_name == "nonexistent_tool"
        assert result.error == "Tool nonexistent_tool not found"
        assert result.error_code == "TOOL_NOT_FOUND"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_tool_no_connection_pool(self, tool_executor, sample_tools):
        """Test executing tool without connection pool."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1", tool_name="test_tool_1", arguments={"param": "value"}
        )

        result = await tool_executor.execute_tool(tool_call)

        assert result.error == "Connection pool not available"
        assert result.error_code == "NO_CONNECTION_POOL"

    @pytest.mark.asyncio
    async def test_execute_tool_success(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test successful tool execution."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Mock the connection pool and client
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text='{"result": "success"}')]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        tool_call = ToolCall(
            id="test-1", tool_name="test_tool_1", arguments={"param": "value"}
        )

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert isinstance(result, ToolResult)
        assert result.id == "test-1"
        assert result.tool_name == "test_tool_1"
        assert result.error is None
        assert result.result == {"result": "success"}
        assert result.server_name == "server1"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_tool_with_complex_arguments(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test tool execution with complex arguments."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text='{"processed": true}')]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        complex_args = {
            "nested": {"key": "value", "number": 42},
            "list": [1, 2, 3],
            "boolean": True,
            "null_value": None,
        }

        tool_call = ToolCall(
            id="test-complex", tool_name="test_tool_1", arguments=complex_args
        )

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is None
        assert result.result == {"processed": True}
        # Verify the arguments were passed correctly
        mock_client.call_tool.assert_called_once_with("test_tool_1", complex_args)

    @pytest.mark.asyncio
    async def test_execute_tool_timeout(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test tool execution timeout."""
        tool_executor.tool_timeout = 0.1  # Very short timeout
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Mock a slow client
        mock_client = MagicMock()

        async def slow_call_tool(*args, **kwargs):
            await asyncio.sleep(0.2)  # Longer than timeout
            return MagicMock()

        mock_client.call_tool = slow_call_tool

        tool_call = ToolCall(
            id="test-1", tool_name="slow_tool", arguments={"param": "value"}
        )

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "timed out" in result.error
        assert result.error_code == "TOOL_TIMEOUT"

    @pytest.mark.asyncio
    async def test_execute_tool_execution_error(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test tool execution error handling."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Mock client that raises an exception
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            side_effect=Exception("Tool execution failed")
        )

        tool_call = ToolCall(
            id="test-1", tool_name="test_tool_1", arguments={"param": "value"}
        )

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "Tool execution failed" in result.error
        assert result.error_code == "TOOL_EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_execute_tool_connection_pool_error(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test tool execution when connection pool fails."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        tool_call = ToolCall(
            id="test-1", tool_name="test_tool_1", arguments={"param": "value"}
        )

        # Mock connection pool to raise an exception
        with patch.object(
            connection_pool,
            "get_connection",
            side_effect=Exception("Connection failed"),
        ):
            result = await tool_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "Connection failed" in result.error
        assert result.error_code == "TOOL_EXECUTION_ERROR"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_text(self, tool_executor):
        """Test converting MCP result with text content."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with text content
        mock_content = MagicMock()
        mock_content.text = '{"key": "value"}'
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.id == "test-1"
        assert result.tool_name == "test_tool"
        assert result.result == {"key": "value"}  # Should parse JSON
        assert result.error is None

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_plain_text(self, tool_executor):
        """Test converting MCP result with plain text."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with plain text
        mock_content = MagicMock()
        mock_content.text = "plain text result"
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == "plain text result"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_invalid_json(self, tool_executor):
        """Test converting MCP result with invalid JSON."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with invalid JSON
        mock_content = MagicMock()
        mock_content.text = '{"invalid": json}'  # Invalid JSON
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        # Should store as plain text when JSON parsing fails
        assert result.result == '{"invalid": json}'

    @pytest.mark.asyncio
    async def test_convert_mcp_result_empty(self, tool_executor):
        """Test converting empty MCP result."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock empty MCP result
        mock_result = MagicMock()
        mock_result.content = []

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.error == "No result returned"
        assert result.error_code == "EMPTY_RESULT"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_none_content(self, tool_executor):
        """Test converting MCP result with None content."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with None content
        mock_result = MagicMock()
        mock_result.content = None

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.error == "No result returned"
        assert result.error_code == "EMPTY_RESULT"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_list_format(self, tool_executor):
        """Test converting MCP result in list format."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result as list
        mock_content = MagicMock()
        mock_content.text = "list result"
        mock_result = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == "list result"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_non_text_content(self, tool_executor):
        """Test converting MCP result with non-text content."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with non-text content
        mock_content = MagicMock()
        # Remove text attribute to simulate non-text content
        del mock_content.text
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert "type" in result.result
        assert "content" in result.result

    @pytest.mark.asyncio
    async def test_convert_mcp_result_hasattr_content(self, tool_executor):
        """Test converting MCP result that has content attribute."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with content attribute
        mock_content = MagicMock()
        mock_content.text = "content result"
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == "content result"

    @pytest.mark.asyncio
    async def test_convert_mcp_result_direct_result(self, tool_executor):
        """Test converting MCP result that is not a list or has content."""
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result as direct result
        mock_result = "direct result"

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == "direct result"

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_empty(self, tool_executor):
        """Test executing empty list of tools."""
        results = await tool_executor.execute_tools_concurrently([])
        assert results == []

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_success(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test successful concurrent tool execution."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Mock successful tool calls
        mock_client = MagicMock()
        mock_result1 = MagicMock()
        mock_result1.content = [MagicMock(text='{"result": "tool1"}')]
        mock_result2 = MagicMock()
        mock_result2.content = [MagicMock(text='{"result": "tool2"}')]

        call_count = 0

        async def mock_call_tool(tool_name, args):
            nonlocal call_count
            call_count += 1
            if tool_name == "test_tool_1":
                return mock_result1
            else:
                return mock_result2

        mock_client.call_tool = mock_call_tool

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool_1", arguments={}),
            ToolCall(id="2", tool_name="test_tool_2", arguments={}),
        ]

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 2
        assert all(isinstance(r, ToolResult) for r in results)
        assert results[0].result == {"result": "tool1"}
        assert results[1].result == {"result": "tool2"}
        assert all(r.error is None for r in results)

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_with_failures(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test concurrent tool execution with some failures."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Mock one success, one failure
        mock_client = MagicMock()

        async def mock_call_tool(tool_name, args):
            if tool_name == "test_tool_1":
                mock_result = MagicMock()
                mock_result.content = [MagicMock(text='{"result": "success"}')]
                return mock_result
            else:
                raise Exception("Tool failed")

        mock_client.call_tool = mock_call_tool

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool_1", arguments={}),
            ToolCall(id="2", tool_name="test_tool_2", arguments={}),
        ]

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 2
        assert results[0].error is None
        assert results[0].result == {"result": "success"}
        assert results[1].error is not None
        assert "Tool failed" in results[1].error

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_concurrency_limit(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test concurrent execution respects concurrency limit."""
        tool_executor.max_concurrent = 2
        await tool_executor.update_tools(sample_tools, connection_pool)

        execution_order = []

        async def mock_call_tool(tool_name, args):
            execution_order.append(f"start_{tool_name}")
            await asyncio.sleep(0.1)
            execution_order.append(f"end_{tool_name}")
            mock_result = MagicMock()
            mock_result.content = [MagicMock(text='{"result": "done"}')]
            return mock_result

        mock_client = MagicMock()
        mock_client.call_tool = mock_call_tool

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool_1", arguments={}),
            ToolCall(id="2", tool_name="test_tool_2", arguments={}),
            ToolCall(id="3", tool_name="test_tool_1", arguments={}),  # Reuse tool
        ]

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            start_time = time.time()
            results = await tool_executor.execute_tools_concurrently(tool_calls)
            total_time = time.time() - start_time

        assert len(results) == 3
        assert all(r.error is None for r in results)

        # With max_concurrent=2, should take at least 0.2s (two batches of 0.1s each)
        assert total_time >= 0.15

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_large_batch(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test concurrent execution with large batch of tools."""
        tool_executor.max_concurrent = 5
        await tool_executor.update_tools(sample_tools, connection_pool)

        mock_client = MagicMock()

        async def mock_call_tool(tool_name, args):
            await asyncio.sleep(0.01)  # Small delay
            mock_result = MagicMock()
            mock_result.content = [MagicMock(text=f'{{"tool": "{tool_name}"}}')]
            return mock_result

        mock_client.call_tool = mock_call_tool

        # Create 20 tool calls
        tool_calls = [
            ToolCall(id=str(i), tool_name="test_tool_1", arguments={})
            for i in range(20)
        ]

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 20
        assert all(r.error is None for r in results)
        assert all(r.result == {"tool": "test_tool_1"} for r in results)

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_mixed_success_failure(
        self, tool_executor, connection_pool, sample_tools
    ):
        """Test concurrent execution with mixed success and failure."""
        await tool_executor.update_tools(sample_tools, connection_pool)

        mock_client = MagicMock()

        async def mock_call_tool(tool_name, args):
            if "error" in tool_name:
                raise Exception(f"Error in {tool_name}")
            mock_result = MagicMock()
            mock_result.content = [MagicMock(text=f'{{"success": "{tool_name}"}}')]
            return mock_result

        mock_client.call_tool = mock_call_tool

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool_1", arguments={}),
            ToolCall(id="2", tool_name="error_tool", arguments={}),
            ToolCall(id="3", tool_name="test_tool_2", arguments={}),
            ToolCall(id="4", tool_name="error_tool", arguments={}),
        ]

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 4
        # Check success results
        assert results[0].error is None
        assert results[0].result == {"success": "test_tool_1"}
        assert results[2].error is None
        assert results[2].result == {"success": "test_tool_2"}
        # Check error results
        assert results[1].error is not None
        assert "Error in error_tool" in results[1].error
        assert results[3].error is not None
        assert "Error in error_tool" in results[3].error

    def test_get_available_tools(self, tool_executor, sample_tools):
        """Test getting available tools mapping."""
        tool_executor.available_tools = sample_tools

        tools_map = tool_executor.get_available_tools()

        expected = {
            "test_tool_1": "server1",
            "test_tool_2": "server2",
            "slow_tool": "server1",
            "json_tool": "server1",
            "error_tool": "server2",
        }
        assert tools_map == expected

    def test_get_available_tools_empty(self, tool_executor):
        """Test getting available tools when none are available."""
        tools_map = tool_executor.get_available_tools()
        assert tools_map == {}

    def test_get_tool_info(self, tool_executor, sample_tools):
        """Test getting tool information."""
        tool_executor.available_tools = sample_tools

        info = tool_executor.get_tool_info("test_tool_1")
        assert info is not None
        mcp_tool, server_name = info
        assert mcp_tool.name == "test_tool_1"
        assert server_name == "server1"

        # Test non-existent tool
        info = tool_executor.get_tool_info("nonexistent")
        assert info is None

    def test_get_tool_info_all_tools(self, tool_executor, sample_tools):
        """Test getting information for all tools."""
        tool_executor.available_tools = sample_tools

        for tool_name in sample_tools:
            info = tool_executor.get_tool_info(tool_name)
            assert info is not None
            mcp_tool, server_name = info
            assert mcp_tool.name == tool_name
            assert server_name in ["server1", "server2"]

    def test_validate_tool_call_success(self, tool_executor, sample_tools):
        """Test successful tool call validation."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1", tool_name="test_tool_1", arguments={"param": "value"}
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is True
        assert error is None

    def test_validate_tool_call_not_found(self, tool_executor, sample_tools):
        """Test tool call validation for non-existent tool."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1", tool_name="nonexistent_tool", arguments={"param": "value"}
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "not found" in error

    def test_validate_tool_call_missing_id(self, tool_executor, sample_tools):
        """Test tool call validation with missing ID."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="", tool_name="test_tool_1", arguments={"param": "value"}
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "ID is required" in error

    def test_validate_tool_call_none_id(self, tool_executor, sample_tools):
        """Test tool call validation with None ID."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id=None, tool_name="test_tool_1", arguments={"param": "value"}
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "ID is required" in error

    def test_validate_tool_call_invalid_arguments(self, tool_executor, sample_tools):
        """Test tool call validation with invalid arguments."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1",
            tool_name="test_tool_1",
            arguments="not a dict",  # Should be dict
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "must be a dictionary" in error

    def test_validate_tool_call_none_arguments(self, tool_executor, sample_tools):
        """Test tool call validation with None arguments."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1",
            tool_name="test_tool_1",
            arguments=None,  # Should be dict
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "must be a dictionary" in error

    def test_validate_tool_call_list_arguments(self, tool_executor, sample_tools):
        """Test tool call validation with list arguments."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1",
            tool_name="test_tool_1",
            arguments=[1, 2, 3],  # Should be dict
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is False
        assert "must be a dictionary" in error

    def test_validate_tool_call_empty_arguments(self, tool_executor, sample_tools):
        """Test tool call validation with empty arguments."""
        tool_executor.available_tools = sample_tools

        tool_call = ToolCall(
            id="test-1",
            tool_name="test_tool_1",
            arguments={},  # Empty dict is valid
        )

        is_valid, error = tool_executor.validate_tool_call(tool_call)
        assert is_valid is True
        assert error is None


class TestToolExecutorEdgeCases:
    """Test edge cases and error scenarios for ToolExecutor."""

    @pytest.fixture
    async def connection_pool(self):
        """Create a mock connection pool for testing."""
        pool = ConnectionPool()
        await pool.initialize()
        yield pool
        await pool.close_all()

    @pytest.mark.asyncio
    async def test_execute_tool_with_connection_pool_error(self):
        """Test tool execution when connection pool fails."""
        tool_executor = ToolExecutor()

        # Mock tools and connection pool
        sample_tools = {"test_tool": (MockMCPTool("test_tool"), "server1")}

        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("Connection failed")

        await tool_executor.update_tools(sample_tools, mock_pool)

        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        result = await tool_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_operation_wrapper_failure(
        self, connection_pool
    ):
        """Test concurrent execution when operation wrapper fails."""
        tool_executor = ToolExecutor()

        # Mock tools but don't set connection pool
        sample_tools = {"test_tool": (MockMCPTool("test_tool"), "server1")}
        tool_executor.available_tools = sample_tools
        # Don't set connection pool to cause failure

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool", arguments={}),
        ]

        results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 1
        assert results[0].error is not None
        assert "Connection pool not available" in results[0].error

    @pytest.mark.asyncio
    async def test_tool_executor_with_different_timeout_values(self, connection_pool):
        """Test tool executor with different timeout values."""
        # Test with very short timeout
        short_executor = ToolExecutor(tool_timeout=0.01)
        sample_tools = {"slow_tool": (MockMCPTool("slow_tool"), "server1")}
        await short_executor.update_tools(sample_tools, connection_pool)

        mock_client = MagicMock()

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(0.1)  # Longer than timeout
            return MagicMock()

        mock_client.call_tool = slow_call

        tool_call = ToolCall(id="test-1", tool_name="slow_tool", arguments={})

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await short_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_tool_executor_initialization_edge_cases(self):
        """Test tool executor initialization with edge case values."""
        # Test with zero max_concurrent
        executor = ToolExecutor(max_concurrent=0)
        assert executor.max_concurrent == 0

        # Test with zero timeout
        executor = ToolExecutor(tool_timeout=0.0)
        assert executor.tool_timeout == 0.0

        # Test with negative values
        executor = ToolExecutor(max_concurrent=-1, tool_timeout=-1.0)
        assert executor.max_concurrent == -1
        assert executor.tool_timeout == -1.0

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_complex_json(self):
        """Test converting MCP result with complex JSON structures."""
        tool_executor = ToolExecutor()
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        complex_json = {
            "nested": {
                "array": [1, 2, {"inner": "value"}],
                "boolean": True,
                "null": None,
                "number": 42.5,
            },
            "unicode": "测试",
            "escaped": "line1\nline2\ttab",
        }

        mock_content = MagicMock()
        mock_content.text = json.dumps(complex_json)
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == complex_json

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_multiple_content_items(self):
        """Test converting MCP result with multiple content items."""
        tool_executor = ToolExecutor()
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock MCP result with multiple content items (should use first one)
        mock_content1 = MagicMock()
        mock_content1.text = "first content"
        mock_content2 = MagicMock()
        mock_content2.text = "second content"
        mock_result = MagicMock()
        mock_result.content = [mock_content1, mock_content2]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        # Should use the first content item
        assert result.result == "first content"

    @pytest.mark.asyncio
    async def test_execute_tool_with_very_large_arguments(self, connection_pool):
        """Test tool execution with very large arguments."""
        tool_executor = ToolExecutor()
        sample_tools = {"test_tool": (MockMCPTool("test_tool"), "server1")}
        await tool_executor.update_tools(sample_tools, connection_pool)

        # Create very large arguments
        large_args = {
            "large_string": "x" * 10000,  # 10KB string
            "large_list": list(range(1000)),
            "nested_data": {f"key_{i}": f"value_{i}" for i in range(100)},
        }

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.content = [MagicMock(text='{"processed": true}')]
        mock_client.call_tool = AsyncMock(return_value=mock_result)

        tool_call = ToolCall(
            id="test-large", tool_name="test_tool", arguments=large_args
        )

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is None
        assert result.result == {"processed": True}

    @pytest.mark.asyncio
    async def test_execute_tools_concurrently_with_zero_max_concurrent(self):
        """Test concurrent execution with zero max_concurrent."""
        tool_executor = ToolExecutor(max_concurrent=0)

        tool_calls = [
            ToolCall(id="1", tool_name="test_tool", arguments={}),
        ]

        # Should still work, with unlimited concurrency (since max_concurrent=0 is treated as unlimited)
        results = await tool_executor.execute_tools_concurrently(tool_calls)

        assert len(results) == 1
        # Will fail because no tools are available, but that's expected
        assert results[0].error is not None
        assert "Tool test_tool not found" in results[0].error

    @pytest.mark.asyncio
    async def test_execute_tool_with_connection_context_manager_error(
        self, connection_pool
    ):
        """Test tool execution when connection context manager fails."""
        tool_executor = ToolExecutor()
        sample_tools = {"test_tool": (MockMCPTool("test_tool"), "server1")}
        await tool_executor.update_tools(sample_tools, connection_pool)

        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        # Mock connection context manager to raise exception on enter
        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Context manager failed")
            )
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is not None
        assert "Context manager failed" in result.error

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_empty_string_content(self):
        """Test converting MCP result with empty string content."""
        tool_executor = ToolExecutor()
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        mock_content = MagicMock()
        mock_content.text = ""  # Empty string
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == ""

    @pytest.mark.asyncio
    async def test_convert_mcp_result_with_whitespace_only_content(self):
        """Test converting MCP result with whitespace-only content."""
        tool_executor = ToolExecutor()
        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        mock_content = MagicMock()
        mock_content.text = "   \n\t   "  # Only whitespace
        mock_result = MagicMock()
        mock_result.content = [mock_content]

        result = tool_executor._convert_mcp_result(mock_result, tool_call)

        assert result.result == "   \n\t   "

    @pytest.mark.asyncio
    async def test_execute_tool_duration_measurement_accuracy(self, connection_pool):
        """Test that tool execution duration is measured accurately."""
        tool_executor = ToolExecutor()
        sample_tools = {"test_tool": (MockMCPTool("test_tool"), "server1")}
        await tool_executor.update_tools(sample_tools, connection_pool)

        mock_client = MagicMock()

        async def timed_call_tool(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            mock_result = MagicMock()
            mock_result.content = [MagicMock(text='{"result": "timed"}')]
            return mock_result

        mock_client.call_tool = timed_call_tool

        tool_call = ToolCall(id="test-1", tool_name="test_tool", arguments={})

        with patch.object(connection_pool, "get_connection") as mock_get_conn:
            mock_get_conn.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_get_conn.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await tool_executor.execute_tool(tool_call)

        assert result.error is None
        # Duration should be approximately 100ms (allow some variance)
        assert 80 <= result.duration_ms <= 200
