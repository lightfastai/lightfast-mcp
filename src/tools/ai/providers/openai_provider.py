"""OpenAI AI provider implementation."""

import json
from typing import Any, Dict, List

import mcp.types as mcp_types
import openai

from tools.common import (
    ConversationStep,
    OperationStatus,
    Result,
    ToolCall,
    get_logger,
)

from .base_provider import BaseAIProvider

logger = get_logger("OpenAIProvider")


class OpenAIProvider(BaseAIProvider):
    """OpenAI AI provider implementation."""

    def __init__(self, api_key: str):
        """Initialize OpenAI provider."""
        super().__init__(api_key)
        self.client = openai.AsyncOpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return "openai"

    @property
    def default_model(self) -> str:
        """Get the default model for this provider."""
        return "gpt-4o"

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

            # Format messages for OpenAI (includes system message in messages array)
            formatted_messages = [
                {"role": "system", "content": system_prompt}
            ] + self.format_messages_for_api(messages)

            # Build tools for OpenAI's function calling
            openai_tools = []
            for tool_name, (mcp_tool, server_name) in available_tools.items():
                openai_tool = self.format_tool_for_api(mcp_tool, server_name)
                openai_tools.append(openai_tool)

            # Prepare API parameters
            api_params = {
                "model": self.default_model,
                "messages": formatted_messages,
                "max_tokens": 4000,
            }

            # Only add tools if we have any
            if openai_tools:
                api_params["tools"] = openai_tools
                api_params["tool_choice"] = "auto"

            logger.debug(f"Making OpenAI API call with {len(openai_tools)} tools")
            response = await self.client.chat.completions.create(**api_params)

            # Create conversation step
            step = ConversationStep(step_number=step_number)
            message = response.choices[0].message

            # Parse the response
            if message.content:
                step.text = message.content

            if message.tool_calls:
                # Parse OpenAI tool calls
                tool_calls = self.parse_tool_calls(message)
                for tool_call in tool_calls:
                    step.add_tool_call(tool_call)

            # Set finish reason if no tool calls and no text
            if not step.tool_calls and not step.text:
                step.finish_reason = "stop"

            return Result(status=OperationStatus.SUCCESS, data=step)

        except Exception as e:
            logger.error("OpenAI API call failed", error=e)
            return Result(
                status=OperationStatus.FAILED,
                error=f"OpenAI API error: {e}",
                error_code="OPENAI_API_ERROR",
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
        """Convert MCP tool to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": mcp_tool.name,
                "description": mcp_tool.description
                or f"Call {mcp_tool.name} on {server_name} server",
                "parameters": mcp_tool.inputSchema,
            },
        }

    def parse_tool_calls(self, message: Any) -> List[ToolCall]:
        """Parse tool calls from OpenAI response."""
        tool_calls = []

        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                try:
                    arguments = json.loads(
                        tool_call.function.arguments
                        if hasattr(tool_call.function, "arguments")
                        else "{}"
                    )
                except json.JSONDecodeError:
                    arguments = {}

                parsed_call = ToolCall(
                    id=tool_call.id if hasattr(tool_call, "id") else "",
                    tool_name=tool_call.function.name
                    if hasattr(tool_call.function, "name")
                    else "",
                    arguments=arguments,
                )
                tool_calls.append(parsed_call)

        return tool_calls

    def format_messages_for_api(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format messages for OpenAI's API."""
        # OpenAI accepts all message types in the messages array
        return messages

    def format_tool_results_for_api(
        self, tool_calls: List[ToolCall], tool_results: List[Any]
    ) -> List[Dict[str, Any]]:
        """Format tool results for OpenAI's API."""
        # OpenAI expects tool results as separate tool messages
        tool_messages = []

        for tool_call, result in zip(tool_calls, tool_results):
            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result.result)
                if hasattr(result, "result") and result.result
                else result.error
                if hasattr(result, "error")
                else "No result",
            }
            tool_messages.append(tool_message)

        return tool_messages
