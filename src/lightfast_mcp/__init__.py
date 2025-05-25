"""
Lightfast MCP - MCP server implementations for creative applications.

This package provides MCP (Model Context Protocol) server implementations for
creative applications like Blender, with optional management and AI client tools.

Core MCP Servers:
- Blender MCP Server: Control Blender through MCP protocol
- Mock MCP Server: Testing and development server

Optional Features:
- Multi-server management infrastructure
- AI client for testing and interaction
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

# Optional management features (only if dependencies are available)
try:
    from .management import (
        ConfigLoader,
        MultiServerManager,
        ServerRegistry,
        ServerSelector,
        get_manager,
        get_registry,
    )

    __all__.extend(
        [
            "MultiServerManager",
            "get_manager",
            "ServerRegistry",
            "get_registry",
            "ConfigLoader",
            "ServerSelector",
        ]
    )
except ImportError:
    # Management features not available (missing pyyaml)
    pass

# Optional AI client features (only if dependencies are available)
try:
    from .clients import MultiServerAIClient

    __all__.append("MultiServerAIClient")
except ImportError:
    # AI client features not available (missing anthropic/openai)
    pass
