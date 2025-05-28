// Lightfast MCP Figma Plugin - Socket Server Version
// This file handles Figma API interactions and acts as a socket server for MCP communication
// Following the Blender pattern: Plugin acts as server, MCP server acts as client

// Plugin state
let isPluginActive = true;
let serverPort = 9003;

// Runs this code if the plugin is run in Figma
if (figma.editorType === 'figma') {
  // Show the HTML UI
  figma.showUI(__html__, { 
    width: 320, 
    height: 450,
    themeColors: true 
  });

  // Send initial status to UI
  figma.ui.postMessage({
    type: 'plugin_status',
    data: {
      status: 'Plugin loaded - ready to start server',
      port: serverPort,
      active: isPluginActive
    }
  });

  // Handle messages from the UI
  figma.ui.onmessage = async (msg: any) => {
    try {
      switch (msg.type) {
        case 'ping':
          figma.ui.postMessage({ type: 'pong', timestamp: Date.now() });
          break;

        case 'get_document_info':
          await sendDocumentInfoToUI();
          break;

        case 'execute_design_command':
          await executeDesignCommand(msg.command || '');
          break;

        case 'start_server':
          await startSocketServer(msg.port || serverPort);
          break;

        case 'stop_server':
          await stopSocketServer();
          break;

        case 'mcp_command':
          await handleMCPCommand(msg.command);
          break;

        case 'close-plugin':
          cleanup();
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

async function startSocketServer(port: number) {
  try {
    serverPort = port;
    
    // Send status update to UI bridge
    figma.ui.postMessage({
      type: 'server_status',
      data: {
        status: 'Server started',
        port: serverPort,
        timestamp: Date.now()
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    // Send error response back to UI bridge
    figma.ui.postMessage({
      type: 'error',
      message: `Error starting server: ${errorMessage}`
    });
  }
}

async function stopSocketServer() {
  try {
    // Send status update to UI bridge
    figma.ui.postMessage({
      type: 'server_status',
      data: {
        status: 'Server stopped',
        port: serverPort,
        timestamp: Date.now()
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error stopping server: ${errorMessage}`
    });
  }
}

async function handleMCPCommand(command: any) {
  try {
    // Use the existing MCP command handler
    const response = handleMCPCommandInternal(command);
    
    // Send response back to UI bridge
    figma.ui.postMessage({
      type: 'mcp_command_response',
      response: response
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    // Send error response back to UI bridge
    figma.ui.postMessage({
      type: 'mcp_command_response',
      response: {
        status: 'error',
        message: errorMessage,
        timestamp: Date.now()
      }
    });
  }
}

async function sendDocumentInfoToUI() {
  try {
    // Gather comprehensive document information
    const documentInfo = {
      document: {
        name: figma.root.name,
        id: figma.root.id,
        type: figma.root.type,
      },
      currentPage: {
        name: figma.currentPage.name,
        id: figma.currentPage.id,
        children: figma.currentPage.children.length,
        selection: figma.currentPage.selection.length
      },
      selection: figma.currentPage.selection.map(node => ({
        id: node.id,
        name: node.name,
        type: node.type,
        visible: node.visible,
        locked: node.locked
      })),
      viewport: {
        center: figma.viewport.center,
        zoom: figma.viewport.zoom
      },
      timestamp: Date.now()
    };

    // Send to UI
    figma.ui.postMessage({
      type: 'document_info',
      data: documentInfo
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error getting document info: ${errorMessage}`
    });
  }
}

async function executeDesignCommand(command: string) {
  try {
    console.log('Executing design command:', command);
    
    // Example: Simple command parsing
    let result: any = { message: 'Command received but not implemented', command: command };
    
    if (command.toLowerCase().includes('create rectangle')) {
      // Example implementation
      const rect = figma.createRectangle();
      rect.name = 'AI Created Rectangle';
      rect.resize(100, 100);
      figma.currentPage.appendChild(rect);
      figma.currentPage.selection = [rect];
      figma.viewport.scrollAndZoomIntoView([rect]);
      
      result = {
        message: 'Rectangle created successfully',
        command: command,
        created_node: {
          id: rect.id,
          name: rect.name,
          type: rect.type
        }
      };
    } else if (command.toLowerCase().includes('create circle')) {
      // Create ellipse (circle)
      const ellipse = figma.createEllipse();
      ellipse.name = 'AI Created Circle';
      ellipse.resize(100, 100);
      figma.currentPage.appendChild(ellipse);
      figma.currentPage.selection = [ellipse];
      figma.viewport.scrollAndZoomIntoView([ellipse]);
      
      result = {
        message: 'Circle created successfully',
        command: command,
        created_node: {
          id: ellipse.id,
          name: ellipse.name,
          type: ellipse.type
        }
      };
    } else if (command.toLowerCase().includes('create text')) {
      // Create text node
      const text = figma.createText();
      text.name = 'AI Created Text';
      text.characters = 'Hello from AI!';
      figma.currentPage.appendChild(text);
      figma.currentPage.selection = [text];
      figma.viewport.scrollAndZoomIntoView([text]);
      
      result = {
        message: 'Text created successfully',
        command: command,
        created_node: {
          id: text.id,
          name: text.name,
          type: text.type,
          text: text.characters
        }
      };
    }

    // Send result back to UI
    figma.ui.postMessage({
      type: 'design_command_result',
      data: result
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error executing design command: ${errorMessage}`
    });
  }
}

// Command handlers for MCP server communication
// These functions handle commands that come from the MCP server via the UI bridge

function handleMCPCommandInternal(command: any): any {
  try {
    const cmdType = command.type;
    const params = command.params || {};

    console.log(`Handling MCP command: ${cmdType}`);

    switch (cmdType) {
      case 'ping':
        return {
          status: 'success',
          result: {
            message: 'pong',
            timestamp: Date.now(),
            server: 'figma-plugin'
          }
        };

      case 'get_document_info':
        return {
          status: 'success',
          result: getCurrentDocumentInfo()
        };

      case 'execute_design_command':
        const designCommand = params.command || '';
        return {
          status: 'success',
          result: executeDesignCommandSync(designCommand)
        };

      default:
        return {
          status: 'error',
          message: `Unknown command type: ${cmdType}`
        };
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return {
      status: 'error',
      message: errorMessage
    };
  }
}

function getCurrentDocumentInfo(): any {
  try {
    return {
      document: {
        name: figma.root.name,
        id: figma.root.id,
        type: figma.root.type,
      },
      currentPage: {
        name: figma.currentPage.name,
        id: figma.currentPage.id,
        children: figma.currentPage.children.length,
        selection: figma.currentPage.selection.length
      },
      selection: figma.currentPage.selection.map(node => ({
        id: node.id,
        name: node.name,
        type: node.type,
        visible: node.visible,
        locked: node.locked
      })),
      viewport: {
        center: figma.viewport.center,
        zoom: figma.viewport.zoom
      },
      timestamp: Date.now()
    };
  } catch (error) {
    throw new Error(`Error getting document info: ${error}`);
  }
}

function executeDesignCommandSync(command: string): any {
  try {
    console.log('Executing design command synchronously:', command);
    
    let result: any = { message: 'Command received but not implemented', command: command };
    
    if (command.toLowerCase().includes('create rectangle')) {
      const rect = figma.createRectangle();
      rect.name = 'AI Created Rectangle';
      rect.resize(100, 100);
      figma.currentPage.appendChild(rect);
      figma.currentPage.selection = [rect];
      figma.viewport.scrollAndZoomIntoView([rect]);
      
      result = {
        message: 'Rectangle created successfully',
        command: command,
        created_node: {
          id: rect.id,
          name: rect.name,
          type: rect.type
        }
      };
    } else if (command.toLowerCase().includes('create circle')) {
      const ellipse = figma.createEllipse();
      ellipse.name = 'AI Created Circle';
      ellipse.resize(100, 100);
      figma.currentPage.appendChild(ellipse);
      figma.currentPage.selection = [ellipse];
      figma.viewport.scrollAndZoomIntoView([ellipse]);
      
      result = {
        message: 'Circle created successfully',
        command: command,
        created_node: {
          id: ellipse.id,
          name: ellipse.name,
          type: ellipse.type
        }
      };
    } else if (command.toLowerCase().includes('create text')) {
      const text = figma.createText();
      text.name = 'AI Created Text';
      text.characters = 'Hello from AI!';
      figma.currentPage.appendChild(text);
      figma.currentPage.selection = [text];
      figma.viewport.scrollAndZoomIntoView([text]);
      
      result = {
        message: 'Text created successfully',
        command: command,
        created_node: {
          id: text.id,
          name: text.name,
          type: text.type,
          text: text.characters
        }
      };
    }

    return result;
  } catch (error) {
    throw new Error(`Error executing design command: ${error}`);
  }
}

function cleanup() {
  isPluginActive = false;
}

// Cleanup on plugin close
figma.on('close', () => {
  cleanup();
});

// Export the MCP command handler for the UI to use
(globalThis as any).handleMCPCommand = handleMCPCommand;