# Lightfast MCP Plugin for Photoshop

This plugin provides a socket server inside Photoshop that allows the Lightfast MCP server to connect and control Photoshop.

## Features

- Socket server that listens on port 8765 (configurable)
- Command handling for common Photoshop operations
- UI panel to start/stop the server and monitor connections
- Support for executing arbitrary JSX code
- Document information retrieval

## Installation

### Prerequisites

- Adobe Photoshop 2021 (version 22.0) or later
- UXP Developer Tool (for development)

### Installation Steps

#### Development Installation (using UXP Developer Tool)

1. Download and install the [UXP Developer Tool](https://developer.adobe.com/photoshop/uxp/devtool/)
2. Open UXP Developer Tool
3. Click "Add Plugin" and select the folder containing this plugin
4. Click "Load" to load the plugin
5. Click "Actions" → "Debug" to launch the plugin in Photoshop

#### Production Installation

1. Package the plugin using UXP Developer Tool:
   - Click "Package" on your plugin entry
   - This will create a `.ccx` file
2. Install the package:
   - In Photoshop, go to Plugins → Manage Plugins
   - Click the "..." button and select "Install Plugins"
   - Navigate to and select the `.ccx` file
   - Follow the installation prompts

## Usage

1. Open the plugin panel in Photoshop via `Plugins → Lightfast MCP`
2. Set the desired port number (default: 8765)
3. Click "Start Server" to start the socket server
4. The Lightfast MCP server should now be able to connect to Photoshop
5. The UI will show the connection status and provide logs of operations

## Troubleshooting

- If you see a "Network access is not available" error, make sure the plugin has network permissions
- Ensure the port is not in use by another application
- Check the plugin logs for any error messages
- Verify your Photoshop version is 22.0 or later
- Try restarting Photoshop after installation

## Development

### Structure

- `manifest.json` - UXP plugin manifest
- `index.html` - UI panel HTML
- `styles.css` - CSS for UI panel
- `js/main.js` - JavaScript for the UI panel and socket server logic

### Adding New Commands

To add new commands, modify the `executeCommand` function in `js/main.js`:

```javascript
async function executeCommand(command) {
    const { type, params = {} } = command;
    
    switch (type) {
        // Existing commands...
        
        case 'your_new_command':
            return {
                status: 'success',
                result: await yourNewFunction(params)
            };
            
        // ...
    }
}
```

Then implement the corresponding function to handle the command. 