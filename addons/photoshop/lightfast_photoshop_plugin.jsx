// Lightfast MCP Plugin for Photoshop
// Created by Lightfast Team © 2025

// Socket server implementation
var SOCKET_PORT = 8765;
var SOCKET_HOST = "127.0.0.1";
var server = null;
var isServerRunning = false;

// Photoshop connection status
var isConnected = false;

// CEP includes
#include "json2.js"

function startServer() {
    if (isServerRunning) {
        alert("Server is already running.");
        return false;
    }
    
    try {
        // Create a socket server
        server = new Socket();
        
        // Configure the server socket
        server.timeout = 10000; // 10 seconds timeout
        
        // Attempt to listen on the specified port
        if (!server.listen(SOCKET_PORT, SOCKET_HOST)) {
            alert("Failed to start server: " + server.error);
            server.close();
            return false;
        }
        
        isServerRunning = true;
        logMessage("Lightfast MCP Server started on " + SOCKET_HOST + ":" + SOCKET_PORT);
        
        // Start the server loop
        startServerLoop();
        return true;
    } catch(e) {
        alert("Error starting server: " + e.toString());
        if (server) {
            server.close();
            server = null;
        }
        isServerRunning = false;
        return false;
    }
}

function stopServer() {
    if (!isServerRunning) {
        alert("Server is not running.");
        return false;
    }
    
    try {
        if (server) {
            server.close();
            server = null;
        }
        isServerRunning = false;
        logMessage("Lightfast MCP Server stopped.");
        return true;
    } catch(e) {
        alert("Error stopping server: " + e.toString());
        return false;
    }
}

function startServerLoop() {
    // This will be executed in a loop to handle client connections
    if (!isServerRunning || !server) {
        return;
    }
    
    // Check for incoming connections
    if (server.connected) {
        isConnected = true;
        
        // Handle the connection
        handleClient(server);
    } else {
        // Wait for a connection
        if (server.listen(SOCKET_PORT, SOCKET_HOST)) {
            // Continue waiting
            $.sleep(100); // Sleep for 100ms to prevent high CPU usage
            startServerLoop();
        } else {
            // Error occurred
            logMessage("Error in server loop: " + server.error);
            stopServer();
        }
    }
}

function handleClient(client) {
    logMessage("Client connected");
    
    try {
        // Read data from client
        var buffer = "";
        
        // Keep reading until the client disconnects
        while (client.connected) {
            // Read available data
            var data = client.read();
            if (data && data.length > 0) {
                buffer += data;
                
                // Try to parse the data as JSON
                try {
                    var command = JSON.parse(buffer);
                    buffer = ""; // Clear the buffer after successful parse
                    
                    // Process the command
                    var response = executeCommand(command);
                    
                    // Send the response
                    var responseJson = JSON.stringify(response);
                    client.write(responseJson);
                    logMessage("Response sent: " + responseJson.substring(0, 100) + (responseJson.length > 100 ? "..." : ""));
                } catch(e) {
                    // Not a valid JSON yet, continue reading
                    if (buffer.length > 65536) {
                        // Buffer too large, discard it
                        logMessage("Buffer too large, discarding.");
                        buffer = "";
                    }
                }
            } else {
                // No data available, sleep a bit
                $.sleep(100);
            }
        }
    } catch(e) {
        logMessage("Error handling client: " + e.toString());
    } finally {
        // Close the client connection
        client.close();
        isConnected = false;
        
        // Restart the server loop
        startServerLoop();
    }
}

function executeCommand(command) {
    try {
        var cmdType = command.type;
        var params = command.params || {};
        
        logMessage("Executing command: " + cmdType);
        
        // Command handlers
        if (cmdType === "ping") {
            return {
                status: "success",
                result: {
                    message: "pong",
                    timestamp: new Date().getTime()
                }
            };
        } else if (cmdType === "get_document_info") {
            return {
                status: "success",
                result: getDocumentInfo()
            };
        } else if (cmdType === "execute_jsx") {
            if (!params.code) {
                return {
                    status: "error",
                    message: "No code provided for execution"
                };
            }
            
            return {
                status: "success",
                result: executeJSX(params.code)
            };
        } else {
            return {
                status: "error",
                message: "Unknown command type: " + cmdType
            };
        }
    } catch(e) {
        logMessage("Error executing command: " + e.toString());
        return {
            status: "error",
            message: e.toString()
        };
    }
}

function getDocumentInfo() {
    try {
        // Check if a document is open
        if (!app.documents.length) {
            return {
                error: "No document open"
            };
        }
        
        var doc = app.activeDocument;
        var info = {
            name: doc.name,
            width: doc.width.value,
            height: doc.height.value,
            resolution: doc.resolution,
            mode: getDocumentMode(doc),
            layers: getLayersInfo(doc),
            path: doc.path !== null ? doc.path.fsName : "",
            fileSize: 0 // Placeholder, difficult to get accurate file size in JSX
        };
        
        return info;
    } catch(e) {
        return {
            error: "Error getting document info: " + e.toString()
        };
    }
}

function getDocumentMode(doc) {
    switch (doc.mode) {
        case DocumentMode.RGB:
            return "RGB";
        case DocumentMode.CMYK:
            return "CMYK";
        case DocumentMode.GRAYSCALE:
            return "Grayscale";
        case DocumentMode.BITMAP:
            return "Bitmap";
        case DocumentMode.INDEXEDCOLOR:
            return "Indexed";
        case DocumentMode.MULTICHANNEL:
            return "Multichannel";
        case DocumentMode.DUOTONE:
            return "Duotone";
        case DocumentMode.LAB:
            return "Lab";
        default:
            return "Unknown";
    }
}

function getLayersInfo(doc) {
    var layers = [];
    
    try {
        // Get a limited number of top-level layers
        var maxLayers = 20; // Limit to 20 layers to prevent large responses
        var layerCount = Math.min(doc.artLayers.length, maxLayers);
        
        for (var i = 0; i < layerCount; i++) {
            var layer = doc.artLayers[i];
            layers.push({
                name: layer.name,
                visible: layer.visible,
                locked: layer.locked,
                type: getLayerType(layer)
            });
        }
        
        if (doc.artLayers.length > maxLayers) {
            layers.push({
                name: "... and " + (doc.artLayers.length - maxLayers) + " more layers",
                type: "info"
            });
        }
    } catch(e) {
        logMessage("Error getting layers info: " + e.toString());
    }
    
    return layers;
}

function getLayerType(layer) {
    switch (layer.kind) {
        case LayerKind.NORMAL:
            return "normal";
        case LayerKind.TEXT:
            return "text";
        case LayerKind.SOLIDFILL:
            return "solid fill";
        case LayerKind.GRADIENTFILL:
            return "gradient fill";
        case LayerKind.PATTERNFILL:
            return "pattern fill";
        case LayerKind.SMARTOBJECT:
            return "smart object";
        case LayerKind.ADJUSTMENT:
            return "adjustment";
        default:
            return "unknown";
    }
}

function executeJSX(code) {
    try {
        // Execute the provided JSX code
        var result = eval(code);
        
        // Return the result
        return {
            executed: true,
            result: result !== undefined ? result.toString() : "No output."
        };
    } catch(e) {
        return {
            executed: false,
            error: e.toString()
        };
    }
}

function logMessage(message) {
    // In a real plugin, you'd log to a file or console
    $.writeln("Lightfast MCP: " + message);
}

// Export the functions for CEP panel
function getServerStatus() {
    return {
        isRunning: isServerRunning,
        isConnected: isConnected,
        port: SOCKET_PORT,
        host: SOCKET_HOST
    };
}

function setServerPort(port) {
    if (!isServerRunning) {
        SOCKET_PORT = parseInt(port, 10);
        return true;
    }
    return false;
}

// Module exports for CEP
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        startServer: startServer,
        stopServer: stopServer,
        getServerStatus: getServerStatus,
        setServerPort: setServerPort
    };
} 