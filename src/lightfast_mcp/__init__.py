"""
Lightfast MCP - Production-ready MCP server implementations for creative applications.

This package provides core MCP (Model Context Protocol) server implementations
for creative applications like Blender. It focuses purely on the server
implementations themselves.

🎯 Core MCP Servers:
- Blender MCP Server: Control Blender through MCP protocol
- Mock MCP Server: Testing and development server

🔧 Development Tools:
- Available separately in the `tools` package
- Use `from tools.orchestration import get_orchestrator` for development tools

Example Usage:
```python
# Core server usage
from lightfast_mcp.servers.blender import BlenderMCPServer
from lightfast_mcp.core import ServerConfig

config = ServerConfig(name="my-blender", config={"type": "blender"})
server = BlenderMCPServer(config)
await server.run()

# Development tools (optional)
from tools.orchestration import get_orchestrator
orchestrator = get_orchestrator()
# orchestrator.start_server(config) # Example usage
```
"""

# Core MCP server infrastructure (always available)
from .core import BaseServer, ServerConfig, ServerInfo

# Core server implementations (always available)
from .servers.blender import BlenderMCPServer
from .servers.mock import MockMCPServer

__all__ = [
    # Core infrastructure
    "BaseServer",
    "ServerConfig",
    "ServerInfo",
    # Server implementations
    "BlenderMCPServer",
    "MockMCPServer",
]

__version__ = "0.0.1"
