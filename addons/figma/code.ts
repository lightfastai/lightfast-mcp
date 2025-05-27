// This file holds the main code for plugins. Code in this file has access to
// the *figma document* via the figma global object.
// You can access browser APIs in the <script> tag inside "ui.html" which has a
// full browser environment (See https://www.figma.com/plugin-docs/how-plugins-run).

// Lightfast MCP Figma Plugin - Main Code
// This file handles communication between the UI and Figma's document API

// Plugin state
let isPluginActive = true;
let selectionChangeHandler: () => void;

// Utility function for error handling
function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Runs this code if the plugin is run in Figma
if (figma.editorType === 'figma') {
  // Show the HTML UI
  figma.showUI(__html__, { 
    width: 320, 
    height: 600,
    themeColors: true 
  });

  // Set up selection change monitoring
  selectionChangeHandler = () => {
    const selection = figma.currentPage.selection;
    const selectionData = selection.map(node => ({
      id: node.id,
      name: node.name,
      type: node.type,
      x: 'x' in node ? node.x : undefined,
      y: 'y' in node ? node.y : undefined,
      width: 'width' in node ? node.width : undefined,
      height: 'height' in node ? node.height : undefined,
    }));

    // Send selection data to UI
    figma.ui.postMessage({
      type: 'selection-changed',
      selection: selectionData
    });
  };

  // Monitor selection changes
  figma.on('selectionchange', selectionChangeHandler);

  // Handle messages from the UI
  figma.ui.onmessage = async (msg: any) => {
    try {
      switch (msg.type) {
        case 'get_document_info':
          await handleGetDocumentInfo();
          break;

        case 'get_selection':
          await handleGetSelection();
          break;

        case 'get_node_info':
          await handleGetNodeInfo(msg.params.node_id);
          break;

        case 'create_rectangle':
          await handleCreateRectangle(msg.params);
          break;

        case 'create_frame':
          await handleCreateFrame(msg.params);
          break;

        case 'create_text':
          await handleCreateText(msg.params);
          break;

        case 'set_text_content':
          await handleSetTextContent(msg.params.node_id, msg.params.text);
          break;

        case 'move_node':
          await handleMoveNode(msg.params.node_id, msg.params.x, msg.params.y);
          break;

        case 'resize_node':
          await handleResizeNode(msg.params.node_id, msg.params.width, msg.params.height);
          break;

        case 'delete_node':
          await handleDeleteNode(msg.params.node_id);
          break;

        case 'set_fill_color':
          await handleSetFillColor(msg.params);
          break;

        case 'selection-changed':
          // Initial selection request from UI
          selectionChangeHandler();
          break;

        case 'ping':
          // Simple ping/pong for connection testing
          figma.ui.postMessage({ type: 'pong', timestamp: Date.now() });
          break;

        case 'figma_command':
          // Handle WebSocket commands forwarded from UI
          await handleWebSocketCommand(msg);
          break;

        case 'close-plugin':
          figma.closePlugin();
          break;

        default:
          figma.ui.postMessage({
            type: 'error',
            message: `Unknown message type: ${msg.type}`
          });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      figma.ui.postMessage({
        type: 'error',
        message: `Error handling ${msg.type}: ${errorMessage}`,
        error: errorMessage
      });
    }
  };

  // Send initial selection data
  setTimeout(() => {
    selectionChangeHandler();
  }, 100);
}

// Tool implementations

async function handleGetDocumentInfo() {
  const documentInfo = {
    name: figma.root.name,
    id: figma.root.id,
    type: figma.root.type,
    children: figma.root.children.length,
    currentPage: {
      name: figma.currentPage.name,
      id: figma.currentPage.id,
      children: figma.currentPage.children.length
    },
    selection: figma.currentPage.selection.length,
    viewport: {
      center: figma.viewport.center,
      zoom: figma.viewport.zoom
    }
  };

  figma.ui.postMessage({
    type: 'tool-response',
    tool: 'get_document_info',
    data: documentInfo,
    success: true
  });
}

async function handleGetSelection() {
  const selection = figma.currentPage.selection;
  const selectionData = selection.map(node => ({
    id: node.id,
    name: node.name,
    type: node.type,
    x: 'x' in node ? node.x : undefined,
    y: 'y' in node ? node.y : undefined,
    width: 'width' in node ? node.width : undefined,
    height: 'height' in node ? node.height : undefined,
    fills: 'fills' in node ? node.fills : undefined,
    characters: 'characters' in node ? node.characters : undefined
  }));

  figma.ui.postMessage({
    type: 'tool-response',
    tool: 'get_selection',
    data: { selection: selectionData, count: selection.length },
    success: true
  });
}

async function handleGetNodeInfo(nodeId: string) {
  try {
    const node = figma.getNodeById(nodeId);
    if (!node) {
      throw new Error(`Node with ID ${nodeId} not found`);
    }

    const nodeInfo = {
      id: node.id,
      name: node.name,
      type: node.type,
      ...((node as any).visible !== undefined && { visible: (node as any).visible }),
      ...((node as any).locked !== undefined && { locked: (node as any).locked }),
      parent: node.parent ? {
        id: node.parent.id,
        name: node.parent.name,
        type: node.parent.type
      } : null,
      // Add position and size if available
      ...(('x' in node) && { x: node.x }),
      ...(('y' in node) && { y: node.y }),
      ...(('width' in node) && { width: node.width }),
      ...(('height' in node) && { height: node.height }),
      // Add text content if it's a text node
      ...(('characters' in node) && { characters: node.characters }),
      // Add fill information if available
      ...(('fills' in node) && { fills: node.fills })
    };

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'get_node_info',
      data: nodeInfo,
      success: true
    });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'get_node_info',
      data: null,
      success: false,
      error: errorMessage
    });
  }
}

async function handleCreateRectangle(params: any) {
  try {
    const rect = figma.createRectangle();
    
    // Set properties
    rect.x = params.x || 0;
    rect.y = params.y || 0;
    rect.resize(params.width || 100, params.height || 100);
    rect.name = params.name || 'Rectangle';

    // Add to current page
    figma.currentPage.appendChild(rect);
    
    // Select the new rectangle
    figma.currentPage.selection = [rect];
    figma.viewport.scrollAndZoomIntoView([rect]);

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_rectangle',
      data: {
        id: rect.id,
        name: rect.name,
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_rectangle',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleCreateFrame(params: any) {
  try {
    const frame = figma.createFrame();
    
    frame.x = params.x || 0;
    frame.y = params.y || 0;
    frame.resize(params.width || 200, params.height || 200);
    frame.name = params.name || 'Frame';

    figma.currentPage.appendChild(frame);
    figma.currentPage.selection = [frame];
    figma.viewport.scrollAndZoomIntoView([frame]);

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_frame',
      data: {
        id: frame.id,
        name: frame.name,
        x: frame.x,
        y: frame.y,
        width: frame.width,
        height: frame.height
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_frame',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleCreateText(params: any) {
  try {
    const textNode = figma.createText();
    
    // Load font before setting text
    await figma.loadFontAsync({ family: params.font_family || "Inter", style: "Regular" });
    
    textNode.characters = params.text || 'Hello World';
    textNode.x = params.x || 0;
    textNode.y = params.y || 0;
    textNode.fontSize = params.font_size || 16;
    textNode.name = params.name || 'Text';

    figma.currentPage.appendChild(textNode);
    figma.currentPage.selection = [textNode];
    figma.viewport.scrollAndZoomIntoView([textNode]);

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_text',
      data: {
        id: textNode.id,
        name: textNode.name,
        characters: textNode.characters,
        x: textNode.x,
        y: textNode.y,
        fontSize: textNode.fontSize
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'create_text',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleSetTextContent(nodeId: string, text: string) {
  try {
    const node = figma.getNodeById(nodeId);
    if (!node) {
      throw new Error(`Node with ID ${nodeId} not found`);
    }

    if (node.type !== 'TEXT') {
      throw new Error(`Node ${nodeId} is not a text node`);
    }

    const textNode = node as TextNode;
    
    // Load font if needed
    await figma.loadFontAsync(textNode.fontName as FontName);
    textNode.characters = text;

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'set_text_content',
      data: {
        id: textNode.id,
        characters: textNode.characters
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'set_text_content',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleMoveNode(nodeId: string, x: number, y: number) {
  try {
    const node = figma.getNodeById(nodeId);
    if (!node) {
      throw new Error(`Node with ID ${nodeId} not found`);
    }

    if (!('x' in node) || !('y' in node)) {
      throw new Error(`Node ${nodeId} cannot be moved`);
    }

    const movableNode = node as LayoutMixin;
    movableNode.x = x;
    movableNode.y = y;

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'move_node',
      data: {
        id: node.id,
        x: movableNode.x,
        y: movableNode.y
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'move_node',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleResizeNode(nodeId: string, width: number, height: number) {
  try {
    const node = figma.getNodeById(nodeId);
    if (!node) {
      throw new Error(`Node with ID ${nodeId} not found`);
    }

    if (!('resize' in node)) {
      throw new Error(`Node ${nodeId} cannot be resized`);
    }

    const resizableNode = node as LayoutMixin;
    resizableNode.resize(width, height);

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'resize_node',
      data: {
        id: node.id,
        width: resizableNode.width,
        height: resizableNode.height
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'resize_node',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleDeleteNode(nodeId: string) {
  try {
    const node = figma.getNodeById(nodeId);
    if (!node) {
      throw new Error(`Node with ID ${nodeId} not found`);
    }

    const nodeInfo = {
      id: node.id,
      name: node.name,
      type: node.type
    };

    node.remove();

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'delete_node',
      data: nodeInfo,
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'delete_node',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleSetFillColor(params: any) {
  try {
    const node = figma.getNodeById(params.node_id);
    if (!node) {
      throw new Error(`Node with ID ${params.node_id} not found`);
    }

    if (!('fills' in node)) {
      throw new Error(`Node ${params.node_id} does not support fills`);
    }

    const fillableNode = node as GeometryMixin;
    
    // Convert RGB values (0-255) to Figma's format (0-1)
    const r = (params.r || 0) / 255;
    const g = (params.g || 0) / 255;
    const b = (params.b || 0) / 255;
    const a = params.a !== undefined ? params.a : 1.0;

    const newFill: SolidPaint = {
      type: 'SOLID',
      color: { r, g, b },
      opacity: a
    };

    fillableNode.fills = [newFill];

    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'set_fill_color',
      data: {
        id: node.id,
        color: { r: params.r, g: params.g, b: params.b, a: a }
      },
      success: true
    });
  } catch (error) {
    figma.ui.postMessage({
      type: 'tool-response',
      tool: 'set_fill_color',
      data: null,
      success: false,
      error: getErrorMessage(error)
    });
  }
}

async function handleWebSocketCommand(msg: any) {
  try {
    const { command, params, id } = msg;
    
    switch (command) {
      case 'execute_tool':
        // Execute tool directly from WebSocket server
        await executeToolDirectly(params.tool, params.params, id);
        break;
      
      case 'get_current_selection':
        // Send current selection back to server
        await handleGetSelection();
        break;
        
      case 'batch_operations':
        // Execute multiple operations in sequence
        for (const operation of params.operations) {
          await executeToolDirectly(operation.tool, operation.params);
        }
        break;
        
      default:
        figma.ui.postMessage({
          type: 'error',
          message: `Unknown WebSocket command: ${command}`
        });
    }
  } catch (error) {
    const errorMessage = getErrorMessage(error);
    figma.ui.postMessage({
      type: 'error',
      message: `WebSocket command error: ${errorMessage}`
    });
  }
}

async function executeToolDirectly(toolName: string, params: any, messageId?: string) {
  try {
    let result;
    
    switch (toolName) {
      case 'get_document_info':
        await handleGetDocumentInfo();
        break;
      case 'get_selection':
        await handleGetSelection();
        break;
      case 'get_node_info':
        await handleGetNodeInfo(params.node_id);
        break;
      case 'create_rectangle':
        await handleCreateRectangle(params);
        break;
      case 'create_frame':
        await handleCreateFrame(params);
        break;
      case 'create_text':
        await handleCreateText(params);
        break;
      case 'set_text_content':
        await handleSetTextContent(params.node_id, params.text);
        break;
      case 'move_node':
        await handleMoveNode(params.node_id, params.x, params.y);
        break;
      case 'resize_node':
        await handleResizeNode(params.node_id, params.width, params.height);
        break;
      case 'delete_node':
        await handleDeleteNode(params.node_id);
        break;
      case 'set_fill_color':
        await handleSetFillColor(params);
        break;
      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
    
    // If messageId provided, this was a direct WebSocket call
    if (messageId) {
      figma.ui.postMessage({
        type: 'websocket_response',
        messageId: messageId,
        success: true,
        tool: toolName
      });
    }
    
  } catch (error) {
    const errorMessage = getErrorMessage(error);
    
    if (messageId) {
      figma.ui.postMessage({
        type: 'websocket_response',
        messageId: messageId,
        success: false,
        tool: toolName,
        error: errorMessage
      });
    }
    
    throw error;
  }
}

// Cleanup on plugin close
figma.on('close', () => {
  isPluginActive = false;
  if (selectionChangeHandler) {
    figma.off('selectionchange', selectionChangeHandler);
  }
});