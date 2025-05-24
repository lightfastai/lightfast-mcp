#!/usr/bin/env python3
"""
Run Blender MCP server as HTTP service for AI model integration.
Usage: python run_blender_http.py
"""

from lightfast_mcp.servers.blender_mcp_server import mcp


def main():
    """Run the Blender MCP server with HTTP transport"""
    print("🚀 Starting Blender MCP server as HTTP service...")
    print("📡 Server will be available at: http://localhost:8000/mcp")
    print("🔧 Make sure Blender is running with the addon active!")

    # Run with Streamable HTTP transport
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000, path="/mcp")


if __name__ == "__main__":
    main()
