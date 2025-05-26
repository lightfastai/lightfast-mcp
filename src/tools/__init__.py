"""
Development tools for lightfast-mcp.

This package contains development and testing tools that are useful for
multi-server coordination and AI integration, but are not part of the
core MCP server implementations.

Core MCP servers are in the lightfast_mcp package.
Development tools are in this tools package.

## New Architecture (Recommended)
- tools.orchestration.ServerOrchestrator: Advanced server management
- tools.ai.ConversationClient: Modern AI conversation handling
- tools.common: Shared utilities, types, and error handling

## Legacy Architecture (Deprecated)
- tools.orchestration.MultiServerManager: Old server management
- tools.ai.MultiServerAIClient: Old AI client
"""

# New architecture (recommended)
# Legacy imports (deprecated - will be removed in future version)
from .ai import ConversationClient, MultiServerAIClient, create_conversation_client
from .orchestration import (
    ConfigLoader,
    MultiServerManager,
    ServerOrchestrator,
    ServerRegistry,
    ServerSelector,
    get_manager,
    get_orchestrator,
    get_registry,
)

__all__ = [
    # New Architecture (Recommended)
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
    # Legacy Architecture (Deprecated)
    "MultiServerManager",
    "get_manager",
    "MultiServerAIClient",
]
