"""
Development tools for lightfast-mcp.

This package contains development and testing tools that are useful for
multi-server coordination and AI integration, but are not part of the
core MCP server implementations.

Core MCP servers are in the lightfast_mcp package.
Development tools are in this tools package.

## Architecture
- tools.orchestration.ServerOrchestrator: Advanced server management
- tools.ai.ConversationClient: Modern AI conversation handling
- tools.common: Shared utilities, types, and error handling
"""

# New architecture
from .ai import ConversationClient, create_conversation_client
from .orchestration import (
    ConfigLoader,
    ServerOrchestrator,
    ServerRegistry,
    ServerSelector,
    get_orchestrator,
    get_registry,
)

__all__ = [
    # Orchestration
    "ConfigLoader",
    "ServerOrchestrator",
    "ServerRegistry",
    "ServerSelector",
    "get_orchestrator",
    "get_registry",
    # AI
    "ConversationClient",
    "create_conversation_client",
]
