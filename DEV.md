# Developer Guide for Lightfast MCP

This comprehensive guide covers everything developers need to know about Lightfast MCP, from initial setup to creating new server implementations.

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or newer
- `uv` package manager ([Installation Guide](https://docs.astral.sh/uv/getting-started/installation/))

### Setup
```bash
# 1. Clone and setup
git clone https://github.com/lightfastai/lightfast-mcp.git
cd lightfast-mcp
uv venv
source .venv/bin/activate  # macOS/Linux or .venv\Scripts\activate on Windows

# 2. Install dependencies
uv pip install -e ".[dev]"

# 3. Initialize configuration
uv run lightfast-mcp-manager init

# 4. Start servers interactively
uv run lightfast-mcp-manager start

# 5. Connect AI client (set API key first)
export ANTHROPIC_API_KEY=your_key_here
uv run lightfast-mcp-manager ai
```

## 📊 Commands & Usage

### Server Management
```bash
# List all available servers and configurations
uv run lightfast-mcp-manager list

# Start specific servers by name
uv run lightfast-mcp-manager start blender-server mock-server

# Start servers with verbose logging
uv run lightfast-mcp-manager start --verbose
```

### AI Integration
```bash
# Start AI client (auto-discovers running servers)
uv run lightfast-mcp-manager ai

# Use a specific AI provider
AI_PROVIDER=openai uv run lightfast-mcp-manager ai
```

### Development Tasks
```bash
# Testing
uv run python scripts/run_tests.py              # All tests
uv run python scripts/run_tests.py fast         # Fast tests only
uv run python scripts/run_tests.py coverage     # With coverage
uv run python scripts/test_working_system.py    # Quick system verification

# Code quality
uv run ruff check .                      # Lint
uv run ruff format .                     # Format
uv run ruff check . --fix               # Auto-fix

# Direct server execution
uv run python -m lightfast_mcp.servers.mock_server
uv run python -m lightfast_mcp.servers.blender_mcp_server
```

## 🏗️ Architecture Overview

### Core Components

#### **BaseServer** (`src/lightfast_mcp/core/base_server.py`)
Common interface for all MCP servers with:
- Configuration management via `ServerConfig`
- Lifecycle management (startup/shutdown)
- Health checks and monitoring
- Standardized tool registration

#### **ServerRegistry** (`src/lightfast_mcp/core/server_registry.py`)  
Auto-discovery and management system:
- Discovers available server classes automatically
- Manages server type registration
- Validates configurations
- Creates server instances

#### **MultiServerManager** (`src/lightfast_mcp/core/multi_server_manager.py`)
Multi-server orchestration:
- Manages multiple server instances
- Handles concurrent startup/shutdown
- Provides health monitoring
- Background execution support

#### **MultiServerAIClient** (`src/lightfast_mcp/clients/multi_server_ai_client.py`)
AI integration layer:
- Connects to multiple MCP servers simultaneously
- Routes AI tool calls to appropriate servers
- Supports Claude and OpenAI APIs

### Server Structure
```
src/lightfast_mcp/servers/
├── blender/
│   ├── server.py       # BlenderMCPServer class
│   └── __init__.py
├── mock/
│   ├── server.py       # MockMCPServer class  
│   ├── tools.py        # Tool implementations
│   └── __init__.py
└── your_new_server/    # Your custom server
    ├── server.py       # YourMCPServer class
    ├── tools.py        # Tool implementations
    └── __init__.py
```

## 📝 Configuration

### Server Configuration (`config/servers.yaml`)
```yaml
servers:
  - name: "blender-server"
    description: "Blender MCP Server for 3D modeling"
    type: "blender"
    host: "localhost"
    port: 8001
    transport: "streamable-http"  # stdio, http, streamable-http
    path: "/mcp"
    config:
      type: "blender"
      blender_host: "localhost"
      blender_port: 9876
      timeout: 30
    dependencies: []
    required_apps: ["Blender"]

  - name: "mock-server"
    description: "Mock server for testing"
    type: "mock"
    host: "localhost"
    port: 8002
    transport: "streamable-http"
    config:
      type: "mock"
      delay_seconds: 0.5
```

### Environment Configuration
```bash
# AI Provider selection
export AI_PROVIDER=claude                    # or openai
export ANTHROPIC_API_KEY=your_key_here
export OPENAI_API_KEY=your_key_here

# Alternative JSON configuration
export LIGHTFAST_MCP_SERVERS='{"servers": [...]}'
```

## 🔧 Creating New Servers

### 1. Create Server Class
```python
# src/lightfast_mcp/servers/myapp/server.py
from typing import ClassVar
from fastmcp import Context
from ...core.base_server import BaseServer, ServerConfig

class MyAppMCPServer(BaseServer):
    SERVER_TYPE: ClassVar[str] = "myapp"
    SERVER_VERSION: ClassVar[str] = "1.0.0" 
    REQUIRED_APPS: ClassVar[list[str]] = ["MyApp"]
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = ["myapp-python-sdk"]
    
    def _register_tools(self):
        """Register tools with the MCP server."""
        self.mcp.tool()(self.my_tool)
        self.mcp.tool()(self.another_tool)
        self.info.tools = ["my_tool", "another_tool"]
    
    async def my_tool(self, ctx: Context, param: str) -> str:
        """My custom tool description."""
        # Your tool implementation
        return f"Result from MyApp: {param}"
        
    async def another_tool(self, ctx: Context, data: dict) -> dict:
        """Another tool description."""
        # Tool implementation
        return {"processed": data, "app": "MyApp"}
    
    async def _on_startup(self):
        """Custom startup logic."""
        # Connect to your application, initialize resources, etc.
        pass
        
    async def _on_shutdown(self):
        """Custom shutdown logic."""
        # Cleanup resources, close connections, etc.
        pass
        
    async def _perform_health_check(self) -> bool:
        """Custom health check logic."""
        # Check if your application is accessible
        return True
```

### 2. Create Tools Module (Optional)
```python
# src/lightfast_mcp/servers/myapp/tools.py
import asyncio
from typing import Any

async def my_tool_function(ctx: Any, param: str) -> str:
    """Standalone tool function."""
    return f"Processed: {param}"

async def complex_tool(ctx: Any, **kwargs) -> dict:
    """More complex tool with multiple parameters."""
    await asyncio.sleep(0.1)  # Simulate work
    return {"result": "success", "data": kwargs}
```

### 3. Add Package Init
```python
# src/lightfast_mcp/servers/myapp/__init__.py
from .server import MyAppMCPServer

__all__ = ["MyAppMCPServer"]
```

### 4. Add Configuration
```yaml
# Add to config/servers.yaml
servers:
  - name: "myapp-server"
    type: "myapp"
    description: "My custom application server"
    port: 8003
    transport: "streamable-http"
    config:
      type: "myapp"
      api_endpoint: "http://localhost:9999"
      timeout: 15
```

**That's it!** The server will be auto-discovered by the registry.

## 🤖 AI Integration Patterns

### Multi-Server AI Client Usage
```python
from lightfast_mcp.clients import MultiServerAIClient

# Setup
client = MultiServerAIClient(ai_provider="claude")
client.add_server("blender", "http://localhost:8001/mcp", "3D modeling")
client.add_server("myapp", "http://localhost:8003/mcp", "Custom app")

# Connect and use
await client.connect_to_servers()
tools = client.get_all_tools()
result = await client.execute_tool("my_tool", {"param": "value"})

# AI conversation
response = await client.chat_with_ai("Create a sphere in Blender")
final_result = await client.process_ai_response(response)
```

### Tool Routing
AI automatically receives context about all servers:
```
Connected Servers and Available Tools:
**blender** (3D modeling):
  - get_state
  - execute_command

**myapp** (Custom app):
  - my_tool
  - another_tool
```

AI can call tools with automatic routing:
```json
{"action": "tool_call", "tool": "my_tool", "server": "myapp", "arguments": {"param": "test"}}
```

## 🧪 Testing & Development

### Test Structure
```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_base_server.py
│   ├── test_server_registry.py
│   ├── test_mock_server_tools.py
│   └── test_modular_servers.py
├── integration/             # Integration tests
│   └── test_system_integration.py
└── conftest.py              # Shared fixtures
```

### Running Tests
```bash
# Quick verification
uv run python scripts/test_working_system.py

# Test categories
uv run python scripts/run_tests.py fast         # Fast tests (< 1s each)
uv run python scripts/run_tests.py slow         # Slow tests
uv run python scripts/run_tests.py unit         # Unit tests only
uv run python scripts/run_tests.py integration  # Integration tests only
uv run python scripts/run_tests.py coverage     # With coverage report

# Direct pytest usage
uv run pytest tests/unit/test_mock_server_tools.py -v
uv run pytest tests/ -k "test_health_check" -v
```

### Test Development
```python
# Example test for your custom server
import pytest
from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.servers.myapp.server import MyAppMCPServer

@pytest.fixture
def myapp_config():
    return ServerConfig(
        name="test-myapp",
        description="Test MyApp server",
        config={"type": "myapp", "api_endpoint": "http://localhost:9999"}
    )

def test_myapp_server_creation(myapp_config):
    server = MyAppMCPServer(myapp_config)
    assert server.SERVER_TYPE == "myapp"
    assert server.config == myapp_config

@pytest.mark.asyncio
async def test_myapp_tools(myapp_config):
    server = MyAppMCPServer(myapp_config)
    result = await server.my_tool(None, "test")
    assert "test" in result
```

## 🛠️ Development Tools

### Taskipy Tasks
We use `taskipy` for common development tasks:
```bash
# Available tasks
uv run task --list

# Common tasks
uv run task lint                    # Check linting
uv run task format                  # Auto-format code
uv run task fix                     # Fix linting + format
uv run task test                    # Run all tests
uv run task test_fast               # Run fast tests
uv run task test_coverage           # Tests with coverage
uv run task demo                    # Run system demo
```

### Ruff Configuration
Ruff handles both linting and formatting:
```bash
# Manual usage
uv run ruff check .                 # Check for issues
uv run ruff check . --fix          # Auto-fix issues
uv run ruff format .                # Format code
```

Configuration in `pyproject.toml`:
```toml
[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "C4", "SIM"]
```

### VS Code Integration

**Recommended Extensions:**
- `ms-python.python` - Python support
- `charliermarsh.ruff` - Ruff integration  
- `tamasfe.even-better-toml` - TOML support

**Setup:**
1. Open project in VS Code
2. Install recommended extensions (VS Code will prompt)
3. Select Python interpreter from `.venv/bin/python`
4. Ruff integration is pre-configured in `.vscode/settings.json`

### Nox for Multi-Environment Testing
```bash
# List available sessions
uv run nox --list

# Core development sessions
uv run nox -s lint                  # Linting with ruff
uv run nox -s typecheck             # Type checking with mypy
uv run nox -s test_fast             # Fast tests via scripts/run_tests.py
uv run nox -s verify_system         # System verification

# Testing across Python versions
uv run nox -s test-3.10             # Tests on Python 3.10
uv run nox -s test-3.11             # Tests on Python 3.11
uv run nox -s test-3.12             # Tests on Python 3.12
uv run nox -s test-3.13             # Tests on Python 3.13

# Specialized testing
uv run nox -s test_integration      # Integration tests
uv run nox -s test_coverage         # Coverage reporting
uv run nox -s cli_test              # CLI functionality testing

# Package and security
uv run nox -s build                 # Build and verify package
uv run nox -s security              # Security scanning
uv run nox -s format                # Format code

# Utility sessions
uv run nox -s demo                  # Run system demo
uv run nox -s dev                   # Setup dev environment
```

## 📊 Example Workflows

### Development Workflow
```bash
# 1. Setup
git clone <repo> && cd lightfast-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Verify setup
uv run python scripts/test_working_system.py

# 3. Start development server
uv run lightfast-mcp-manager init
uv run lightfast-mcp-manager start mock-server

# 4. Make changes, test, iterate
uv run task fix                     # Format & lint
uv run task test_fast               # Quick tests
uv run python scripts/run_tests.py coverage # Full test suite

# 5. Test AI integration
export ANTHROPIC_API_KEY=your_key
uv run lightfast-mcp-manager ai
```

### Multi-Application Creative Workflow
```bash
# 1. Start multiple creative app servers
uv run lightfast-mcp-manager start blender-server touchdesigner-server

# 2. Connect AI to control both
uv run lightfast-mcp-manager ai

# 3. AI can now coordinate between applications:
# "Create a sphere in Blender and send its vertices to TouchDesigner"
```

### Custom Server Development
```bash
# 1. Create server structure
mkdir -p src/lightfast_mcp/servers/myapp
touch src/lightfast_mcp/servers/myapp/{__init__.py,server.py,tools.py}

# 2. Implement server class (see Creating New Servers)

# 3. Test auto-discovery
uv run python -c "
from lightfast_mcp.core import get_registry
registry = get_registry()
print('Available servers:', registry.get_available_server_types())
"

# 4. Add configuration and test
uv run lightfast-mcp-manager list
uv run lightfast-mcp-manager start myapp-server
```

## 🔍 Monitoring & Debugging

### Health Checks
```python
# Programmatic health monitoring
from lightfast_mcp.core import get_manager

manager = get_manager()
health_results = await manager.health_check_all()
print(health_results)  # {"server-name": True/False, ...}
```

### Server Status
```bash
# Check running servers
uv run lightfast-mcp-manager list

# Server URLs (when using HTTP transport)
# 📡 Server URLs:
#    • blender-server: http://localhost:8001/mcp
#    • mock-server: http://localhost:8002/mcp
```

### Debugging
```python
# Enable verbose logging
import logging
from lightfast_mcp.utils.logging_utils import configure_logging

configure_logging(level="DEBUG")

# Or via command line
uv run lightfast-mcp-manager start --verbose
```

## 🚀 Benefits of Modular Architecture

### For Developers
- **Extensible**: Easy to add new server types following patterns
- **Consistent**: Common base class and standardized patterns  
- **Auto-discovery**: New servers found automatically
- **Health monitoring**: Built-in health checks and monitoring
- **Testing**: Comprehensive test infrastructure

### For Users
- **Selective**: Only start servers you need
- **Multi-app control**: Control multiple applications simultaneously
- **Easy configuration**: YAML-based server configuration
- **AI integration**: Single AI client for all servers

### For Operations  
- **Scalable**: Run many servers efficiently with background execution
- **Configurable**: Environment and file-based configuration
- **Observable**: Comprehensive logging and status reporting
- **Reliable**: Graceful error handling and recovery

## 🔄 Migration from Legacy Systems

### Old Single-Server Approach:
```bash
# Individual server management
python run_blender_http.py
python ai_blender_client.py
```

### New Modular Approach:
```bash
# Unified management
uv run lightfast-mcp-manager init    # Create config
uv run lightfast-mcp-manager start   # Start servers
uv run lightfast-mcp-manager ai      # Connect AI
```

The new system maintains backward compatibility while providing much more flexibility and power.

## 📚 Additional Resources

- **Examples**: See `examples/` directory for working demos
- **Protocol Specification**: [Model Context Protocol](https://modelcontextprotocol.io/introduction)
- **Contributing**: See `CONTRIBUTING.md` for contribution guidelines
- **FastMCP Documentation**: Core MCP implementation we build upon

---

## 🎯 Quick Reference

### Essential Commands
```bash
# Setup & verification
uv pip install -e ".[dev]"
uv run python scripts/test_working_system.py

# Development
uv run task fix && uv run task test_fast
uv run lightfast-mcp-manager start

# AI integration
export ANTHROPIC_API_KEY=key && uv run lightfast-mcp-manager ai
```

### File Structure
```
lightfast-mcp/
├── src/lightfast_mcp/          # Main library
│   ├── core/                   # Core architecture  
│   ├── servers/                # Server implementations
│   ├── clients/                # AI clients
│   └── utils/                  # Utilities
├── tests/                      # Test suite
├── examples/                   # Examples & demos
├── config/                     # Configuration
├── scripts/                    # Utility scripts
│   ├── test_blender.sh          # Blender testing utilities
│   ├── run_tests.py             # Test runner
│   └── test_working_system.py   # Quick verification
```

This modular architecture scales from simple single-server setups to complex multi-application creative workflows, all managed through a unified interface with powerful AI integration. 