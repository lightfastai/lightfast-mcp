"""Claude AI provider implementation."""

import json
from typing import Any, Dict, List

import anthropic
import mcp.types as mcp_types

from tools.common import (
    ConversationStep,
    OperationStatus,
    Result,
    ToolCall,
    get_logger,
)

from .base_provider import BaseAIProvider

logger = get_logger("ClaudeProvider")


class ClaudeProvider(BaseAIProvider):
    """Claude AI provider implementation."""

    def __init__(self, api_key: str):
        """Initialize Claude provider."""
        super().__init__(api_key)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "claude"

    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return "claude-3-5-sonnet-20241022"

    async def generate_step(
        self,
        messages: List[Dict[str, Any]],
        available_tools: Dict[str, tuple[mcp_types.Tool, str]],
        step_number: int,
    ) -> Result[ConversationStep]:
        """Generate a single conversation step with potential tool calls."""
        try:
            # Build system prompt with tools context
            tools_context = self.build_tools_context(available_tools)
            system_prompt = f"""You are an AI assistant that can control multiple creative applications through MCP servers.

{tools_context}

You can use the available tools to interact with the connected servers. When you need to perform actions, use the appropriate tools. For conversational responses, respond normally with helpful information."""

            # Build tools for Claude's native tool calling
            claude_tools = []
            for tool_name, (mcp_tool, server_name) in available_tools.items():
                claude_tool = self.format_tool_for_api(mcp_tool, server_name)
                claude_tools.append(claude_tool)

            # Prepare API parameters
            api_params = {
                "model": self.default_model,
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": self.format_messages_for_api(messages),
            }

            # Only add tools if we have any
            if claude_tools:
                api_params["tools"] = claude_tools

            logger.debug(f"Making Claude API call with {len(claude_tools)} tools")
            response = await self.client.messages.create(**api_params)

            # Create conversation step
            step = ConversationStep(step_number=step_number)

            # Parse Claude's response
            if response.content:
                for content_block in response.content:
                    if content_block.type == "text":
                        step.text = content_block.text
                    elif content_block.type == "tool_use":
                        # Convert Claude's tool call to our format
                        tool_call = ToolCall(
                            id=content_block.id,
                            tool_name=content_block.name,
                            arguments=content_block.input,
                        )
                        step.add_tool_call(tool_call)

            # Set finish reason if no tool calls and no text
            if not step.tool_calls and not step.text:
                step.finish_reason = "stop"

            return Result(status=OperationStatus.SUCCESS, data=step)

        except Exception as e:
            logger.error("Claude API call failed", error=e)
            return Result(
                status=OperationStatus.FAILED,
                error=f"Claude API error: {e}",
                error_code="CLAUDE_API_ERROR",
            )

    def build_tools_context(
        self, available_tools: Dict[str, tuple[mcp_types.Tool, str]]
    ) -> str:
        """Build a context description of available tools."""
        if not available_tools:
            return "No connected servers or tools available."

        tools_desc = []
        tools_by_server: Dict[str, List[mcp_types.Tool]] = {}

        # Group tools by server
        for tool_name, (mcp_tool, server_name) in available_tools.items():
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(mcp_tool)

        # Build description
        for server_name, server_tools in tools_by_server.items():
            tools_desc.append(f"**{server_name} Server**:")
            for tool in server_tools:
                description = tool.description or "No description available"
                tools_desc.append(f"  - {tool.name}: {description}")

        return "Connected Servers and Available Tools:\n" + "\n".join(tools_desc)

    def format_tool_for_api(
        self, mcp_tool: mcp_types.Tool, server_name: str
    ) -> Dict[str, Any]:
        """Convert MCP tool to Claude tool format."""
        return {
            "name": mcp_tool.name,
            "description": mcp_tool.description
            or f"Call {mcp_tool.name} on {server_name} server",
            "input_schema": mcp_tool.inputSchema,
        }

    def parse_tool_calls(self, response: Any) -> List[ToolCall]:
        """Parse tool calls from Claude response."""
        tool_calls = []

        if hasattr(response, "content"):
            for content_block in response.content:
                if hasattr(content_block, "type") and content_block.type == "tool_use":
                    tool_call = ToolCall(
                        id=getattr(content_block, "id", ""),
                        tool_name=getattr(content_block, "name", ""),
                        arguments=getattr(content_block, "input", {}),
                    )
                    tool_calls.append(tool_call)

        return tool_calls

    def format_messages_for_api(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format messages for Claude's API."""
        # Claude expects messages without system messages (those go in system parameter)
        formatted_messages = []

        for message in messages:
            if message.get("role") != "system":
                formatted_messages.append(message)

        return formatted_messages

    def format_tool_results_for_api(
        self, tool_calls: List[ToolCall], tool_results: List[Any]
    ) -> List[Dict[str, Any]]:
        """Format tool results for Claude's API."""
        # Claude expects tool results in user messages
        tool_result_blocks = []

        for tool_call, result in zip(tool_calls, tool_results):
            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": json.dumps(result.result)
                    if hasattr(result, "result") and result.result
                    else result.error
                    if hasattr(result, "error")
                    else "No result",
                }
            )

        return tool_result_blocks
