#!/usr/bin/env python3
"""
Simple AI-integrated Blender client using official SDKs.
Connects AI models (Claude/OpenAI) with Blender MCP server.
"""

import asyncio
import json
import os
from typing import Any

import anthropic
import openai
from fastmcp import Client


class AIBlenderClient:
    """Simple client that bridges AI models with Blender MCP server"""

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:8000/mcp",
        ai_provider: str = "claude",
        api_key: str | None = None,
    ):
        self.mcp_server_url = mcp_server_url
        self.ai_provider = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.mcp_client = None

        # Initialize AI client
        self._setup_ai_client()

    def _get_api_key(self) -> str:
        """Get API key from environment variables"""
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
        """Setup AI client using official SDKs"""
        if self.ai_provider == "claude":
            self.ai_client = anthropic.AsyncAnthropic(api_key=self.api_key)
        elif self.ai_provider == "openai":
            self.ai_client = openai.AsyncOpenAI(api_key=self.api_key)

    async def connect_to_blender(self) -> bool:
        """Connect to the Blender MCP server"""
        try:
            self.mcp_client = Client(self.mcp_server_url)
            await self.mcp_client.__aenter__()
            print("✅ Connected to Blender MCP server")

            tools = await self.mcp_client.list_tools()
            print(f"📝 Available tools: {[tool.name for tool in tools]}")
            return True

        except Exception as e:
            print(f"❌ Failed to connect to Blender MCP server: {e}")
            print(
                "   Make sure the HTTP server is running: ./scripts/test_blender.sh http"
            )
            return False

    async def disconnect_from_blender(self):
        """Disconnect from Blender MCP server"""
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
            self.mcp_client = None

    async def get_blender_context(self) -> dict[str, Any]:
        """Get current Blender context for AI"""
        if not self.mcp_client:
            return {}

        try:
            # Get tools description
            tools = await self.mcp_client.list_tools()
            tools_desc = "\n".join(
                [f"- {tool.name}: {tool.description}" for tool in tools]
            )

            # Get scene state
            result = await self.mcp_client.call_tool("get_state")
            scene_state = json.loads(result[0].text) if result else {}

            return {
                "tools_description": f"Available Blender tools:\n{tools_desc}",
                "scene_state": scene_state,
            }
        except Exception as e:
            print(f"⚠️  Warning: Could not get Blender context: {e}")
            return {}

    async def execute_blender_tool(
        self, tool_name: str, arguments: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Execute a tool on the Blender MCP server"""
        if not self.mcp_client:
            raise RuntimeError("Not connected to Blender MCP server")

        try:
            result = await self.mcp_client.call_tool(tool_name, arguments or {})
            if result and len(result) > 0:
                return json.loads(result[0].text)
            return {"error": "No result returned"}
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}

    async def chat_with_ai(self, message: str, include_context: bool = True) -> str:
        """Chat with AI using official SDKs"""

        # Build prompt with Blender context
        if include_context:
            context = await self.get_blender_context()
            if context:
                system_prompt = f"""You are an AI assistant that can control Blender through tools.

{context.get("tools_description", "")}

Current scene state:
{json.dumps(context.get("scene_state", {}), indent=2)}

When you want to use a Blender tool, respond with JSON in this format:
{{"action": "blender_tool", "tool": "tool_name", "arguments": {{"param": "value"}}}}
Otherwise, respond normally."""

                full_message = f"{system_prompt}\n\nUser: {message}"
            else:
                full_message = message
        else:
            full_message = message

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
    """AI Blender client main function"""
    print("🤖 AI Blender Client")
    print("=" * 30)

    # Get provider from environment or default to Claude
    ai_provider = os.getenv("AI_PROVIDER", "claude")
    print(f"Using provider: {ai_provider}")

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
