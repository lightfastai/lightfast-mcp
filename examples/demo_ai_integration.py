#!/usr/bin/env python3
"""
Demo script showing AI integration with Blender MCP server.
This demonstrates the complete workflow without requiring actual API keys.
"""

import asyncio
import json
import os

from fastmcp import Client


async def demo_blender_connection():
    """Demo the Blender MCP connection via HTTP"""
    print("🎯 DEMO: AI Integration with Blender MCP Server")
    print("=" * 50)

    # Test direct connection to HTTP server
    mcp_url = "http://localhost:8000/mcp"
    print(f"📡 Connecting to: {mcp_url}")

    try:
        client = Client(mcp_url)
        async with client:
            print("✅ Connected to Blender MCP HTTP server!")

            # List available tools
            tools = await client.list_tools()
            print("\n📝 Available Blender tools:")
            for tool in tools:
                print(f"  • {tool.name}: {tool.description}")

            # Test get_state
            print("\n🎯 Testing get_state tool...")
            result = await client.call_tool("get_state")
            if result:
                state_data = json.loads(result[0].text)
                print("✅ Blender scene state:")
                print(f"   - Scene: {state_data.get('name', 'Unknown')}")
                print(f"   - Objects: {state_data.get('object_count', 0)}")
                print(f"   - Active: {state_data.get('active_object_name', 'None')}")

            # Test execute_command
            print("\n🔧 Testing execute_command tool...")
            test_code = "print('Hello from AI -> MCP -> Blender!')"
            result = await client.call_tool(
                "execute_command", {"code_to_execute": test_code}
            )
            if result:
                exec_result = json.loads(result[0].text)
                print(
                    f"✅ Code execution result: {exec_result.get('result', 'No output')}"
                )

            return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("   Make sure HTTP server is running: ./scripts/test_blender.sh http")
        return False


async def demo_ai_workflow():
    """Demo the AI workflow (simulated)"""
    print("\n🤖 DEMO: AI Workflow Simulation")
    print("=" * 50)

    # Simulate AI understanding a request
    user_request = "What objects are in my Blender scene?"
    print(f"👤 User: {user_request}")

    # Simulate AI deciding to use get_state tool
    print("🤔 AI: I'll check your Blender scene state...")

    try:
        client = Client("http://localhost:8000/mcp")
        async with client:
            # Execute the tool
            result = await client.call_tool("get_state")
            state_data = json.loads(result[0].text)

            # Simulate AI response
            objects = state_data.get("objects", [])[:5]  # First 5 objects
            object_count = state_data.get("object_count", 0)
            response = f"""I can see your Blender scene contains {object_count} objects. Here are some of them:
{chr(10).join(f"• {obj}" for obj in objects)}

The active object is: {state_data.get("active_object_name", "None")}
The current frame is: {state_data.get("frame_current", 1)}"""

            print(f"🤖 AI: {response}")

    except Exception as e:
        print(f"❌ Simulated AI request failed: {e}")


async def demo_ai_action():
    """Demo AI executing an action in Blender"""
    print("\n🛠️  DEMO: AI Action Execution")
    print("=" * 50)

    user_request = "Add a sphere to my scene"
    print(f"👤 User: {user_request}")
    print("🤔 AI: I'll add a UV sphere to your Blender scene...")

    try:
        client = Client("http://localhost:8000/mcp")
        async with client:
            # Execute Python code to add a sphere
            code = """
import bpy

# Add a UV sphere
bpy.ops.mesh.primitive_uv_sphere_add(location=(2, 0, 0))

# Get the new object
new_obj = bpy.context.active_object
new_obj.name = "AI_Created_Sphere"

print(f"✅ Created sphere: {new_obj.name} at location {new_obj.location}")
"""

            result = await client.call_tool(
                "execute_command", {"code_to_execute": code}
            )
            exec_result = json.loads(result[0].text)

            print(f"🤖 AI: {exec_result.get('result', 'Command executed')}")
            print("✅ Sphere added successfully!")

    except Exception as e:
        print(f"❌ Action execution failed: {e}")


def show_setup_guide():
    """Show setup instructions"""
    print("\n🚀 SETUP GUIDE: Real AI Integration")
    print("=" * 50)

    print("""
1. 📋 Copy environment template:
   cp env_template.txt .env

2. 🔑 Add your API keys to .env:
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   # OR
   OPENAI_API_KEY=sk-your-openai-key-here

3. 🌐 Start HTTP server (Terminal 1):
   ./scripts/test_blender.sh http

4. 🤖 Start AI client (Terminal 2):
   ./scripts/test_blender.sh ai

5. 💬 Chat with AI about Blender:
   "What's in my scene?"
   "Add a red cube at position (1, 1, 1)"
   "Create a golden material called 'Gold'"
""")

    # Check if .env exists
    if os.path.exists(".env"):
        print("✅ .env file found")
        with open(".env") as f:
            content = f.read()
            if (
                "ANTHROPIC_API_KEY=" in content
                and "your_claude_api_key_here" not in content
            ):
                print("✅ Claude API key appears to be set")
            elif (
                "OPENAI_API_KEY=" in content
                and "your_openai_api_key_here" not in content
            ):
                print("✅ OpenAI API key appears to be set")
            else:
                print("⚠️  API keys need to be configured in .env")
    else:
        print("⚠️  .env file not found - copy from env_template.txt")


async def main():
    """Run the complete demo"""
    print("🎨 Blender AI Integration Demo")
    print("🔗 Bridging AI Models with Blender via FastMCP")
    print()

    # Test basic connection
    success = await demo_blender_connection()

    if success:
        # Demo AI workflows
        await demo_ai_workflow()
        await demo_ai_action()

    # Show setup guide
    show_setup_guide()

    print("\n🎯 Demo complete! Your Blender MCP server is ready for AI integration.")


if __name__ == "__main__":
    asyncio.run(main())
