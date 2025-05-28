// Lightfast MCP Figma Plugin - Simplified Version
// This file handles basic communication between the UI and Figma's document API

// Plugin state
let isPluginActive = true;

// Runs this code if the plugin is run in Figma
if (figma.editorType === 'figma') {
  // Show the HTML UI
  figma.showUI(__html__, { 
    width: 320, 
    height: 400,
    themeColors: true 
  });

  // Handle messages from the UI
  figma.ui.onmessage = async (msg: any) => {
    try {
      switch (msg.type) {
        case 'ping':
          figma.ui.postMessage({ type: 'pong', timestamp: Date.now() });
          break;

        case 'get_document_info':
          const documentInfo = {
            name: figma.root.name,
            id: figma.root.id,
            type: figma.root.type,
            currentPage: {
              name: figma.currentPage.name,
              id: figma.currentPage.id,
              children: figma.currentPage.children.length
            }
          };
          figma.ui.postMessage({
            type: 'response',
            data: documentInfo
          });
          break;

        case 'close-plugin':
          figma.closePlugin();
          break;

        default:
          figma.ui.postMessage({
            type: 'error',
            message: `Unknown message type: ${msg.type}`
          });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      figma.ui.postMessage({
        type: 'error',
        message: `Error handling ${msg.type}: ${errorMessage}`
      });
    }
  };
}

// Cleanup on plugin close
figma.on('close', () => {
  isPluginActive = false;
});