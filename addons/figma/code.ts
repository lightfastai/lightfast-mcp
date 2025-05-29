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
      console.log('Plugin received message:', msg.type, 'Full message:', JSON.stringify(msg));
      
      switch (msg.type) {
        case 'ping':
          figma.ui.postMessage({ type: 'pong', timestamp: Date.now() });
          break;

        case 'get_document_info':
          await sendDocumentInfoForServer(msg.request_id);
          break;

        case 'get_document_info_for_server':
          await sendDocumentInfoForServer(msg.request_id);
          break;

        case 'execute_code':
          await executeCodeCommand(msg.code || '', msg.request_id);
          break;

        case 'test_code_execution':
          await testCodeExecution();
          break;

        case 'websocket_connected':
          isConnected = true;
          console.log('✅ WebSocket connected via UI:', msg.data);
          // Acknowledge the connection
          figma.ui.postMessage({
            type: 'websocket_connected',
            data: { status: 'acknowledged', connected: true }
          });
          break;

        case 'websocket_disconnected':
          isConnected = false;
          console.log('⚠️ WebSocket disconnected via UI:', msg.data);
          // Acknowledge the disconnection
          figma.ui.postMessage({
            type: 'websocket_disconnected',
            data: { status: 'acknowledged', connected: false }
          });
          break;

        case 'connection_test_result':
          console.log('🔧 Connection test result:', msg.data);
          break;

        case 'close-plugin':
          cleanup();
          figma.closePlugin();
          break;

        default:
          console.log(`⚠️ Unknown message type: ${msg.type}`);
          figma.ui.postMessage({
            type: 'error',
            message: `Unknown message type: ${msg.type}`,
            requestId: msg.requestId
          });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Error handling ${msg.type}:`, errorMessage);
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

async function executeCodeCommand(code: string, requestId?: string) {
  try {
    console.log('Executing JavaScript code:', code);
    
    const result = executeCodeSync(code);

    // Send result back to UI
    figma.ui.postMessage({
      type: 'code_execution_result',
      data: result,
      request_id: requestId
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error executing JavaScript code: ${errorMessage}`,
      request_id: requestId
    });
  }
}

async function testCodeExecution() {
  try {
    console.log('Testing code execution with sample JavaScript');
    
    // Execute a simple test code that creates a rectangle
    const testCode = `
      const rect = figma.createRectangle();
      rect.name = 'Test Rectangle from Code';
      rect.resize(100, 50);
      rect.x = figma.viewport.center.x - 50;
      rect.y = figma.viewport.center.y - 25;
      rect.fills = [{type: 'SOLID', color: {r: 0.2, g: 0.7, b: 1.0}}];
      figma.currentPage.appendChild(rect);
      figma.currentPage.selection = [rect];
      figma.viewport.scrollAndZoomIntoView([rect]);
      console.log('Test rectangle created successfully');
      result = 'Test rectangle created successfully';
    `;
    
    const result = executeCodeSync(testCode);

    // Send result back to UI
    figma.ui.postMessage({
      type: 'code_execution_result',
      data: result
    });

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error in test code execution: ${errorMessage}`
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

function executeCodeSync(code: string): any {
  try {
    console.log('Executing JavaScript code synchronously:', code);
    
    // Capture console output
    let output: string[] = [];
    const originalLog = console.log;
    console.log = (...args: any[]) => {
      output.push(args.join(' '));
      originalLog(...args);
    };
    
    let result: any = undefined;
    let executed = true;
    let error: string | undefined = undefined;
    
    try {
      // Execute code directly in the main context
      // This is necessary for Figma API calls to work properly
      eval(code);
      
      // If code sets a result variable, use it
      if (typeof result !== 'undefined') {
        return {
          code_executed: true,
          original_code: code,
          execution_result: { 
            executed: true, 
            result: result, 
            output: output.join('\n') || 'Code executed successfully' 
          },
          timestamp: Date.now()
        };
      }
      
      return {
        code_executed: true,
        original_code: code,
        execution_result: { 
          executed: true, 
          result: 'Code executed successfully', 
          output: output.join('\n') || 'No output' 
        },
        timestamp: Date.now()
      };
      
    } catch (execError) {
      executed = false;
      error = execError instanceof Error ? execError.message : String(execError);
      
      return {
        code_executed: false,
        original_code: code,
        execution_result: { 
          executed: false, 
          error: error, 
          output: output.join('\n') 
        },
        timestamp: Date.now()
      };
      
    } finally {
      console.log = originalLog;
    }
    
  } catch (error) {
    console.error('Code execution error:', error);
    return {
      code_executed: false,
      original_code: code,
      error: error instanceof Error ? error.message : String(error),
      timestamp: Date.now()
    };
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