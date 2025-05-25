"""
Internal tools for lightfast-mcp development and testing.

This package contains management and client tools that are useful for
development, testing, and multi-server coordination, but are not part
of the core MCP server implementations.

Core MCP servers are in the lightfast_mcp package.
Internal tools are in this internal package.
"""

# Management infrastructure (optional)
# AI client tools (optional)
from .clients import MultiServerAIClient
from .management import (
    ConfigLoader,
    MultiServerManager,
    ServerRegistry,
    ServerSelector,
    get_manager,
    get_registry,
)

__all__ = [
    # Management
    "ConfigLoader",
    "MultiServerManager",
    "ServerRegistry",
    "ServerSelector",
    "get_manager",
    "get_registry",
    # Clients
    "MultiServerAIClient",
]
