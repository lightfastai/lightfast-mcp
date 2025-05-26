"""Tool executor for handling MCP tool calls with connection pooling."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import mcp.types as mcp_types

from tools.common import (
    ToolCall,
    ToolExecutionError,
    ToolResult,
    ToolTimeoutError,
    get_logger,
    run_concurrent_operations,
    with_correlation_id,
)
from tools.common.async_utils import ConnectionPool

logger = get_logger("ToolExecutor")


class ToolExecutor:
    """Handles execution of MCP tool calls with connection pooling and concurrency."""

    def __init__(self, max_concurrent: int = 5, tool_timeout: float = 30.0):
        """Initialize the tool executor."""
        self.max_concurrent = max_concurrent
        self.tool_timeout = tool_timeout
        self.available_tools: Dict[str, Tuple[mcp_types.Tool, str]] = {}
        self.connection_pool: Optional[ConnectionPool] = None

    async def update_tools(
        self,
        available_tools: Dict[str, Tuple[mcp_types.Tool, str]],
        connection_pool: ConnectionPool,
    ):
        """Update the available tools and connection pool."""
        self.available_tools = available_tools
        self.connection_pool = connection_pool
        logger.info(f"Updated tool executor with {len(available_tools)} tools")

    @with_correlation_id
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        start_time = time.time()

        # Check if tool exists
        if tool_call.tool_name not in self.available_tools:
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error=f"Tool {tool_call.tool_name} not found",
                error_code="TOOL_NOT_FOUND",
                duration_ms=(time.time() - start_time) * 1000,
            )

        mcp_tool, server_name = self.available_tools[tool_call.tool_name]

        if not self.connection_pool:
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error="Connection pool not available",
                error_code="NO_CONNECTION_POOL",
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._execute_tool_with_connection(tool_call, server_name),
                timeout=self.tool_timeout,
            )

            duration_ms = (time.time() - start_time) * 1000
            result.duration_ms = duration_ms
            result.server_name = server_name

            logger.debug(
                f"Tool {tool_call.tool_name} executed successfully",
                tool_name=tool_call.tool_name,
                server_name=server_name,
                duration_ms=duration_ms,
            )

            return result

        except asyncio.TimeoutError:
            error = ToolTimeoutError(
                f"Tool {tool_call.tool_name} timed out after {self.tool_timeout}s",
                tool_name=tool_call.tool_name,
                server_name=server_name,
            )
            logger.error("Tool execution timed out", error=error)
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error=str(error),
                error_code=error.error_code,
                server_name=server_name,
                duration_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            execution_error = ToolExecutionError(
                f"Error executing tool {tool_call.tool_name}: {e}",
                tool_name=tool_call.tool_name,
                server_name=server_name,
                cause=e,
            )
            logger.error("Tool execution failed", error=execution_error)
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error=str(execution_error),
                error_code=execution_error.error_code,
                server_name=server_name,
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def _execute_tool_with_connection(
        self, tool_call: ToolCall, server_name: str
    ) -> ToolResult:
        """Execute tool using connection pool."""
        if not self.connection_pool:
            raise ToolExecutionError(
                "Connection pool not available",
                tool_name=tool_call.tool_name,
                server_name=server_name,
            )
        async with self.connection_pool.get_connection(server_name) as client:
            # Call the tool
            mcp_result = await client.call_tool(
                tool_call.tool_name, tool_call.arguments
            )

            # Convert MCP result to our format
            result = self._convert_mcp_result(mcp_result, tool_call)
            return result

    def _convert_mcp_result(self, mcp_result: Any, tool_call: ToolCall) -> ToolResult:
        """Convert MCP tool call result to our ToolResult format."""
        result = ToolResult(
            id=tool_call.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
        )

        # Handle different response formats
        if hasattr(mcp_result, "content"):
            content = mcp_result.content
        elif isinstance(mcp_result, list):
            content = mcp_result
        else:
            content = [mcp_result] if mcp_result else []

        if content and len(content) > 0:
            # Handle different content types safely
            first_content = content[0]
            if hasattr(first_content, "text"):
                try:
                    # Try to parse as JSON first
                    result.result = json.loads(first_content.text)
                except json.JSONDecodeError:
                    # If not JSON, store as text
                    result.result = first_content.text
            else:
                # Handle other content types
                result.result = {
                    "type": type(first_content).__name__,
                    "content": str(first_content),
                }
        else:
            result.error = "No result returned"
            result.error_code = "EMPTY_RESULT"

        return result

    async def execute_tools_concurrently(
        self, tool_calls: List[ToolCall]
    ) -> List[ToolResult]:
        """Execute multiple tool calls concurrently."""
        if not tool_calls:
            return []

        logger.info(f"Executing {len(tool_calls)} tools concurrently")

        # Create operations for concurrent execution
        async def execute_single_tool(tool_call: ToolCall) -> ToolResult:
            return await self.execute_tool(tool_call)

        operations = [
            lambda tc=tool_call: execute_single_tool(tc) for tool_call in tool_calls
        ]
        operation_names = [f"tool_{tc.tool_name}" for tc in tool_calls]

        # Execute concurrently
        results = await run_concurrent_operations(
            operations,
            max_concurrent=self.max_concurrent,
            operation_names=operation_names,
        )

        # Extract the actual ToolResult objects from Result wrappers
        tool_results = []
        for result in results:
            if result.is_success:
                tool_results.append(result.data)
            else:
                # Create error ToolResult for failed operations
                tool_results.append(
                    ToolResult(
                        id="",
                        tool_name="unknown",
                        arguments={},
                        error=result.error,
                        error_code=result.error_code,
                    )
                )

        successful = sum(1 for tr in tool_results if not tr.error)
        logger.info(
            f"Tool execution completed: {successful}/{len(tool_calls)} successful"
        )

        return tool_results

    def get_available_tools(self) -> Dict[str, str]:
        """Get available tools mapped to their server names."""
        return {
            tool_name: server_name
            for tool_name, (_, server_name) in self.available_tools.items()
        }

    def get_tool_info(self, tool_name: str) -> Optional[Tuple[mcp_types.Tool, str]]:
        """Get information about a specific tool."""
        return self.available_tools.get(tool_name)

    def validate_tool_call(self, tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
        """Validate a tool call before execution."""
        if tool_call.tool_name not in self.available_tools:
            return False, f"Tool {tool_call.tool_name} not found"

        if not tool_call.id:
            return False, "Tool call ID is required"

        if not isinstance(tool_call.arguments, dict):
            return False, "Tool arguments must be a dictionary"

        # Could add more validation here (e.g., schema validation)
        return True, None
