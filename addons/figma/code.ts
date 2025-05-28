// Lightfast MCP Figma Plugin - WebSocket Client Version
// This file handles Figma API interactions and connects as a WebSocket client to the MCP server
// The UI handles the actual WebSocket connection, this code handles Figma-specific operations

// Plugin state
let isPluginActive = true;
let serverUrl = "ws://localhost:9003";
let isConnected = false;

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
      status: 'Plugin loaded - ready to connect to MCP server',
      serverUrl: serverUrl,
      active: isPluginActive,
      connected: isConnected
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

        case 'get_document_info_for_server':
          await sendDocumentInfoForServer(msg.request_id);
          break;

        case 'execute_design_command':
          await executeDesignCommand(msg.command || '');
          break;

        case 'execute_design_command_from_server':
          await executeDesignCommandFromServer(msg.command || '', msg.request_id);
          break;

        case 'websocket_connected':
          isConnected = true;
          console.log('WebSocket connected via UI:', msg.data);
          break;

        case 'websocket_disconnected':
          isConnected = false;
          console.log('WebSocket disconnected via UI:', msg.data);
          break;

        case 'close-plugin':
          cleanup();
          figma.closePlugin();
          break;

        default:
          figma.ui.postMessage({
            type: 'error',
            message: `Unknown message type: ${msg.type}`,
            requestId: msg.requestId
          });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      figma.ui.postMessage({
        type: 'error',
        message: `Error handling ${msg.type}: ${errorMessage}`,
        requestId: msg.requestId
      });
    }
  };
}

async function sendDocumentInfoToUI() {
  try {
    // Gather comprehensive document information
    const documentInfo = getCurrentDocumentInfo();

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

async function sendDocumentInfoForServer(requestId?: string) {
  try {
    // Gather comprehensive document information
    const documentInfo = getCurrentDocumentInfo();

    // Send to UI with request ID for server forwarding
    figma.ui.postMessage({
      type: 'document_info',
      data: documentInfo,
      request_id: requestId
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error getting document info for server: ${errorMessage}`,
      request_id: requestId
    });
  }
}

async function executeDesignCommand(command: string) {
  try {
    console.log('Executing design command:', command);
    
    const result = executeDesignCommandSync(command);

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

async function executeDesignCommandFromServer(command: string, requestId?: string) {
  try {
    console.log('Executing design command from server:', command);
    
    const result = executeDesignCommandSync(command);

    // Send result back to UI with request ID for server forwarding
    figma.ui.postMessage({
      type: 'design_command_result',
      data: result,
      request_id: requestId
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error executing design command from server: ${errorMessage}`,
      request_id: requestId
    });
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
      connectionInfo: {
        connected: isConnected,
        serverUrl: serverUrl,
        pluginActive: isPluginActive
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
      rect.x = figma.viewport.center.x - 50;
      rect.y = figma.viewport.center.y - 50;
      figma.currentPage.appendChild(rect);
      figma.currentPage.selection = [rect];
      figma.viewport.scrollAndZoomIntoView([rect]);
      
      result = {
        message: 'Rectangle created successfully',
        command: command,
        created_node: {
          id: rect.id,
          name: rect.name,
          type: rect.type,
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height
        }
      };
    } else if (command.toLowerCase().includes('create circle')) {
      const ellipse = figma.createEllipse();
      ellipse.name = 'AI Created Circle';
      ellipse.resize(100, 100);
      ellipse.x = figma.viewport.center.x - 50;
      ellipse.y = figma.viewport.center.y - 50;
      figma.currentPage.appendChild(ellipse);
      figma.currentPage.selection = [ellipse];
      figma.viewport.scrollAndZoomIntoView([ellipse]);
      
      result = {
        message: 'Circle created successfully',
        command: command,
        created_node: {
          id: ellipse.id,
          name: ellipse.name,
          type: ellipse.type,
          x: ellipse.x,
          y: ellipse.y,
          width: ellipse.width,
          height: ellipse.height
        }
      };
    } else if (command.toLowerCase().includes('create text')) {
      const text = figma.createText();
      text.name = 'AI Created Text';
      text.characters = 'Hello from AI!';
      text.x = figma.viewport.center.x - 50;
      text.y = figma.viewport.center.y - 10;
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
          text: text.characters,
          x: text.x,
          y: text.y
        }
      };
    } else if (command.toLowerCase().includes('delete selected')) {
      const selection = figma.currentPage.selection;
      if (selection.length > 0) {
        const deletedNodes = selection.map(node => ({
          id: node.id,
          name: node.name,
          type: node.type
        }));
        
        selection.forEach(node => node.remove());
        figma.currentPage.selection = [];
        
        result = {
          message: `Deleted ${deletedNodes.length} selected node(s)`,
          command: command,
          deleted_nodes: deletedNodes
        };
      } else {
        result = {
          message: 'No nodes selected to delete',
          command: command,
          deleted_nodes: []
        };
      }
    } else if (command.toLowerCase().includes('select all')) {
      const allNodes = figma.currentPage.children;
      figma.currentPage.selection = allNodes;
      
      result = {
        message: `Selected ${allNodes.length} node(s)`,
        command: command,
        selected_count: allNodes.length
      };
    }

    return result;
  } catch (error) {
    throw new Error(`Error executing design command: ${error}`);
  }
}

function cleanup() {
  isPluginActive = false;
  isConnected = false;
}

// Cleanup on plugin close
figma.on('close', () => {
  cleanup();
});