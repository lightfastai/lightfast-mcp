#!/usr/bin/env python3
"""
AI-integrated Blender client that connects AI models to FastMCP Blender server.
Supports Claude API, OpenAI API, and other providers.
"""

import asyncio
import json
import os
from typing import Any

import httpx
from fastmcp import Client


class AIBlenderClient:
    """Client that bridges AI models with Blender MCP server"""

    def __init__(
        self, mcp_server_url: str = "http://localhost:8000/mcp", ai_provider: str = "claude", api_key: str | None = None
    ):
        self.mcp_server_url = mcp_server_url
        self.ai_provider = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.mcp_client = None

    def _get_api_key(self) -> str:
        """Get API key from environment variables"""
        if self.ai_provider == "claude":
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY environment variable required for Claude")
        elif self.ai_provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY environment variable required for OpenAI")
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")
        return key

    async def connect_to_blender(self):
        """Connect to the Blender MCP server"""
        try:
            self.mcp_client = Client(self.mcp_server_url)
            await self.mcp_client.__aenter__()
            print("✅ Connected to Blender MCP server")

            # Test connection by listing tools
            tools = await self.mcp_client.list_tools()
            print(f"📝 Available tools: {[tool.name for tool in tools]}")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to Blender MCP server: {e}")
            print("   Make sure the HTTP server is running: python run_blender_http.py")
            return False

    async def disconnect_from_blender(self):
        """Disconnect from Blender MCP server"""
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
            self.mcp_client = None

    async def get_blender_tools_description(self) -> str:
        """Get formatted description of available Blender tools for AI"""
        if not self.mcp_client:
            raise RuntimeError("Not connected to Blender MCP server")

        tools = await self.mcp_client.list_tools()

        descriptions = []
        for tool in tools:
            descriptions.append(f"- {tool.name}: {tool.description}")

        return "Available Blender tools:\n" + "\n".join(descriptions)

    async def execute_blender_tool(self, tool_name: str, arguments: dict[str, Any] = None) -> dict[str, Any]:
        """Execute a tool on the Blender MCP server"""
        if not self.mcp_client:
            raise RuntimeError("Not connected to Blender MCP server")

        try:
            result = await self.mcp_client.call_tool(tool_name, arguments or {})
            # Parse the result
            if result and len(result) > 0:
                return json.loads(result[0].text)
            return {"error": "No result returned"}

        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    async def chat_with_ai(self, message: str, include_blender_context: bool = True) -> str:
        """Send message to AI with optional Blender context"""

        # Build the prompt
        full_prompt = message

        if include_blender_context and self.mcp_client:
            try:
                tools_desc = await self.get_blender_tools_description()
                scene_state = await self.execute_blender_tool("get_state")

                context = f"""
{tools_desc}

Current Blender scene state:
{json.dumps(scene_state, indent=2)}

User request: {message}

You can use the available Blender tools by responding with JSON in this format:
{{"action": "blender_tool", "tool": "tool_name", "arguments": {{"param": "value"}}}}

Or respond normally if no Blender action is needed.
"""
                full_prompt = context

            except Exception as e:
                print(f"⚠️  Warning: Could not get Blender context: {e}")

        # Call the appropriate AI API
        if self.ai_provider == "claude":
            return await self._call_claude_api(full_prompt)
        elif self.ai_provider == "openai":
            return await self._call_openai_api(full_prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {self.ai_provider}")

    async def _call_claude_api(self, prompt: str) -> str:
        """Call Claude API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code != 200:
                raise Exception(f"Claude API error: {response.status_code} - {response.text}")

            result = response.json()
            return result["content"][0]["text"]

    async def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": prompt}], "max_tokens": 4000},
            )

            if response.status_code != 200:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

    async def process_ai_response(self, ai_response: str) -> str:
        """Process AI response and execute Blender tools if requested"""
        try:
            # Try to parse as JSON (tool call)
            response_data = json.loads(ai_response.strip())

            if response_data.get("action") == "blender_tool":
                tool_name = response_data.get("tool")
                arguments = response_data.get("arguments", {})

                print(f"🔧 Executing Blender tool: {tool_name}")
                result = await self.execute_blender_tool(tool_name, arguments)

                return f"Executed {tool_name}: {json.dumps(result, indent=2)}"

        except json.JSONDecodeError:
            # Not a tool call, return as-is
            pass

        return ai_response


async def main():
    """Example usage"""
    # You can set AI_PROVIDER environment variable to "claude" or "openai"
    ai_provider = os.getenv("AI_PROVIDER", "claude")

    client = AIBlenderClient(ai_provider=ai_provider)

    # Connect to Blender
    if not await client.connect_to_blender():
        return

    try:
        print(f"\n🤖 AI Blender Client ready! (Using {ai_provider.upper()})")
        print("Ask questions about Blender or request actions...")
        print("Type 'quit' to exit\n")

        while True:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break

            try:
                # Get AI response
                print("🤔 AI is thinking...")
                ai_response = await client.chat_with_ai(user_input)

                # Process any tool calls
                final_response = await client.process_ai_response(ai_response)

                print(f"🤖 AI: {final_response}\n")

            except Exception as e:
                print(f"❌ Error: {e}\n")

    finally:
        await client.disconnect_from_blender()


if __name__ == "__main__":
    asyncio.run(main())
