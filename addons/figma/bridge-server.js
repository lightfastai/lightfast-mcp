#!/usr/bin/env node

/**
 * Figma MCP Bridge Server
 * 
 * This Node.js server acts as a bridge between the MCP server and Figma plugin:
 * 1. Listens on a socket for MCP server connections (like Blender addon)
 * 2. Communicates with Figma plugin via HTTP/WebSocket
 * 3. Forwards commands and responses between them
 */

const net = require('net');
const http = require('http');
const WebSocket = require('ws');

const SOCKET_PORT = 9003; // Port for MCP server to connect to
const HTTP_PORT = 9004;   // Port for Figma plugin to connect to
const WS_PORT = 9005;     // WebSocket port for Figma plugin

class FigmaMCPBridge {
    constructor() {
        this.socketServer = null;
        this.httpServer = null;
        this.wsServer = null;
        this.mcpClients = new Set();
        this.figmaClients = new Set();
        this.isRunning = false;
    }

    async start() {
        try {
            await this.startSocketServer();
            await this.startHttpServer();
            await this.startWebSocketServer();
            this.isRunning = true;
            console.log('🚀 Figma MCP Bridge Server started successfully');
            console.log(`📡 MCP Socket Server: localhost:${SOCKET_PORT}`);
            console.log(`🌐 HTTP Server: http://localhost:${HTTP_PORT}`);
            console.log(`🔌 WebSocket Server: ws://localhost:${WS_PORT}`);
        } catch (error) {
            console.error('❌ Failed to start bridge server:', error);
            throw error;
        }
    }

    async startSocketServer() {
        return new Promise((resolve, reject) => {
            this.socketServer = net.createServer((socket) => {
                console.log('🔗 MCP server connected');
                this.mcpClients.add(socket);

                socket.on('data', (data) => {
                    try {
                        const command = JSON.parse(data.toString());
                        console.log('📨 Received command from MCP:', command.type);
                        this.forwardToFigma(command, socket);
                    } catch (error) {
                        console.error('❌ Error parsing MCP command:', error);
                        this.sendErrorToMCP(socket, 'Invalid JSON command');
                    }
                });

                socket.on('close', () => {
                    console.log('🔌 MCP server disconnected');
                    this.mcpClients.delete(socket);
                });

                socket.on('error', (error) => {
                    console.error('❌ MCP socket error:', error);
                    this.mcpClients.delete(socket);
                });
            });

            this.socketServer.listen(SOCKET_PORT, '127.0.0.1', () => {
                console.log(`✅ Socket server listening on 127.0.0.1:${SOCKET_PORT}`);
                resolve();
            });

            this.socketServer.on('error', reject);
        });
    }

    async startHttpServer() {
        return new Promise((resolve, reject) => {
            this.httpServer = http.createServer((req, res) => {
                // Enable CORS
                res.setHeader('Access-Control-Allow-Origin', '*');
                res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
                res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

                if (req.method === 'OPTIONS') {
                    res.writeHead(200);
                    res.end();
                    return;
                }

                if (req.method === 'POST' && req.url === '/command') {
                    let body = '';
                    req.on('data', chunk => body += chunk);
                    req.on('end', () => {
                        try {
                            const response = JSON.parse(body);
                            console.log('📤 Received response from Figma:', response);
                            this.forwardToMCP(response);
                            res.writeHead(200, { 'Content-Type': 'application/json' });
                            res.end(JSON.stringify({ status: 'ok' }));
                        } catch (error) {
                            console.error('❌ Error processing Figma response:', error);
                            res.writeHead(400);
                            res.end(JSON.stringify({ error: 'Invalid JSON' }));
                        }
                    });
                } else if (req.method === 'GET' && req.url === '/status') {
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        status: 'running',
                        mcpClients: this.mcpClients.size,
                        figmaClients: this.figmaClients.size,
                        ports: {
                            socket: SOCKET_PORT,
                            http: HTTP_PORT,
                            websocket: WS_PORT
                        }
                    }));
                } else {
                    res.writeHead(404);
                    res.end('Not found');
                }
            });

                         this.httpServer.listen(HTTP_PORT, '127.0.0.1', () => {
                 console.log(`✅ HTTP server listening on 127.0.0.1:${HTTP_PORT}`);
                 resolve();
             });

            this.httpServer.on('error', reject);
        });
    }

    async startWebSocketServer() {
        return new Promise((resolve, reject) => {
            this.wsServer = new WebSocket.Server({ port: WS_PORT });

            this.wsServer.on('connection', (ws) => {
                console.log('🔗 Figma plugin connected via WebSocket');
                this.figmaClients.add(ws);

                ws.on('message', (data) => {
                    try {
                        const response = JSON.parse(data.toString());
                        console.log('📤 Received response from Figma via WS:', response);
                        this.forwardToMCP(response);
                    } catch (error) {
                        console.error('❌ Error parsing Figma response:', error);
                    }
                });

                ws.on('close', () => {
                    console.log('🔌 Figma plugin disconnected');
                    this.figmaClients.delete(ws);
                });

                ws.on('error', (error) => {
                    console.error('❌ Figma WebSocket error:', error);
                    this.figmaClients.delete(ws);
                });
            });

            console.log(`✅ WebSocket server listening on localhost:${WS_PORT}`);
            resolve();
        });
    }

    forwardToFigma(command, mcpSocket) {
        // Store the MCP socket for response routing
        command._mcpSocket = mcpSocket;

        // Try WebSocket first
        if (this.figmaClients.size > 0) {
            const figmaClient = Array.from(this.figmaClients)[0];
            if (figmaClient.readyState === WebSocket.OPEN) {
                figmaClient.send(JSON.stringify(command));
                return;
            }
        }

        // If no WebSocket clients, send error back to MCP
        this.sendErrorToMCP(mcpSocket, 'No Figma plugin connected');
    }

    forwardToMCP(response) {
        // Find the original MCP socket (this is simplified - in production you'd want proper request/response matching)
        if (this.mcpClients.size > 0) {
            const mcpClient = Array.from(this.mcpClients)[0];
            try {
                mcpClient.write(JSON.stringify(response));
            } catch (error) {
                console.error('❌ Error sending response to MCP:', error);
            }
        }
    }

    sendErrorToMCP(socket, message) {
        const errorResponse = {
            status: 'error',
            message: message,
            timestamp: Date.now()
        };
        try {
            socket.write(JSON.stringify(errorResponse));
        } catch (error) {
            console.error('❌ Error sending error to MCP:', error);
        }
    }

    async stop() {
        console.log('🛑 Stopping Figma MCP Bridge Server...');
        
        if (this.socketServer) {
            this.socketServer.close();
        }
        if (this.httpServer) {
            this.httpServer.close();
        }
        if (this.wsServer) {
            this.wsServer.close();
        }

        this.mcpClients.clear();
        this.figmaClients.clear();
        this.isRunning = false;
        
        console.log('✅ Bridge server stopped');
    }
}

// CLI interface
if (require.main === module) {
    const bridge = new FigmaMCPBridge();

    process.on('SIGINT', async () => {
        console.log('\n🛑 Received SIGINT, shutting down gracefully...');
        await bridge.stop();
        process.exit(0);
    });

    process.on('SIGTERM', async () => {
        console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
        await bridge.stop();
        process.exit(0);
    });

    bridge.start().catch((error) => {
        console.error('❌ Failed to start bridge server:', error);
        process.exit(1);
    });
}

module.exports = FigmaMCPBridge; 