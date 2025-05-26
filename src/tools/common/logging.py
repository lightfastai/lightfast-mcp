"""Structured logging with correlation IDs and metrics."""

import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional

from rich.console import Console
from rich.logging import RichHandler

# Context variables for request tracing
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
operation_context: ContextVar[Dict[str, Any]] = ContextVar(
    "operation_context", default={}
)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        # Create base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        if correlation_id.get():
            log_entry["correlation_id"] = correlation_id.get()

        # Add operation context if available
        context = operation_context.get()
        if context:
            log_entry["context"] = context

        # Add any extra fields from the log record
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class StructuredLogger:
    """Enhanced logger with structured output and correlation IDs."""

    def __init__(self, name: str, use_rich: bool = True):
        self.logger = logging.getLogger(f"LightfastMCP.{name}")
        self.use_rich = use_rich
        self._setup_formatter()

    def _setup_formatter(self):
        """Setup structured formatter or rich handler."""
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        if self.use_rich:
            # Use Rich handler for development/interactive use
            handler = RichHandler(
                console=Console(stderr=True),
                rich_tracebacks=True,
                show_path=False,
                show_time=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        else:
            # Use JSON formatter for production/structured logging
            handler = logging.StreamHandler()
            handler.setFormatter(StructuredFormatter())

        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log with correlation ID and context."""
        extra_fields = {
            "correlation_id": correlation_id.get(),
            "context": operation_context.get(),
            **kwargs,
        }

        # Create a log record with extra fields
        extra = {"extra_fields": extra_fields}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with context and optional exception."""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_details"] = str(error)
            if hasattr(error, "error_code"):
                kwargs["error_code"] = error.error_code
            if hasattr(error, "details"):
                kwargs["error_context"] = error.details

        self._log_with_context(logging.ERROR, message, **kwargs)

        # Also log the exception traceback if provided
        if error:
            self.logger.exception("Exception details:", exc_info=error)

    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log critical message with context."""
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_details"] = str(error)

        self._log_with_context(logging.CRITICAL, message, **kwargs)


def get_logger(name: str, use_rich: bool = True) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (will be prefixed with 'LightfastMCP.')
        use_rich: Whether to use Rich formatting (True) or JSON (False)
    """
    return StructuredLogger(name, use_rich=use_rich)


def with_correlation_id(func: Optional[Callable] = None, *, generate_new: bool = True):
    """Decorator to add correlation ID to operations.

    Args:
        func: Function to decorate
        generate_new: Whether to generate a new correlation ID if one doesn't exist
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def async_wrapper(*args, **kwargs):
            if generate_new and not correlation_id.get():
                correlation_id.set(str(uuid.uuid4()))
            return await f(*args, **kwargs)

        @wraps(f)
        def sync_wrapper(*args, **kwargs):
            if generate_new and not correlation_id.get():
                correlation_id.set(str(uuid.uuid4()))
            return f(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(f):
            return async_wrapper
        else:
            return sync_wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def with_operation_context(**context_kwargs):
    """Decorator to add operation context to logs.

    Args:
        **context_kwargs: Context key-value pairs to add
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Merge with existing context
            current_context = operation_context.get()
            new_context = {**current_context, **context_kwargs}
            operation_context.set(new_context)
            try:
                return await func(*args, **kwargs)
            finally:
                # Restore previous context
                operation_context.set(current_context)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_context = operation_context.get()
            new_context = {**current_context, **context_kwargs}
            operation_context.set(new_context)
            try:
                return func(*args, **kwargs)
            finally:
                operation_context.set(current_context)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def configure_logging(
    level: str = "INFO", use_rich: bool = True, logger_name: str = "LightfastMCP"
) -> None:
    """Configure logging for the entire application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        use_rich: Whether to use Rich formatting
        logger_name: Root logger name
    """
    root_logger = logging.getLogger(logger_name)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if use_rich:
        handler = RichHandler(
            console=Console(stderr=True),
            rich_tracebacks=True,
            show_path=False,
            show_time=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())

    root_logger.addHandler(handler)
    root_logger.propagate = False
