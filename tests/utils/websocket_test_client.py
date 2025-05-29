"""
WebSocket test client utility for testing the WebSocket Mock MCP server.

This utility provides a simple WebSocket client that can connect to the
WebSocket Mock server and interact with it for testing and demonstration purposes.
"""

import asyncio
import json
import sys
import time
from typing import Any, Dict, Optional

import websockets
from websockets.client import WebSocketClientProtocol


class WebSocketTestClient:
    """Simple WebSocket client for testing the WebSocket Mock server."""

    def __init__(self, host: str = "localhost", port: int = 9004):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.client_id: Optional[str] = None
        self.running = False

    async def connect(self) -> bool:
        """Connect to the WebSocket server."""
        try:
            print(f"🔗 Connecting to WebSocket server at {self.uri}...")
            self.websocket = await websockets.connect(self.uri)

            # Receive welcome message
            welcome_message = await self.websocket.recv()
            welcome_data = json.loads(welcome_message)

            if welcome_data.get("type") == "welcome":
                self.client_id = welcome_data.get("client_id")
                print(f"✅ Connected successfully! Client ID: {self.client_id}")
                print(
                    f"📋 Server capabilities: {welcome_data['server_info']['capabilities']}"
                )
                return True
            else:
                print(f"❌ Unexpected welcome message: {welcome_data}")
                return False

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.client_id = None
            print("🔌 Disconnected from WebSocket server")

    async def send_message(
        self, message_type: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Send a message to the WebSocket server and return the response."""
        if not self.websocket:
            print("❌ Not connected to WebSocket server")
            return None

        message = {"type": message_type, **kwargs}

        try:
            print(f"📤 Sending: {json.dumps(message, indent=2)}")
            await self.websocket.send(json.dumps(message))

            # Wait for response
            response = await self.websocket.recv()
            response_data = json.loads(response)

            print(f"📥 Received: {json.dumps(response_data, indent=2)}")
            return response_data

        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return None

    async def ping(self) -> Optional[Dict[str, Any]]:
        """Send a ping message."""
        return await self.send_message("ping", test_id=f"ping_{int(time.time())}")

    async def echo(self, message: str) -> Optional[Dict[str, Any]]:
        """Send an echo message."""
        return await self.send_message("echo", message=message, timestamp=time.time())

    async def broadcast(self, message: str) -> Optional[Dict[str, Any]]:
        """Send a broadcast message."""
        return await self.send_message("broadcast", message=message)

    async def get_clients(self) -> Optional[Dict[str, Any]]:
        """Get list of connected clients."""
        return await self.send_message("get_clients")

    async def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get server statistics."""
        return await self.send_message("get_stats")

    async def simulate_delay(
        self, delay_seconds: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """Test delay simulation."""
        return await self.send_message("simulate_delay", delay_seconds=delay_seconds)

    async def test_error(self, error_type: str = "generic") -> Optional[Dict[str, Any]]:
        """Test error handling."""
        return await self.send_message("error_test", error_type=error_type)

    async def listen_for_messages(self):
        """Listen for incoming messages (for broadcasts, etc.)."""
        if not self.websocket:
            print("❌ Not connected to WebSocket server")
            return

        print("👂 Listening for incoming messages... (Press Ctrl+C to stop)")
        self.running = True

        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    message_data = json.loads(message)

                    if (
                        message_data.get("type") != "pong"
                    ):  # Don't spam with pong messages
                        print(f"📨 Incoming: {json.dumps(message_data, indent=2)}")

                except asyncio.TimeoutError:
                    continue  # Continue listening
                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Connection closed by server")
                    break

        except KeyboardInterrupt:
            print("\n⏹️ Stopped listening")
        finally:
            self.running = False

    async def interactive_session(self):
        """Run an interactive session with the WebSocket server."""
        if not await self.connect():
            return

        print("\n🎮 Interactive WebSocket Test Client")
        print("Available commands:")
        print("  ping          - Send a ping message")
        print("  echo <msg>    - Send an echo message")
        print("  broadcast <msg> - Send a broadcast message")
        print("  clients       - Get list of connected clients")
        print("  stats         - Get server statistics")
        print("  delay <sec>   - Test delay simulation")
        print("  error <type>  - Test error handling")
        print("  listen        - Listen for incoming messages")
        print("  quit          - Disconnect and exit")
        print()

        try:
            while True:
                command = input("📝 Enter command: ").strip().split()

                if not command:
                    continue

                cmd = command[0].lower()

                if cmd == "quit":
                    break
                elif cmd == "ping":
                    await self.ping()
                elif cmd == "echo":
                    message = (
                        " ".join(command[1:])
                        if len(command) > 1
                        else "Hello WebSocket!"
                    )
                    await self.echo(message)
                elif cmd == "broadcast":
                    message = (
                        " ".join(command[1:])
                        if len(command) > 1
                        else "Broadcast message"
                    )
                    await self.broadcast(message)
                elif cmd == "clients":
                    await self.get_clients()
                elif cmd == "stats":
                    await self.get_stats()
                elif cmd == "delay":
                    delay = float(command[1]) if len(command) > 1 else 1.0
                    await self.simulate_delay(delay)
                elif cmd == "error":
                    error_type = command[1] if len(command) > 1 else "generic"
                    await self.test_error(error_type)
                elif cmd == "listen":
                    await self.listen_for_messages()
                else:
                    print(f"❌ Unknown command: {cmd}")

                print()  # Add spacing between commands

        except KeyboardInterrupt:
            print("\n⏹️ Interrupted")
        finally:
            await self.disconnect()


async def run_test_scenarios(client: WebSocketTestClient):
    """Run a series of test scenarios."""
    print("🧪 Running WebSocket test scenarios...")

    if not await client.connect():
        return

    try:
        # Test 1: Basic ping-pong
        print("\n🧪 Test 1: Ping-Pong")
        await client.ping()

        # Test 2: Echo functionality
        print("\n🧪 Test 2: Echo")
        await client.echo("This is a test echo message!")

        # Test 3: Get server stats
        print("\n🧪 Test 3: Server Statistics")
        await client.get_stats()

        # Test 4: Get client list
        print("\n🧪 Test 4: Client List")
        await client.get_clients()

        # Test 5: Delay simulation
        print("\n🧪 Test 5: Delay Simulation (2 seconds)")
        start_time = time.time()
        await client.simulate_delay(2.0)
        end_time = time.time()
        print(f"⏱️ Actual delay: {end_time - start_time:.2f} seconds")

        # Test 6: Error handling
        print("\n🧪 Test 6: Error Handling")
        await client.test_error("generic")

        # Test 7: Broadcast (won't see response since we're the only client)
        print("\n🧪 Test 7: Broadcast")
        await client.broadcast("Test broadcast message from test client")

        print("\n✅ All test scenarios completed!")

    finally:
        await client.disconnect()


async def main():
    """Main function for the WebSocket test client."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Run automated test scenarios
            client = WebSocketTestClient()
            await run_test_scenarios(client)
        elif sys.argv[1] == "interactive":
            # Run interactive session
            client = WebSocketTestClient()
            await client.interactive_session()
        else:
            print("Usage: python websocket_test_client.py [test|interactive]")
    else:
        # Default to interactive mode
        client = WebSocketTestClient()
        await client.interactive_session()


if __name__ == "__main__":
    asyncio.run(main())
