"""AI integration tools for multi-server coordination."""

from .conversation_client import ConversationClient, create_conversation_client

# Legacy import for backward compatibility (will be removed in future version)
try:
    from .multi_server_ai_client import MultiServerAIClient

    _LEGACY_AVAILABLE = True
except ImportError:
    _LEGACY_AVAILABLE = False

    # Create a deprecation warning class
    class MultiServerAIClient:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "MultiServerAIClient has been removed. "
                "Please use ConversationClient instead:\n"
                "  from tools.ai import ConversationClient, create_conversation_client\n"
                "  client_result = await create_conversation_client(servers=...)\n"
                "  client = client_result.data"
            )


__all__ = [
    "ConversationClient",
    "create_conversation_client",
    "MultiServerAIClient",  # For backward compatibility (deprecated)
]
