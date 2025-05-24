"""Logging utilities for FastMCP."""

import logging
from typing import Literal

from rich.console import Console
from rich.logging import RichHandler


def get_logger(name: str) -> logging.Logger:
    """Get a logger nested under FastMCP namespace.

    Args:
        name: the name of the logger, which will be prefixed with 'FastMCP.'

    Returns:
        a configured logger instance
    """
    return logging.getLogger(f"FastMCP.{name}")


def configure_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | int = "INFO",
    logger: logging.Logger | None = None,
) -> None:
    """
    Configure logging for FastMCP.

    Args:
        logger: the logger to configure
        level: the log level to use
    """
    if logger is None:
        # If no specific logger is passed, configure the root "FastMCP" logger.
        # Child loggers created with get_logger() will inherit this configuration.
        logger = logging.getLogger("FastMCP")

    # Set the level for the logger we are configuring.
    # This ensures that even if child loggers are created before this call,
    # they will respect this base level if they don't override it.
    logger.setLevel(level)

    # Configure the handler specifically for the logger instance being passed or the root "FastMCP" logger.
    # Avoid adding handlers to the root logger of Python's logging system unless intended.
    handler = RichHandler(
        console=Console(stderr=True), rich_tracebacks=True, show_path=False
    )
    # Using a simple formatter as RichHandler does most of the styling.
    # The default RichHandler format is "%(message)s" and it includes time and level.
    # formatter = logging.Formatter("%(message)s")
    # handler.setFormatter(formatter) # Not strictly necessary if RichHandler default is fine

    # Remove any existing handlers from THIS logger to avoid duplicates on reconfiguration.
    # This is important if configure_logging can be called multiple times.
    for hdlr in logger.handlers[:]:
        logger.removeHandler(hdlr)

    logger.addHandler(handler)

    # Ensure that messages propagate up to the root "FastMCP" logger if this is a child logger.
    # And ensure the root "FastMCP" logger doesn't propagate to Python's root logger
    # if we only want RichHandler on "FastMCP" namespace.
    if logger.name != "FastMCP":
        logger.propagate = True  # Default, but good to be aware of
    else:
        # For the root "FastMCP" logger, decide if it should propagate to Python's root.
        # If Python's root has handlers (e.g. from basicConfig elsewhere), you might get duplicates.
        # Setting propagate to False for "FastMCP" means only RichHandler will handle its logs.
        logger.propagate = False
