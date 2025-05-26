# Examples Directory

This directory contains example scripts and demonstrations for the Lightfast MCP modular architecture.

## Demo Scripts

### `demo_modular_system.py`
Comprehensive demonstration of the complete modular MCP server architecture:
- Server auto-discovery
- Multi-server management  
- AI client integration with multiple servers
- Configuration management
- Health monitoring and cleanup

**Usage**: `uv run python examples/demo_modular_system.py`

### `demo_ai_integration.py`
Demo showing AI integration workflow with Blender MCP server without requiring API keys:
- Basic MCP server connection testing
- Tool execution simulation
- AI workflow simulation
- Setup guide for real AI integration

**Usage**: `uv run python examples/demo_ai_integration.py`

## Reference Implementations

### `ai_blender_client.py`
Simple single-server AI client specifically for Blender MCP integration:
- Direct connection to one Blender MCP server
- AI conversation with tool execution
- Example of using official Anthropic/OpenAI SDKs

**Usage**: `uv run python examples/ai_blender_client.py`

**Note**: For production use, consider the multi-server orchestrator: `uv run lightfast-mcp-orchestrator ai`

## Requirements

- Make sure you have the modular system installed: `uv install` 
- For AI integration examples, set environment variables:
  - `ANTHROPIC_API_KEY` for Claude
  - `OPENAI_API_KEY` for OpenAI
  - `AI_PROVIDER` (optional, defaults to "claude")

## Related Scripts

- Main multi-server orchestrator: `uv run lightfast-mcp-orchestrator`
- Test system: `uv run python scripts/test_working_system.py`
- Blender-specific testing: `./scripts/test_blender.sh` 