#!/usr/bin/env python3
"""Quick WebSocket connection test."""

import asyncio

import websockets


async def test():
    try:
        print("Attempting to connect...")
        websocket = await asyncio.wait_for(
            websockets.connect("ws://localhost:9003"), timeout=5.0
        )
        print("Connected! Waiting for welcome message...")
        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        print(f"Received: {message}")
        await websocket.close()
        print("Test completed successfully!")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test())
