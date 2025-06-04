# WebSocket Mock MCP Server

A comprehensive WebSocket Mock MCP server for testing WebSocket communications and developing WebSocket-based applications. This server provides both an MCP interface for AI model interactions and a real WebSocket server for client connections.

## Features

### 🔌 WebSocket Server
- **Real WebSocket Server**: Runs a full WebSocket server that clients can connect to
- **Automatic Startup**: WebSocket server starts automatically when the MCP server starts
- **Multiple Client Support**: Handles multiple concurrent WebSocket connections
- **Message Broadcasting**: Supports broadcasting messages between connected clients
- **Client Management**: Tracks and manages connected clients with unique IDs
- **Statistics Tracking**: Monitors connections, messages, and server performance
- **Error Simulation**: Built-in error testing and simulation capabilities
- **Port Auto-Discovery**: Automatically finds an available port if the default is in use

### 🤖 MCP Integration
- **MCP Tools**: Full set of MCP tools for controlling the WebSocket server
- **AI Model Ready**: Designed for AI model interactions and testing
- **Configuration Driven**: Flexible configuration options
- **Health Monitoring**: Built-in health checks and status monitoring
- **Robust Startup**: Automatic retry logic with port fallback for reliable startup

### 🧪 Testing & Development
- **Comprehensive Test Suite**: Unit, integration, and end-to-end tests
- **Test Client Utility**: Interactive WebSocket test client
- **Multiple Test Scenarios**: Stress testing, error handling, and edge cases
- **Development Tools**: Debugging and monitoring capabilities

## Quick Start

### 1. Start the WebSocket Mock Server

```bash
# Start directly
uv run lightfast-websocket-mock-server

# Or via orchestrator
uv run lightfast-mcp-orchestrator start

# Or via task runner
uv run task websocket_mock_server
```

The WebSocket server will start automatically on `ws://localhost:9004` (or the next available port if 9004 is in use).

### 2. Connect WebSocket Clients

The server runs a WebSocket server on `ws://localhost:9004` by default. You can connect any WebSocket client:

```javascript
// JavaScript example
const ws = new WebSocket('ws://localhost:9004');

ws.onopen = function() {
    console.log('Connected to WebSocket Mock Server');
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

// Send a ping
ws.send(JSON.stringify({type: 'ping'}));
```

### 3. Use MCP Tools

The server provides MCP tools for AI models to interact with the WebSocket server:

- `get_websocket_server_status` - Get server status and statistics
- `send_websocket_message` - Send messages to connected clients
- `get_websocket_clients` - Get list of connected clients
- `test_websocket_connection` - Test WebSocket connections

**Note**: The WebSocket server starts automatically when the MCP server starts and runs continuously. There are no manual start/stop tools needed.

## Configuration

### Server Configuration

```yaml
# config/servers.yaml
websocket_mock:
  name: "WebSocketMockMCP"
  description: "WebSocket Mock MCP Server"
  type: "websocket_mock"
  host: "localhost"
  port: 8004
  transport: "streamable-http"
  config:
    websocket_host: "localhost"
    websocket_port: 9004
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `websocket_host` | `localhost` | Host for the WebSocket server |
| `websocket_port` | `9004` | Port for the WebSocket server (will auto-increment if in use) |

**Note**: The WebSocket server now starts automatically when the MCP server starts. There's no need for manual startup or configuration flags.

## WebSocket Protocol

### Connection Flow

1. **Connect**: Client connects to WebSocket server
2. **Welcome**: Server sends welcome message with client ID and capabilities
3. **Messaging**: Client can send various message types
4. **Responses**: Server responds to messages and forwards broadcasts
5. **Disconnect**: Clean disconnection and client cleanup

### Message Types

#### Client → Server Messages

**Ping**
```json
{
  "type": "ping",
  "test_id": "optional_test_id"
}
```

**Echo**
```json
{
  "type": "echo",
  "message": "Your message here",
  "additional_data": "any additional fields"
}
```

**Broadcast**
```json
{
  "type": "broadcast",
  "message": "Message to broadcast to all other clients"
}
```

**Get Clients**
```json
{
  "type": "get_clients"
}
```

**Get Stats**
```json
{
  "type": "get_stats"
}
```

**Simulate Delay**
```json
{
  "type": "simulate_delay",
  "delay_seconds": 2.0
}
```

**Error Test**
```json
{
  "type": "error_test",
  "error_type": "generic|exception|timeout|invalid_json"
}
```

#### Server → Client Messages

**Welcome**
```json
{
  "type": "welcome",
  "client_id": "abc123",
  "server_info": {
    "name": "WebSocket Mock Server",
    "version": "1.0.0",
    "capabilities": ["ping", "echo", "broadcast", ...]
  },
  "timestamp": 1234567890.123
}
```

**Pong**
```json
{
  "type": "pong",
  "client_id": "abc123",
  "timestamp": 1234567890.123,
  "server_time": "2023-01-01T12:00:00Z"
}
```

**Echo Response**
```json
{
  "type": "echo_response",
  "client_id": "abc123",
  "original_message": {...},
  "timestamp": 1234567890.123
}
```

**Broadcast**
```json
{
  "type": "broadcast",
  "from_client": "def456",
  "message": "Broadcast message content",
  "timestamp": 1234567890.123
}
```

## MCP Tools Reference

### `get_websocket_server_status`

Get comprehensive status information about the WebSocket server.

**Returns:**
```json
{
  "websocket_server": {
    "host": "localhost",
    "port": 9004,
    "is_running": true,
    "url": "ws://localhost:9004",
    "clients_connected": 3,
    "stats": {
      "total_connections": 15,
      "total_messages": 127,
      "start_time": "2023-01-01T12:00:00Z",
      "uptime_seconds": 3600,
      "errors": 0
    },
    "capabilities": ["ping", "echo", "broadcast", ...]
  },
  "mcp_server": {
    "mcp_server_name": "WebSocketMockMCP",
    "mcp_server_type": "websocket_mock",
    "mcp_server_version": "1.0.0"
  }
}
```

### `send_websocket_message`

Send a message to connected WebSocket clients.

**Parameters:**
- `message_type` (string): Type of message to send
- `payload` (object, optional): Message payload data
- `target_client` (string, optional): Specific client ID (if None, sends to all)

**Returns:**
```json
{
  "status": "sent|no_clients|server_not_running|error",
  "message_type": "test_message",
  "target_client": "abc123",
  "sent_to_clients": 2,
  "total_clients": 3,
  "errors": []
}
```

### `get_websocket_clients`

Get information about all connected WebSocket clients.

**Returns:**
```json
{
  "status": "success|server_not_running|error",
  "clients": [
    {
      "id": "abc123",
      "connected_at": "2023-01-01T12:00:00Z",
      "last_ping": "2023-01-01T12:05:00Z",
      "remote_address": "127.0.0.1:54321",
      "connection_status": "open"
    }
  ],
  "total_clients": 1,
  "server_info": {
    "host": "localhost",
    "port": 9004,
    "url": "ws://localhost:9004"
  }
}
```

### `test_websocket_connection`

Test WebSocket connections with various test types.

**Parameters:**
- `test_type` (string): Type of test ("ping", "echo", "broadcast", "stress")
- `target_client` (string, optional): Specific client for targeted tests

**Returns:**
```json
{
  "status": "test_completed|stress_test_completed|no_clients|error",
  "test_type": "ping",
  "result": {...}
}
```

## Testing

### Running Tests

```bash
# Unit tests
uv run pytest tests/unit/test_websocket_mock_server.py -v

# Integration tests
uv run pytest tests/integration/test_websocket_mock_integration.py -v

# End-to-end tests
uv run pytest tests/e2e/test_websocket_mock_e2e.py -v

# All WebSocket mock tests
uv run pytest tests/ -k "websocket_mock" -v
```

### Interactive Test Client

Use the included test client for manual testing:

```bash
# Interactive mode
python tests/utils/websocket_test_client.py interactive

# Automated test scenarios
python tests/utils/websocket_test_client.py test
```

### Test Scenarios

The test suite covers:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Real WebSocket connections
- **End-to-End Tests**: Complete workflows
- **Stress Tests**: Multiple concurrent connections
- **Error Handling**: Various error conditions
- **Edge Cases**: Connection cleanup, timeouts, etc.

## Development

### Architecture

```
websocket_mock/
├── __init__.py          # Module exports
├── server.py            # Main MCP server implementation
├── websocket_server.py  # WebSocket server implementation
├── tools.py             # MCP tools implementation
└── README.md           # This file
```

### Key Components

- **WebSocketMockMCPServer**: Main MCP server class
- **WebSocketMockServer**: WebSocket server implementation
- **WebSocketClient**: Client connection management
- **Tools**: MCP tool implementations

### Adding New Features

1. **New Message Types**: Add handlers to `WebSocketMockServer._register_default_handlers()`
2. **New MCP Tools**: Add tools to `tools.py` and register in `server.py`
3. **Configuration Options**: Add to `ServerConfig.config` handling
4. **Tests**: Add corresponding tests for new functionality

## Use Cases

### 🧪 Testing WebSocket Applications
- Test WebSocket client implementations
- Simulate various server behaviors
- Test error handling and edge cases
- Performance and stress testing

### 🤖 AI Model Development
- Train models on WebSocket interactions
- Test AI-driven WebSocket applications
- Develop conversational WebSocket bots
- Real-time communication testing

### 🔧 Development & Debugging
- Debug WebSocket communication issues
- Prototype WebSocket-based features
- Test message broadcasting
- Monitor connection patterns

### 📚 Learning & Education
- Learn WebSocket protocol
- Understand real-time communication
- Practice async programming
- Study client-server architectures

## Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Check what's using the port
lsof -i :9004

# Use a different port
export WEBSOCKET_PORT=9005
```

**Connection Refused**
```bash
# Ensure server is running
uv run lightfast-websocket-mock-server

# Check server status via MCP tools
```

**WebSocket Connection Drops**
- Check network connectivity
- Verify firewall settings
- Monitor server logs for errors

### Debugging

Enable debug logging:
```python
import logging
logging.getLogger("WebSocketServer").setLevel(logging.DEBUG)
```

Monitor server statistics:
```bash
# Use the test client to get stats
python tests/utils/websocket_test_client.py
# Then run: stats
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
uv run pytest tests/unit/test_websocket_mock_server.py

# Run linting
uv run task lint

# Format code
uv run task format
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 