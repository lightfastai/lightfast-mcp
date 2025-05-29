"""
WebSocket server implementation for the WebSocket Mock MCP server.

This module provides a WebSocket server that can handle multiple client connections
and process various types of messages for testing and development purposes.
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

logger = get_logger("WebSocketServer")


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""

    id: str
    websocket: WebSocketServerProtocol
    connected_at: datetime = field(default_factory=datetime.now)
    last_ping: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert client to dictionary representation."""
        return {
            "id": self.id,
            "connected_at": self.connected_at.isoformat(),
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "metadata": self.metadata,
            "remote_address": f"{self.websocket.remote_address[0]}:{self.websocket.remote_address[1]}"
            if self.websocket.remote_address
            else "unknown",
        }


class WebSocketMockServer:
    """WebSocket server for handling mock MCP communications."""

    def __init__(self, host: str = "localhost", port: int = 9004):
        self.host = host
        self.port = port
        self.server: Optional[websockets.WebSocketServer] = None
        self.clients: Dict[str, WebSocketClient] = {}
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
                "echo": self._handle_echo,
                "broadcast": self._handle_broadcast,
                "get_clients": self._handle_get_clients,
                "get_stats": self._handle_get_stats,
                "simulate_delay": self._handle_simulate_delay,
                "error_test": self._handle_error_test,
            }
        )

    async def start(self) -> bool:
        """Start the WebSocket server."""
        if self.is_running:
            logger.warning("WebSocket server is already running")
            return True

        try:
            logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

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
                f"✅ WebSocket server started successfully on ws://{self.host}:{self.port}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            self.is_running = False
            return False

    async def stop(self):
        """Stop the WebSocket server."""
        if not self.is_running:
            logger.warning("WebSocket server is not running")
            return

        logger.info("Stopping WebSocket server...")

        # Close all client connections
        if self.clients:
            logger.info(f"Closing {len(self.clients)} client connections...")
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
        logger.info("✅ WebSocket server stopped")

    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str = "/"):
        """Handle a new client connection."""
        client_id = str(uuid.uuid4())[:8]
        client = WebSocketClient(id=client_id, websocket=websocket)

        self.clients[client_id] = client
        self.stats["total_connections"] += 1

        logger.info(
            f"📱 New client connected: {client_id} from {websocket.remote_address}"
        )

        # Send welcome message
        welcome_message = {
            "type": "welcome",
            "client_id": client_id,
            "server_info": {
                "name": "WebSocket Mock Server",
                "version": "1.0.0",
                "capabilities": list(self.message_handlers.keys()),
            },
            "timestamp": time.time(),
        }

        try:
            await websocket.send(json.dumps(welcome_message))

            # Handle messages from this client
            async for message in websocket:
                await self._process_message(client, message)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📱 Client {client_id} disconnected normally")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_id}: {e}")
            self.stats["errors"] += 1
        finally:
            # Clean up client
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info(f"🧹 Cleaned up client {client_id}")

    async def _process_message(self, client: WebSocketClient, message: str):
        """Process a message from a client."""
        try:
            data = json.loads(message)
            self.stats["total_messages"] += 1

            message_type = data.get("type", "unknown")
            logger.debug(f"📨 Received message from {client.id}: {message_type}")

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
            logger.error(f"❌ Invalid JSON from client {client.id}: {e}")
            error_response = {
                "type": "error",
                "error": f"Invalid JSON: {str(e)}",
                "timestamp": time.time(),
            }
            await client.websocket.send(json.dumps(error_response))
        except Exception as e:
            logger.error(f"❌ Error processing message from client {client.id}: {e}")
            self.stats["errors"] += 1

    # Message handlers
    async def _handle_ping(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle ping message."""
        return {
            "type": "pong",
            "client_id": client.id,
            "timestamp": time.time(),
            "server_time": datetime.now().isoformat(),
        }

    async def _handle_echo(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle echo message."""
        return {
            "type": "echo_response",
            "client_id": client.id,
            "original_message": data,
            "timestamp": time.time(),
        }

    async def _handle_broadcast(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Handle broadcast message to all clients."""
        message = data.get("message", "")
        broadcast_data = {
            "type": "broadcast",
            "from_client": client.id,
            "message": message,
            "timestamp": time.time(),
        }

        # Send to all other clients
        broadcast_tasks = []
        for other_client in self.clients.values():
            if other_client.id != client.id and not self._is_websocket_closed(
                other_client.websocket
            ):
                broadcast_tasks.append(
                    other_client.websocket.send(json.dumps(broadcast_data))
                )

        if broadcast_tasks:
            await asyncio.gather(*broadcast_tasks, return_exceptions=True)

        # Confirm to sender
        return {
            "type": "broadcast_sent",
            "client_id": client.id,
            "recipients": len(broadcast_tasks),
            "timestamp": time.time(),
        }

    async def _handle_get_clients(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get clients request."""
        return {
            "type": "clients_list",
            "client_id": client.id,
            "clients": [c.to_dict() for c in self.clients.values()],
            "total_clients": len(self.clients),
            "timestamp": time.time(),
        }

    async def _handle_get_stats(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle get stats request."""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()

        return {
            "type": "server_stats",
            "client_id": client.id,
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
            "timestamp": time.time(),
        }

    async def _handle_simulate_delay(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle simulate delay request."""
        delay = data.get("delay_seconds", 1.0)
        delay = max(0, min(delay, 10))  # Limit delay to 0-10 seconds

        await asyncio.sleep(delay)

        return {
            "type": "delay_completed",
            "client_id": client.id,
            "delay_seconds": delay,
            "timestamp": time.time(),
        }

    async def _handle_error_test(
        self, client: WebSocketClient, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle error test request."""
        error_type = data.get("error_type", "generic")

        if error_type == "exception":
            raise Exception("Simulated exception for testing")
        elif error_type == "timeout":
            await asyncio.sleep(15)  # Simulate timeout
        elif error_type == "invalid_json":
            # This would normally cause JSON encoding error, but we'll simulate it
            return {
                "type": "error_test_response",
                "error_type": error_type,
                "message": "Simulated invalid JSON error",
                "timestamp": time.time(),
            }
        else:
            return {
                "type": "error_test_response",
                "client_id": client.id,
                "error_type": error_type,
                "message": f"Simulated error of type: {error_type}",
                "timestamp": time.time(),
            }

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
