// Lightfast MCP Figma Plugin - UI-WebSocket Version
// This file handles Figma API interactions and communicates with UI via messaging

// Plugin state
let isPluginActive = true;

// Runs this code if the plugin is run in Figma
if (figma.editorType === 'figma') {
  // Show the HTML UI
  figma.showUI(__html__, { 
    width: 320, 
    height: 450,
    themeColors: true 
  });

  // Send initial document info to UI
  sendDocumentInfoToUI();

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

function cleanup() {
  isPluginActive = false;
}

// Cleanup on plugin close
figma.on('close', () => {
  cleanup();
});