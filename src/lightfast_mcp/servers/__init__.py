# This file makes the 'servers' directory a Python package.
from .blender_mcp_server import mcp as blender_mcp
from .photoshop_mcp_server import mcp as photoshop_mcp

__all__ = ["blender_mcp", "photoshop_mcp"]
