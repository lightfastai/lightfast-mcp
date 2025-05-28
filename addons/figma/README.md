# Lightfast MCP Figma Plugin (UI-WebSocket Architecture)

This Figma plugin provides WebSocket-based communication between Figma and the Lightfast MCP server through a unique architecture where the UI handles WebSocket connections and the plugin code handles Figma API interactions.

## Architecture

The plugin uses a split architecture to work around Figma's sandboxed environment:

```
┌─────────────────┐    Plugin Messages    ┌─────────────────┐    WebSocket     ┌─────────────────┐
│   Plugin Code   │ ←──────────────────→ │   Plugin UI     │ ←──────────────→ │   MCP Server    │
│   (code.ts)     │                      │   (ui.html)     │   ws://9003      │                 │
│                 │                      │                 │                  │                 │
│ - Figma API     │                      │ - WebSocket     │                  │ - Tool Registry │
│ - Document Ops  │                      │ - Server Comm   │                  │ - AI Integration│
│ - Design Cmds   │                      │ - Message Queue │                  │ - State Mgmt    │
└─────────────────┘                      └─────────────────┘                  └─────────────────┘
```

**Why this architecture?**
- Figma's plugin sandbox doesn't have WebSocket APIs
- The UI runs in a browser-like environment with full WebSocket support
- Plugin messaging bridges the gap between Figma API and WebSocket communication

## Features

- **Real-time Communication**: WebSocket connection from UI to MCP server
- **Figma API Integration**: Full access to Figma's document and design APIs
- **Design Command Execution**: Execute AI-generated design commands
- **Automatic Reconnection**: Robust connection management with message queuing
- **Comprehensive Logging**: Real-time status updates and debugging info

## Installation

### Development Installation (Local Testing)

1. **Open Figma Desktop App** (required for plugin development)

2. **Create a New Plugin**:
   - Go to `Plugins` → `Development` → `New Plugin`
   - Choose `"Link existing plugin"`
   - Select the `manifest.json` file from this directory (`addons/figma/manifest.json`)

3. **Plugin Ready**: The plugin will now appear in your development plugins list

## Usage

### 1. Start the MCP Server

First, ensure your Lightfast MCP server is running:

```bash
# Start the Figma server directly
uv run lightfast-figma-server

# Or start via orchestrator
uv run lightfast-mcp-orchestrator start
```

The server will start:
- **MCP HTTP Server**: `http://localhost:8003/mcp` (for AI client connections)
- **WebSocket Server**: `ws://localhost:9003` (for Figma plugin UI communication)

### 2. Run the Plugin

1. Open Figma and load your design file
2. Go to `Plugins` → Find "Lightfast MCP Figma Plugin"
3. Click to run the plugin

### 3. Test the Connection

1. Plugin UI will open in the sidebar
2. Watch the WebSocket status indicator (should show "Connected to MCP Server")
3. Click `"Test WebSocket Connection"` to test server communication
4. Click `"Test Plugin Communication"` to test internal plugin functionality
5. Click `"Get Document Info"` to retrieve and send document data to the server
6. Click `"Test Design Command"` to test design command execution

## Available Features

### Plugin UI Tools
- `Test WebSocket Connection` - Tests WebSocket communication with MCP server
- `Test Plugin Communication` - Tests internal plugin messaging (ping/pong)
- `Get Document Info` - Retrieves comprehensive document data and sends to server
- `Test Design Command` - Tests design command execution (creates a rectangle)
- `Close Plugin` - Closes the plugin and WebSocket connection

### MCP Server Tools
The MCP server exposes these tools for AI clients:
- `get_server_info` - Get server information and WebSocket status
- `ping` - Simple connectivity test
- `get_document_state` - Get current Figma document state via WebSocket
- `execute_design_command` - Execute design commands in Figma via WebSocket

### Design Commands
The plugin supports these design commands:
- `"create rectangle"` - Creates a rectangle shape
- `"create circle"` - Creates a circle/ellipse shape  
- `"create text"` - Creates a text node with default content

### Communication Flow

1. **AI Client → MCP Server**: AI sends tool calls via HTTP
2. **MCP Server → Plugin UI**: Server sends commands via WebSocket
3. **Plugin UI → Plugin Code**: UI forwards commands via plugin messaging
4. **Plugin Code → Figma API**: Plugin executes commands using Figma API
5. **Results flow back**: Plugin Code → UI → WebSocket → MCP Server → AI Client

## Configuration

### Server Configuration

The server can be configured via `config/servers.yaml`:

```yaml
- config:
    type: figma
    websocket_host: "localhost"
    websocket_port: 9003
    command_timeout: 30.0
    plugin_channel: "default"
  description: Figma MCP Server for web design and collaborative design workflows
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

### Plugin Configuration

The plugin connects to `ws://localhost:9003` by default. To change this, modify the `WEBSOCKET_URL` constant in `ui.html`.

## File Structure

```
addons/figma/
├── manifest.json    # Plugin metadata and configuration
├── code.ts         # Plugin logic (Figma API interactions)
├── code.js         # Compiled JavaScript (generated)
├── ui.html         # Plugin UI with WebSocket functionality
├── tsconfig.json   # TypeScript configuration
├── package.json    # Node.js dependencies
└── README.md       # This documentation
```

## Development

### Building the Plugin

```bash
cd addons/figma
pnpm install
pnpm run build
```

This compiles `code.ts` to `code.js` which is used by the plugin.

### Testing the Full Stack

1. **Start the MCP server**: `uv run lightfast-figma-server`
2. **Verify WebSocket server**: `netstat -an | grep 9003`
3. **Load the plugin** in Figma Desktop app
4. **Check connection status** in the plugin UI
5. **Test all buttons** to verify functionality

### Adding New Design Commands

To add new design commands:

1. **Update plugin code** (`code.ts`):
   ```typescript
   else if (command.toLowerCase().includes('create frame')) {
     const frame = figma.createFrame();
     frame.name = 'AI Created Frame';
     // ... setup frame
   }
   ```

2. **Rebuild**: `pnpm run build`
3. **Reload plugin** in Figma

## Troubleshooting

### Plugin Won't Load
- Ensure you're using Figma Desktop app (not web version)
- Check that `manifest.json` is valid
- Verify `code.js` exists (run `pnpm run build` if needed)

### WebSocket Connection Issues
- Ensure MCP server is running: `uv run lightfast-figma-server`
- Check WebSocket port is open: `netstat -an | grep 9003`
- Check server logs for WebSocket errors
- Verify no firewall blocking port 9003

### Plugin Communication Issues
- Check Figma console (`Developer` → `Console`) for errors
- Monitor plugin UI logs in the output area
- Test plugin messaging with "Test Plugin Communication" button

### Design Command Issues
- Verify commands are properly formatted
- Check plugin logs for execution errors
- Test with simple commands first (create rectangle)

## Example Usage

### Via MCP Client (AI Integration)

```python
# Get current document state
document_state = await server.get_document_state()

# Execute design commands
result = await server.execute_design_command("create rectangle")
result = await server.execute_design_command("create circle")
result = await server.execute_design_command("create text")
```

### Via Plugin UI (Manual Testing)

1. Click "Get Document Info" to see current document structure
2. Click "Test Design Command" to create a rectangle
3. Monitor the output area for real-time logs
4. Check WebSocket status indicator for connection health

## License

This plugin is part of the Lightfast MCP project and follows the same license terms.

## Support

For issues and support:
1. Check the main lightfast-mcp project documentation
2. Review server logs: `uv run lightfast-figma-server`
3. Test WebSocket connectivity: `netstat -an | grep 9003`
4. Use the MCP orchestrator: `uv run lightfast-mcp-orchestrator start`
5. Check Figma console for plugin errors 