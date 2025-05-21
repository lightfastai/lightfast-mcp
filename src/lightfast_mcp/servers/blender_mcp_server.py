import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from ..exceptions import (
    BlenderCommandError,
    BlenderConnectionError,
    BlenderMCPError,
    BlenderResponseError,
    BlenderTimeoutError,
)

# Import from your new logging utility
from ..utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("BlenderMCPClient")


@dataclass
class BlenderConnection:
    host: str
    port: int
    sock: socket.socket = None

    def connect(self) -> bool:
        """Connect to the Blender addon socket server"""
        if self.sock:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Blender at {self.host}:{self.port}")
            return True
        except TimeoutError as e:
            logger.error(f"Timeout during connection to Blender: {str(e)}")
            self.sock = None
            raise BlenderTimeoutError(f"Timeout connecting to Blender at {self.host}:{self.port}") from e
        except OSError as e:  # Catches various socket-related errors including ConnectionRefusedError
            logger.error(f"Socket error connecting to Blender: {str(e)}")
            self.sock = None
            # Re-raise as a specific connection error
            raise BlenderConnectionError(
                f"Failed to connect to Blender at {self.host}:{self.port} (Socket error: {e})"
            ) from e
        except Exception as e:  # Catch any other unexpected errors during connection
            logger.error(f"Unexpected error connecting to Blender: {str(e)}")
            self.sock = None
            raise BlenderConnectionError(f"Unexpected error connecting to Blender: {str(e)}") from e

    def disconnect(self):
        """Disconnect from the Blender addon"""
        if self.sock:
            try:
                self.sock.close()
                logger.info("Disconnected from Blender.")
            except OSError as e:  # Changed from Exception to socket.error for more specificity
                logger.error(f"Socket error during disconnect from Blender: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, buffer_size=8192, timeout=15.0) -> bytes:
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        if not self.sock:
            raise BlenderConnectionError("Cannot receive response: socket not connected.")

        self.sock.settimeout(timeout)

        try:
            while True:
                try:
                    chunk = self.sock.recv(buffer_size)
                    if not chunk:  # Connection closed by peer
                        if not chunks:
                            raise BlenderConnectionError("Connection closed by Blender before sending any data.")
                        logger.info(
                            "Connection closed by Blender after sending partial data. Processing received data."
                        )
                        break
                    chunks.append(chunk)
                    try:
                        # Try to parse to see if we have a complete JSON object
                        data_so_far = b"".join(chunks)
                        json.loads(data_so_far.decode("utf-8"))
                        logger.debug(f"Received complete JSON response ({len(data_so_far)} bytes)")
                        return data_so_far  # Return as soon as a full JSON is detected
                    except json.JSONDecodeError:
                        # Not a complete JSON object yet, continue receiving
                        logger.debug("Partial JSON received, continuing for more data...")
                        continue
                except TimeoutError:
                    logger.warning("Socket timeout during chunked receive.")
                    if not chunks:
                        raise BlenderTimeoutError("Timeout waiting for data from Blender (no data received).")
                    else:  # Timeout with partial data
                        logger.info("Socket timeout with partial data. Attempting to process what was received.")
                        break  # Break to process partial data
                except OSError as e:  # Catch socket-level errors during recv
                    raise BlenderConnectionError(f"Socket error during receive: {str(e)}") from e

            # This point is reached if loop broke (e.g. connection closed by peer after partial data, or timeout with partial data)
            if not chunks:
                # This case should ideally be covered by raises within the loop (e.g. timeout with no data)
                # Or if connection closed cleanly before any data was sent by peer after our request.
                raise BlenderResponseError("No data chunks received from Blender.")

            final_data = b"".join(chunks)
            try:
                # Final validation of the (potentially partial) data
                json.loads(final_data.decode("utf-8"))
                logger.debug(f"Validated final data ({len(final_data)} bytes) after receive loop completion.")
                return final_data
            except json.JSONDecodeError as e:
                logger.error(
                    f"Malformed or incomplete JSON response from Blender ({len(final_data)} bytes): {final_data[:200]}..."
                )
                raise BlenderResponseError(
                    f"Malformed JSON response from Blender: {e.msg}. Partial data: {final_data[:200]}"
                ) from e

        except BlenderMCPError:  # Re-raise our own errors
            raise
        except Exception as e:  # Catch-all for truly unexpected issues in this method
            logger.error(f"Unexpected error in receive_full_response: {type(e).__name__}: {str(e)}")
            raise BlenderMCPError(f"Unexpected issue in receive_full_response: {str(e)}") from e

    def send_command(self, command_type: str, params: dict[str, Any] = None) -> dict[str, Any]:
        """Send a command to Blender and return the response"""
        if not self.sock:  # Try to connect if not already connected or if connect() failed before
            try:
                self.connect()
            except BlenderConnectionError as e:  # Catch if connect() fails
                raise BlenderConnectionError(f"Cannot send command, connection attempt failed: {e}") from e

        if not self.sock:  # If still not connected after attempt
            raise BlenderConnectionError("Not connected to Blender. Ensure Blender is running and the addon is active.")

        command = {"type": command_type, "params": params or {}}
        try:
            logger.info(f"Sending command to Blender: {command_type} with params: {params}")
            self.sock.sendall(json.dumps(command).encode("utf-8"))

            response_data = self.receive_full_response()  # Can raise BlenderTimeout, BlenderConnection, BlenderResponse

            try:
                response = json.loads(response_data.decode("utf-8"))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response from Blender: {e}. Raw data: {response_data[:200]}...")
                raise BlenderResponseError(f"Invalid JSON structure in response from Blender: {e.msg}") from e

            logger.info(f"Response from Blender parsed. Status: {response.get('status', 'unknown')}")

            if response.get("status") == "error":
                error_message = response.get("message", "Unknown error from Blender")
                logger.error(f"Blender addon reported an error: {error_message}")
                raise BlenderCommandError(error_message)

            return response.get("result", {})

        except BlenderTimeoutError as e:
            logger.error(f"Timeout communicating with Blender for command '{command_type}': {e}")
            self.disconnect()  # Invalidate socket on timeout
            raise  # Re-raise

        except BlenderResponseError as e:
            logger.error(f"Response error from Blender for command '{command_type}': {e}")
            # self.disconnect()? A bad response doesn't always mean the connection is dead.
            raise

        except BlenderConnectionError as e:  # From receive_full_response or initial connect check
            logger.error(f"Connection error with Blender for command '{command_type}': {e}")
            self.disconnect()  # Definitely disconnect if connection is the issue
            raise

        except BlenderCommandError:  # Raised above if status is "error"
            # Already logged. Just re-raise.
            raise

        except OSError as e:  # For errors during sendall itself, or other unexpected socket issues
            logger.error(f"Socket error during send_command '{command_type}': {str(e)}")
            self.disconnect()
            raise BlenderConnectionError(f"Socket error sending command to Blender: {str(e)}") from e

        except Exception as e:  # Catch-all for other unexpected issues
            if isinstance(e, BlenderMCPError):  # Should have been caught by specific handlers
                raise

            logger.error(f"Unexpected error in send_command '{command_type}': {type(e).__name__}: {str(e)}")
            self.disconnect()  # Safer to disconnect on unknown errors
            raise BlenderMCPError(f"Unexpected error sending/receiving for command '{command_type}': {str(e)}") from e


# Global connection
_blender_connection: BlenderConnection = None


def get_blender_connection(host: str = "localhost", port: int = 9876) -> BlenderConnection:
    """Get or create a persistent Blender connection."""
    global _blender_connection
    if _blender_connection is not None and _blender_connection.sock is not None:  # Check sock too
        try:
            # Simple ping to check connection validity. send_command can raise BlenderMCPError subtypes.
            logger.debug("Pinging Blender to check existing connection...")
            _blender_connection.send_command("ping")  # "ping" should be a low-impact command on addon side
            logger.info("Reusing existing Blender connection.")
            return _blender_connection
        except BlenderMCPError as e:  # Catch our specific errors from send_command
            logger.warning(
                f"Existing Blender connection check (ping) failed: {type(e).__name__}: {str(e)}. Attempting to reconnect."
            )
            _blender_connection.disconnect()
            _blender_connection = None
        # Catch other unexpected errors during ping, treat as connection failure
        except Exception as e:
            logger.warning(f"Unexpected error during ping: {type(e).__name__}: {str(e)}. Invalidating connection.")
            _blender_connection.disconnect()
            _blender_connection = None

    logger.info(f"Attempting to establish new connection to Blender at {host}:{port}.")
    _blender_connection = BlenderConnection(host=host, port=port)
    try:
        _blender_connection.connect()  # Can raise BlenderConnectionError or BlenderTimeoutError
        # Verify with a ping after connect
        logger.debug("Verifying new connection with a ping...")
        _blender_connection.send_command("ping")
        logger.info("Successfully established and verified new Blender connection.")
    except BlenderMCPError as e:  # Catch errors from connect() or the verification ping
        logger.error(f"Failed to establish or verify new Blender connection: {type(e).__name__}: {str(e)}")
        if _blender_connection:  # Ensure disconnect if object exists but failed
            _blender_connection.disconnect()
        _blender_connection = None
        raise  # Re-raise the specific BlenderMCPError (e.g. BlenderConnectionError)

    return _blender_connection


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    try:
        logger.info("Blender MCP Server starting up...")
        # Attempt to establish connection on startup to verify Blender is accessible
        get_blender_connection()  # This will raise BlenderConnectionError etc. if fails
        logger.info("Initial connection to Blender successful and verified during startup.")
        yield {}  # Context for lifespan, not used by tools directly
    except BlenderMCPError as e:  # Catch our specific errors from get_blender_connection
        logger.error(
            f"Blender MCP Server failed to start: Could not connect/verify Blender. Error: {type(e).__name__}: {str(e)}"
        )
        raise  # Re-raise to prevent server from starting incorrectly
    except Exception as e:  # Catch any other unexpected errors
        logger.error(f"Unexpected error during Blender MCP server startup: {type(e).__name__}: {str(e)}")
        raise BlenderMCPError(f"Fatal server startup error: {str(e)}") from e
    finally:
        global _blender_connection
        if _blender_connection:
            logger.info("Blender MCP Server shutting down. Disconnecting from Blender.")
            _blender_connection.disconnect()
            _blender_connection = None
        else:
            logger.info("Blender MCP Server shutting down. No active Blender connection to close.")


mcp = FastMCP(
    "BlenderMCP",
    description="A simplified MCP server for basic Blender interaction.",
    lifespan=server_lifespan,
)


@mcp.tool()
async def get_state(ctx: Context) -> str:
    """
    Get detailed information about the current Blender scene.
    This corresponds to the 'get_scene_info' command in the Blender addon.
    """
    loop = asyncio.get_event_loop()
    try:
        logger.info("Executing get_state (get_scene_info) command.")
        # Run synchronous get_blender_connection and send_command in executor
        blender_conn = await loop.run_in_executor(None, get_blender_connection)
        result = await loop.run_in_executor(None, blender_conn.send_command, "get_scene_info")
        return json.dumps(result, indent=2)
    except BlenderMCPError as e:  # Catch specific Blender errors first
        logger.error(f"BlenderMCPError in get_state: {type(e).__name__}: {str(e)}")
        return json.dumps({"error": f"Blender Interaction Error: {str(e)}", "type": type(e).__name__}, indent=2)
    except Exception as e:  # Catch any other unexpected errors
        logger.error(f"Unexpected error in get_state: {type(e).__name__}: {str(e)}")
        return json.dumps({"error": f"Unexpected server error: {str(e)}", "type": type(e).__name__}, indent=2)


@mcp.tool()
async def execute_command(ctx: Context, code_to_execute: str) -> str:
    """
    Execute arbitrary Python code in Blender.
    This corresponds to the 'execute_code' command in the Blender addon.

    Parameters:
    - code_to_execute: The Python code string to execute in Blender's context.
    """
    loop = asyncio.get_event_loop()
    try:
        logger.info(f"Executing execute_command with code: {code_to_execute[:100]}...")
        blender_conn = await loop.run_in_executor(None, get_blender_connection)
        result = await loop.run_in_executor(None, blender_conn.send_command, "execute_code", {"code": code_to_execute})
        return json.dumps(result, indent=2)
    except BlenderMCPError as e:  # Catch specific Blender errors
        logger.error(f"BlenderMCPError in execute_command: {type(e).__name__}: {str(e)}")
        return json.dumps({"error": f"Blender Command Execution Error: {str(e)}", "type": type(e).__name__}, indent=2)
    except Exception as e:  # Catch any other unexpected errors
        logger.error(f"Unexpected error in execute_command: {type(e).__name__}: {str(e)}")
        return json.dumps(
            {"error": f"Unexpected server error during command execution: {str(e)}", "type": type(e).__name__}, indent=2
        )


def main():
    """Run the Simplified Blender MCP server."""
    logger.info(f"Initializing Blender MCP Server ({mcp.name}) for host communication.")
    mcp.run()


if __name__ == "__main__":
    main()
