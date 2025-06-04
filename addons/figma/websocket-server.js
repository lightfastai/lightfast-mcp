#!/usr/bin/env node

/**
 * WebSocket Server for Figma Plugin Testing
 * 
 * This is a standalone WebSocket server that simulates the Figma plugin
 * WebSocket server for testing the MCP server WebSocket client functionality.
 * 
 * Usage: node websocket-server.js [port]
 */

const WebSocket = require('ws');
const port = process.argv[2] || 9003;

console.log(`🚀 Starting Figma Plugin WebSocket Server on port ${port}`);

const wss = new WebSocket.Server({ port: port });

// Simulated Figma document state
const mockDocumentState = {
    document: {
        name: "Test Document",
        id: "doc_123",
        type: "DOCUMENT"
    },
    currentPage: {
        name: "Page 1",
        id: "page_456",
        children: 3,
        selection: 1
    },
    selection: [
        {
            id: "node_789",
            name: "Rectangle 1",
            type: "RECTANGLE",
            visible: true,
            locked: false
        }
    ],
    viewport: {
        center: { x: 0, y: 0 },
        zoom: 1.0
    },
    serverInfo: {
        serverRunning: true,
        port: port,
        pluginActive: true
    },
    timestamp: Date.now()
};

wss.on('connection', function connection(ws, req) {
    const clientId = Math.floor(Math.random() * 10000);
    console.log(`📱 New MCP client connected: ${clientId} from ${req.socket.remoteAddress}`);

    // Send welcome message
    const welcomeMessage = {
        type: 'welcome',
        clientId: clientId,
        serverInfo: {
            name: 'Figma WebSocket Server (Test)',
            version: '1.0.0',
            capabilities: ['document_info', 'design_commands', 'ping']
        }
    };
    
    ws.send(JSON.stringify(welcomeMessage));
    console.log(`📤 Sent welcome to client ${clientId}`);

    ws.on('message', function message(data) {
        try {
            const command = JSON.parse(data.toString());
            console.log(`📨 Received from client ${clientId}: ${command.type}`);
            
            // Process the command
            const response = processCommand(command);
            
            // Send response
            ws.send(JSON.stringify(response));
            console.log(`📤 Sent response to client ${clientId}: ${response.type}`);
            
        } catch (error) {
            console.error(`❌ Error processing message from client ${clientId}:`, error.message);
            
            const errorResponse = {
                type: 'response',
                requestId: Date.now(),
                status: 'error',
                error: `Invalid message format: ${error.message}`
            };
            
            ws.send(JSON.stringify(errorResponse));
        }
    });

    ws.on('close', function close() {
        console.log(`📱 Client ${clientId} disconnected`);
    });

    ws.on('error', function error(err) {
        console.error(`❌ WebSocket error for client ${clientId}:`, err.message);
    });
});

function processCommand(command) {
    const requestId = command.id || Date.now();
    
    try {
        switch (command.type) {
            case 'ping':
                return {
                    type: 'response',
                    requestId: requestId,
                    status: 'success',
                    result: {
                        message: 'pong',
                        timestamp: Date.now(),
                        server: 'figma-plugin-test',
                        serverRunning: true,
                        port: port
                    }
                };

            case 'get_document_info':
                return {
                    type: 'response',
                    requestId: requestId,
                    status: 'success',
                    result: mockDocumentState
                };

            case 'execute_design_command':
                const designCommand = command.params?.command || '';
                console.log(`🎨 Executing design command: ${designCommand}`);
                
                let result = { 
                    message: 'Command received but not implemented', 
                    command: designCommand 
                };
                
                if (designCommand.toLowerCase().includes('create rectangle')) {
                    result = {
                        message: 'Rectangle created successfully',
                        command: designCommand,
                        created_node: {
                            id: `rect_${Date.now()}`,
                            name: 'AI Created Rectangle',
                            type: 'RECTANGLE'
                        }
                    };
                } else if (designCommand.toLowerCase().includes('create circle')) {
                    result = {
                        message: 'Circle created successfully',
                        command: designCommand,
                        created_node: {
                            id: `circle_${Date.now()}`,
                            name: 'AI Created Circle',
                            type: 'ELLIPSE'
                        }
                    };
                } else if (designCommand.toLowerCase().includes('create text')) {
                    result = {
                        message: 'Text created successfully',
                        command: designCommand,
                        created_node: {
                            id: `text_${Date.now()}`,
                            name: 'AI Created Text',
                            type: 'TEXT',
                            text: 'Hello from AI!'
                        }
                    };
                }
                
                return {
                    type: 'response',
                    requestId: requestId,
                    status: 'success',
                    result: result
                };

            case 'get_server_status':
                return {
                    type: 'response',
                    requestId: requestId,
                    status: 'success',
                    result: {
                        serverRunning: true,
                        port: port,
                        pluginActive: true,
                        timestamp: Date.now()
                    }
                };

            default:
                return {
                    type: 'response',
                    requestId: requestId,
                    status: 'error',
                    error: `Unknown command type: ${command.type}`
                };
        }
    } catch (error) {
        return {
            type: 'response',
            requestId: requestId,
            status: 'error',
            error: error.message
        };
    }
}

wss.on('listening', () => {
    console.log(`✅ Figma Plugin WebSocket Server started successfully`);
    console.log(`📡 Listening for MCP client connections on port ${port}`);
    console.log(`🔗 WebSocket URL: ws://localhost:${port}`);
    console.log(`\n💡 To test with MCP server, run:`);
    console.log(`   uv run lightfast-figma-server`);
    console.log(`\n🛑 Press Ctrl+C to stop the server`);
});

wss.on('error', (error) => {
    console.error(`❌ Failed to start WebSocket server:`, error.message);
    process.exit(1);
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log(`\n🛑 Shutting down WebSocket server...`);
    wss.close(() => {
        console.log(`✅ WebSocket server stopped`);
        process.exit(0);
    });
});

process.on('SIGTERM', () => {
    console.log(`\n🛑 Shutting down WebSocket server...`);
    wss.close(() => {
        console.log(`✅ WebSocket server stopped`);
        process.exit(0);
    });
}); 