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
            } catch (err) {
                addToLog(`Error parsing message: ${err.message}`, 'error');
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
    
    if (message.status === 'error') {
        addToLog(`Server error: ${message.message}`, 'error');
    } else {
        // Handle success responses
        if (message.result) {
            // Process result if needed
            if (message.result.message === 'pong') {
                addToLog('Server ping successful', 'success');
            }
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

// Initialize when the document is ready
document.addEventListener('DOMContentLoaded', init); 