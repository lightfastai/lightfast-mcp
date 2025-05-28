"""
WebSocket server implementation for the Figma MCP server.

This module provides a WebSocket server that Figma plugins can connect to
for real-time design automation and AI integration.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol

from ...utils.logging_utils import get_logger

logger = get_logger("FigmaWebSocketServer")


@dataclass
class FigmaClient:
    """Represents a connected Figma plugin client."""

    id: str
    websocket: WebSocketServerProtocol
    connected_at: datetime = field(default_factory=datetime.now)
    last_ping: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    plugin_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert client to dictionary representation."""
        return {
            "id": self.id,
            "connected_at": self.connected_at.isoformat(),
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "metadata": self.metadata,
            "plugin_info": self.plugin_info,
            "remote_address": f"{self.websocket.remote_address[0]}:{self.websocket.remote_address[1]}"
            if self.websocket.remote_address
            else "unknown",
        }


class FigmaWebSocketServer:
    """WebSocket server for handling Figma plugin communications."""

    def __init__(self, host: str = "localhost", port: int = 9003):
        self.host = host
        self.port = port
        self.server: Optional[websockets.WebSocketServer] = None
        self.clients: Dict[str, FigmaClient] = {}
        self.is_running = False
        self.message_handlers: Dict[str, callable] = {}
        self.stats = {
            "total_connections": 0,
            "total_messages": 0,
            "start_time": None,
            "errors": 0,
        }

        # Register default message handlers
        self._register_default_handlers()

    def _is_websocket_closed(self, websocket) -> bool:
        """Check if a WebSocket connection is closed (compatible with different websockets versions)."""
        try:
            # Try the newer websockets library approach
            if hasattr(websocket, "closed"):
                return websocket.closed
            # Try the older approach
            elif hasattr(websocket, "state"):
                from websockets.protocol import State

                return websocket.state == State.CLOSED
            # Fallback - assume it's open if we can't determine
            else:
                return False
        except Exception:
            # If we can't determine, assume it's closed to be safe
            return True

    def _register_default_handlers(self):
        """Register default message handlers."""
        self.message_handlers.update(
            {
                "ping": self._handle_ping,
                "get_document_info": self._handle_get_document_info,
                "execute_design_command": self._handle_execute_design_command,
                "get_server_status": self._handle_get_server_status,
                "plugin_info": self._handle_plugin_info,
                "document_update": self._handle_document_update,
            }
        )

    async def start(self) -> bool:
        """Start the WebSocket server."""
        if self.is_running:
            logger.warning("Figma WebSocket server is already running")
            return True

        try:
            logger.info(f"Starting Figma WebSocket server on {self.host}:{self.port}")

            # Create a wrapper to handle the different websockets library versions
            async def client_handler(websocket, path=None):
                await self._handle_client(websocket, path or "/")

            self.server = await websockets.serve(
                client_handler,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
            )

            self.is_running = True
            self.stats["start_time"] = datetime.now()

            logger.info(
                f"✅ Figma WebSocket server started successfully on ws://{self.host}:{self.port}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start Figma WebSocket server: {e}")
            self.is_running = False
            return False

    async def stop(self):
        """Stop the WebSocket server."""
        if not self.is_running:
            logger.warning("Figma WebSocket server is not running")
            return

        logger.info("Stopping Figma WebSocket server...")

        # Close all client connections
        if self.clients:
            logger.info(f"Closing {len(self.clients)} Figma plugin connections...")
            close_tasks = []
            for client in self.clients.values():
                if not self._is_websocket_closed(client.websocket):
                    close_tasks.append(client.websocket.close())

            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)

        # Stop the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.is_running = False
        self.clients.clear()
        logger.info("✅ Figma WebSocket server stopped")

    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str = "/"):
        """Handle a new Figma plugin connection."""
        client_id = str(uuid.uuid4())[:8]
        client = FigmaClient(id=client_id, websocket=websocket)

        self.clients[client_id] = client
        self.stats["total_connections"] += 1

        logger.info(
            f"🎨 New Figma plugin connected: {client_id} from {websocket.remote_address}"
        )

        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "client_id": client_id,
            "server_info": {
                "name": "Figma MCP WebSocket Server",
                "version": "1.0.0",
                "capabilities": list(self.message_handlers.keys()),
            },
            "timestamp": time.time(),
        }

        try:
            await websocket.send(json.dumps(welcome_message))

            # Handle messages from this Figma plugin
            async for message in websocket:
                await self._process_message(client, message)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🎨 Figma plugin {client_id} disconnected normally")
        except Exception as e:
            logger.error(f"❌ Error handling Figma plugin {client_id}: {e}")
            self.stats["errors"] += 1
        finally:
            # Clean up client
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"🧹 Cleaned up Figma plugin {client_id}")

    async def _process_message(self, client: FigmaClient, message: str):
        """Process a message from a Figma plugin."""
        try:
            data = json.loads(message)
            self.stats["total_messages"] += 1

            message_type = data.get("type", "unknown")
            logger.debug(
                f"📨 Received message from Figma plugin {client.id}: {message_type}"
            )

            # Update client last activity
            client.last_ping = datetime.now()

            # Handle the message
            if message_type in self.message_handlers:
                response = await self.message_handlers[message_type](client, data)
                if response:
                    await client.websocket.send(json.dumps(response))
            else:
                # Unknown message type
                error_response = {
                    "type": "error",
                    "error": f"Unknown message type: {message_type}",
                    "available_types": list(self.message_handlers.keys()),
                    "timestamp": time.time(),
                }
                await client.websocket.send(json.dumps(error_response))

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON from Figma plugin {client.id}: {e}")
            error_response = {
                "type": "error",
                "error": f"Invalid JSON: {str(e)}",
                "timestamp": time.time(),
            }
            await client.websocket.send(json.dumps(error_response))
        except Exception as e:
            logger.error(
                f"❌ Error processing message from Figma plugin {client.id}: {e}"
            )
            self.stats["errors"] += 1

    # Message handlers
    async def _handle_ping(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle ping message from Figma plugin."""
        return {
            "type": "pong",
            "client_id": client.id,
            "timestamp": time.time(),
            "server_time": datetime.now().isoformat(),
        }

    async def _handle_get_document_info(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get document info request from Figma plugin."""
        # This will be handled by the plugin - we just acknowledge the request
        return {
            "type": "document_info_request",
            "client_id": client.id,
            "request_id": data.get("request_id", str(uuid.uuid4())),
            "timestamp": time.time(),
        }

    async def _handle_execute_design_command(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle execute design command request from MCP."""
        command = data.get("command", "")
        request_id = data.get("request_id", str(uuid.uuid4()))

        logger.info(f"🎨 Executing design command for client {client.id}: {command}")

        # Send command to Figma plugin
        command_message = {
            "type": "execute_design_command",
            "command": command,
            "request_id": request_id,
            "timestamp": time.time(),
        }

        await client.websocket.send(json.dumps(command_message))

        # Return acknowledgment
        return {
            "type": "design_command_sent",
            "client_id": client.id,
            "command": command,
            "request_id": request_id,
            "timestamp": time.time(),
        }

    async def _handle_get_server_status(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get server status request."""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()

        return {
            "type": "server_status",
            "client_id": client.id,
            "status": {
                **self.stats,
                "start_time": self.stats["start_time"].isoformat()
                if self.stats["start_time"]
                else None,
                "uptime_seconds": uptime,
                "current_clients": len(self.clients),
                "server_info": {
                    "host": self.host,
                    "port": self.port,
                    "is_running": self.is_running,
                },
            },
            "timestamp": time.time(),
        }

    async def _handle_plugin_info(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle plugin info update from Figma plugin."""
        plugin_info = data.get("plugin_info", {})
        client.plugin_info = plugin_info

        logger.info(f"📋 Updated plugin info for client {client.id}: {plugin_info}")

        return {
            "type": "plugin_info_received",
            "client_id": client.id,
            "timestamp": time.time(),
        }

    async def _handle_document_update(
        self, client: FigmaClient, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Handle document update notification from Figma plugin."""
        document_info = data.get("document_info", {})

        logger.debug(f"📄 Document update from client {client.id}")

        # Store document info in client metadata
        client.metadata["last_document_info"] = document_info
        client.metadata["last_document_update"] = time.time()

        # No response needed for updates
        return None

    async def send_command_to_plugin(
        self, client_id: str, command_type: str, params: Dict[str, Any] = None
    ) -> bool:
        """Send a command to a specific Figma plugin."""
        if client_id not in self.clients:
            logger.error(f"Client {client_id} not found")
            return False

        client = self.clients[client_id]
        if self._is_websocket_closed(client.websocket):
            logger.error(f"Client {client_id} connection is closed")
            return False

        message = {
            "type": command_type,
            "params": params or {},
            "request_id": str(uuid.uuid4()),
            "timestamp": time.time(),
        }

        try:
            await client.websocket.send(json.dumps(message))
            logger.debug(f"📤 Sent command {command_type} to Figma plugin {client_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error sending command to Figma plugin {client_id}: {e}")
            return False

    async def broadcast_to_plugins(
        self, command_type: str, params: Dict[str, Any] = None
    ) -> int:
        """Broadcast a command to all connected Figma plugins."""
        message = {
            "type": command_type,
            "params": params or {},
            "request_id": str(uuid.uuid4()),
            "timestamp": time.time(),
        }

        sent_count = 0
        for client in self.clients.values():
            if not self._is_websocket_closed(client.websocket):
                try:
                    await client.websocket.send(json.dumps(message))
                    sent_count += 1
                except Exception as e:
                    logger.error(
                        f"❌ Error broadcasting to Figma plugin {client.id}: {e}"
                    )

        logger.info(f"📡 Broadcasted {command_type} to {sent_count} Figma plugins")
        return sent_count

    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()

        return {
            "host": self.host,
            "port": self.port,
            "is_running": self.is_running,
            "url": f"ws://{self.host}:{self.port}",
            "clients_connected": len(self.clients),
            "stats": {
                **self.stats,
                "start_time": self.stats["start_time"].isoformat()
                if self.stats["start_time"]
                else None,
                "uptime_seconds": uptime,
                "current_clients": len(self.clients),
                "server_info": {
                    "host": self.host,
                    "port": self.port,
                    "is_running": self.is_running,
                },
            },
            "capabilities": list(self.message_handlers.keys()),
        }
