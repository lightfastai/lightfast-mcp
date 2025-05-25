"""Common utilities and types for the tools package."""

from .async_utils import (
    ConnectionPool,
    RetryManager,
    get_connection_pool,
    run_concurrent_operations,
    shutdown_connection_pool,
)
from .errors import (
    AIProviderError,
    ConfigurationError,
    ConversationError,
    LightfastMCPError,
    ServerConnectionError,
    ServerError,
    ServerStartupError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
    ValidationError,
)
from .logging import (
    correlation_id,
    get_logger,
    operation_context,
    with_correlation_id,
    with_operation_context,
)
from .types import (
    ConversationResult,
    ConversationStep,
    HealthStatus,
    OperationStatus,
    Result,
    ServerInfo,
    ServerState,
    ToolCall,
    ToolResult,
)

__all__ = [
    # Types
    "OperationStatus",
    "ServerState",
    "Result",
    "ServerInfo",
    "ConversationResult",
    "ConversationStep",
    "ToolCall",
    "ToolResult",
    "HealthStatus",
    # Errors
    "LightfastMCPError",
    "ConfigurationError",
    "ConversationError",
    "ServerError",
    "ServerStartupError",
    "ServerConnectionError",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ToolTimeoutError",
    "AIProviderError",
    "ValidationError",
    # Logging
    "get_logger",
    "with_correlation_id",
    "with_operation_context",
    "correlation_id",
    "operation_context",
    # Async utilities
    "ConnectionPool",
    "RetryManager",
    "get_connection_pool",
    "run_concurrent_operations",
    "shutdown_connection_pool",
]
