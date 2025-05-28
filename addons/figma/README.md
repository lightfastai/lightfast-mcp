# Lightfast MCP Figma Plugin (Simplified)

This is a simplified Figma plugin that demonstrates basic communication between Figma and the Lightfast MCP server.

## Features

- **Basic Plugin Communication**: Simple message passing between UI and Figma
- **Document Information**: Get basic document structure and metadata
- **Connection Testing**: Ping/pong functionality to test plugin communication
- **Minimal UI**: Clean, simple interface for testing

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
# Start the Figma server
uv run lightfast-figma-server

# Or start via orchestrator
uv run lightfast-mcp-orchestrator start
```

### 2. Run the Plugin

1. Open Figma and load your design file
2. Go to `Plugins` → Find "Lightfast MCP Figma Plugin"
3. Click to run the plugin

### 3. Test the Plugin

1. Plugin UI will open in the sidebar
2. Click `"Test Connection"` to test internal plugin communication
3. Click `"Get Document Info"` to retrieve basic document information
4. Click `"Close Plugin"` to close the plugin

## Available Features

The simplified plugin provides:

### Basic Tools
- `Test Connection` - Tests internal plugin communication (ping/pong)
- `Get Document Info` - Retrieves basic document structure and metadata
- `Close Plugin` - Closes the plugin

### MCP Server Tools
The MCP server exposes these tools:
- `get_server_info` - Get server information and status
- `ping` - Simple connectivity test

## Configuration

This simplified version requires no special configuration. The plugin communicates internally without external WebSocket connections.

## File Structure

```
addons/figma/
├── manifest.json    # Plugin metadata and configuration
├── code.ts         # Simplified plugin logic
├── ui.html         # Simplified plugin user interface
├── tsconfig.json   # TypeScript configuration
├── package.json    # Node.js dependencies
└── README.md       # This documentation
```

## Development

To build the TypeScript code:

```bash
cd addons/figma
npm install
npm run build
```

This will compile `code.ts` to `code.js` which is used by the plugin.

## Troubleshooting

### Plugin Won't Load
- Ensure you're using Figma Desktop app (not web version)
- Check that `manifest.json` is valid
- Verify `code.js` exists (run `npm run build` if needed)

### Plugin Development
- Use Figma Desktop app for development
- Check the Figma console (`Developer` → `Console`) for debugging
- Test with simple commands first (ping, get_document_info)

## License

This plugin is part of the Lightfast MCP project and follows the same license terms.

## Support

For issues and support:
1. Check the main lightfast-mcp project documentation
2. Review server logs for connection issues
3. Test with the MCP orchestrator commands 