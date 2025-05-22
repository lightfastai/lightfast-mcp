/**
 * Lightfast MCP Plugin for Photoshop
 * JavaScript for UXP Panel
 */

// Plugin state
let isServerRunning = false;
let isClientConnected = false;
let wsPort = 8765;
let wsHost = "localhost";
let socket = null;

// Initialize the extension
function init() {
    // Register event listeners
    document.getElementById('startServer').addEventListener('click', connectToServer);
    document.getElementById('stopServer').addEventListener('click', disconnectFromServer);
    document.getElementById('port').addEventListener('change', updatePort);
    
    // Register shape creation buttons
    document.getElementById('addRectangle').addEventListener('click', createRectangle);
    document.getElementById('addCircle').addEventListener('click', createCircle);
    
    // Update status periodically
    setInterval(updateStatus, 2000);
    
    // Initial status update
    updateStatus();
    
    // Add initial log message
    addToLog('Plugin initialized successfully');
}

// Connect to the Python WebSocket server
function connectToServer() {
    if (isClientConnected) {
        addToLog('Already connected to server', 'error');
        return;
    }
    
    const wsUrl = `ws://${wsHost}:${wsPort}`;
    addToLog(`Attempting to connect to server at ${wsUrl}...`);
    
    try {
        // Create WebSocket connection
        socket = new WebSocket(wsUrl);
        
        // Connection opened
        socket.addEventListener('open', (event) => {
            isClientConnected = true;
            addToLog(`Connected to server at ${wsUrl}`, 'success');
            updateButtonState(true);
            updateStatus();
            
            // Send a ping to verify connection
            sendCommand('ping', {});
        });
        
        // Listen for messages
        socket.addEventListener('message', (event) => {
            try {
                const message = JSON.parse(event.data);
                handleServerMessage(message);

                // Check if this message is a command to execute code from the server
                if (message.command_id && (message.type === 'execute_photoshop_code_cmd' || message.type === 'execute_jsx')) {
                    const scriptToExecute = message.params?.script || message.params?.code;
                    const commandId = message.command_id;
                    const commandType = message.type;

                    if (scriptToExecute) {
                        addToLog(`Received ${commandType} command (ID: ${commandId}) from server. Executing script...`);
                        executeScriptFromMCP(scriptToExecute, commandId);
                    } else {
                        addToLog(`Received ${commandType} command (ID: ${commandId}) but no script was provided.`, 'error');
                        sendScriptResultToMCP(commandId, null, 'No script provided in command');
                    }
                }
            } catch (err) {
                addToLog(`Error parsing message or initial handling: ${err.message}`, 'error');
                if (message && message.command_id) {
                    // If we know the command_id, try to send an error back
                    sendScriptResultToMCP(message.command_id, null, `Error parsing message: ${err.message}`);
                }
            }
        });
        
        // Listen for connection close
        socket.addEventListener('close', (event) => {
            isClientConnected = false;
            addToLog(`Disconnected from server: ${event.reason || 'Connection closed'}`, event.wasClean ? 'info' : 'error');
            updateButtonState(false);
            updateStatus();
            socket = null;
        });
        
        // Connection error
        socket.addEventListener('error', (event) => {
            addToLog('Connection error', 'error');
            if (socket) {
                socket.close();
            }
            isClientConnected = false;
            updateButtonState(false);
            updateStatus();
            socket = null;
        });
        
    } catch (err) {
        addToLog(`Failed to connect: ${err.message}`, 'error');
        isClientConnected = false;
        updateButtonState(false);
        updateStatus();
    }
}

// Disconnect from the Python WebSocket server
function disconnectFromServer() {
    if (!isClientConnected || !socket) {
        addToLog('Not connected to server', 'error');
        return;
    }
    
    try {
        socket.close();
        addToLog('Disconnected from server', 'success');
    } catch (err) {
        addToLog(`Error disconnecting: ${err.message}`, 'error');
    }
    
    isClientConnected = false;
    updateButtonState(false);
    updateStatus();
    socket = null;
}

// Send a command to the Python WebSocket server
function sendCommand(type, params) {
    if (!isClientConnected || !socket) {
        addToLog('Cannot send command: Not connected to server', 'error');
        return false;
    }
    
    try {
        const command = {
            type: type,
            params: params || {}
        };
        
        const commandJson = JSON.stringify(command);
        socket.send(commandJson);
        addToLog(`Sent command: ${type}`);
        return true;
    } catch (err) {
        addToLog(`Error sending command: ${err.message}`, 'error');
        return false;
    }
}

// Handle incoming messages from the server
function handleServerMessage(message) {
    addToLog(`Received message from server: ${JSON.stringify(message).substring(0, 100)}...`);
    
    if (message.status === 'error' && !message.command_id) { // Only log general server errors, not command responses
        addToLog(`Server error: ${message.message}`, 'error');
    } else {
        // Handle success responses for commands *initiated by this client*
        if (message.result && message.command_id) { 
            // This is a response to a command like 'ping' or 'get_document_info' sent from the client
            if (message.result.message === 'pong') {
                addToLog('Server ping successful', 'success');
            }
            // Other client-initiated command responses could be handled here too
        }
    }
}

// Get document information using the Python WebSocket server
async function getDocumentInfo() {
    return sendCommand('get_document_info');
}

// Update the port setting
function updatePort() {
    const portInput = document.getElementById('port');
    const port = parseInt(portInput.value, 10);
    
    // Validate port number
    if (isNaN(port) || port < 1024 || port > 65535) {
        addToLog('Invalid port number. Must be between 1024 and 65535', 'error');
        portInput.value = wsPort; // Reset to current value
        return;
    }
    
    if (isClientConnected) {
        addToLog('Cannot change port while connected', 'error');
        portInput.value = wsPort; // Reset to current value
        return;
    }
    
    wsPort = port;
    addToLog(`Port updated to ${port}`);
}

// Create a rectangle in Photoshop
function createRectangle() {
    try {
        // Get the Photoshop API
        const photoshop = require('photoshop');
        const app = photoshop.app;
        const batchPlay = photoshop.action.batchPlay;
        
        // Get active document or create a new one if none exists
        let doc = app.activeDocument;
        if (!doc) {
            // Create a new document if none is open
            doc = app.documents.add({
                width: 800,
                height: 600,
                resolution: 72,
                mode: 'RGBColorMode',
                fill: 'white'
            });
            addToLog('Created new document for rectangle', 'info');
        }
        
        // Log document info for debugging
        addToLog(`Creating rectangle in document: ${doc.title}`, 'info');
        
        // Get the color from the color picker
        const colorInput = document.getElementById('shapeColor');
        const colorHex = colorInput.value;
        
        // Convert hex to RGB
        const r = parseInt(colorHex.substring(1, 3), 16);
        const g = parseInt(colorHex.substring(3, 5), 16);
        const b = parseInt(colorHex.substring(5, 7), 16);
        
        // Create a rectangle using batchPlay
        // Size is relative to document size
        const docWidth = doc.width;
        const docHeight = doc.height;
        
        // Create a smaller rectangle - 1/6 of the document size
        const width = Math.round(docWidth / 6);
        const height = Math.round(docHeight / 6);
        
        // Create a slightly randomized position near center
        const offset = Math.round(width / 2); // Allow some randomization
        const x = Math.round((docWidth - width) / 2) + Math.round(Math.random() * offset * 2) - offset;
        const y = Math.round((docHeight - height) / 2) + Math.round(Math.random() * offset * 2) - offset;
        
        // First, select the document and ensure we're adding to it
        batchPlay(
            [
                {
                    _obj: "select",
                    _target: [
                        {
                            _ref: "document",
                            _enum: "ordinal",
                            _value: "targetEnum"
                        }
                    ],
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        // Create a shape layer
        const result = batchPlay(
            [
                {
                    _obj: "make",
                    _target: [
                        {
                            _ref: "layer"
                        }
                    ],
                    using: {
                        _obj: "shapeLayer",
                        type: {
                            _obj: "solidColorLayer",
                            color: {
                                _obj: "RGBColor",
                                red: r,
                                grain: g,
                                blue: b
                            }
                        },
                        bounds: {
                            _obj: "rectangle",
                            top: y,
                            left: x,
                            bottom: y + height,
                            right: x + width
                        },
                        name: "Rectangle Layer"
                    },
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        // Ensure the new layer is visible and at the top
        batchPlay(
            [
                {
                    _obj: "show",
                    null: [
                        {
                            _ref: "layer",
                            _enum: "ordinal",
                            _value: "targetEnum"
                        }
                    ],
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        addToLog(`Created rectangle at (${x}, ${y}) with size ${width}x${height}`, 'success');
    } catch (err) {
        addToLog(`Error creating rectangle: ${err.message}`, 'error');
        console.error(err);
    }
}

// Create a circle in Photoshop
function createCircle() {
    try {
        // Get the Photoshop API
        const photoshop = require('photoshop');
        const app = photoshop.app;
        const batchPlay = photoshop.action.batchPlay;
        
        // Get active document or create a new one if none exists
        let doc = app.activeDocument;
        if (!doc) {
            // Create a new document if none is open
            doc = app.documents.add({
                width: 800,
                height: 600,
                resolution: 72,
                mode: 'RGBColorMode',
                fill: 'white'
            });
            addToLog('Created new document for circle', 'info');
        }
        
        // Log document info for debugging
        addToLog(`Creating circle in document: ${doc.title}`, 'info');
        
        // Get the color from the color picker
        const colorInput = document.getElementById('shapeColor');
        const colorHex = colorInput.value;
        
        // Convert hex to RGB
        const r = parseInt(colorHex.substring(1, 3), 16);
        const g = parseInt(colorHex.substring(3, 5), 16);
        const b = parseInt(colorHex.substring(5, 7), 16);
        
        // Define the circle path
        // Size is relative to document size
        const docWidth = doc.width;
        const docHeight = doc.height;
        
        // Create a smaller circle - 1/8 of the document size
        const radius = Math.round(Math.min(docWidth, docHeight) / 8);
        
        // Create a slightly randomized position near center
        const offset = radius; // Allow some randomization
        const centerX = Math.round(docWidth / 2) + Math.round(Math.random() * offset * 2) - offset;
        const centerY = Math.round(docHeight / 2) + Math.round(Math.random() * offset * 2) - offset;
        
        // First, select the document and ensure we're adding to it
        batchPlay(
            [
                {
                    _obj: "select",
                    _target: [
                        {
                            _ref: "document",
                            _enum: "ordinal",
                            _value: "targetEnum"
                        }
                    ],
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        // Create a shape layer for the circle
        const result = batchPlay(
            [
                {
                    _obj: "make",
                    _target: [
                        {
                            _ref: "layer"
                        }
                    ],
                    using: {
                        _obj: "shapeLayer",
                        type: {
                            _obj: "solidColorLayer",
                            color: {
                                _obj: "RGBColor",
                                red: r,
                                grain: g,
                                blue: b
                            }
                        },
                        bounds: {
                            _obj: "ellipse",
                            top: centerY - radius,
                            left: centerX - radius,
                            bottom: centerY + radius,
                            right: centerX + radius
                        },
                        name: "Circle Layer"
                    },
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        // Ensure the new layer is visible and at the top
        batchPlay(
            [
                {
                    _obj: "show",
                    null: [
                        {
                            _ref: "layer",
                            _enum: "ordinal",
                            _value: "targetEnum"
                        }
                    ],
                    _options: {
                        dialogOptions: "dontDisplay"
                    }
                }
            ],
            {
                synchronousExecution: true,
                modalBehavior: "fail"
            }
        );
        
        addToLog(`Created circle at (${centerX}, ${centerY}) with radius ${radius}`, 'success');
    } catch (err) {
        addToLog(`Error creating circle: ${err.message}`, 'error');
        console.error(err);
    }
}

// Update status indicators
function updateStatus() {
    // Update server status indicator
    const serverStatusElem = document.getElementById('serverStatus');
    
    if (isClientConnected) {
        serverStatusElem.innerHTML = `<div class="indicator on"></div>Connected to ${wsHost}:${wsPort}`;
    } else {
        serverStatusElem.innerHTML = '<div class="indicator off"></div>Disconnected';
    }
    
    // Update client status indicator
    const clientStatusElem = document.getElementById('clientStatus');
    
    if (isClientConnected) {
        clientStatusElem.innerHTML = '<div class="indicator on"></div>Yes';
    } else {
        clientStatusElem.innerHTML = '<div class="indicator off"></div>No';
    }
}

// Update the state of the start/stop buttons
function updateButtonState(isConnected) {
    document.getElementById('startServer').disabled = isConnected;
    document.getElementById('stopServer').disabled = !isConnected;
    document.getElementById('port').disabled = isConnected;
}

// Add message to the log
function addToLog(message, type) {
    const logElem = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    if (type) {
        entry.className += ' ' + type;
    }
    
    // Add timestamp
    const now = new Date();
    const timestamp = now.getHours().toString().padStart(2, '0') + ':' + 
                     now.getMinutes().toString().padStart(2, '0') + ':' + 
                     now.getSeconds().toString().padStart(2, '0');
    
    entry.textContent = '[' + timestamp + '] ' + message;
    
    // Add to log and scroll to bottom
    logElem.appendChild(entry);
    logElem.scrollTop = logElem.scrollHeight;
    
    // Limit the number of log entries
    while (logElem.children.length > 100) {
        logElem.removeChild(logElem.firstChild);
    }
}

// New function to execute script received from MCP and send back the result
async function executeScriptFromMCP(scriptContent, commandId) {
    try {
        // Make Photoshop API and logging available to the script
        // Note: 'photoshop', 'app', 'batchPlay' are already available via require('photoshop')
        // if the script uses it. We make them directly available for convenience, and also `addToLog`.
        const scriptFunction = new Function('photoshop', 'app', 'batchPlay', 'addToLog', 'require', scriptContent);
        
        // Get Photoshop objects to pass to the script
        const ps = require('photoshop');
        const currentApp = ps.app;
        const currentBatchPlay = ps.action.batchPlay;
        
        addToLog(`Executing script (ID: ${commandId}):\n${scriptContent.substring(0, 200)}${scriptContent.length > 200 ? '...' : ''}`, 'info');
        
        const result = await scriptFunction(ps, currentApp, currentBatchPlay, addToLog, require);
        
        addToLog(`Script (ID: ${commandId}) executed successfully. Result: ${JSON.stringify(result)}`, 'success');
        sendScriptResultToMCP(commandId, result, null);
    } catch (e) {
        const errorMessage = `Error executing script (ID: ${commandId}): ${e.message}\nStack: ${e.stack}`;
        addToLog(errorMessage, 'error');
        console.error(e);
        sendScriptResultToMCP(commandId, null, errorMessage);
    }
}

// New function to send the script execution result back to the MCP server
function sendScriptResultToMCP(commandId, data, error) {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        addToLog(`Cannot send script result (ID: ${commandId}): WebSocket not open.`, 'error');
        return;
    }

    const response = {
        command_id: commandId,
        result: {},
    };

    if (error) {
        response.result.status = 'error';
        response.result.message = error;
    } else {
        response.result.status = 'success';
        response.result.data = data; // The actual return value from the script
    }

    try {
        const responseJson = JSON.stringify(response);
        socket.send(responseJson);
        addToLog(`Sent script execution result (ID: ${commandId}) to server.`, 'info');
    } catch (err) {
        addToLog(`Error sending script execution result (ID: ${commandId}): ${err.message}`, 'error');
    }
}

// Initialize when the document is ready
document.addEventListener('DOMContentLoaded', init); 