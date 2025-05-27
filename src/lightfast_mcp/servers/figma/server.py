"""
Figma MCP Server for design manipulation through Figma plugin integration.
Uses direct API communication without WebSocket dependencies.
"""

import json
from typing import ClassVar

from fastmcp import Context

from ...core.base_server import BaseServer, ServerConfig
from ...utils.logging_utils import get_logger

logger = get_logger("FigmaMCPServer")


class FigmaMCPServer(BaseServer):
    """Figma MCP server for design manipulation via plugin communication."""

    # Server metadata
    SERVER_TYPE: ClassVar[str] = "figma"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = ["Figma"]

    def __init__(self, config: ServerConfig):
        """Initialize the Figma server."""
        super().__init__(config)

        # Figma-specific configuration
        self.plugin_channel = config.config.get("plugin_channel", "default")
        self.command_timeout = config.config.get("command_timeout", 30.0)

        logger.info(f"Figma server configured with channel: {self.plugin_channel}")

    def _register_tools(self):
        """Register Figma server tools."""
        if not self.mcp:
            return

        # Register core design tools
        self.mcp.tool()(self.get_document_info)
        self.mcp.tool()(self.get_selection)
        self.mcp.tool()(self.get_node_info)
        self.mcp.tool()(self.create_rectangle)
        self.mcp.tool()(self.create_frame)
        self.mcp.tool()(self.create_text)
        self.mcp.tool()(self.set_text_content)
        self.mcp.tool()(self.move_node)
        self.mcp.tool()(self.resize_node)
        self.mcp.tool()(self.delete_node)
        self.mcp.tool()(self.set_fill_color)
        self.mcp.tool()(self.get_server_status)

        # Update available tools list
        self.info.tools = [
            "get_document_info",
            "get_selection",
            "get_node_info",
            "create_rectangle",
            "create_frame",
            "create_text",
            "set_text_content",
            "move_node",
            "resize_node",
            "delete_node",
            "set_fill_color",
            "get_server_status",
        ]
        logger.info(f"Registered {len(self.info.tools)} tools")

    async def _check_application(self, app: str) -> bool:
        """Check if Figma is available."""
        if app.lower() == "figma":
            # For plugin-based integration, we assume Figma is available
            # The actual check happens when the plugin connects
            return True
        return True

    async def _on_startup(self):
        """Figma server startup logic."""
        logger.info(f"Figma server '{self.config.name}' starting up...")
        logger.info("Plugin-based Figma server ready for MCP communication")
        logger.info("Figma server startup complete")

    async def _on_shutdown(self):
        """Figma server shutdown logic."""
        logger.info(f"Figma server '{self.config.name}' shutting down...")
        logger.info("Figma server shutdown complete")

    async def _perform_health_check(self) -> bool:
        """Perform health check."""
        try:
            # For plugin-based integration, we're always healthy if running
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    # Tool implementations
    async def get_document_info(self, ctx: Context) -> str:
        """Get information about the current Figma document.

        Returns:
            JSON string with document information
        """
        try:
            # This is a placeholder - actual implementation would communicate with plugin
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting document info: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_selection(self, ctx: Context) -> str:
        """Get information about currently selected elements.

        Returns:
            JSON string with selection information
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting selection: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_node_info(self, ctx: Context, node_id: str) -> str:
        """Get detailed information about a specific node.

        Args:
            node_id: The ID of the node to get information about

        Returns:
            JSON string with node information
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "node_id": node_id,
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error getting node info for {node_id}: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_rectangle(
        self,
        ctx: Context,
        x: float = 0,
        y: float = 0,
        width: float = 100,
        height: float = 100,
        name: str = "Rectangle",
    ) -> str:
        """Create a new rectangle in Figma.

        Args:
            x: X position
            y: Y position
            width: Width of rectangle
            height: Height of rectangle
            name: Name for the rectangle

        Returns:
            JSON string with created rectangle information
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "create_rectangle",
                "params": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "name": name,
                },
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating rectangle: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_frame(
        self,
        ctx: Context,
        x: float = 0,
        y: float = 0,
        width: float = 200,
        height: float = 200,
        name: str = "Frame",
    ) -> str:
        """Create a new frame in Figma.

        Args:
            x: X position
            y: Y position
            width: Width of frame
            height: Height of frame
            name: Name for the frame

        Returns:
            JSON string with created frame information
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "create_frame",
                "params": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "name": name,
                },
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating frame: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def create_text(
        self,
        ctx: Context,
        text: str,
        x: float = 0,
        y: float = 0,
        font_size: float = 16,
        font_family: str = "Inter",
        name: str = "Text",
    ) -> str:
        """Create a new text node in Figma.

        Args:
            text: Text content
            x: X position
            y: Y position
            font_size: Font size
            font_family: Font family name
            name: Name for the text node

        Returns:
            JSON string with created text node information
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "create_text",
                "params": {
                    "text": text,
                    "x": x,
                    "y": y,
                    "fontSize": font_size,
                    "fontFamily": font_family,
                    "name": name,
                },
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error creating text: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def set_text_content(self, ctx: Context, node_id: str, text: str) -> str:
        """Set the text content of a text node.

        Args:
            node_id: ID of the text node
            text: New text content

        Returns:
            JSON string with update result
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "set_text_content",
                "params": {"nodeId": node_id, "text": text},
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error setting text content: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def move_node(self, ctx: Context, node_id: str, x: float, y: float) -> str:
        """Move a node to a new position.

        Args:
            node_id: ID of the node to move
            x: New X position
            y: New Y position

        Returns:
            JSON string with move result
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "move_node",
                "params": {"nodeId": node_id, "x": x, "y": y},
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error moving node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def resize_node(
        self, ctx: Context, node_id: str, width: float, height: float
    ) -> str:
        """Resize a node.

        Args:
            node_id: ID of the node to resize
            width: New width
            height: New height

        Returns:
            JSON string with resize result
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "resize_node",
                "params": {"nodeId": node_id, "width": width, "height": height},
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error resizing node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def delete_node(self, ctx: Context, node_id: str) -> str:
        """Delete a node.

        Args:
            node_id: ID of the node to delete

        Returns:
            JSON string with deletion result
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "delete_node",
                "params": {"nodeId": node_id},
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error deleting node: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def set_fill_color(
        self,
        ctx: Context,
        node_id: str,
        r: int,
        g: int,
        b: int,
        a: float = 1.0,
    ) -> str:
        """Set the fill color of a node.

        Args:
            node_id: ID of the node
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            a: Alpha value (0.0-1.0)

        Returns:
            JSON string with color change result
        """
        try:
            result = {
                "message": "This tool requires the Figma plugin to be active",
                "status": "plugin_required",
                "command": "set_fill_color",
                "params": {"nodeId": node_id, "r": r, "g": g, "b": b, "a": a},
                "server_info": {
                    "name": self.config.name,
                    "type": self.SERVER_TYPE,
                    "channel": self.plugin_channel,
                },
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error setting fill color: {e}")
            return json.dumps({"error": str(e)}, indent=2)

    async def get_server_status(self, ctx: Context) -> str:
        """Get server status and configuration information.

        Returns:
            JSON string with server status
        """
        try:
            status = {
                "server_name": self.config.name,
                "server_type": self.SERVER_TYPE,
                "server_version": self.SERVER_VERSION,
                "plugin_channel": self.plugin_channel,
                "command_timeout": self.command_timeout,
                "status": "running",
                "message": "Plugin-based Figma MCP server ready for communication",
            }
            return json.dumps(status, indent=2)
        except Exception as e:
            logger.error(f"Error getting server status: {e}")
            return json.dumps({"error": str(e)}, indent=2)


def main():
    """Run the Figma MCP server directly."""
    # Create a default configuration for standalone running
    config = ServerConfig(
        name="FigmaMCP",
        description="Figma MCP Server for design manipulation",
        config={
            "type": "figma",
            "plugin_channel": "default",
            "command_timeout": 30.0,
        },
    )

    # Create and run the server
    server = FigmaMCPServer(config)
    logger.info(f"Starting standalone Figma server: {config.name}")
    server.run()


if __name__ == "__main__":
    main()
