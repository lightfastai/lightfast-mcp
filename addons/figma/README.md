# Lightfast MCP Figma Plugin (WebSocket Server Architecture)

This Figma plugin provides WebSocket-based communication between Figma and the Lightfast MCP server through a WebSocket server architecture where the plugin UI acts as a WebSocket server and the MCP server connects as a WebSocket client.

## Architecture

The plugin uses a WebSocket server architecture following the Blender pattern:

```
┌─────────────────┐    Plugin Messages    ┌─────────────────┐    WebSocket     ┌─────────────────┐
│   Plugin Code   │ ←──────────────────→ │   UI WebSocket  │ ←──────────────→ │   MCP Server    │
│   (code.ts)     │                      │   Server        │   localhost:9003 │   (WebSocket    │
│                 │                      │   (ui.html)     │                  │    Client)      │
│ - Figma API     │                      │ - WebSocket Srv │                  │ - Tool Registry │
│ - Document Ops  │                      │ - MCP Commands  │                  │ - AI Integration│
│ - Design Cmds   │                      │ - Response Mgmt │                  │ - State Mgmt    │
└─────────────────┘                      └─────────────────┘                  └─────────────────┘
```

**Why this architecture?**
- Follows the proven Blender pattern (plugin acts as server, MCP server acts as client)
- UI acts as WebSocket server, eliminating complex server integration in MCP server
- MCP server connects as WebSocket client for simple, reliable communication
- Real-time bidirectional communication with proper message handling

## Features

- **WebSocket Server**: UI runs a WebSocket server on configurable port
- **Real-time Communication**: WebSocket connection from MCP server to UI server
- **Figma API Integration**: Full access to Figma's document and design APIs
- **Design Command Execution**: Execute AI-generated design commands
- **Server Management**: Manual server control with status indicators
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

### 1. Start the WebSocket Server (Plugin UI)

1. Open Figma and load your design file
2. Go to `Plugins` → Find "Lightfast MCP Figma Plugin"
3. Click to run the plugin
4. **Configure WebSocket Server**:
   - **WS Port**: Enter WebSocket server port (default: `9003`)
5. **Start Server**: Click the "🚀 Start Server" button
6. **Verify**: Watch the status indicator turn green when server is running

### 2. Start the MCP Server (WebSocket Client)

With the plugin WebSocket server running, start your Lightfast MCP server:

```bash
# Start the Figma server directly
uv run lightfast-figma-server

# Or start via orchestrator
uv run lightfast-mcp-orchestrator start
```

The MCP server will:
- **Connect as WebSocket Client**: Connects to `ws://localhost:9003` (plugin UI server)
- **MCP HTTP Server**: Runs on `http://localhost:8003/mcp` (for AI client connections)

### 3. Test the Connection

1. **Plugin UI**: Click `"🔧 Test Server"` to test WebSocket server functionality
2. **MCP Server**: Use the ping tool to test WebSocket client connection
3. **Full Stack**: Test document info and design commands

## Available Features

### WebSocket Server Controls (Plugin UI)
- **Port Configuration**: Set custom WebSocket server port
- **Start/Stop Server**: Full control over WebSocket server state
- **Server Status**: Real-time server status indicators
- **Test Server**: Verify WebSocket server functionality

### Plugin UI Tools
- `🚀 Start Server` - Start WebSocket server on configured port
- `🛑 Stop Server` - Stop WebSocket server
- `🔧 Test Server` - Tests WebSocket server functionality and broadcasts to clients
- `🔄 Test Plugin Communication` - Tests internal plugin messaging (ping/pong)
- `📄 Get Document Info` - Retrieves comprehensive document data
- `🎨 Test Design Command` - Tests design command execution (creates a rectangle)
- `✕ Close Plugin` - Closes the plugin and stops WebSocket server

### MCP Server Tools
The MCP server exposes these tools for AI clients:
- `get_server_info` - Get server information and WebSocket connection status
- `ping` - Simple connectivity test via WebSocket
- `get_document_state` - Get current Figma document state via WebSocket
- `execute_design_command` - Execute design commands in Figma via WebSocket

### Design Commands
The plugin supports these design commands:
- `"create rectangle"` - Creates a rectangle shape
- `"create circle"` - Creates a circle/ellipse shape  
- `"create text"` - Creates a text node with default content

### Communication Flow

1. **AI Client → MCP Server**: AI sends tool calls via HTTP
2. **MCP Server → Plugin UI**: Server sends commands via WebSocket client connection
3. **Plugin UI → Plugin Code**: UI forwards commands via plugin messaging
4. **Plugin Code → Figma API**: Plugin executes commands using Figma API
5. **Results flow back**: Plugin Code → Plugin UI → WebSocket → MCP Server → AI Client

## Configuration

### Server Configuration

The server can be configured via `config/servers.yaml`:

```yaml
- config:
    type: figma
    figma_host: "localhost"
    figma_port: 9003
    command_timeout: 30.0
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

The plugin UI allows you to configure:
- **WS Port**: WebSocket server port number (default: `9003`)

For different server configurations:
- **Local Development**: `9003` (default)
- **Custom Port**: `8080` (if you want to use a different port)

## File Structure

```
addons/figma/
├── manifest.json         # Plugin metadata and configuration
├── code.ts              # Plugin logic (Figma API interactions)
├── code.js              # Compiled JavaScript (generated)
├── ui.html              # Plugin UI with WebSocket server functionality
├── websocket-server.js  # Standalone WebSocket server for testing
├── tsconfig.json        # TypeScript configuration
├── package.json         # Node.js dependencies
└── README.md            # This documentation
```

## Development

### Building the Plugin

```bash
cd addons/figma
pnpm install
pnpm run build
```

This compiles `code.ts` to `code.js` which is used by the plugin.

### Testing with Standalone WebSocket Server

For testing without the full Figma plugin, you can use the standalone WebSocket server:

```bash
cd addons/figma
pnpm install
node websocket-server.js [port]
```

This starts a WebSocket server that simulates the plugin WebSocket server functionality.

### Testing the Full Stack

1. **Start the plugin WebSocket server**: Load plugin in Figma, click "🚀 Start Server"
2. **Verify WebSocket server**: Check plugin UI shows "WebSocket Server Running"
3. **Start the MCP server**: `uv run lightfast-figma-server`
4. **Verify connection**: MCP server logs should show successful WebSocket connection
5. **Test all tools** via MCP server or AI client

### Testing with Different Ports

To test with different WebSocket ports:

1. **Change plugin UI port**: Enter custom port (e.g., `8080`) and start server
2. **Update server config** in `config/servers.yaml`:
   ```yaml
   figma_port: 8080  # Custom port
   ```
3. **Restart MCP server**: `uv run lightfast-figma-server`

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

### WebSocket Server Issues
- **"Server failed to start"**: Check if port is already in use
- **"Port in use"**: Try a different port or stop other services using the port
- **Browser limitations**: Note that browser-based WebSocket servers have limitations

### MCP Server Connection Issues
- **"Failed to connect"**: Ensure plugin WebSocket server is running first
- **"Connection refused"**: Verify host and port settings match
- **"Timeout"**: Check firewall settings and network connectivity

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

1. **Start WebSocket Server**:
   - WS Port: `9003`
   - Click "🚀 Start Server"

2. **Test Functionality**:
   - Click "🔧 Test Server" to test WebSocket server functionality
   - Click "📄 Get Document Info" to see current document structure
   - Click "🎨 Test Design Command" to create a rectangle
   - Monitor the output area for real-time logs

3. **Check Status**:
   - Green status = WebSocket server running and working
   - Red status = Server stopped or error
   - Yellow status = Starting or warning

## Production Considerations

### Browser WebSocket Server Limitations

The current implementation simulates a WebSocket server in the browser environment. For production use, consider:

1. **Node.js WebSocket Server**: Use the standalone `websocket-server.js` as a template
2. **External WebSocket Server**: Deploy a separate WebSocket server service
3. **Alternative Architecture**: Consider HTTP polling or other communication methods

### Recommended Production Architecture

```
┌─────────────────┐    HTTP/Plugin API    ┌─────────────────┐    WebSocket     ┌─────────────────┐
│   Plugin Code   │ ←──────────────────→ │   Node.js       │ ←──────────────→ │   MCP Server    │
│   (code.ts)     │                      │   WebSocket     │   localhost:9003 │   (WebSocket    │
│                 │                      │   Server        │                  │    Client)      │
│ - Figma API     │                      │ - Real WS Srv   │                  │ - Tool Registry │
│ - Document Ops  │                      │ - MCP Commands  │                  │ - AI Integration│
│ - Design Cmds   │                      │ - Response Mgmt │                  │ - State Mgmt    │
└─────────────────┘                      └─────────────────┘                  └─────────────────┘
```

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