# Lightfast MCP Figma Plugin

A Figma plugin that connects as a WebSocket client to the Lightfast MCP server for real-time design automation.

## Architecture

- **UI (ui.html)**: Handles the WebSocket connection to the MCP server
- **Plugin Code (code.ts)**: Handles Figma API interactions and design commands
- **Communication**: UI and plugin code communicate via `postMessage`

## Features

### WebSocket Connection
- Real WebSocket client implementation in the UI
- Automatic reconnection with exponential backoff
- Connection status monitoring
- Ping/pong heartbeat support

### Design Commands
- Create rectangles, circles, and text
- Delete selected elements
- Select all elements
- Get document information
- Real-time command execution from MCP server

### Document Information
- Current document and page details
- Selection information
- Viewport state
- Connection status

## Usage

1. **Load the Plugin**: Install and run the plugin in Figma
2. **Connect to Server**: Enter the MCP server URL (default: `ws://localhost:9003`) and click Connect
3. **Test Connection**: Use the test buttons to verify communication
4. **Execute Commands**: Commands can be executed locally or received from the MCP server

## WebSocket Protocol

### Client → Server Messages
```json
{
  "type": "plugin_info",
  "plugin_info": {
    "name": "Lightfast MCP Figma Plugin",
    "version": "1.0.0",
    "capabilities": ["document_info", "design_commands"],
    "platform": "figma"
  }
}
```

### Server → Client Messages
```json
{
  "type": "execute_design_command",
  "command": "create rectangle",
  "request_id": "12345"
}
```

### Response Messages
```json
{
  "type": "design_command_response",
  "request_id": "12345",
  "result": {
    "message": "Rectangle created successfully",
    "created_node": {
      "id": "node_id",
      "name": "AI Created Rectangle",
      "type": "RECTANGLE"
    }
  }
}
```

## Development

### Building
The plugin uses TypeScript. Compile with:
```bash
tsc
```

### Testing
1. Start the MCP server on `ws://localhost:9003`
2. Load the plugin in Figma
3. Connect to the server
4. Test commands and communication

## Configuration

### Network Access
The plugin requires network access to connect to the MCP server. Allowed domains are configured in `manifest.json`:
- `ws://localhost:9003` (default)
- `ws://localhost:8003` (alternative)

### Capabilities
- Document access: `dynamic-page`
- Editor type: `figma`
- Network access: WebSocket connections to localhost

## Error Handling

- Connection failures with retry logic
- Command execution error reporting
- Graceful disconnection handling
- UI error display and logging

## License

This plugin is part of the Lightfast MCP project and follows the same license terms.

## Support

For issues and support:
1. Check the main lightfast-mcp project documentation
2. Review server logs: `uv run lightfast-figma-server`
3. Test WebSocket connectivity: Use the standalone server for testing
4. Use the MCP orchestrator: `uv run lightfast-mcp-orchestrator start`
5. Check Figma console for plugin errors
6. Verify WebSocket server settings in plugin UI 