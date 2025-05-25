# Lightfast MCP Architecture

## Overview

Lightfast MCP is designed with **strict separation of concerns** to emphasize that the core value is in the **MCP server implementations**, while management and AI client features are optional conveniences.

## 🎯 Core Value: MCP Server Implementations

The primary purpose of this repository is to provide production-ready MCP server implementations for creative applications.

### Core Components (Always Available)

```
src/lightfast_mcp/
├── core/                      # 🎯 Core MCP infrastructure
│   └── base_server.py         # BaseServer, ServerConfig, ServerInfo
├── servers/                   # 🎯 MCP server implementations  
│   ├── blender/              # Blender MCP server
│   ├── mock/                 # Mock MCP server for testing
│   └── {future_apps}/        # Future server implementations
└── utils/                     # 🎯 Shared utilities
    └── logging_utils.py       # Logging infrastructure
```

**Dependencies**: Only `fastmcp` and `rich` (for logging)

**Entry Points**:
- `lightfast-blender-server` - Direct Blender MCP server
- `lightfast-mock-server` - Direct Mock MCP server

## 🔧 Optional Features

### Management Infrastructure

```
src/lightfast_mcp/management/
├── multi_server_manager.py   # Run multiple servers
├── server_registry.py        # Auto-discover servers
├── config_loader.py          # YAML/JSON configuration
├── server_selector.py        # Interactive server selection
└── cli.py                    # Management CLI
```

**Additional Dependencies**: `pyyaml`

**Entry Points**:
- `lightfast-mcp-manager` - Multi-server management CLI

### AI Client Infrastructure

```
src/lightfast_mcp/clients/
├── multi_server_ai_client.py # Connect to multiple servers
└── cli.py                    # AI client CLI
```

**Additional Dependencies**: `anthropic`, `openai`, `typer`

**Entry Points**:
- `lightfast-mcp-ai` - AI client CLI

## Installation Options

### 🎯 Core Only (Recommended for Production)
```bash
pip install lightfast-mcp
# Only installs: fastmcp, rich
# Available: lightfast-blender-server, lightfast-mock-server
```

### 🔧 With Management Features
```bash
pip install lightfast-mcp[management]
# Adds: pyyaml
# Available: lightfast-mcp-manager
```

### 🔧 With AI Client Features
```bash
pip install lightfast-mcp[ai-client]
# Adds: anthropic, openai, typer
# Available: lightfast-mcp-ai
```

### 🔧 Everything
```bash
pip install lightfast-mcp[all]
# All features available
```

## Usage Patterns

### 🎯 Primary: Individual MCP Servers

```bash
# Direct server usage (core functionality)
lightfast-blender-server     # Start Blender MCP server
lightfast-mock-server        # Start Mock MCP server

# Use with any MCP client (Claude Desktop, etc.)
```

### 🔧 Secondary: Multi-Server Management

```bash
# Optional convenience for development/testing
lightfast-mcp-manager init   # Create configuration
lightfast-mcp-manager start  # Start multiple servers
```

### 🔧 Secondary: AI Client Testing

```bash
# Optional tool for testing servers
lightfast-mcp-ai chat        # Interactive AI chat
lightfast-mcp-ai test        # Quick testing
```

## Design Principles

1. **Core First**: MCP server implementations are the primary value
2. **Optional Convenience**: Management and AI features are helpful but not essential
3. **Minimal Dependencies**: Core functionality has minimal dependencies
4. **Graceful Degradation**: Features gracefully unavailable if dependencies missing
5. **Clear Entry Points**: Each component has clear, purpose-specific entry points

## Adding New Servers

To add a new MCP server implementation:

1. **Create server directory**: `src/lightfast_mcp/servers/{app}/`
2. **Implement server class**: Inherit from `BaseServer`
3. **Create entry point**: `src/lightfast_mcp/servers/{app}_mcp_server.py`
4. **Add to pyproject.toml**: `lightfast-{app}-server = "..."`
5. **Auto-discovery**: Server registry will automatically find it

The new server will be:
- ✅ Available as individual entry point
- ✅ Auto-discovered by management tools
- ✅ Usable with AI client
- ✅ Testable with existing infrastructure

## Migration from Previous Architecture

### Before (Mixed Concerns)
- Everything bundled together
- Heavy dependencies for simple server usage
- Unclear what the primary purpose was
- Multiple confusing entry points

### After (Separated Concerns)
- Core MCP servers are lightweight and focused
- Optional features have clear dependency boundaries
- Primary purpose (MCP servers) is emphasized
- Clean, purpose-specific entry points

### Breaking Changes
- Import paths changed: `lightfast_mcp.core.config_loader` → `lightfast_mcp.management.config_loader`
- CLI entry points renamed: `lightfast-mcp-manager ai` → `lightfast-mcp-ai`
- Dependencies are now optional for management/AI features

### Migration Guide
```python
# Old imports
from lightfast_mcp.core import ConfigLoader, get_manager
from lightfast_mcp.clients import ServerSelector

# New imports  
from lightfast_mcp.management import ConfigLoader, get_manager, ServerSelector
```

This architecture ensures that users who just want MCP server implementations get a lightweight, focused package, while users who want the full development and management experience can opt into those features. 