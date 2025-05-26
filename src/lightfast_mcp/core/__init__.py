"""Core infrastructure for MCP server implementations."""

# Import shared types from common module
import sys
from pathlib import Path

from .base_server import BaseServer, ServerConfig

# Import shared types from tools.common
try:
    from tools.common import HealthStatus, ServerInfo, ServerState
except ImportError:
    # Fallback for development/testing
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from tools.common import HealthStatus, ServerInfo, ServerState

__all__ = [
    "BaseServer",
    "ServerConfig",
    "ServerInfo",
    "ServerState",
    "HealthStatus",
]
