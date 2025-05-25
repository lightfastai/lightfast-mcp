"""Multi-server AI client for connecting to multiple MCP servers simultaneously."""

import asyncio
import json
import os
import shlex
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

import anthropic
import mcp.types as mcp_types
import openai
from fastmcp import Client

from ..utils.logging_utils import get_logger

logger = get_logger("MultiServerAIClient")


class ToolCallState(Enum):
    """States of tool call execution."""

    CALL = "call"
    RESULT = "result"
    ERROR = "error"


@dataclass
class ToolCall:
    """Represents a tool call at the application level."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    server_name: Optional[str] = None


@dataclass
class ToolResult:
    """Represents a tool call result at the application level."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    server_name: Optional[str] = None

    @property
    def state(self) -> ToolCallState:
        """Get the current state of this tool result."""
        if self.error:
            return ToolCallState.ERROR
        elif self.result is not None:
            return ToolCallState.RESULT
        else:
            return ToolCallState.CALL


@dataclass
class Step:
    """Represents a single step in the conversation."""

    step_number: int
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[dict[str, Any]] = None

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call to this step."""
        self.tool_calls.append(tool_call)

    def add_tool_result(self, tool_result: ToolResult) -> None:
        """Add a tool result to this step."""
        self.tool_results.append(tool_result)

    def has_pending_tool_calls(self) -> bool:
        """Check if this step has tool calls that haven't been executed yet."""
        executed_ids = {result.id for result in self.tool_results}
        return any(call.id not in executed_ids for call in self.tool_calls)


@dataclass
class ConversationState:
    """Tracks the current state of the conversation."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    current_step: int = 0
    max_steps: int = 1
    is_complete: bool = False

    def get_current_step(self) -> Optional[Step]:
        """Get the current step being processed."""
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def create_new_step(self) -> Step:
        """Create and add a new step."""
        step = Step(step_number=len(self.steps))
        self.steps.append(step)
        return step

    def can_continue(self) -> bool:
        """Check if the conversation can continue to the next step."""
        return (
            not self.is_complete
            and self.current_step < self.max_steps - 1
            and len(self.steps) > 0
        )


def mcp_result_to_our_result(
    mcp_result: list[
        mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource
    ],
    tool_call: ToolCall,
) -> ToolResult:
    """Convert MCP tool call result to our ToolResult format."""
    result = ToolResult(
        id=tool_call.id,
        tool_name=tool_call.tool_name,
        arguments=tool_call.arguments,
        server_name=tool_call.server_name,
    )

    if mcp_result and len(mcp_result) > 0:
        # Handle different content types safely
        content = mcp_result[0]
        if hasattr(content, "text"):
            try:
                # Try to parse as JSON first
                result.result = json.loads(content.text)
            except json.JSONDecodeError:
                # If not JSON, store as text
                result.result = content.text
        else:
            # Handle other content types
            result.result = {"type": type(content).__name__, "content": str(content)}
    else:
        result.error = "No result returned"

    return result


def mcp_tool_to_claude_tool(
    mcp_tool: mcp_types.Tool, server_name: str
) -> dict[str, Any]:
    """Convert MCP Tool to Claude tool format."""
    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description
        or f"Call {mcp_tool.name} on {server_name} server",
        "input_schema": mcp_tool.inputSchema,
    }


def mcp_tool_to_openai_tool(
    mcp_tool: mcp_types.Tool, server_name: str
) -> dict[str, Any]:
    """Convert MCP Tool to OpenAI tool format."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description
            or f"Call {mcp_tool.name} on {server_name} server",
            "parameters": mcp_tool.inputSchema,
        },
    }


class MultiServerAIClient:
    """Multi-server AI client for connecting to multiple MCP servers simultaneously."""

    def __init__(
        self,
        servers: dict[str, dict[str, Any]],
        ai_provider: str = "claude",
        api_key: Optional[str] = None,
        max_steps: int = 5,
    ):
        """Initialize the multi-server AI client."""
        self.servers = servers
        self.clients: dict[str, Client] = {}
        self.tools: dict[
            str, tuple[mcp_types.Tool, str]
        ] = {}  # tool_name -> (mcp_tool, server_name)

        # AI client setup
        self.ai_provider = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.conversation_state = ConversationState(max_steps=max_steps)

        # Callbacks
        self.on_step_finish: Optional[Callable[[Step], None]] = None
        self.on_tool_call: Optional[Callable[[ToolCall], Any]] = None

        # Initialize AI client
        self._setup_ai_client()

    def _get_api_key(self) -> str:
        """Get API key from environment variables."""
        if self.ai_provider == "claude":
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable required for Claude"
                )
        elif self.ai_provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable required for OpenAI"
                )
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")
        return key

    def _setup_ai_client(self):
        """Setup AI client using official SDKs."""
        if self.ai_provider == "claude":
            self.ai_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        elif self.ai_provider == "openai":
            self.ai_client = openai.AsyncOpenAI(api_key=self.api_key)

    async def connect_to_servers(self) -> None:
        """Connect to all configured servers."""
        for server_name, server_config in self.servers.items():
            try:
                logger.info(f"Connecting to {server_name}...")

                if server_config.get("type") == "stdio":
                    # For stdio, we need to use the command and args properly
                    command = server_config.get("command", "")
                    args = server_config.get("args", [])

                    if not command:
                        raise ValueError(
                            f"Missing command for stdio server {server_name}"
                        )

                    # Combine command and args properly
                    if args:
                        full_command = shlex.join([command] + args)
                    else:
                        full_command = command

                    # URL-encode the command for the stdio URL
                    encoded_command = urllib.parse.quote(full_command, safe="")
                    client = Client(f"stdio://{encoded_command}")
                elif server_config.get("type") == "sse":
                    # For HTTP/SSE, use the URL directly
                    url = server_config.get("url", "")
                    client = Client(url)
                else:
                    logger.error(
                        f"Unsupported transport type for {server_name}: {server_config.get('type')}"
                    )
                    continue

                # Store the client - connection will be managed per-operation
                self.clients[server_name] = client
                logger.info(f"Connected to {server_name}")
            except Exception as e:
                logger.error(f"Failed to connect to {server_name}: {e}")

        # Get tools after connecting
        await self._get_available_tools()

    async def _get_available_tools(self) -> None:
        """Get available tools from all connected servers using MCP types."""
        self.tools = {}
        for server_name, client in self.clients.items():
            try:
                # Get tools using MCP list_tools with async context manager
                async with client:
                    tools_result = await client.list_tools()
                    # Handle different response formats - might be a list or an object with .tools
                    if hasattr(tools_result, "tools"):
                        mcp_tools = tools_result.tools
                    elif isinstance(tools_result, list):
                        mcp_tools = tools_result
                    else:
                        mcp_tools = []

                    for mcp_tool in mcp_tools:
                        # Store the MCP tool object along with server name
                        self.tools[mcp_tool.name] = (mcp_tool, server_name)
                        logger.debug(f"Added tool {mcp_tool.name} from {server_name}")

            except Exception as e:
                logger.error(f"Failed to get tools from {server_name}: {e}")

    def _build_claude_tools(self) -> list[dict[str, Any]]:
        """Build tools list for Claude API using MCP tools."""
        claude_tools = []
        for tool_name, (mcp_tool, server_name) in self.tools.items():
            claude_tool = mcp_tool_to_claude_tool(mcp_tool, server_name)
            claude_tools.append(claude_tool)
        return claude_tools

    def _build_openai_tools(self) -> list[dict[str, Any]]:
        """Build tools list for OpenAI API using MCP tools."""
        openai_tools = []
        for tool_name, (mcp_tool, server_name) in self.tools.items():
            openai_tool = mcp_tool_to_openai_tool(mcp_tool, server_name)
            openai_tools.append(openai_tool)
        return openai_tools

    async def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call using MCP and convert result."""
        if tool_call.tool_name not in self.tools:
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error=f"Tool {tool_call.tool_name} not found",
            )

        mcp_tool, server_name = self.tools[tool_call.tool_name]
        client = self.clients[server_name]

        try:
            # Use MCP call_tool with async context manager
            async with client:
                mcp_result = await client.call_tool(
                    tool_call.tool_name, tool_call.arguments
                )

            # Convert MCP result to our format
            # Handle different response formats - might be a list or an object with .content
            if hasattr(mcp_result, "content"):
                content = mcp_result.content
            elif isinstance(mcp_result, list):
                content = mcp_result
            else:
                content = [mcp_result] if mcp_result else []

            result = mcp_result_to_our_result(content, tool_call)
            result.server_name = server_name
            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_call.tool_name}: {e}")
            return ToolResult(
                id=tool_call.id,
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments,
                error=str(e),
                server_name=server_name,
            )

    async def _execute_tool_calls_concurrently(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolResult]:
        """Execute multiple tool calls concurrently."""
        if not tool_calls:
            return []

        tasks = [self._execute_tool_call(call) for call in tool_calls]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def _parse_claude_tool_calls(self, message: dict[str, Any]) -> list[ToolCall]:
        """Parse tool calls from Claude response."""
        tool_calls = []
        content = message.get("content", [])

        for item in content:
            if item.get("type") == "tool_use":
                tool_call = ToolCall(
                    id=item.get("id", ""),
                    tool_name=item.get("name", ""),
                    arguments=item.get("input", {}),
                )
                tool_calls.append(tool_call)

        return tool_calls

    def _parse_openai_tool_calls(self, message: dict[str, Any]) -> list[ToolCall]:
        """Parse tool calls from OpenAI response."""
        tool_calls = []
        raw_tool_calls = message.get("tool_calls", [])

        for tool_call in raw_tool_calls:
            try:
                arguments = json.loads(
                    tool_call.get("function", {}).get("arguments", "{}")
                )
            except json.JSONDecodeError:
                arguments = {}

            parsed_call = ToolCall(
                id=tool_call.get("id", ""),
                tool_name=tool_call.get("function", {}).get("name", ""),
                arguments=arguments,
            )
            tool_calls.append(parsed_call)

        return tool_calls

    async def generate_text_step(
        self, messages: list[dict[str, Any]], step: Step
    ) -> None:
        """Generate text for a single step."""
        # Make AI request based on provider
        if self.ai_provider == "claude":
            # Claude expects system prompt as separate parameter and native tool calling
            tools_context = self._build_tools_context()
            system_prompt = f"""You are an AI assistant that can control multiple creative applications through MCP servers.

{tools_context}

You can use the available tools to interact with the connected servers. When you need to perform actions, use the appropriate tools. For conversational responses, respond normally with helpful information."""

            # Build tools for Claude's native tool calling
            claude_tools = self._build_claude_tools()

            logger.info(f"Built {len(claude_tools)} tools for Claude")

            # Only pass tools if we have some, otherwise omit the parameter entirely
            api_params = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": messages,
            }

            if claude_tools:  # Only add tools if we have any
                api_params["tools"] = claude_tools

            response = await self.ai_client.messages.create(**api_params)

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

            if not step.tool_calls and not step.text:
                step.finish_reason = "stop"

        elif self.ai_provider == "openai":
            # OpenAI accepts system message in messages array and uses function calling
            tools_context = self._build_tools_context()
            system_prompt = f"""You are an AI assistant that can control multiple creative applications through MCP servers.

{tools_context}

You can use the available tools to interact with the connected servers. When you need to perform actions, use the appropriate tools. For conversational responses, respond normally with helpful information."""

            full_messages = [{"role": "system", "content": system_prompt}] + messages
            openai_tools = self._build_openai_tools()

            # Build API parameters, only including tools if we have any
            api_params = {
                "model": "gpt-4o",
                "messages": full_messages,
                "max_tokens": 4000,
            }

            if openai_tools:  # Only add tools if we have any
                api_params["tools"] = openai_tools
                api_params["tool_choice"] = "auto"

            response = await self.ai_client.chat.completions.create(**api_params)

            message = response.choices[0].message

            # Parse the response
            if message.content:
                step.text = message.content

            if message.tool_calls:
                # Parse OpenAI tool calls
                tool_calls = self._parse_openai_tool_calls(
                    {"tool_calls": message.tool_calls}
                )
                for tool_call in tool_calls:
                    step.add_tool_call(tool_call)

            if not step.tool_calls and not step.text:
                step.finish_reason = "stop"
        else:
            step.text = "Unsupported AI provider"
            step.finish_reason = "stop"

    def _build_tools_context(self) -> str:
        """Build a context description of available tools."""
        if not self.tools:
            return "No connected servers or tools available."

        tools_desc = []
        tools_by_server = {}

        # Group tools by server
        for tool_name, (mcp_tool, server_name) in self.tools.items():
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

    async def execute_step_tool_calls(self, step: Step) -> None:
        """Execute all tool calls in a step."""
        if not step.tool_calls:
            return

        # Execute tool calls concurrently
        results = await self._execute_tool_calls_concurrently(step.tool_calls)

        # Add results to the step
        for result in results:
            step.add_tool_result(result)

    async def generate_with_steps(
        self, prompt: str, include_context: bool = True
    ) -> AsyncIterator[Step]:
        """Generate a response using the step-based approach with tool calling."""
        # Initialize conversation
        self.conversation_state = ConversationState(
            max_steps=self.conversation_state.max_steps
        )
        self.conversation_state.messages = [{"role": "user", "content": prompt}]

        current_messages = self.conversation_state.messages.copy()

        for step_num in range(self.conversation_state.max_steps):
            # Create new step
            step = self.conversation_state.create_new_step()
            step.step_number = step_num

            logger.info(
                f"Starting step {step_num + 1}/{self.conversation_state.max_steps}"
            )

            # Generate text for this step
            await self.generate_text_step(current_messages, step)

            # If we have tool calls, execute them
            if step.tool_calls:
                await self.execute_step_tool_calls(step)

                if self.ai_provider == "claude":
                    # Claude format: tool calls and results in assistant message content
                    content_blocks = []

                    # Add text content if any
                    if step.text:
                        content_blocks.append({"type": "text", "text": step.text})

                    # Add tool use blocks
                    for tc in step.tool_calls:
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tc.id,
                                "name": tc.tool_name,
                                "input": tc.arguments,
                            }
                        )

                    assistant_message = {
                        "role": "assistant",
                        "content": content_blocks,
                    }
                    current_messages.append(assistant_message)

                    # Add user message with tool results
                    tool_result_blocks = []
                    for result in step.tool_results:
                        tool_result_blocks.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": result.id,
                                "content": json.dumps(result.result)
                                if result.result
                                else result.error or "No result",
                            }
                        )

                    if tool_result_blocks:
                        user_message = {
                            "role": "user",
                            "content": tool_result_blocks,
                        }
                        current_messages.append(user_message)

                elif self.ai_provider == "openai":
                    # OpenAI format: separate tool call and tool result messages
                    assistant_message = {
                        "role": "assistant",
                        "content": step.text or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.tool_name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in step.tool_calls
                        ],
                    }
                    current_messages.append(assistant_message)

                    # Add tool result messages
                    for result in step.tool_results:
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": result.id,
                            "content": json.dumps(result.result)
                            if result.result
                            else result.error or "No result",
                        }
                        current_messages.append(tool_message)

            else:
                # Regular text response - conversation is complete
                current_messages.append({"role": "assistant", "content": step.text})
                step.finish_reason = "stop"
                self.conversation_state.is_complete = True

            # Call step finish callback
            if self.on_step_finish:
                self.on_step_finish(step)

            # Yield the completed step
            yield step

            # Check if we should continue
            if (
                self.conversation_state.is_complete
                or step.finish_reason == "stop"
                or not step.tool_calls
            ):
                break

        # Update conversation state
        self.conversation_state.current_step = len(self.conversation_state.steps)

    async def chat_with_steps(
        self,
        message: str,
        include_context: bool = True,
        max_steps: Optional[int] = None,
    ) -> list[Step]:
        """Chat with AI and return all steps."""
        if max_steps:
            self.conversation_state.max_steps = max_steps

        steps = []
        async for step in self.generate_with_steps(message, include_context):
            steps.append(step)

        return steps

    async def chat_with_ai(self, message: str, include_context: bool = True) -> str:
        """Chat with AI about the connected servers (legacy method for backward compatibility)."""
        steps = await self.chat_with_steps(message, include_context)

        # Combine all step outputs
        result_parts = []
        for step in steps:
            if step.text:
                result_parts.append(step.text)

            # Add tool execution summaries
            for result in step.tool_results:
                if result.result:
                    result_parts.append(
                        f"Tool {result.tool_name} result: {result.result}"
                    )
                elif result.error:
                    result_parts.append(
                        f"Tool {result.tool_name} error: {result.error}"
                    )

        return "\n\n".join(result_parts) if result_parts else "No response generated."

    def get_connected_servers(self) -> list[str]:
        """Get list of connected server names."""
        return list(self.clients.keys())

    def get_all_tools(self) -> dict[str, list[str]]:
        """Get all available tools organized by server."""
        tools_by_server = {}
        for tool_name, (mcp_tool, server_name) in self.tools.items():
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool_name)
        return tools_by_server

    def find_tool_server(self, tool_name: str) -> Optional[str]:
        """Find which server has a specific tool."""
        if tool_name in self.tools:
            return self.tools[tool_name][1]
        return None

    def get_server_status(self) -> dict[str, dict[str, Any]]:
        """Get status information for all servers."""
        status = {}
        for server_name, client in self.clients.items():
            server_tools = [
                tool for tool, (_, srv) in self.tools.items() if srv == server_name
            ]
            status[server_name] = {
                "connected": True,  # If it's in clients, it's connected
                "tools_count": len(server_tools),
                "tools": server_tools,
            }
        return status

    def get_conversation_state(self) -> ConversationState:
        """Get the current conversation state."""
        return self.conversation_state

    async def disconnect_from_servers(self):
        """Disconnect from all servers."""
        logger.info("Disconnecting from all servers...")

        for server_name, client in self.clients.items():
            try:
                await client.close()
                logger.debug(f"Disconnected from {server_name}")
            except Exception as e:
                logger.debug(f"Error disconnecting from {server_name}: {e}")

        self.clients.clear()
        self.tools.clear()


async def create_multi_server_client_from_config(
    servers: dict[str, dict[str, Any]],
    ai_provider: str = "claude",
    api_key: Optional[str] = None,
    max_steps: int = 5,
) -> MultiServerAIClient:
    """Create and connect a multi-server client from configuration."""
    client = MultiServerAIClient(
        servers=servers,
        ai_provider=ai_provider,
        api_key=api_key,
        max_steps=max_steps,
    )
    await client.connect_to_servers()
    return client
