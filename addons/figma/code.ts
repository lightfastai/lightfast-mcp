// Lightfast MCP Figma Plugin - WebSocket Server Version
// This file handles Figma API interactions and runs a WebSocket server for MCP communication
// Following the Blender pattern: Plugin acts as server, MCP server acts as client

// Plugin state
let isPluginActive = true;
let serverPort = 9003;
let isServerRunning = false;
let wsServer: any = null;
let mcpClients = new Map<string, any>();

// WebSocket server implementation using Figma's network capabilities
class FigmaWebSocketServer {
  private port: number;
  private isRunning: boolean = false;
  private clients: Map<string, any> = new Map();
  private nextClientId: number = 1;

  constructor(port: number) {
    this.port = port;
  }

  async start(): Promise<boolean> {
    try {
      this.isRunning = true;
      console.log(`🚀 Starting Figma WebSocket Server on port ${this.port}`);
      
      // Note: Figma plugins can't create actual WebSocket servers
      // This is a simulation that logs what would happen
      console.log(`📡 WebSocket server would start on port ${this.port}`);
      console.log('⚠️  Note: Figma plugins cannot create real WebSocket servers');
      console.log('💡 This is a simulation for development purposes');
      
      // Simulate server startup
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Notify UI that server is "running"
      figma.ui.postMessage({
        type: 'server_status',
        data: {
          status: 'WebSocket server simulation started',
          port: this.port,
          isRunning: true,
          note: 'This is a simulation - real WebSocket server not possible in Figma plugins'
        }
      });
      
      console.log(`✅ WebSocket server simulation started successfully`);
      console.log(`📡 Ready to simulate MCP client connections on port ${this.port}`);
      
      return true;
    } catch (error) {
      this.isRunning = false;
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Failed to start WebSocket server simulation: ${errorMessage}`);
      throw error;
    }
  }

  async stop(): Promise<void> {
    try {
      this.isRunning = false;
      
      // Close all simulated client connections
      for (const [clientId, client] of this.clients) {
        console.log(`Closing simulated client ${clientId}`);
      }
      this.clients.clear();
      
      // Notify UI that server is stopped
      figma.ui.postMessage({
        type: 'server_status',
        data: {
          status: 'WebSocket server simulation stopped',
          port: this.port,
          isRunning: false
        }
      });
      
      console.log('🛑 WebSocket server simulation stopped');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Error stopping WebSocket server simulation: ${errorMessage}`);
    }
  }

  // Simulate handling a new client connection
  simulateNewClient(): string {
    const clientId = `client_${this.nextClientId++}`;
    const client = {
      id: clientId,
      connectedAt: Date.now(),
      lastPing: Date.now()
    };
    
    this.clients.set(clientId, client);
    console.log(`📱 Simulated new MCP client connected: ${clientId}`);
    
    // Send simulated welcome message
    const welcomeMessage = {
      type: 'welcome',
      clientId: clientId,
      serverInfo: {
        name: 'Figma WebSocket Server (Simulation)',
        version: '1.0.0',
        capabilities: ['document_info', 'design_commands', 'ping']
      }
    };
    
    console.log(`📤 Sent simulated welcome to client ${clientId}:`, welcomeMessage);
    return clientId;
  }

  // Simulate handling a command from MCP client
  async simulateClientCommand(clientId: string, command: any): Promise<any> {
    try {
      console.log(`📨 Simulated command from client ${clientId}: ${command.type}`);
      
      // Update client last activity
      const client = this.clients.get(clientId);
      if (client) {
        client.lastPing = Date.now();
      }
      
      // Process the command using existing handlers
      const response = await this.processCommand(command);
      
      console.log(`📤 Sending simulated response to client ${clientId}:`, response);
      return response;
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Error processing simulated command from client ${clientId}:`, errorMessage);
      return {
        type: 'response',
        requestId: command.id || Date.now(),
        status: 'error',
        error: `Error processing command: ${errorMessage}`
      };
    }
  }

  // Process command using existing MCP command handlers
  async processCommand(command: any): Promise<any> {
    const requestId = command.id || Date.now();
    
    try {
      const result = handleMCPCommandInternal(command);
      return {
        type: 'response',
        requestId: requestId,
        status: 'success',
        result: result.result || result
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      return {
        type: 'response',
        requestId: requestId,
        status: 'error',
        error: errorMessage
      };
    }
  }

  // Get server stats
  getStats() {
    return {
      isRunning: this.isRunning,
      port: this.port,
      clientCount: this.clients.size,
      clients: Array.from(this.clients.values()).map(client => ({
        id: client.id,
        connectedAt: client.connectedAt,
        lastPing: client.lastPing
      }))
    };
  }
}

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
      status: 'Plugin loaded - ready to start WebSocket server',
      port: serverPort,
      active: isPluginActive,
      serverRunning: isServerRunning
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

        case 'start_websocket_server':
          await startWebSocketServer(msg.port || serverPort);
          break;

        case 'stop_websocket_server':
          await stopWebSocketServer();
          break;

        case 'test_websocket_server':
          await testWebSocketServer();
          break;

        case 'simulate_mcp_connection':
          await simulateMCPConnection();
          break;

        case 'mcp_command':
          await handleMCPCommand(msg.command, msg.requestId);
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

async function startWebSocketServer(port: number) {
  try {
    if (wsServer) {
      console.log('WebSocket server already running...');
      return;
    }

    serverPort = port;
    wsServer = new FigmaWebSocketServer(port);
    
    await wsServer.start();
    isServerRunning = true;
    
    // Notify UI
    figma.ui.postMessage({
      type: 'websocket_server_started',
      data: {
        status: 'WebSocket server simulation started',
        port: serverPort,
        serverRunning: isServerRunning
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error starting WebSocket server: ${errorMessage}`
    });
  }
}

async function stopWebSocketServer() {
  try {
    if (!wsServer) {
      console.log('No WebSocket server to stop...');
      return;
    }

    await wsServer.stop();
    wsServer = null;
    isServerRunning = false;
    
    // Notify UI
    figma.ui.postMessage({
      type: 'websocket_server_stopped',
      data: {
        status: 'WebSocket server simulation stopped',
        port: serverPort,
        serverRunning: isServerRunning
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error stopping WebSocket server: ${errorMessage}`
    });
  }
}

async function testWebSocketServer() {
  try {
    if (!wsServer || !isServerRunning) {
      figma.ui.postMessage({
        type: 'error',
        message: 'WebSocket server not running - start server first'
      });
      return;
    }
    
    // Get server stats
    const stats = wsServer.getStats();
    console.log('📊 Server Stats:', stats);
    
    // Simulate a test client connection and command
    const clientId = wsServer.simulateNewClient();
    
    // Simulate a ping command
    const testCommand = {
      type: 'ping',
      id: Date.now(),
      params: {}
    };
    
    const response = await wsServer.simulateClientCommand(clientId, testCommand);
    
    figma.ui.postMessage({
      type: 'websocket_test_result',
      data: {
        stats: stats,
        testCommand: testCommand,
        testResponse: response,
        message: 'WebSocket server test completed successfully'
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error testing WebSocket server: ${errorMessage}`
    });
  }
}

async function simulateMCPConnection() {
  try {
    if (!wsServer || !isServerRunning) {
      figma.ui.postMessage({
        type: 'error',
        message: 'WebSocket server not running - start server first'
      });
      return;
    }
    
    // Simulate MCP client connection
    const clientId = wsServer.simulateNewClient();
    
    // Simulate some MCP commands
    const commands = [
      { type: 'ping', id: Date.now() + 1 },
      { type: 'get_document_info', id: Date.now() + 2 },
      { type: 'execute_design_command', id: Date.now() + 3, params: { command: 'create rectangle' } }
    ];
    
    const results: Array<{command: any, response: any}> = [];
    for (const command of commands) {
      const response = await wsServer.simulateClientCommand(clientId, command);
      results.push({ command, response });
    }
    
    figma.ui.postMessage({
      type: 'mcp_simulation_result',
      data: {
        clientId: clientId,
        results: results,
        message: 'MCP connection simulation completed'
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error simulating MCP connection: ${errorMessage}`
    });
  }
}

async function handleMCPCommand(command: any, requestId?: number) {
  try {
    // Use the existing MCP command handler
    const response = handleMCPCommandInternal(command);
    
    // Send response back to UI
    figma.ui.postMessage({
      type: 'mcp_command_response',
      response: response,
      requestId: requestId
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    // Send error response back to UI
    figma.ui.postMessage({
      type: 'mcp_command_response',
      response: {
        status: 'error',
        message: errorMessage,
        timestamp: Date.now()
      },
      requestId: requestId
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
// These functions handle commands that come from the MCP server

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
            server: 'figma-plugin',
            serverRunning: isServerRunning,
            port: serverPort
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

      case 'get_server_status':
        return {
          status: 'success',
          result: {
            serverRunning: isServerRunning,
            port: serverPort,
            pluginActive: isPluginActive,
            timestamp: Date.now(),
            serverStats: wsServer ? wsServer.getStats() : null
          }
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
      serverInfo: {
        serverRunning: isServerRunning,
        port: serverPort,
        pluginActive: isPluginActive,
        serverStats: wsServer ? wsServer.getStats() : null
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
  isServerRunning = false;
  if (wsServer) {
    wsServer.stop();
    wsServer = null;
  }
}

// Cleanup on plugin close
figma.on('close', () => {
  cleanup();
});

// Export the MCP command handler for the UI to use
(globalThis as any).handleMCPCommand = handleMCPCommand;