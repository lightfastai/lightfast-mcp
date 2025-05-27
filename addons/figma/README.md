# Lightfast MCP Figma Plugin

This Figma plugin enables real-time communication between Figma and the Lightfast MCP server via WebSocket, providing comprehensive design automation capabilities.

## Features

- **Real-time Design Manipulation**: Create, modify, and delete design elements directly from AI models
- **Document Inspection**: Get detailed information about Figma documents, pages, and nodes
- **Text Management**: Bulk text content replacement and editing
- **Layout Control**: Auto-layout, positioning, and styling operations
- **Component Operations**: Work with Figma components and instances
- **WebSocket Communication**: Stable, real-time bidirectional communication

## Installation

### Development Installation (Local Testing)

1. **Open Figma Desktop App** (required for plugin development)

2. **Create a New Plugin**:
   - Go to `Plugins` → `Development` → `New Plugin`
   - Choose `"Link existing plugin"`
   - Select the `manifest.json` file from this directory (`addons/figma/manifest.json`)

3. **Plugin Ready**: The plugin will now appear in your development plugins list

### Publishing Options

## Option 1: Organization/Team Publishing (Recommended)

**Best for**: Private team use, no review process needed

1. **Access Plugin Management**:
   - Go to your Figma workspace
   - Navigate to `Settings` → `Plugins`
   - Click `"Publish plugin"`

2. **Upload Plugin Files**:
   - Upload `manifest.json`, `code.js`, and `ui.html`
   - Set visibility to `"Only members of [your organization]"`

3. **Instant Availability**: Plugin is immediately available to your team

## Option 2: Community Publishing (Public)

**Best for**: Public distribution, requires Figma review

1. **Prepare for Review**:
   - Ensure plugin follows [Figma's plugin guidelines](https://www.figma.com/plugin-docs/publishing-guidelines/)
   - Add proper descriptions, screenshots, and documentation
   - Test thoroughly across different files and scenarios

2. **Submit for Review**:
   - Go to `Plugins` → `Development` → Select your plugin
   - Click `"Publish to Community"`
   - Fill out the submission form with:
     - Plugin description
     - Screenshots/preview images
     - Tags and categories
     - Detailed usage instructions

3. **Review Process**:
   - Figma team reviews (typically 1-2 weeks)
   - May request changes or improvements
   - Once approved, available to all Figma users

## Usage

### 1. Start the MCP Server

First, ensure your Lightfast MCP server is running with WebSocket support:

```bash
# Start the WebSocket server (on port 3001)
uv run lightfast-mcp-orchestrator socket

# Or start individual Figma server
uv run lightfast-figma-server --transport websocket
```

### 2. Run the Plugin

1. Open Figma and load your design file
2. Go to `Plugins` → Find "Lightfast MCP Figma Plugin"
3. Click to run the plugin

### 3. Connect to MCP Server

1. Plugin UI will open in the sidebar
2. Click `"Connect"` to establish WebSocket connection
3. Enter channel name (default: "default") and click `"Join Channel"`
4. Green status indicates successful connection

### 4. Use with AI Models

Once connected, AI models can interact with Figma through MCP tools:

```bash
# Example: Using with Cursor AI
# The AI can now execute commands like:
# - "Create a red rectangle at position 100, 100"
# - "Change all heading text to blue"
# - "Export the selected frame as PNG"
```

## Available MCP Tools

The plugin exposes these tools to MCP clients:

### Document & Selection
- `get_document_info` - Get document structure and metadata
- `get_selection` - Get currently selected elements
- `get_node_info` - Get detailed node information

### Creating Elements
- `create_rectangle` - Create rectangles with positioning
- `create_frame` - Create frames for layouts
- `create_text` - Create text nodes with styling

### Modifying Elements
- `set_text_content` - Update text content
- `move_node` - Change element position
- `resize_node` - Resize elements
- `delete_node` - Remove elements
- `set_fill_color` - Change fill colors

### Styling & Layout
- Auto-layout controls
- Padding and spacing
- Component instance management
- Style applications

## Configuration

### WebSocket Settings

The plugin connects to `ws://localhost:3001` by default. To change this:

1. Edit `code.js`
2. Update the `WEBSOCKET_URL` constant:
   ```javascript
   const WEBSOCKET_URL = 'ws://your-server:port';
   ```

### Network Access

The plugin requires network access for WebSocket communication. Allowed domains are configured in `manifest.json`:

```json
{
  "networkAccess": {
    "allowedDomains": [
      "localhost:*",
      "127.0.0.1:*",
      "*.lightfast.dev"
    ]
  }
}
```

## Troubleshooting

### Plugin Won't Connect
- Ensure MCP WebSocket server is running on port 3001
- Check browser/Figma console for error messages
- Verify network permissions in manifest.json

### Commands Not Working
- Confirm channel is joined (green status in plugin UI)
- Check that Figma file has appropriate permissions
- Verify node IDs are valid when targeting specific elements

### Plugin Development
- Use Figma Desktop app for development (web version has limitations)
- Check the Figma console (`Developer` → `Console`) for debugging
- Test with simple commands first (ping, get_document_info)

## File Structure

```
addons/figma/
├── manifest.json    # Plugin metadata and configuration
├── code.js         # Main plugin logic and tool handlers
├── ui.html         # Plugin user interface
└── README.md       # This documentation
```

## License

This plugin is part of the Lightfast MCP project and follows the same license terms.

## Support

For issues and support:
1. Check the main lightfast-mcp project documentation
2. Review WebSocket server logs for connection issues
3. Test with the MCP orchestrator's socket demo commands 