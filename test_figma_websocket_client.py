#!/usr/bin/env python3
"""
Figma WebSocket Test Client

This script connects to the Figma WebSocket server and tests various message types
to verify the server is working correctly.

Usage:
    python test_figma_websocket_client.py
"""

import asyncio
import json
import time

import websockets


class FigmaWebSocketTestClient:
    """Test client for the Figma WebSocket server."""

    def __init__(self, uri: str = "ws://localhost:9003"):
        self.uri = uri
        self.websocket = None
        self.client_id = None
        self.connected = False

    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            print(f"🔌 Connecting to {self.uri}...")
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            print("✅ Connected successfully!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    async def disconnect(self):
        """Disconnect from the WebSocket server."""
        if self.websocket and self.connected:
            await self.websocket.close()
            self.connected = False
            print("🔌 Disconnected from server")

    async def send_message(self, message: dict):
        """Send a message to the server."""
        if not self.connected or not self.websocket:
            print("❌ Not connected to server")
            return

        try:
            message_str = json.dumps(message)
            await self.websocket.send(message_str)
            print(f"📤 Sent: {message}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")

    async def receive_message(self, timeout: float = 5.0):
        """Receive a message from the server."""
        if not self.connected or not self.websocket:
            print("❌ Not connected to server")
            return None

        try:
            message_str = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            message = json.loads(message_str)
            print(f"📥 Received: {message}")
            return message
        except asyncio.TimeoutError:
            print(f"⏰ No message received within {timeout} seconds")
            return None
        except Exception as e:
            print(f"❌ Error receiving message: {e}")
            return None

    async def test_welcome_message(self):
        """Test receiving the welcome message."""
        print("\n🧪 Testing welcome message...")
        message = await self.receive_message()
        if message and message.get("type") == "welcome":
            self.client_id = message.get("client_id")
            print(f"✅ Welcome message received! Client ID: {self.client_id}")
            print(
                f"   Server capabilities: {message.get('server_info', {}).get('capabilities', [])}"
            )
            return True
        else:
            print("❌ Expected welcome message not received")
            return False

    async def test_ping(self):
        """Test ping/pong functionality."""
        print("\n🧪 Testing ping/pong...")
        ping_message = {"type": "ping", "test_id": f"test_{int(time.time())}"}

        await self.send_message(ping_message)
        response = await self.receive_message()

        if response and response.get("type") == "pong":
            print("✅ Ping/pong test successful!")
            return True
        else:
            print("❌ Ping/pong test failed")
            return False

    async def test_plugin_info(self):
        """Test sending plugin info."""
        print("\n🧪 Testing plugin info...")
        plugin_info_message = {
            "type": "plugin_info",
            "plugin_info": {
                "name": "Test Figma Plugin",
                "version": "1.0.0",
                "capabilities": ["document_info", "design_commands"],
            },
        }

        await self.send_message(plugin_info_message)
        response = await self.receive_message()

        if response and response.get("type") == "plugin_info_received":
            print("✅ Plugin info test successful!")
            return True
        else:
            print("❌ Plugin info test failed")
            return False

    async def test_document_update(self):
        """Test sending document update."""
        print("\n🧪 Testing document update...")
        document_update_message = {
            "type": "document_update",
            "document_info": {
                "document": {"id": "test_doc_123", "name": "Test Document"},
                "currentPage": {"id": "page_456", "name": "Page 1"},
                "selection": [],
                "viewport": {"center": {"x": 0, "y": 0}, "zoom": 1.0},
            },
        }

        await self.send_message(document_update_message)
        # Document updates typically don't get a response
        print("✅ Document update sent (no response expected)")
        return True

    async def test_get_server_status(self):
        """Test getting server status."""
        print("\n🧪 Testing get server status...")
        status_message = {"type": "get_server_status"}

        await self.send_message(status_message)
        response = await self.receive_message()

        if response and response.get("type") == "server_status":
            print("✅ Server status test successful!")
            print(
                f"   Server uptime: {response.get('status', {}).get('uptime_seconds', 'unknown')} seconds"
            )
            return True
        else:
            print("❌ Server status test failed")
            return False

    async def test_unknown_message(self):
        """Test sending an unknown message type."""
        print("\n🧪 Testing unknown message type...")
        unknown_message = {"type": "unknown_test_message", "data": "test"}

        await self.send_message(unknown_message)
        response = await self.receive_message()

        if response and response.get("type") == "error":
            print("✅ Unknown message type handled correctly!")
            print(f"   Error: {response.get('error')}")
            return True
        else:
            print("❌ Unknown message type test failed")
            return False

    async def run_all_tests(self):
        """Run all tests."""
        print("🚀 Starting Figma WebSocket Server Tests")
        print("=" * 50)

        # Connect to server
        if not await self.connect():
            return False

        try:
            # Run tests
            tests = [
                ("Welcome Message", self.test_welcome_message),
                ("Ping/Pong", self.test_ping),
                ("Plugin Info", self.test_plugin_info),
                ("Document Update", self.test_document_update),
                ("Server Status", self.test_get_server_status),
                ("Unknown Message", self.test_unknown_message),
            ]

            passed = 0
            total = len(tests)

            for test_name, test_func in tests:
                try:
                    if await test_func():
                        passed += 1
                except Exception as e:
                    print(f"❌ {test_name} test failed with exception: {e}")

            print("\n" + "=" * 50)
            print(f"📊 Test Results: {passed}/{total} tests passed")

            if passed == total:
                print(
                    "🎉 All tests passed! Figma WebSocket server is working correctly."
                )
            else:
                print("⚠️ Some tests failed. Check the server implementation.")

            return passed == total

        finally:
            await self.disconnect()


async def main():
    """Main function to run the tests."""
    client = FigmaWebSocketTestClient()

    try:
        success = await client.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
