"""Multi-server orchestration tools."""

from .config_loader import ConfigLoader
from .server_orchestrator import ServerOrchestrator, get_orchestrator
from .server_registry import ServerRegistry, get_registry
from .server_selector import ServerSelector

# Legacy import for backward compatibility (will be removed in future version)
try:
    from .multi_server_manager import MultiServerManager, get_manager

    _LEGACY_AVAILABLE = True
except ImportError:
    _LEGACY_AVAILABLE = False

    # Create deprecation warning classes
    class MultiServerManager:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MultiServerManager has been removed. "
                "Please use ServerOrchestrator instead:\n"
                "  from tools.orchestration import get_orchestrator\n"
                "  orchestrator = get_orchestrator()"
            )

    def get_manager():
        raise ImportError(
            "get_manager() has been removed. "
            "Please use get_orchestrator() instead:\n"
            "  from tools.orchestration import get_orchestrator\n"
            "  orchestrator = get_orchestrator()"
        )


__all__ = [
    "ServerOrchestrator",
    "get_orchestrator",
    "ServerRegistry",
    "get_registry",
    "ConfigLoader",
    "ServerSelector",
    # Legacy exports (deprecated)
    "MultiServerManager",
    "get_manager",
]
