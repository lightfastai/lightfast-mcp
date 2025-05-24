"""Multi-server AI client for connecting to multiple MCP servers simultaneously."""

import asyncio
import json
import os
from typing import Any

import anthropic
import openai
from fastmcp import Client

from ..utils.logging_utils import get_logger

logger = get_logger("MultiServerAIClient")


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
                logger.error(f"Error disconnecting from {self.name}: {e}")
            finally:
                self.client = None
                self.is_connected = False

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Call a tool on this server."""
        if not self.is_connected or not self.client:
            raise RuntimeError(f"Not connected to {self.name}")

        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not available on {self.name}")

        try:
            result = await self.client.call_tool(tool_name, arguments or {})
            if result and len(result) > 0:
                return json.loads(result[0].text)
            return {"error": "No result returned"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}


class MultiServerAIClient:
    """AI client that can connect to multiple MCP servers simultaneously."""

    def __init__(
        self,
        ai_provider: str = "claude",
        api_key: str | None = None,
    ):
        self.ai_provider = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.servers: dict[str, ServerConnection] = {}

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
                connection_results[server.name] = result

        successful = sum(1 for success in connection_results.values() if success)
        logger.info(
            f"Successfully connected to {successful}/{len(self.servers)} servers"
        )

        return connection_results

    async def disconnect_from_servers(self):
        """Disconnect from all servers."""
        logger.info("Disconnecting from all servers...")

        tasks = []
        for server in self.servers.values():
            if server.is_connected:
                tasks.append(server.disconnect())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

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

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] = None,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool on the appropriate server."""
        # If server is specified, use it
        if server_name:
            if server_name not in self.servers:
                return {"error": f"Server '{server_name}' not found"}

            if not self.servers[server_name].is_connected:
                return {"error": f"Server '{server_name}' not connected"}

            return await self.servers[server_name].call_tool(tool_name, arguments)

        # Otherwise, find the server that has this tool
        server_name = self.find_tool_server(tool_name)
        if not server_name:
            return {"error": f"Tool '{tool_name}' not found on any connected server"}

        return await self.servers[server_name].call_tool(tool_name, arguments)

    async def get_context_for_ai(self) -> dict[str, Any]:
        """Get context about all connected servers for AI."""
        context = {
            "connected_servers": {},
            "available_tools": {},
            "server_descriptions": {},
        }

        for name, server in self.servers.items():
            if server.is_connected:
                context["connected_servers"][name] = {
                    "url": server.url,
                    "tools": server.tools,
                    "description": server.description,
                }
                context["available_tools"][name] = server.tools
                context["server_descriptions"][name] = server.description

        return context

    async def chat_with_ai(self, message: str, include_context: bool = True) -> str:
        """Chat with AI about the connected servers."""
        # Build prompt with server context
        if include_context:
            context = await self.get_context_for_ai()

            # Build tools description
            tools_desc = []
            for server_name, tools in context["available_tools"].items():
                server_desc = context["server_descriptions"].get(server_name, "")
                tools_desc.append(f"**{server_name}** ({server_desc}):")
                for tool in tools:
                    tools_desc.append(f"  - {tool}")

            tools_description = "\n".join(tools_desc)

            system_prompt = f"""You are an AI assistant that can control multiple creative applications through MCP \
servers.

Connected Servers and Available Tools:
{tools_description}

When you want to use a tool, respond with JSON in this format:
{{"action": "tool_call", "tool": "tool_name", "server": "server_name", "arguments": {{"param": "value"}}}}

If the server name is not specified, I'll automatically find the right server for the tool.
Otherwise, respond normally with helpful information."""

            full_message = f"{system_prompt}\n\nUser: {message}"
        else:
            full_message = message

        # Make AI request
        if self.ai_provider == "claude":
            response = await self.ai_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": full_message}],
            )
            return response.content[0].text

        elif self.ai_provider == "openai":
            response = await self.ai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": full_message}],
                max_tokens=4000,
            )
            return response.choices[0].message.content

    async def process_ai_response(self, ai_response: str) -> str:
        """Process AI response and execute tool calls if requested."""
        try:
            # Try to parse as JSON (tool call)
            response_data = json.loads(ai_response.strip())

            if response_data.get("action") == "tool_call":
                tool_name = response_data.get("tool")
                server_name = response_data.get("server")
                arguments = response_data.get("arguments", {})

                if not tool_name:
                    return "Error: Tool name is required for tool calls"

                logger.info(
                    f"Executing tool: {tool_name} on server: {server_name or 'auto-detect'}"
                )
                result = await self.execute_tool(tool_name, arguments, server_name)

                return f"Executed {tool_name}: {json.dumps(result, indent=2)}"

        except json.JSONDecodeError:
            # Not a tool call, return as-is
            pass

        return ai_response

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


# Convenience functions for common workflows
async def create_multi_server_client_from_urls(
    server_urls: dict[str, str], ai_provider: str = "claude", api_key: str | None = None
) -> MultiServerAIClient:
    """Create and connect a multi-server client from a dictionary of server URLs."""
    client = MultiServerAIClient(ai_provider=ai_provider, api_key=api_key)

    for name, url in server_urls.items():
        client.add_server(name, url)

    await client.connect_to_servers()
    return client
