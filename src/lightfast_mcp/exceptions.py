"""Custom exceptions for the Blender MCP Server."""


class BlenderMCPError(Exception):
    """Base exception for all Blender MCP Server related errors."""

    pass


class BlenderConnectionError(BlenderMCPError):
    """Raised when there are issues connecting to or maintaining a connection with Blender."""

    pass


class BlenderCommandError(BlenderMCPError):
    """Raised when a command sent to Blender fails during its execution within Blender."""

    pass


class BlenderResponseError(BlenderMCPError):
    """Raised when the response from Blender is unexpected, malformed, or indicates an error."""

    pass


class BlenderTimeoutError(BlenderConnectionError):
    """Raised specifically when a timeout occurs while waiting for a response from Blender."""

    pass


class InvalidCommandTypeError(BlenderMCPError):
    """Raised if an unsupported command type is sent to Blender."""

    pass
