/**
 * Lightfast MCP Plugin for Photoshop
 * JavaScript for UXP Panel
 */

// Plugin state
let isServerRunning = false;
let isClientConnected = false;
let serverPort = 8765;
let socket = null;

// Initialize the extension
function init() {
    // Register event listeners
    document.getElementById('startServer').addEventListener('click', startServer);
    document.getElementById('stopServer').addEventListener('click', stopServer);
    document.getElementById('port').addEventListener('change', updatePort);
    
    // Update status periodically
    setInterval(updateStatus, 2000);
    
    // Initial status update
    updateStatus();
    
    // Add initial log message
    addToLog('Plugin initialized successfully');
}

// Start the server
function startServer() {
    const port = serverPort;
    
    addToLog(`Attempting to start server on port ${port}...`);
    
    try {
        // In UXP, we can't directly create a server
        // Instead, we'll simulate the server for UI demonstration
        isServerRunning = true;
        addToLog(`Server simulated on port ${port}`, 'success');
        addToLog('Note: UXP cannot create actual socket servers.', 'error');
        addToLog('This is a UI simulation only.', 'error');
        
        // We could call back to our MCP server instead to notify it to connect to Photoshop
        
        updateButtonState(true);
        updateStatus();
        
        // Simulate client connection after a delay
        setTimeout(() => {
            isClientConnected = true;
            addToLog('Client connected (simulated)', 'success');
            updateStatus();
            
            // Simulate some command activity
            setTimeout(() => {
                addToLog('Received command: ping');
                addToLog('Sent response: pong');
            }, 2000);
            
            setTimeout(() => {
                addToLog('Received command: get_document_info');
                getDocumentInfo().then(info => {
                    addToLog(`Sent document info: ${info.name || 'No document open'}`);
                });
            }, 4000);
        }, 3000);
    } catch (err) {
        addToLog(`Failed to start server: ${err.message}`, 'error');
        isServerRunning = false;
        updateButtonState(false);
        updateStatus();
    }
}

// Stop the server
function stopServer() {
    addToLog('Stopping server...');
    
    try {
        // Clean up simulated server
        isServerRunning = false;
        isClientConnected = false;
        
        addToLog('Server stopped', 'success');
        updateButtonState(false);
        updateStatus();
    } catch (err) {
        addToLog(`Error stopping server: ${err.message}`, 'error');
    }
}

// Get document information using Photoshop APIs
async function getDocumentInfo() {
    try {
        // Check if app and require are available (they may not be in UXP)
        if (typeof require !== 'function') {
            return { error: 'UXP API not available' };
        }
        
        // Try to access Photoshop API
        try {
            const photoshop = require('photoshop');
            const app = photoshop.app;
            
            // Check if a document is open
            if (!app.documents || app.documents.length === 0) {
                return { error: 'No document open' };
            }
            
            const doc = app.activeDocument;
            
            // Get basic document info
            return {
                name: doc.name,
                width: doc.width,
                height: doc.height,
                path: doc.path || ''
            };
        } catch (e) {
            return { error: 'Failed to access Photoshop API' };
        }
    } catch (err) {
        return { error: err.message };
    }
}

// Update the port setting
function updatePort() {
    const portInput = document.getElementById('port');
    const port = parseInt(portInput.value, 10);
    
    // Validate port number
    if (isNaN(port) || port < 1024 || port > 65535) {
        addToLog('Invalid port number. Must be between 1024 and 65535', 'error');
        portInput.value = serverPort; // Reset to current value
        return;
    }
    
    if (isServerRunning) {
        addToLog('Cannot change port while server is running', 'error');
        portInput.value = serverPort; // Reset to current value
        return;
    }
    
    serverPort = port;
    addToLog(`Port updated to ${port}`);
}

// Update status indicators
function updateStatus() {
    // Update server status indicator
    const serverStatusElem = document.getElementById('serverStatus');
    
    if (isServerRunning) {
        serverStatusElem.innerHTML = `<div class="indicator on"></div>Active on port ${serverPort}`;
    } else {
        serverStatusElem.innerHTML = '<div class="indicator off"></div>Inactive';
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
function updateButtonState(isRunning) {
    document.getElementById('startServer').disabled = isRunning;
    document.getElementById('stopServer').disabled = !isRunning;
    document.getElementById('port').disabled = isRunning;
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