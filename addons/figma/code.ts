// Lightfast MCP Figma Plugin - WebSocket Client Version
// This file handles Figma API interactions and connects as a WebSocket client to the MCP server
// Following the new architecture: MCP server acts as WebSocket server, plugin acts as client

// Plugin state
let isPluginActive = true;
let serverUrl = "ws://localhost:9003";
let isConnected = false;
let wsClient: WebSocket | null = null;
let reconnectAttempts = 0;
let maxReconnectAttempts = 5;
let reconnectDelay = 2000; // 2 seconds

// WebSocket client implementation
class FigmaWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 2000;

  constructor(url: string) {
    this.url = url;
  }

  async connect(): Promise<boolean> {
    try {
      console.log(`🔌 Connecting to MCP server at ${this.url}`);
      
      // Note: Figma plugins have limited WebSocket support
      // This is a simulation of what would happen with real WebSocket support
      console.log(`📡 Would connect to WebSocket server at ${this.url}`);
      console.log('⚠️  Note: Figma plugins have limited WebSocket client capabilities');
      console.log('💡 This is a simulation for development purposes');
      
      // Simulate connection
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.isConnected = true;
      this.reconnectAttempts = 0;
      
      // Notify UI that client is "connected"
      figma.ui.postMessage({
        type: 'connection_status',
        data: {
          status: 'WebSocket client simulation connected',
          url: this.url,
          isConnected: true,
          note: 'This is a simulation - real WebSocket client not fully supported in Figma plugins'
        }
      });
      
      console.log(`✅ WebSocket client simulation connected successfully`);
      console.log(`📡 Ready to simulate communication with MCP server`);
      
      // Simulate sending plugin info to server
      this.simulateSendMessage({
        type: 'plugin_info',
        plugin_info: {
          name: 'Lightfast MCP Figma Plugin',
          version: '1.0.0',
          capabilities: ['document_info', 'design_commands']
        }
      });
      
      return true;
    } catch (error) {
      this.isConnected = false;
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Failed to connect to MCP server: ${errorMessage}`);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    try {
      this.isConnected = false;
      
      // Notify UI that client is disconnected
      figma.ui.postMessage({
        type: 'connection_status',
        data: {
          status: 'WebSocket client simulation disconnected',
          url: this.url,
          isConnected: false
        }
      });
      
      console.log('🔌 WebSocket client simulation disconnected');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Error disconnecting from MCP server: ${errorMessage}`);
    }
  }

  // Simulate sending a message to the MCP server
  simulateSendMessage(message: any): void {
    if (!this.isConnected) {
      console.error('❌ Cannot send message - not connected to MCP server');
      return;
    }
    
    console.log(`📤 Simulated sending message to MCP server:`, message);
    
    // Simulate server response based on message type
    setTimeout(() => {
      this.simulateServerResponse(message);
    }, 100);
  }

  // Simulate receiving a response from the MCP server
  simulateServerResponse(originalMessage: any): void {
    let response: any;
    
    switch (originalMessage.type) {
      case 'plugin_info':
        response = {
          type: 'plugin_info_received',
          timestamp: Date.now()
        };
        break;
        
      case 'document_update':
        response = {
          type: 'document_update_received',
          timestamp: Date.now()
        };
        break;
        
      default:
        response = {
          type: 'message_received',
          original_type: originalMessage.type,
          timestamp: Date.now()
        };
    }
    
    console.log(`📨 Simulated response from MCP server:`, response);
    
    // Process the simulated response
    this.handleServerMessage(response);
  }

  // Simulate receiving a command from the MCP server
  simulateServerCommand(command: any): void {
    console.log(`📨 Simulated command from MCP server:`, command);
    this.handleServerMessage(command);
  }

  // Handle messages/commands from the MCP server
  handleServerMessage(message: any): void {
    try {
      switch (message.type) {
        case 'welcome':
          console.log('🎉 Received welcome from MCP server');
          break;
          
        case 'ping':
          // Respond to ping
          this.simulateSendMessage({
            type: 'pong',
            timestamp: Date.now()
          });
          break;
          
        case 'get_document_info':
          // Send current document info
          const documentInfo = getCurrentDocumentInfo();
          this.simulateSendMessage({
            type: 'document_info_response',
            request_id: message.request_id,
            document_info: documentInfo
          });
          break;
          
        case 'execute_design_command':
          // Execute the design command
          const result = executeDesignCommandSync(message.command || message.params?.command || '');
          this.simulateSendMessage({
            type: 'design_command_response',
            request_id: message.request_id,
            result: result
          });
          break;
          
        default:
          console.log(`📋 Unhandled message type from MCP server: ${message.type}`);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Error handling server message: ${errorMessage}`);
    }
  }

  // Get connection stats
  getStats() {
    return {
      isConnected: this.isConnected,
      url: this.url,
      reconnectAttempts: this.reconnectAttempts,
      maxReconnectAttempts: this.maxReconnectAttempts
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

        case 'execute_design_command':
          await executeDesignCommand(msg.command || '');
          break;

        case 'connect_to_server':
          await connectToMCPServer(msg.url || serverUrl);
          break;

        case 'disconnect_from_server':
          await disconnectFromMCPServer();
          break;

        case 'test_connection':
          await testConnection();
          break;

        case 'simulate_server_command':
          await simulateServerCommand(msg.command);
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

async function connectToMCPServer(url: string) {
  try {
    if (wsClient) {
      console.log('WebSocket client already exists...');
      return;
    }

    serverUrl = url;
    wsClient = new FigmaWebSocketClient(url);
    
    await wsClient.connect();
    isConnected = true;
    
    // Notify UI
    figma.ui.postMessage({
      type: 'websocket_connected',
      data: {
        status: 'WebSocket client simulation connected',
        url: serverUrl,
        connected: isConnected
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error connecting to MCP server: ${errorMessage}`
    });
  }
}

async function disconnectFromMCPServer() {
  try {
    if (!wsClient) {
      console.log('No WebSocket client to disconnect...');
      return;
    }

    await wsClient.disconnect();
    wsClient = null;
    isConnected = false;
    
    // Notify UI
    figma.ui.postMessage({
      type: 'websocket_disconnected',
      data: {
        status: 'WebSocket client simulation disconnected',
        url: serverUrl,
        connected: isConnected
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error disconnecting from MCP server: ${errorMessage}`
    });
  }
}

async function testConnection() {
  try {
    if (!wsClient || !isConnected) {
      figma.ui.postMessage({
        type: 'error',
        message: 'Not connected to MCP server - connect first'
      });
      return;
    }
    
    // Get connection stats
    const stats = wsClient.getStats();
    console.log('📊 Connection Stats:', stats);
    
    // Simulate a test ping
    wsClient.simulateSendMessage({
      type: 'ping',
      timestamp: Date.now()
    });
    
    figma.ui.postMessage({
      type: 'connection_test_result',
      data: {
        stats: stats,
        message: 'Connection test completed successfully'
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error testing connection: ${errorMessage}`
    });
  }
}

async function simulateServerCommand(command: any) {
  try {
    if (!wsClient || !isConnected) {
      figma.ui.postMessage({
        type: 'error',
        message: 'Not connected to MCP server - connect first'
      });
      return;
    }
    
    // Simulate receiving a command from the MCP server
    wsClient.simulateServerCommand(command);
    
    figma.ui.postMessage({
      type: 'server_command_simulated',
      data: {
        command: command,
        message: 'Server command simulation completed'
      }
    });
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'error',
      message: `Error simulating server command: ${errorMessage}`
    });
  }
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

    // Also send to MCP server if connected
    if (wsClient && isConnected) {
      wsClient.simulateSendMessage({
        type: 'document_update',
        document_info: documentInfo
      });
    }

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
    
    const result = executeDesignCommandSync(command);

    // Send result back to UI
    figma.ui.postMessage({
      type: 'design_command_result',
      data: result
    });

    // Also send result to MCP server if connected
    if (wsClient && isConnected) {
      wsClient.simulateSendMessage({
        type: 'design_command_result',
        command: command,
        result: result
      });
    }

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    figma.ui.postMessage({
      type: 'error',
      message: `Error executing design command: ${errorMessage}`
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
        pluginActive: isPluginActive,
        connectionStats: wsClient ? wsClient.getStats() : null
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
  isConnected = false;
  if (wsClient) {
    wsClient.disconnect();
    wsClient = null;
  }
}

// Cleanup on plugin close
figma.on('close', () => {
  cleanup();
});