#!/usr/bin/env python3
"""
Simple terminal client for testing the Blender MCP server using MCP Inspector CLI approach.
Usage: python test_blender_simple.py
"""

import json
import shlex
import subprocess
import sys


def run_mcp_command(method, **kwargs):
    """Run an MCP command using the MCP Inspector CLI"""
    cmd = [
        "uv",
        "run",
        "npx",
        "@modelcontextprotocol/inspector",
        "--cli",
        "uv",
        "run",
        "python",
        "-m",
        "lightfast_mcp.servers.blender_mcp_server",
        "--method",
        method,
    ]

    # Add any additional arguments
    for key, value in kwargs.items():
        if key.startswith("tool_"):
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

    print(f"Running: {' '.join(shlex.quote(arg) for arg in cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return result.stdout
        else:
            print(f"❌ Command failed: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return None
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return None


def test_basic_connection():
    """Test basic MCP server commands"""
    print("🔍 Testing Blender MCP server...")

    # List tools
    print("\n📝 Listing available tools...")
    output = run_mcp_command("tools/list")
    if output:
        print("✅ Tools listed successfully")
        try:
            # Try to parse JSON output
            if output.strip().startswith("{") or output.strip().startswith("["):
                data = json.loads(output)
                print(f"   Found {len(data.get('tools', []))} tools")
            else:
                print(f"   Output: {output[:200]}...")
        except:
            print(f"   Raw output: {output[:200]}...")

    # Test get_state tool call
    print("\n🎯 Testing get_state tool...")
    output = run_mcp_command("tools/call", tool_name="get_state")
    if output:
        print("✅ get_state called successfully")
        print(f"   Result: {output[:200]}...")

    # Test execute_command tool call
    print("\n🎯 Testing execute_command tool...")
    output = run_mcp_command(
        "tools/call", tool_name="execute_command", tool_arg="code_to_execute=print('Hello from MCP!')"
    )
    if output:
        print("✅ execute_command called successfully")
        print(f"   Result: {output[:200]}...")


def interactive_mode():
    """Simple interactive mode"""
    print("\n🚀 Interactive mode (simplified)")
    print("Commands: list, state, execute <code>, quit")

    while True:
        try:
            command = input("\nblender-mcp> ").strip()

            if command.lower() in ["quit", "q", "exit"]:
                break
            elif command.lower() in ["list", "tools"]:
                output = run_mcp_command("tools/list")
                if output:
                    print(output)
            elif command.lower() in ["state", "get_state"]:
                output = run_mcp_command("tools/call", tool_name="get_state")
                if output:
                    print(output)
            elif command.lower().startswith("execute "):
                code = command[8:]  # Remove "execute "
                output = run_mcp_command("tools/call", tool_name="execute_command", tool_arg=f"code_to_execute={code}")
                if output:
                    print(output)
            elif command.lower() == "help":
                print("Available commands:")
                print("  list - List available tools")
                print("  state - Get Blender scene state")
                print("  execute <code> - Execute Python code in Blender")
                print("  quit - Exit")
            else:
                print(f"Unknown command: {command}")
                print("Type 'help' for available commands")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        test_basic_connection()
        print("\n✨ Basic tests completed! Try --interactive mode for hands-on testing.")


if __name__ == "__main__":
    main()
