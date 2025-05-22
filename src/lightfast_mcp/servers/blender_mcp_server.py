import asyncio
import json
import socket
import time
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
    sock: socket.socket | None = None

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
            except OSError as e:
                logger.error(f"Socket error during disconnect from Blender: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, buffer_size=8192) -> bytes:
        """Receive the complete response, potentially in multiple chunks"""
        chunks: list[bytes] = []
        if not self.sock:
            raise BlenderConnectionError("Cannot receive response: socket not connected.")

        # Use a consistent timeout value, with extended time for ping checks
        timeout = 15.0  # Default timeout
        if getattr(self, "_is_ping_check", False):
            timeout = 30.0  # Longer timeout for initial ping check
            logger.info(f"Using extended timeout ({timeout}s) for initial ping verification")

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
                        # Try to find valid JSON in the received data
                        # This handles both newline-terminated and non-newline-terminated responses
                        data_str = data_so_far.decode("utf-8")

                        # Find the end of the JSON object by tracking { and }
                        json_end = -1
                        open_braces = 0
                        for i, char in enumerate(data_str):
                            if char == "{":
                                open_braces += 1
                            elif char == "}":
                                open_braces -= 1
                                if open_braces == 0:
                                    json_end = i
                                    break

                        if json_end != -1:
                            # We found a complete JSON object
                            json_str = data_str[: json_end + 1]
                            # Validate the JSON
                            json.loads(json_str)
                            logger.info(f"Received complete JSON response ({len(json_str)} bytes)")
                            return json_str.encode("utf-8")

                        # If we couldn't find a complete JSON with brace matching, try a simple parse
                        # just in case the response is very simple (handles cases like {"foo": "bar"})
                        json.loads(data_str)
                        logger.info(f"Received complete JSON response ({len(data_str)} bytes)")
                        return data_so_far
                    except json.JSONDecodeError:
                        # Not a complete JSON object yet, continue receiving
                        logger.debug("Partial JSON received, continuing for more data...")
                        continue
                except TimeoutError:
                    logger.warning("Socket timeout during chunked receive.")
                    # If we hit a timeout, break the loop and try to use what we have
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise BlenderConnectionError(f"Socket connection error during receive: {str(e)}") from e
                except OSError as e:  # Catch other socket-level errors during recv
                    raise BlenderConnectionError(f"Socket error during receive: {str(e)}") from e
        except BlenderMCPError:
            # Re-raise our own errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error in receive_full_response: {type(e).__name__}: {str(e)}")
            raise BlenderMCPError(f"Unexpected issue in receive_full_response: {str(e)}") from e

        # If we get here, we either timed out or broke out of the loop
        # Try to use what we have
        if chunks:
            final_data = b"".join(chunks)
            logger.info(f"Attempting to process partial data after receive completion ({len(final_data)} bytes)")
            try:
                # Try to parse what we have
                json.loads(final_data.decode("utf-8"))
                return final_data
            except json.JSONDecodeError as e:
                logger.error(f"Malformed or incomplete JSON response from Blender ({len(final_data)} bytes)")
                raise BlenderResponseError(
                    f"Malformed JSON response from Blender: {e.msg}. "
                    f"Partial data: {final_data[:200].decode('utf-8', 'replace')}"
                ) from e
        else:
            raise BlenderResponseError("No data chunks received from Blender.")

    def send_command(self, command_type: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a command to Blender and return the response"""
        if not self.sock:  # Try to connect if not already connected
            try:
                self.connect()
            except BlenderConnectionError as e:
                raise BlenderConnectionError(f"Cannot send command, connection attempt failed: {e}") from e

        if not self.sock:  # If still not connected after attempt
            raise BlenderConnectionError("Not connected to Blender. Ensure Blender is running and the addon is active.")

        # Mark if this is a ping command for initial verification
        self._is_ping_check = command_type == "ping" and not hasattr(self, "_ping_sent")
        if self._is_ping_check:
            self._ping_sent = True

        command = {"type": command_type, "params": params or {}}
        try:
            logger.info(f"Sending command to Blender: {command_type} with params: {params}")
            self.sock.sendall(json.dumps(command).encode("utf-8"))

            # For ping commands, use a more aggressive timeout approach
            if command_type == "ping":
                # Shorter timeout for ping
                ping_timeout = 5.0
                logger.info(f"Using shorter timeout ({ping_timeout}s) for ping command")

                # Set a shorter timeout for just this operation
                old_timeout = self.sock.gettimeout()
                self.sock.settimeout(ping_timeout)

                try:
                    # Just read a small amount of data synchronously for ping
                    raw_data = self.sock.recv(8192)
                    if not raw_data:
                        raise BlenderConnectionError("Connection closed by Blender during ping")

                    try:
                        # Parse the ping response directly
                        response = json.loads(raw_data.decode("utf-8"))
                        logger.info(f"Received ping response: {response}")

                        if response.get("status") == "error":
                            error_message = response.get("message", "Unknown error from Blender")
                            logger.error(f"Blender addon reported an error: {error_message}")
                            raise BlenderCommandError(error_message)

                        return response.get("result", {})
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in ping response: {e}")
                        raise BlenderResponseError(f"Invalid ping response: {e}") from e
                finally:
                    # Restore the original timeout
                    self.sock.settimeout(old_timeout)
            else:
                # For normal commands, use the standard receive method
                response_data = self.receive_full_response()

                try:
                    response = json.loads(response_data.decode("utf-8"))
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode JSON response from Blender: {e}. "
                        f"Raw data: {response_data[:200].decode('utf-8', 'replace')}..."
                    )
                    raise BlenderResponseError(f"Invalid JSON structure in response from Blender: {e.msg}") from e

                logger.info(f"Response from Blender parsed. Status: {response.get('status', 'unknown')}")

                if response.get("status") == "error":
                    error_message = response.get("message", "Unknown error from Blender")
                    logger.error(f"Blender addon reported an error: {error_message}")
                    raise BlenderCommandError(error_message)

                return response.get("result", {})

        except TimeoutError:
            logger.error("Socket timeout while waiting for response from Blender")
            self.disconnect()  # Invalidate socket on timeout
            raise BlenderTimeoutError(f"Timeout waiting for Blender response for command '{command_type}'") from None

        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.disconnect()
            raise BlenderConnectionError(f"Connection to Blender lost: {str(e)}") from e

        except (BlenderTimeoutError, BlenderConnectionError, BlenderResponseError, BlenderCommandError):
            # Re-raise our specific errors
            self.disconnect()  # Disconnect on any Blender-specific error
            raise

        except OSError as e:
            logger.error(f"Socket error during send_command '{command_type}': {str(e)}")
            self.disconnect()
            raise BlenderConnectionError(f"Socket error sending command to Blender: {str(e)}") from e

        except Exception as e:
            logger.error(f"Unexpected error in send_command '{command_type}': {type(e).__name__}: {str(e)}")
            self.disconnect()  # Safer to disconnect on unknown errors
            raise BlenderMCPError(f"Unexpected error sending/receiving for command '{command_type}': {str(e)}") from e


# Global connection
_blender_connection: BlenderConnection | None = None


def check_blender_running(host="localhost", port=9876, timeout=2.0) -> bool:
    """
    Quick check if Blender is running with the addon active.
    Returns True if socket connection is possible, False otherwise.
    """
    try:
        logger.info(f"Checking if Blender is running on {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        logger.info(f"Successfully connected to Blender on {host}:{port}")
        sock.close()
        return True
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        logger.warning(f"Could not connect to Blender: {type(e).__name__}: {str(e)}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking if Blender is running: {type(e).__name__}: {str(e)}")
        return False


def find_blender_port(host="localhost", start_port=9876, end_port=9886, timeout=0.5):
    """
    Try to find which port Blender is listening on by scanning a range of ports.
    Returns the port number if found, None otherwise.
    """
    logger.info(f"Scanning for Blender on ports {start_port} to {end_port}...")
    for port in range(start_port, end_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))

            if result == 0:  # Port is open
                logger.info(f"Found open port at {port}")
                sock.close()

                # Try sending a simple ping to verify it's a Blender server
                try:
                    logger.info(f"Testing if port {port} is a Blender server...")
                    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_sock.settimeout(2.0)  # Short timeout for ping test
                    test_sock.connect((host, port))

                    # Send a ping command
                    ping_cmd = json.dumps({"type": "ping", "params": {}}).encode("utf-8")
                    test_sock.sendall(ping_cmd)

                    # Try to get a response
                    response_data = test_sock.recv(8192)
                    test_sock.close()

                    if response_data:
                        try:
                            response = json.loads(response_data.decode("utf-8"))
                            # Check if it looks like a Blender response
                            if response.get("status") == "success":
                                logger.info(f"Verified Blender running on port {port}")
                                return port
                        except json.JSONDecodeError:
                            logger.debug(f"Port {port} did not return valid JSON")
                            continue
                except Exception as e:
                    logger.debug(f"Port {port} is open but not a Blender server: {e}")
                    continue
            else:
                sock.close()
        except Exception as e:
            logger.debug(f"Error checking port {port}: {e}")
            continue

    logger.warning(f"No Blender server found on ports {start_port}-{end_port}")
    return None


def get_blender_connection(host: str = "localhost", port: int = 9876) -> BlenderConnection:
    """Get or create a persistent Blender connection."""
    global _blender_connection

    # Check if we have an existing connection
    if _blender_connection is not None and _blender_connection.sock is not None:  # Check sock too
        try:
            # Send a simple command directly rather than a complex ping
            logger.debug("Testing existing connection...")
            # Use a faster timeout for the socket test
            _blender_connection.sock.settimeout(2.0)
            # Just try to send something and see if it works
            _blender_connection.sock.sendall(b"test")

            # If we get here without an exception, the socket is likely still connected
            # Reset the socket timeout to normal
            _blender_connection.sock.settimeout(None)

            # Simple ping to verify the connection is still valid
            logger.debug("Pinging Blender to check existing connection...")
            _blender_connection.send_command("ping")
            logger.info("Reusing existing Blender connection.")
            return _blender_connection
        except (OSError, BlenderMCPError) as e:
            logger.warning(f"Existing connection check failed: {type(e).__name__}: {str(e)}. Attempting to reconnect.")
            if _blender_connection is not None:
                _blender_connection.disconnect()
            _blender_connection = None
        except Exception as e:
            logger.warning(
                f"Unexpected error during connection check: {type(e).__name__}: {str(e)}. Invalidating connection."
            )
            if _blender_connection is not None:
                _blender_connection.disconnect()
            _blender_connection = None

    # First try the specified port
    if check_blender_running(host=host, port=port):
        found_port = port
    else:
        # If that fails, try to scan for the correct port
        found_port = find_blender_port(host=host)
        if found_port:
            logger.info(f"Found Blender running on alternative port: {found_port}")
        else:
            # If no port was found, just try the default one
            logger.warning("Could not find Blender running on any port")
            found_port = port  # Fall back to the original port for consistency

    # Don't bother trying multiple times if the port scanning already failed
    if found_port != port and not check_blender_running(host=host, port=found_port):
        logger.error(f"Port {found_port} is not responding to connection attempts.")
        raise BlenderConnectionError(f"Cannot connect to Blender on {host}:{found_port}")

    # Try to create a new connection (fewer attempts if we had to scan for a port)
    max_attempts = 2  # Reduced from 3 to make failure faster when Blender is definitely not available
    attempt = 0

    # Initialize a new connection
    new_connection: BlenderConnection | None = None

    while attempt < max_attempts:
        attempt += 1
        logger.info(
            f"Attempting to establish new connection to Blender at {host}:{found_port} "
            f"(attempt {attempt}/{max_attempts})."
        )
        new_connection = BlenderConnection(host=host, port=found_port)
        try:
            new_connection.connect()  # Can raise BlenderConnectionError or BlenderTimeoutError

            # Verify with a ping after connect
            logger.debug("Verifying new connection with a ping...")
            new_connection.send_command("ping")
            logger.info(
                f"Successfully established and verified new Blender connection (attempt {attempt}/{max_attempts})."
            )
            # Update the global connection
            _blender_connection = new_connection
            return new_connection
        except BlenderMCPError as e:  # Catch errors from connect() or the verification ping
            logger.warning(f"Connection attempt {attempt}/{max_attempts} failed: {type(e).__name__}: {str(e)}")
            if new_connection:  # Ensure disconnect if object exists but failed
                new_connection.disconnect()
            new_connection = None

            # Short delay before retrying
            if attempt < max_attempts:
                time.sleep(1)

    # If we get here, all attempts failed
    logger.error(f"Failed to establish Blender connection after {max_attempts} attempts.")
    raise BlenderConnectionError(f"Failed to establish Blender connection after {max_attempts} attempts.")


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    try:
        logger.info("Blender MCP Server starting up...")

        # First do a quick check if Blender is likely running with the addon active
        if not check_blender_running():
            logger.warning("Cannot connect to Blender. Please ensure Blender is running and the addon is active.")
            logger.warning("1. Open Blender")
            logger.warning("2. Install the addon (Edit > Preferences > Add-ons > Install)")
            logger.warning("3. Enable the Lightfast MCP addon")
            logger.warning("4. Start the MCP Server from the Lightfast MCP panel")
            logger.warning("Proceeding with server startup despite Blender connection failure.")
            # Continue startup despite failure - the server may be able to connect later
            # when Blender is started
        else:
            # Attempt to establish connection on startup to verify Blender is accessible
            try:
                get_blender_connection()  # This will raise BlenderConnectionError etc. if fails
                logger.info("Initial connection to Blender successful and verified during startup.")
            except BlenderTimeoutError as e:
                logger.warning(f"Connection to Blender timed out. Blender may be busy: {e}")
                logger.warning("Proceeding with server startup, but verification failed. Client operations may fail.")
                # Continue startup despite timeout - the server may still be able to connect later
            except BlenderMCPError as e:
                logger.warning(f"Could not connect to Blender during startup: {type(e).__name__}: {str(e)}")
                logger.warning("Proceeding with server startup despite Blender connection failure.")
                # Continue startup despite failure - the server may be able to connect later

        yield {}  # Context for lifespan, not used by tools directly
    except Exception as e:  # Catch any other unexpected errors
        logger.error(f"Unexpected error during Blender MCP server startup: {type(e).__name__}: {str(e)}")
        raise BlenderMCPError(f"Fatal server startup error: {str(e)}") from e
    finally:
        global _blender_connection
        if _blender_connection is not None:
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

        # Add diagnostic information about the connection
        result["_connection_info"] = {
            "connected": True,
            "host": blender_conn.host,
            "port": blender_conn.port,
            "connection_time": time.time(),
        }

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
