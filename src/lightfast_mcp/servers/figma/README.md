# Figma MCP Server

A comprehensive Figma MCP server that acts as a WebSocket server for real-time design automation and AI integration. This server provides both an MCP interface for AI model interactions and a WebSocket server for Figma plugin connections.

## Architecture

The server uses a WebSocket server architecture following the WebSocket Mock pattern:

```
┌─────────────────┐    WebSocket     ┌─────────────────┐    MCP HTTP      ┌─────────────────┐
│   Figma Plugin  │ ←──────────────→ │   MCP Server    │ ←──────────────→ │   AI Client     │
│   (WebSocket    │   localhost:9003 │   (WebSocket    │   localhost:8003 │   (HTTP Client) │
│    Client)      │                  │    Server)      │                  │                 │
│ - Figma API     │                  │ - WebSocket Srv │                  │ - Tool Registry │
│ - Document Ops  │                  │ - MCP Tools     │                  │ - AI Integration│
│ - Design Cmds   │                  │ - State Mgmt    │                  │ - Conversation  │
└─────────────────┘                  └─────────────────┘                  └─────────────────┘
```

**Why this architecture?**
- **MCP Server as WebSocket Server**: Centralized control and management
- **Figma Plugin as WebSocket Client**: Simple, reliable connection to server
- **Real-time bidirectional communication**: Instant design command execution
- **AI-driven design automation**: Direct integration with AI models

## Features

### 🌐 WebSocket Server
- **Real WebSocket Server**: Runs a full WebSocket server that Figma plugins can connect to
- **Multiple Plugin Support**: Handles multiple concurrent Figma plugin connections
- **Message Broadcasting**: Supports broadcasting commands to all connected plugins
- **Client Management**: Tracks and manages connected plugins with unique IDs
- **Statistics Tracking**: Monitors connections, messages, and server performance

### 🤖 MCP Integration
- **MCP Tools**: Full set of MCP tools for controlling Figma plugins
- **AI Model Ready**: Designed for AI model interactions and design automation
- **Configuration Driven**: Flexible configuration options
- **Health Monitoring**: Built-in health checks and status monitoring
- **Auto-start Support**: Optional automatic WebSocket server startup

### 🎨 Design Automation
- **Document State Management**: Real-time document information retrieval
- **Design Command Execution**: Execute AI-generated design commands in Figma
- **Plugin Communication**: Bidirectional communication with Figma plugins
- **Multi-plugin Support**: Broadcast commands to multiple Figma instances

## Quick Start

### 1. Start the Figma MCP Server

```bash
# Start directly
uv run lightfast-figma-server

# Or via orchestrator
uv run lightfast-mcp-orchestrator start

# Or via task runner
uv run task figma_server
```

### 2. Connect Figma Plugin

1. **Load the Figma Plugin**: Install and run the Lightfast MCP Figma Plugin
2. **Configure Connection**: Set server URL to `ws://localhost:9003`
3. **Connect**: Click "🔌 Connect" in the plugin UI
4. **Verify**: Check that the plugin shows "Connected to MCP Server"

### 3. Use MCP Tools

The server provides MCP tools for AI clients:

- `get_figma_server_status` - Get server status and connected plugins
- `start_figma_server` - Start the WebSocket server
- `stop_figma_server` - Stop the WebSocket server
- `get_figma_plugins` - Get list of connected Figma plugins
- `ping_figma_plugin` - Test connectivity with plugins
- `get_document_state` - Get current Figma document state
- `execute_design_command` - Execute design commands in Figma
- `broadcast_design_command` - Broadcast commands to all plugins

## Configuration

### Server Configuration

The server can be configured via `config/servers.yaml`:

```yaml
- config:
    type: figma
    figma_host: "localhost"
    figma_port: 9003
    auto_start_websocket: true
  description: Figma MCP Server for design automation and collaborative design workflows
  host: localhost
  name: figma-server
  path: /mcp
  port: 8003
  required_apps:
  - Figma
  transport: streamable-http
  type: figma
  version: 1.0.0
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `figma_host` | `localhost` | Host for the WebSocket server |
| `figma_port` | `9003` | Port for the WebSocket server |
| `auto_start_websocket` | `true` | Auto-start WebSocket server on MCP server startup |

## WebSocket Protocol

### Connection Flow

1. **Connect**: Figma plugin connects to WebSocket server
2. **Welcome**: Server sends welcome message with client ID and capabilities
3. **Plugin Info**: Plugin sends its information and capabilities
4. **Messaging**: Bidirectional communication for commands and responses
5. **Disconnect**: Clean disconnection and client cleanup

### Message Types

#### Plugin → Server Messages

**Plugin Info**
```json
{
  "type": "plugin_info",
  "plugin_info": {
    "name": "Lightfast MCP Figma Plugin",
    "version": "1.0.0",
    "capabilities": ["document_info", "design_commands"]
  }
}
```

**Document Update**
```json
{
  "type": "document_update",
  "document_info": {
    "document": {...},
    "currentPage": {...},
    "selection": [...],
    "viewport": {...}
  }
}
```

**Design Command Response**
```json
{
  "type": "design_command_response",
  "request_id": "abc123",
  "result": {
    "message": "Rectangle created successfully",
    "created_node": {...}
  }
}
```

#### Server → Plugin Messages

**Welcome**
```json
{
  "type": "welcome",
  "client_id": "abc123",
  "server_info": {
    "name": "Figma MCP WebSocket Server",
    "version": "1.0.0",
    "capabilities": ["ping", "get_document_info", "execute_design_command"]
  }
}
```

**Execute Design Command**
```json
{
  "type": "execute_design_command",
  "command": "create rectangle",
  "request_id": "def456",
  "timestamp": 1234567890.123
}
```

**Ping**
```json
{
  "type": "ping",
  "request_id": "ghi789",
  "timestamp": 1234567890.123
}
```

## MCP Tools Reference

### `get_figma_server_status`

Get comprehensive status information about the Figma WebSocket server.

**Returns:**
```json
{
  "figma_websocket_server": {
    "host": "localhost",
    "port": 9003,
    "is_running": true,
    "url": "ws://localhost:9003",
    "clients_connected": 2,
    "stats": {...}
  },
  "mcp_server": {
    "mcp_server_name": "FigmaMCP",
    "mcp_server_type": "figma",
    "mcp_server_version": "1.0.0"
  }
}
```

### `get_figma_plugins`

Get information about all connected Figma plugins.

**Returns:**
```json
{
  "status": "success",
  "plugins": [
    {
      "id": "abc123",
      "connected_at": "2023-01-01T12:00:00Z",
      "plugin_info": {...},
      "remote_address": "127.0.0.1:54321"
    }
  ],
  "total_plugins": 1
}
```

### `execute_design_command`

Execute a design command in Figma.

**Parameters:**
- `command` (string): The design command to execute
- `plugin_id` (string, optional): Specific plugin ID (if None, uses first available)

**Returns:**
```json
{
  "status": "command_sent",
  "plugin_id": "abc123",
  "command": "create rectangle",
  "message": "Design command sent to Figma plugin"
}
```

### `get_document_state`

Get the current document state from Figma plugins.

**Parameters:**
- `plugin_id` (string, optional): Specific plugin ID (if None, uses first available)

**Returns:**
```json
{
  "status": "success",
  "plugin_id": "abc123",
  "document_state": {
    "document": {...},
    "currentPage": {...},
    "selection": [...]
  },
  "source": "cached"
}
```

## Design Commands

The server supports these design commands:

- `"create rectangle"` - Creates a rectangle shape
- `"create circle"` - Creates a circle/ellipse shape  
- `"create text"` - Creates a text node with default content

### Communication Flow

1. **AI Client → MCP Server**: AI sends tool calls via HTTP
2. **MCP Server → Figma Plugin**: Server sends commands via WebSocket
3. **Figma Plugin → Figma API**: Plugin executes commands using Figma API
4. **Results flow back**: Figma API → Plugin → WebSocket → MCP Server → AI Client

## Development

### Architecture

```
figma/
├── __init__.py          # Module exports
├── server.py            # Main MCP server implementation
├── websocket_server.py  # WebSocket server implementation
├── tools.py             # MCP tools implementation
└── README.md           # This file
```

### Key Components

- **FigmaMCPServer**: Main MCP server class
- **FigmaWebSocketServer**: WebSocket server implementation
- **FigmaClient**: Client connection management
- **Tools**: MCP tool implementations

### Adding New Features

1. **New Message Types**: Add handlers to `FigmaWebSocketServer._register_default_handlers()`
2. **New MCP Tools**: Add tools to `tools.py` and register in `server.py`
3. **Configuration Options**: Add to `ServerConfig.config` handling
4. **Tests**: Add corresponding tests for new functionality

## Use Cases

### 🎨 AI-Driven Design
- Generate design elements through AI commands
- Automate repetitive design tasks
- Create design variations and iterations
- Real-time design collaboration with AI

### 🤖 Design Automation
- Batch create design elements
- Apply consistent styling across projects
- Generate design systems and components
- Automate design workflows

### 🔧 Development & Testing
- Test Figma plugin functionality
- Debug design command execution
- Monitor plugin performance
- Prototype new design features

### 📚 Learning & Education
- Learn Figma API integration
- Understand real-time design communication
- Practice design automation
- Study plugin architecture patterns

## Troubleshooting

### Common Issues

**WebSocket Server Won't Start**
```bash
# Check if port is already in use
lsof -i :9003

# Use a different port in config
figma_port: 9004
```

**Figma Plugin Can't Connect**
```bash
# Ensure MCP server is running
uv run lightfast-figma-server

# Check server status via MCP tools
```

**Design Commands Not Executing**
- Verify plugin is connected and active
- Check plugin logs for errors
- Test with simple commands first

### Debugging

Enable debug logging:
```python
import logging
logging.getLogger("FigmaWebSocketServer").setLevel(logging.DEBUG)
```

Monitor server statistics:
```bash
# Use MCP tools to get server status
# get_figma_server_status tool
```

## Contributing

1. **Fork the repository**
2. **Create a feature branch**
3. **Add tests for new functionality**
4. **Ensure all tests pass**
5. **Submit a pull request**

### Development Setup

```bash
# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/unit/test_figma_server.py

# Run linting
uv run task lint

# Format code
uv run task format
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 