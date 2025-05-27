#!/usr/bin/env python3
"""
Example: OBJ File Transfer with Blender MCP Server

This example demonstrates how to:
1. Export an OBJ file from Blender
2. Import an OBJ file into Blender
3. Transfer OBJ content through the MCP socket connection

Prerequisites:
- Blender running with the Lightfast MCP addon enabled
- Blender MCP server running (uv run lightfast-blender-server)
"""

import asyncio
import json

from fastmcp import Client

# Sample OBJ content for a simple cube
SAMPLE_CUBE_OBJ = """# Simple cube OBJ
v -1.0 -1.0 -1.0
v  1.0 -1.0 -1.0
v  1.0  1.0 -1.0
v -1.0  1.0 -1.0
v -1.0 -1.0  1.0
v  1.0 -1.0  1.0
v  1.0  1.0  1.0
v -1.0  1.0  1.0

f 1 2 3 4
f 5 8 7 6
f 1 5 6 2
f 2 6 7 3
f 3 7 8 4
f 5 1 4 8
"""


async def main():
    """Demonstrate OBJ file transfer functionality."""

    # Connect to the Blender MCP server
    server_url = "http://localhost:8001/mcp"

    print("🔌 Connecting to Blender MCP server...")

    try:
        async with Client(server_url) as client:
            print("✅ Connected to Blender MCP server")

            # List available tools
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]
            print(f"📝 Available tools: {tool_names}")

            # Check if our new tools are available
            if (
                "import_obj_file" not in tool_names
                or "export_obj_file" not in tool_names
            ):
                print(
                    "❌ OBJ import/export tools not found. Make sure you're using the updated server."
                )
                return

            print("\n" + "=" * 50)
            print("🔄 Testing OBJ Import")
            print("=" * 50)

            # Test 1: Import a sample cube
            print("📥 Importing sample cube OBJ...")
            import_result = await client.call_tool(
                "import_obj_file",
                {"obj_content": SAMPLE_CUBE_OBJ, "object_name": "SampleCube"},
            )

            if import_result:
                result_data = json.loads(import_result[0].text)
                print(f"✅ Import result: {result_data}")
            else:
                print("❌ Import failed - no result returned")
                return

            print("\n" + "=" * 50)
            print("📊 Getting Scene State")
            print("=" * 50)

            # Get current scene state to see our imported object
            scene_result = await client.call_tool("get_state")
            if scene_result:
                scene_data = json.loads(scene_result[0].text)
                print(f"📋 Scene objects: {scene_data.get('objects', [])}")
                print(f"📊 Object count: {scene_data.get('object_count', 0)}")

            print("\n" + "=" * 50)
            print("📤 Testing OBJ Export")
            print("=" * 50)

            # Test 2: Export the cube we just imported
            print("📤 Exporting SampleCube...")
            export_result = await client.call_tool(
                "export_obj_file", {"object_name": "SampleCube"}
            )

            if export_result:
                result_data = json.loads(export_result[0].text)
                print("✅ Export successful!")
                print(f"📊 Exported objects: {result_data.get('object_names', [])}")
                print(f"📏 Content size: {result_data.get('content_size', 0)} bytes")

                # Show first few lines of exported OBJ content
                obj_content = result_data.get("obj_content", "")
                if obj_content:
                    lines = obj_content.split("\n")[:10]
                    print("📄 First 10 lines of exported OBJ:")
                    for i, line in enumerate(lines, 1):
                        print(f"   {i:2d}: {line}")
                    if len(obj_content.split("\n")) > 10:
                        print("   ... (truncated)")
            else:
                print("❌ Export failed - no result returned")

            print("\n" + "=" * 50)
            print("🔄 Testing Round-trip Transfer")
            print("=" * 50)

            # Test 3: Round-trip test - export then re-import
            if export_result:
                result_data = json.loads(export_result[0].text)
                exported_obj_content = result_data.get("obj_content", "")

                if exported_obj_content:
                    print("🔄 Re-importing exported OBJ as 'RoundTripCube'...")
                    reimport_result = await client.call_tool(
                        "import_obj_file",
                        {
                            "obj_content": exported_obj_content,
                            "object_name": "RoundTripCube",
                        },
                    )

                    if reimport_result:
                        result_data = json.loads(reimport_result[0].text)
                        print(f"✅ Round-trip successful: {result_data}")
                    else:
                        print("❌ Round-trip failed")

            print("\n" + "=" * 50)
            print("🎯 Summary")
            print("=" * 50)
            print("✅ OBJ file transfer through sockets is working!")
            print("📝 You can now:")
            print("   • Import OBJ content directly into Blender")
            print("   • Export Blender objects as OBJ content")
            print("   • Transfer 3D models between applications via MCP")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure Blender is running")
        print("   2. Enable the Lightfast MCP addon in Blender")
        print("   3. Start the Blender MCP server: uv run lightfast-blender-server")
        print("   4. Check that the addon shows 'Server active' status")


if __name__ == "__main__":
    asyncio.run(main())
