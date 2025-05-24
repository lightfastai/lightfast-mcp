"""
Test package for lightfast-mcp.

This package contains comprehensive tests for the modular MCP server architecture.
"""

import sys
from pathlib import Path

# Add src to Python path for testing
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
