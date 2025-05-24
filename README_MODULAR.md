# Lightfast MCP - Modular Multi-Server Architecture

This document explains the new modular architecture for running multiple MCP servers simultaneously with AI integration.

## 🚀 Quick Start

### 1. Initialize Configuration
```bash
python lightfast_mcp_manager.py init
```
This creates a sample `config/servers.yaml` with example server configurations.

### 2. Start Servers Interactively
```bash
python lightfast_mcp_manager.py start
```
This will show you available servers and let you select which ones to start.

### 3. Connect AI Client
```bash
# Set your API key first
export ANTHROPIC_API_KEY=your_key_here
# or
export OPENAI_API_KEY=your_key_here

# Start the AI client
python lightfast_mcp_manager.py ai
```

## 📋 Commands

### Server Management
```bash
# List all available servers and configurations
python lightfast_mcp_manager.py list

# Start specific servers by name
python lightfast_mcp_manager.py start blender-server mock-server

# Start servers with verbose logging
python lightfast_mcp_manager.py start --verbose
```

### AI Integration
```bash
# Start AI client (auto-discovers running servers)
python lightfast_mcp_manager.py ai

# Use a specific AI provider
AI_PROVIDER=openai python lightfast_mcp_manager.py ai
```

## 🏗️ Architecture Overview

### Core Components

#### 1. **BaseServer** (`src/lightfast_mcp/core/base_server.py`)
- Common interface for all MCP servers
- Handles configuration, lifecycle, and health checks
- Provides standardized tool registration

#### 2. **ServerRegistry** (`src/lightfast_mcp/core/server_registry.py`)
- Auto-discovers available server classes
- Manages server type registration
- Validates configurations

#### 3. **MultiServerManager** (`src/lightfast_mcp/core/multi_server_manager.py`)
- Manages multiple server instances
- Handles concurrent startup/shutdown
- Provides health monitoring

#### 4. **MultiServerAIClient** (`src/lightfast_mcp/clients/multi_server_ai_client.py`)
- Connects to multiple MCP servers simultaneously
- Routes AI tool calls to appropriate servers
- Supports Claude and OpenAI

### Server Structure
```
src/lightfast_mcp/servers/
├── blender/
│   ├── server.py       # BlenderMCPServer class
│   └── __init__.py
├── mock/
│   ├── server.py       # MockMCPServer class  
│   └── __init__.py
└── your_new_server/
    ├── server.py       # YourMCPServer class
    └── __init__.py
```

## 📝 Configuration

### Server Configuration Format (`config/servers.yaml`)
```yaml
servers:
  - name: "blender-server"
    description: "Blender MCP Server for 3D modeling"
    type: "blender"
    version: "1.0.0"
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
# AI Provider (claude or openai)
export AI_PROVIDER=claude
export ANTHROPIC_API_KEY=your_key_here

# Or for OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY=your_key_here

# Server configuration via JSON (alternative to YAML file)
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
    
    def _register_tools(self):
        self.mcp.tool()(self.my_tool)
        self.info.tools = ["my_tool"]
    
    async def my_tool(self, ctx: Context, param: str) -> str:
        """My custom tool."""
        return f"Result from MyApp: {param}"
```

### 2. Add to Package Init
```python
# src/lightfast_mcp/servers/myapp/__init__.py
from .server import MyAppMCPServer
__all__ = ["MyAppMCPServer"]
```

### 3. Add to Configuration
```yaml
# config/servers.yaml
servers:
  - name: "myapp-server"
    type: "myapp"
    description: "My custom application server"
    # ... other config
```

The server will be auto-discovered by the registry!

## 🤖 AI Integration Workflow

### 1. Multi-Server Setup
```python
# The AI client can connect to multiple servers
client = MultiServerAIClient(ai_provider="claude")
client.add_server("blender", "http://localhost:8001/mcp")
client.add_server("mock", "http://localhost:8002/mcp")

await client.connect_to_servers()
```

### 2. AI Context
The AI automatically receives context about all connected servers:
```
Connected Servers and Available Tools:
**blender** (Blender MCP Server):
  - get_state
  - execute_command

**mock** (Mock MCP Server):
  - get_server_status
  - fetch_mock_data
  - execute_mock_action
```

### 3. Tool Routing
AI can call tools and the client routes them automatically:
```json
{"action": "tool_call", "tool": "get_state", "server": "blender"}
```

## 📊 Example Workflows

### Scenario 1: Multi-Application Creative Workflow
```bash
# 1. Start multiple creative app servers
python lightfast_mcp_manager.py start blender-server touchdesigner-server

# 2. Connect AI to control both
python lightfast_mcp_manager.py ai

# 3. AI can now control both applications:
# "Create a sphere in Blender and send its position to TouchDesigner"
```

### Scenario 2: Development & Testing
```bash
# 1. Start mock server for testing
python lightfast_mcp_manager.py start mock-server

# 2. Test AI integration without real applications
python lightfast_mcp_manager.py ai
```

### Scenario 3: Programmatic Control
```python
from lightfast_mcp.core import get_manager, ConfigLoader
from lightfast_mcp.clients import MultiServerAIClient

# Load and start servers
config_loader = ConfigLoader()
configs = config_loader.load_servers_config()

manager = get_manager()
manager.start_multiple_servers(configs, background=True)

# Connect AI client
ai_client = MultiServerAIClient()
# ... use programmatically
```

## 🔍 Monitoring & Health Checks

### Server Status
```bash
# Check running servers
python lightfast_mcp_manager.py list
```

### Health Monitoring
```python
# Programmatic health checks
manager = get_manager()
health_results = await manager.health_check_all()
print(health_results)  # {"blender-server": True, "mock-server": True}
```

### Server URLs
When running HTTP servers, you'll see:
```
📡 Server URLs:
   • blender-server: http://localhost:8001/mcp
   • mock-server: http://localhost:8002/mcp
```

## 🚀 Benefits of Modular Architecture

### For Users
- **Select servers**: Only start what you need
- **Multi-app control**: Control multiple creative applications simultaneously  
- **Easy configuration**: YAML-based server configuration
- **AI integration**: Single AI client for all servers

### For Developers  
- **Extensible**: Easy to add new server types
- **Consistent**: Common base class and patterns
- **Auto-discovery**: Servers are found automatically
- **Health monitoring**: Built-in health checks and monitoring

### For Operations
- **Scalable**: Run many servers efficiently
- **Configurable**: Environment and file-based configuration
- **Observable**: Comprehensive logging and status reporting
- **Reliable**: Graceful error handling and recovery

## 🔧 Migration from Single-Server Setup

If you're using the old single-server approach:

### Old Way:
```bash
# Start individual servers
python run_blender_http.py
python ai_blender_client.py
```

### New Way:
```bash
# Unified management
python lightfast_mcp_manager.py init    # Create config
python lightfast_mcp_manager.py start   # Start servers  
python lightfast_mcp_manager.py ai      # Connect AI
```

The new system is backward compatible - your existing servers still work, but the new modular approach provides much more flexibility and power.

---

## 🎯 Next Steps

1. **Try the Quick Start** above
2. **Create your own server** following the guide
3. **Experiment with multi-server AI workflows**
4. **Contribute new server implementations** for other creative applications

This modular architecture scales from simple single-server setups to complex multi-application creative workflows, all managed through a unified interface with powerful AI integration. 