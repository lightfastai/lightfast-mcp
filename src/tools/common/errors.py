"""Custom exception hierarchy for better error handling."""

from typing import Any, Dict, Optional


class LightfastMCPError(Exception):
    """Base exception for all Lightfast MCP errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": str(self),
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }


class ConfigurationError(LightfastMCPError):
    """Configuration-related errors."""

    pass


class ValidationError(LightfastMCPError):
    """Input validation errors."""

    pass


class ServerError(LightfastMCPError):
    """Base class for server operation errors."""

    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, cause)
        self.server_name = server_name
        if server_name:
            self.details["server_name"] = server_name


class ServerStartupError(ServerError):
    """Server failed to start."""

    pass


class ServerShutdownError(ServerError):
    """Server failed to shutdown gracefully."""

    pass


class ServerConnectionError(ServerError):
    """Server connection issues."""

    def __init__(
        self,
        message: str,
        server_name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, server_name, error_code, details, cause)
        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port


class ServerHealthCheckError(ServerError):
    """Server health check failed."""

    pass


class ToolExecutionError(LightfastMCPError):
    """Tool execution errors."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        server_name: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, cause)
        self.tool_name = tool_name
        self.server_name = server_name
        if tool_name:
            self.details["tool_name"] = tool_name
        if server_name:
            self.details["server_name"] = server_name


class ToolNotFoundError(ToolExecutionError):
    """Requested tool was not found."""

    pass


class ToolTimeoutError(ToolExecutionError):
    """Tool execution timed out."""

    pass


class AIProviderError(LightfastMCPError):
    """AI provider communication errors."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, cause)
        self.provider = provider
        if provider:
            self.details["provider"] = provider


class AIProviderAuthError(AIProviderError):
    """AI provider authentication failed."""

    pass


class AIProviderRateLimitError(AIProviderError):
    """AI provider rate limit exceeded."""

    pass


class AIProviderQuotaError(AIProviderError):
    """AI provider quota exceeded."""

    pass


class ConversationError(LightfastMCPError):
    """Conversation-related errors."""

    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        step_number: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message, error_code, details, cause)
        self.session_id = session_id
        self.step_number = step_number
        if session_id:
            self.details["session_id"] = session_id
        if step_number is not None:
            self.details["step_number"] = step_number


class ConversationTimeoutError(ConversationError):
    """Conversation step timed out."""

    pass


class ConnectionPoolError(LightfastMCPError):
    """Connection pool related errors."""

    pass


class ConnectionPoolExhaustedError(ConnectionPoolError):
    """All connections in pool are in use."""

    pass


class RetryExhaustedError(LightfastMCPError):
    """All retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Optional[Exception] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, error_code, details, last_error)
        self.attempts = attempts
        self.last_error = last_error
        self.details["attempts"] = attempts
        if last_error:
            self.details["last_error"] = str(last_error)
