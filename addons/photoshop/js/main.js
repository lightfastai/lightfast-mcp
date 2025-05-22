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
    document.getElementById('connectButton').addEventListener('click', connectToServer);
    document.getElementById('disconnectButton').addEventListener('click', disconnectFromServer);
    document.getElementById('port').addEventListener('change', updatePort);
    
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
            
            // The server will now send a ping upon connection, UXP will respond to that.
            // No need to send a client-initiated ping here anymore.
            // sendCommand('ping', {}); 
        });
        
        // Listen for messages
        socket.addEventListener('message', async (event) => {
            try {
                const message = JSON.parse(event.data);
                // Log all messages first
                if (message.type === 'execute_photoshop_code_cmd' || message.type === 'execute_jsx') {
                     addToLog(`Received message from server (type: ${message.type}, ID: ${message.command_id}): {params: ${JSON.stringify(message.params).substring(0,100)}...}`);
                } else {
                    // Pass other messages to the general handler, but it won't process command responses itself
                    handleServerMessage(message); 
                }

                // Handle server-initiated ping
                if (message.command_id && message.type === 'ping') {
                    addToLog(`Received ping from server (ID: ${message.command_id}). Sending pong...`);
                    sendScriptResultToMCP(message.command_id, { message: "pong" }, null);
                    return; 
                }

                // Handle server-initiated get_document_info command
                if (message.command_id && message.type === 'get_document_info') {
                    addToLog(`Received get_document_info command from server (ID: ${message.command_id}). Gathering details...`);
                    try {
                        const docDetails = await getDocumentDetailsForMCP();
                        sendScriptResultToMCP(message.command_id, docDetails, null);
                    } catch (e) {
                        addToLog(`Error getting document details for MCP: ${e.message}`, 'error');
                        sendScriptResultToMCP(message.command_id, null, `Error getting document details: ${e.message}`);
                    }
                    return;
                }

                // Check if this message is a command to execute code from the server
                if (message.command_id && (message.type === 'execute_photoshop_code_cmd' || message.type === 'execute_jsx')) {
                    const scriptToExecute = message.params?.script || message.params?.code;
                    const commandId = message.command_id;
                    const commandType = message.type;

                    if (scriptToExecute) {
                        addToLog(`Processing ${commandType} command (ID: ${commandId}) from server. Executing script...`);
                        executeScriptFromMCP(scriptToExecute, commandId); // This is already async
                    } else {
                        addToLog(`Received ${commandType} command (ID: ${commandId}) but no script was provided.`, 'error');
                        sendScriptResultToMCP(commandId, null, 'No script provided in command');
                    }
                    // No return here, executeScriptFromMCP handles sending the response
                }
            } catch (err) {
                addToLog(`Error parsing message or initial handling: ${err.message}`, 'error');
                try {
                    if (event.data) {
                        const originalMessage = JSON.parse(event.data); 
                        if (originalMessage && originalMessage.command_id) {
                            sendScriptResultToMCP(originalMessage.command_id, null, `Fatal error processing message: ${err.message}`);
                        }
                    }
                } catch (e) { /* Ignore secondary error during error reporting */ }
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
    document.getElementById('connectButton').disabled = isConnected;
    document.getElementById('disconnectButton').disabled = !isConnected;
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

// Function to get document details (this was previously client-only, now adapted for MCP)
async function getDocumentDetailsForMCP() {
    const photoshop = require('photoshop');
    const app = photoshop.app;
    const batchPlay = photoshop.action.batchPlay; 

    if (!app.activeDocument) {
        return {
            status: 'error',
            message: 'No active document in Photoshop.',
            hasActiveDocument: false
        };
    }

    const doc = app.activeDocument;
    let layerCount = 0;
    try {
        // A simple batchPlay to get layer count, as doc.layers might not be fully populated or efficient for just count
        const result = await batchPlay([
            {
                _obj: "get",
                _target: [
                    { _property: "numberOfLayers" },
                    { _ref: "document", _id: doc.id }
                ],
                _options: { dialogOptions: "dontDisplay" }
            }
        ], { synchronousExecution: false });
        layerCount = result[0]?.numberOfLayers || doc.layers.length; // Fallback to doc.layers.length if batchPlay fails
    } catch (e) {
        addToLog(`Could not get layer count via batchPlay, falling back: ${e.message}`, 'warning');
        layerCount = doc.layers.length; // Fallback
    }
    
    return {
        status: 'success',
        message: 'Document details retrieved.',
        hasActiveDocument: true,
        title: doc.title,
        width: doc.width,
        height: doc.height,
        resolution: doc.resolution,
        mode: doc.mode,
        layerCount: layerCount,
        id: doc.id, // Document ID
        cloudDocument: doc.cloudDocument,
        saved: doc.saved
    };
}

// Initialize when the document is ready
document.addEventListener('DOMContentLoaded', init); 