"""Custom exceptions for the lightfast-mcp project."""


class LightfastMCPError(Exception):
    """Base exception for all lightfast-mcp related errors."""

    pass


class ServerStartupError(LightfastMCPError):
    """Raised when a server fails to start up properly."""

    pass


class ServerConfigurationError(LightfastMCPError):
    """Raised when there are issues with server configuration."""

    pass


class BlenderMCPError(LightfastMCPError):
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


class FigmaMCPError(LightfastMCPError):
    """Base exception for all Figma MCP Server related errors."""

    pass


class FigmaConnectionError(FigmaMCPError):
    """Raised when there are issues connecting to or maintaining a connection with Figma plugins."""

    pass


class FigmaCommandError(FigmaMCPError):
    """Raised when a command sent to Figma fails during its execution within Figma."""

    pass


class FigmaResponseError(FigmaMCPError):
    """Raised when the response from Figma is unexpected, malformed, or indicates an error."""

    pass


class FigmaTimeoutError(FigmaConnectionError):
    """Raised specifically when a timeout occurs while waiting for a response from Figma."""

    pass
