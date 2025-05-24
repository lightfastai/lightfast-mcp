"""Multi-server AI client for connecting to multiple MCP servers simultaneously."""

import asyncio
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

import anthropic
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
    """Represents a tool call."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    server_name: Optional[str] = None


@dataclass
class ToolResult:
    """Represents a tool call result."""

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


class ServerConnection:
    """Represents a connection to an MCP server."""

    def __init__(self, name: str, url: str, description: str = ""):
        self.name = name
        self.url = url
        self.description = description
        self.client: Client | None = None
        self.tools: list[str] = []
        self.is_connected = False
        self.last_error = ""

    async def connect(self) -> bool:
        """Connect to the MCP server."""
        try:
            self.client = Client(self.url)
            await self.client.__aenter__()

            # Get available tools
            tools_list = await self.client.list_tools()
            self.tools = [tool.name for tool in tools_list]

            self.is_connected = True
            self.last_error = ""
            logger.info(f"Connected to {self.name} at {self.url} (tools: {self.tools})")
            return True

        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            logger.error(f"Failed to connect to {self.name}: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.client and self.is_connected:
            try:
                await self.client.__aexit__(None, None, None)
                logger.info(f"Disconnected from {self.name}")
            except Exception as e:
                # Log the error but don't raise it during cleanup
                logger.debug(f"Error disconnecting from {self.name}: {e}")
            finally:
                self.client = None
                self.is_connected = False

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call a tool on this server."""
        if not self.is_connected or not self.client:
            raise RuntimeError(f"Not connected to {self.name}")

        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not available on {self.name}")

        try:
            result = await self.client.call_tool(tool_name, arguments or {})
            if result and len(result) > 0:
                # Handle different content types safely
                content = result[0]
                if hasattr(content, "text"):
                    return json.loads(content.text)
                else:
                    # Handle other content types or return error
                    return {
                        "error": f"Unsupported content type: {type(content).__name__}"
                    }
            return {"error": "No result returned"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}


class MultiServerAIClient:
    """AI client that can connect to multiple MCP servers with Vercel AI SDK-like behavior."""

    def __init__(
        self,
        ai_provider: str = "claude",
        api_key: str | None = None,
        max_steps: int = 5,
    ):
        self.ai_provider = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.servers: dict[str, ServerConnection] = {}
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

    def add_server(self, name: str, url: str, description: str = ""):
        """Add a server to connect to."""
        self.servers[name] = ServerConnection(name, url, description)
        logger.info(f"Added server: {name} at {url}")

    def remove_server(self, name: str):
        """Remove a server."""
        if name in self.servers:
            asyncio.create_task(self.servers[name].disconnect())
            del self.servers[name]
            logger.info(f"Removed server: {name}")

    async def connect_to_servers(self) -> dict[str, bool]:
        """Connect to all configured servers."""
        logger.info(f"Connecting to {len(self.servers)} servers...")

        # Connect to all servers concurrently
        tasks = []
        for server in self.servers.values():
            tasks.append(server.connect())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dictionary
        connection_results = {}
        for server, result in zip(self.servers.values(), results, strict=False):
            if isinstance(result, Exception):
                connection_results[server.name] = False
                logger.error(f"Exception connecting to {server.name}: {result}")
            else:
                connection_results[server.name] = bool(result)

        successful = sum(1 for success in connection_results.values() if success)
        logger.info(
            f"Successfully connected to {successful}/{len(self.servers)} servers"
        )

        return connection_results

    async def disconnect_from_servers(self):
        """Disconnect from all servers."""
        logger.info("Disconnecting from all servers...")

        # Create list of disconnect tasks but handle them individually
        # to avoid one failure affecting others
        disconnection_tasks = []
        for server in self.servers.values():
            if server.is_connected:
                disconnection_tasks.append(self._safe_disconnect(server))

        if disconnection_tasks:
            # Use gather with return_exceptions=True to handle errors gracefully
            results = await asyncio.gather(*disconnection_tasks, return_exceptions=True)

            # Log any errors that occurred during disconnection
            for server_name, result in zip(
                [s.name for s in self.servers.values() if s.is_connected], results
            ):
                if isinstance(result, Exception):
                    logger.debug(f"Error disconnecting from {server_name}: {result}")

    async def _safe_disconnect(self, server):
        """Safely disconnect from a server with error handling."""
        try:
            await server.disconnect()
        except Exception as e:
            # Don't raise, just log for debugging
            logger.debug(f"Safe disconnect error for {server.name}: {e}")
            # Still mark as disconnected
            server.is_connected = False

    def get_connected_servers(self) -> list[str]:
        """Get list of connected server names."""
        return [name for name, server in self.servers.items() if server.is_connected]

    def get_all_tools(self) -> dict[str, list[str]]:
        """Get all available tools organized by server."""
        tools_by_server = {}
        for name, server in self.servers.items():
            if server.is_connected:
                tools_by_server[name] = server.tools
        return tools_by_server

    def find_tool_server(self, tool_name: str) -> str | None:
        """Find which server has a specific tool."""
        for name, server in self.servers.items():
            if server.is_connected and tool_name in server.tools:
                return name
        return None

    async def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        result = ToolResult(
            id=tool_call.id,
            tool_name=tool_call.tool_name,
            arguments=tool_call.arguments,
            server_name=tool_call.server_name,
        )

        try:
            # Find server if not specified
            if not tool_call.server_name:
                tool_call.server_name = self.find_tool_server(tool_call.tool_name)

            if not tool_call.server_name:
                result.error = (
                    f"Tool '{tool_call.tool_name}' not found on any connected server"
                )
                return result

            # Check if server is connected
            server = self.servers.get(tool_call.server_name)
            if not server or not server.is_connected:
                result.error = f"Server '{tool_call.server_name}' not connected"
                return result

            # Execute the tool
            execution_result = await server.call_tool(
                tool_call.tool_name, tool_call.arguments
            )

            if "error" in execution_result:
                result.error = execution_result["error"]
            else:
                result.result = execution_result

        except Exception as e:
            result.error = f"Tool execution failed: {str(e)}"

        return result

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
            claude_tools = []
            for server_name, server in self.servers.items():
                if server.is_connected:
                    for tool_name in server.tools:
                        claude_tools.append(
                            {
                                "name": tool_name,
                                "description": f"Call {tool_name} on {server_name} server",
                                "input_schema": {
                                    "type": "object",
                                    "properties": {},
                                    "additionalProperties": True,
                                },
                            }
                        )

            response = await self.ai_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=system_prompt,
                messages=messages,
                tools=claude_tools if claude_tools else None,
            )

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
                            server_name=self.find_tool_server(content_block.name),
                        )
                        step.add_tool_call(tool_call)

            if not step.tool_calls and not step.text:
                step.finish_reason = "stop"

        elif self.ai_provider == "openai":
            # OpenAI accepts system message in messages array and uses JSON tool calling
            tools_context = self._build_tools_context()
            system_prompt = f"""You are an AI assistant that can control multiple creative applications through MCP servers.

{tools_context}

When you want to use a tool, respond with ONLY JSON in this exact format (no extra text):
{{"action": "tool_call", "tool": "tool_name", "server": "server_name", "arguments": {{"param": "value"}}}}

If the server name is not specified, I'll automatically find the right server for the tool.
For conversational responses (when not using tools), respond normally with helpful information."""

            full_messages = [{"role": "system", "content": system_prompt}] + messages
            response = await self.ai_client.chat.completions.create(
                model="gpt-4o",
                messages=full_messages,
                max_tokens=4000,
            )
            ai_response = response.choices[0].message.content or ""

            # Parse the response for JSON tool calls
            tool_calls = self._parse_tool_calls_from_response(ai_response)

            if tool_calls:
                # Add tool calls to the step
                for tool_call in tool_calls:
                    step.add_tool_call(tool_call)
            else:
                # Regular text response
                step.text = ai_response
                step.finish_reason = "stop"
        else:
            step.text = "Unsupported AI provider"
            step.finish_reason = "stop"

    def _build_tools_context(self) -> str:
        """Build a context description of available tools."""
        tools_desc = []
        for server_name, server in self.servers.items():
            if server.is_connected:
                server_desc = server.description or ""
                tools_desc.append(f"**{server_name}** ({server_desc}):")
                for tool in server.tools:
                    tools_desc.append(f"  - {tool}")

        return "Connected Servers and Available Tools:\n" + "\n".join(tools_desc)

    def _parse_tool_calls_from_response(self, response: str) -> list[ToolCall]:
        """Parse tool calls from AI response."""
        tool_calls = []

        try:
            # Try to parse as JSON (tool call)
            response_data = json.loads(response.strip())

            if response_data.get("action") == "tool_call":
                tool_name = response_data.get("tool")
                server_name = response_data.get("server")
                arguments = response_data.get("arguments", {})

                if tool_name:
                    tool_call = ToolCall(
                        id=f"call_{len(tool_calls)}_{tool_name}",
                        tool_name=tool_name,
                        arguments=arguments,
                        server_name=server_name,
                    )
                    tool_calls.append(tool_call)

        except json.JSONDecodeError:
            # Try to extract JSON from the response if it's embedded in text
            json_match = self._extract_json_from_text(response)
            if json_match:
                try:
                    response_data = json.loads(json_match)
                    if response_data.get("action") == "tool_call":
                        tool_name = response_data.get("tool")
                        server_name = response_data.get("server")
                        arguments = response_data.get("arguments", {})

                        if tool_name:
                            tool_call = ToolCall(
                                id=f"call_{len(tool_calls)}_{tool_name}",
                                tool_name=tool_name,
                                arguments=arguments,
                                server_name=server_name,
                            )
                            tool_calls.append(tool_call)
                except json.JSONDecodeError:
                    pass

        return tool_calls

    def _extract_json_from_text(self, text: str) -> str | None:
        """Try to extract JSON object from text that might contain explanations."""
        import re

        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_pattern, text)

        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and parsed.get("action") == "tool_call":
                    return match
            except json.JSONDecodeError:
                continue

        return None

    async def execute_step_tool_calls(self, step: Step) -> None:
        """Execute all tool calls in a step."""
        if not step.tool_calls:
            return

        # Execute tool calls concurrently
        tasks = []
        for tool_call in step.tool_calls:
            tasks.append(self.execute_tool_call(tool_call))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Add results to the step
        for result in results:
            if isinstance(result, Exception):
                # Create error result
                error_result = ToolResult(
                    id="error",
                    tool_name="unknown",
                    arguments={},
                    error=str(result),
                )
                step.add_tool_result(error_result)
            else:
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
                        "content": "",
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

            for tool_result in step.tool_results:
                if tool_result.error:
                    result_parts.append(f"Tool error: {tool_result.error}")
                else:
                    result_parts.append(
                        f"Executed {tool_result.tool_name}: {json.dumps(tool_result.result, indent=2)}"
                    )

        return "\n".join(result_parts) if result_parts else "No response generated"

    def get_server_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all servers."""
        status = {}
        for name, server in self.servers.items():
            status[name] = {
                "connected": server.is_connected,
                "url": server.url,
                "tools_count": len(server.tools),
                "tools": server.tools,
                "last_error": server.last_error,
                "description": server.description,
            }
        return status

    def get_conversation_state(self) -> ConversationState:
        """Get the current conversation state."""
        return self.conversation_state


# Convenience functions for common workflows
async def create_multi_server_client_from_urls(
    server_urls: dict[str, str],
    ai_provider: str = "claude",
    api_key: str | None = None,
    max_steps: int = 5,
) -> MultiServerAIClient:
    """Create and connect a multi-server client from a dictionary of server URLs."""
    client = MultiServerAIClient(
        ai_provider=ai_provider, api_key=api_key, max_steps=max_steps
    )

    for name, url in server_urls.items():
        client.add_server(name, url)

    await client.connect_to_servers()
    return client
