"""Custom exceptions for the MCP Servers."""


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


# Photoshop Exceptions
class PhotoshopMCPError(Exception):
    """Base exception for all Photoshop MCP Server related errors."""

    pass


class PhotoshopConnectionError(PhotoshopMCPError):
    """Raised when there are issues connecting to or maintaining a connection with Photoshop."""

    pass


class PhotoshopCommandError(PhotoshopMCPError):
    """Raised when a command sent to Photoshop fails during its execution within Photoshop."""

    pass


class PhotoshopResponseError(PhotoshopMCPError):
    """Raised when the response from Photoshop is unexpected, malformed, or indicates an error."""

    pass


class PhotoshopTimeoutError(PhotoshopConnectionError):
    """Raised specifically when a timeout occurs while waiting for a response from Photoshop."""

    pass
