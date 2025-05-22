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
    BlenderCommandError as PhotoshopCommandError,
)
from ..exceptions import (
    BlenderConnectionError as PhotoshopConnectionError,
)
from ..exceptions import (
    BlenderMCPError as PhotoshopMCPError,
)
from ..exceptions import (
    BlenderResponseError as PhotoshopResponseError,
)
from ..exceptions import (
    BlenderTimeoutError as PhotoshopTimeoutError,
)

# Import from your new logging utility
from ..utils.logging_utils import configure_logging, get_logger

# Configure logging
configure_logging(level="INFO")
logger = get_logger("PhotoshopMCPClient")


@dataclass
class PhotoshopConnection:
    host: str
    port: int
    sock: socket.socket = None

    def connect(self) -> bool:
        """Connect to the Photoshop socket server"""
        if self.sock:
            return True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Photoshop at {self.host}:{self.port}")
            return True
        except TimeoutError as e:
            logger.error(f"Timeout during connection to Photoshop: {str(e)}")
            self.sock = None
            raise PhotoshopTimeoutError(f"Timeout connecting to Photoshop at {self.host}:{self.port}") from e
        except OSError as e:  # Catches various socket-related errors including ConnectionRefusedError
            logger.error(f"Socket error connecting to Photoshop: {str(e)}")
            self.sock = None
            # Re-raise as a specific connection error
            raise PhotoshopConnectionError(
                f"Failed to connect to Photoshop at {self.host}:{self.port} (Socket error: {e})"
            ) from e
        except Exception as e:  # Catch any other unexpected errors during connection
            logger.error(f"Unexpected error connecting to Photoshop: {str(e)}")
            self.sock = None
            raise PhotoshopConnectionError(f"Unexpected error connecting to Photoshop: {str(e)}") from e

    def disconnect(self):
        """Disconnect from the Photoshop addon"""
        if self.sock:
            try:
                self.sock.close()
                logger.info("Disconnected from Photoshop.")
            except OSError as e:
                logger.error(f"Socket error during disconnect from Photoshop: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, buffer_size=8192) -> bytes:
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        if not self.sock:
            raise PhotoshopConnectionError("Cannot receive response: socket not connected.")

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
                            raise PhotoshopConnectionError("Connection closed by Photoshop before sending any data.")
                        logger.info(
                            "Connection closed by Photoshop after sending partial data. Processing received data."
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
                    raise PhotoshopConnectionError(f"Socket connection error during receive: {str(e)}") from e
                except OSError as e:  # Catch other socket-level errors during recv
                    raise PhotoshopConnectionError(f"Socket error during receive: {str(e)}") from e
        except PhotoshopMCPError:
            # Re-raise our own errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error in receive_full_response: {type(e).__name__}: {str(e)}")
            raise PhotoshopMCPError(f"Unexpected issue in receive_full_response: {str(e)}") from e

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
                logger.error(f"Malformed or incomplete JSON response from Photoshop ({len(final_data)} bytes)")
                raise PhotoshopResponseError(
                    f"Malformed JSON response from Photoshop: {e.msg}. Partial data: {final_data[:200]}"
                ) from e
        else:
            raise PhotoshopResponseError("No data chunks received from Photoshop.")

    def send_command(self, command_type: str, params: dict[str, Any] = None) -> dict[str, Any]:
        """Send a command to Photoshop and return the response"""
        if not self.sock:  # Try to connect if not already connected
            try:
                self.connect()
            except PhotoshopConnectionError as e:
                raise PhotoshopConnectionError(f"Cannot send command, connection attempt failed: {e}") from e

        if not self.sock:  # If still not connected after attempt
            raise PhotoshopConnectionError(
                "Not connected to Photoshop. Ensure Photoshop is running and the addon is active."
            )

        # Mark if this is a ping command for initial verification
        self._is_ping_check = command_type == "ping" and not hasattr(self, "_ping_sent")
        if self._is_ping_check:
            self._ping_sent = True

        command = {"type": command_type, "params": params or {}}
        try:
            logger.info(f"Sending command to Photoshop: {command_type} with params: {params}")
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
                        raise PhotoshopConnectionError("Connection closed by Photoshop during ping")

                    try:
                        # Parse the ping response directly
                        response = json.loads(raw_data.decode("utf-8"))
                        logger.info(f"Received ping response: {response}")

                        if response.get("status") == "error":
                            error_message = response.get("message", "Unknown error from Photoshop")
                            logger.error(f"Photoshop addon reported an error: {error_message}")
                            raise PhotoshopCommandError(error_message)

                        return response.get("result", {})
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in ping response: {e}")
                        raise PhotoshopResponseError(f"Invalid ping response: {e}") from e
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
                        f"Failed to decode JSON response from Photoshop: {e}. Raw data: {response_data[:200]}..."
                    )
                    raise PhotoshopResponseError(f"Invalid JSON structure in response from Photoshop: {e.msg}") from e

                logger.info(f"Response from Photoshop parsed. Status: {response.get('status', 'unknown')}")

                if response.get("status") == "error":
                    error_message = response.get("message", "Unknown error from Photoshop")
                    logger.error(f"Photoshop addon reported an error: {error_message}")
                    raise PhotoshopCommandError(error_message)

                return response.get("result", {})

        except TimeoutError:
            logger.error("Socket timeout while waiting for response from Photoshop")
            self.disconnect()  # Invalidate socket on timeout
            raise PhotoshopTimeoutError(
                f"Timeout waiting for Photoshop response for command '{command_type}'"
            ) from None

        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.disconnect()
            raise PhotoshopConnectionError(f"Connection to Photoshop lost: {str(e)}") from e

        except (PhotoshopTimeoutError, PhotoshopConnectionError, PhotoshopResponseError, PhotoshopCommandError):
            # Re-raise our specific errors
            self.disconnect()  # Disconnect on any Photoshop-specific error
            raise

        except OSError as e:
            logger.error(f"Socket error during send_command '{command_type}': {str(e)}")
            self.disconnect()
            raise PhotoshopConnectionError(f"Socket error sending command to Photoshop: {str(e)}") from e

        except Exception as e:
            logger.error(f"Unexpected error in send_command '{command_type}': {type(e).__name__}: {str(e)}")
            self.disconnect()  # Safer to disconnect on unknown errors
            raise PhotoshopMCPError(f"Unexpected error sending/receiving for command '{command_type}': {str(e)}") from e


# Global connection
_photoshop_connection: PhotoshopConnection = None


def check_photoshop_running(host="localhost", port=8765, timeout=2.0) -> bool:
    """
    Quick check if Photoshop is running with the addon active.
    Returns True if socket connection is possible, False otherwise.
    """
    try:
        logger.info(f"Checking if Photoshop is running on {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        logger.info(f"Successfully connected to Photoshop on {host}:{port}")
        sock.close()
        return True
    except (TimeoutError, ConnectionRefusedError, OSError) as e:
        logger.warning(f"Could not connect to Photoshop: {type(e).__name__}: {str(e)}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error checking if Photoshop is running: {type(e).__name__}: {str(e)}")
        return False


def find_photoshop_port(host="localhost", start_port=8765, end_port=8775, timeout=0.5):
    """
    Try to find which port Photoshop is listening on by scanning a range of ports.
    Returns the port number if found, None otherwise.
    """
    logger.info(f"Scanning for Photoshop on ports {start_port} to {end_port}...")
    for port in range(start_port, end_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))

            if result == 0:  # Port is open
                logger.info(f"Found open port at {port}")
                sock.close()

                # Try sending a simple ping to verify it's a Photoshop server
                try:
                    logger.info(f"Testing if port {port} is a Photoshop server...")
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
                            # Check if it looks like a Photoshop response
                            if response.get("status") == "success":
                                logger.info(f"Verified Photoshop running on port {port}")
                                return port
                        except json.JSONDecodeError:
                            logger.debug(f"Port {port} did not return valid JSON")
                            continue
                except Exception as e:
                    logger.debug(f"Port {port} is open but not a Photoshop server: {e}")
                    continue
            else:
                sock.close()
        except Exception as e:
            logger.debug(f"Error checking port {port}: {e}")
            continue

    logger.warning(f"No Photoshop server found on ports {start_port}-{end_port}")
    return None


def get_photoshop_connection(host: str = "localhost", port: int = 8765) -> PhotoshopConnection:
    """Get or create a persistent Photoshop connection."""
    global _photoshop_connection

    # Check if we have an existing connection
    if _photoshop_connection is not None and _photoshop_connection.sock is not None:
        try:
            # Send a simple command directly rather than a complex ping
            logger.debug("Testing existing connection...")
            # Use a faster timeout for the socket test
            _photoshop_connection.sock.settimeout(2.0)
            # Just try to send something and see if it works
            _photoshop_connection.sock.sendall(b"test")

            # If we get here without an exception, the socket is likely still connected
            # Reset the socket timeout to normal
            _photoshop_connection.sock.settimeout(None)

            # Simple ping to verify the connection is still valid
            logger.debug("Pinging Photoshop to check existing connection...")
            _photoshop_connection.send_command("ping")
            logger.info("Reusing existing Photoshop connection.")
            return _photoshop_connection
        except (OSError, PhotoshopMCPError) as e:
            logger.warning(f"Existing connection check failed: {type(e).__name__}: {str(e)}. Attempting to reconnect.")
            _photoshop_connection.disconnect()
            _photoshop_connection = None
        except Exception as e:
            logger.warning(
                f"Unexpected error during connection check: {type(e).__name__}: {str(e)}. Invalidating connection."
            )
            _photoshop_connection.disconnect()
            _photoshop_connection = None

    # First try the specified port
    if check_photoshop_running(host=host, port=port):
        found_port = port
    else:
        # If that fails, try to scan for the correct port
        found_port = find_photoshop_port(host=host)
        if found_port:
            logger.info(f"Found Photoshop running on alternative port: {found_port}")
        else:
            # If no port was found, just try the default one
            logger.warning("Could not find Photoshop running on any port")
            found_port = port  # Fall back to the original port for consistency

    # Don't bother trying multiple times if the port scanning already failed
    if found_port != port and not check_photoshop_running(host=host, port=found_port):
        logger.error(f"Port {found_port} is not responding to connection attempts.")
        raise PhotoshopConnectionError(f"Cannot connect to Photoshop on {host}:{found_port}")

    # Try to create a new connection (fewer attempts if we had to scan for a port)
    max_attempts = 2  # Reduced from 3 to make failure faster when Photoshop is definitely not available
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        logger.info(
            f"Attempting to establish new connection to Photoshop at {host}:{found_port} "
            f"(attempt {attempt}/{max_attempts})."
        )
        _photoshop_connection = PhotoshopConnection(host=host, port=found_port)
        try:
            _photoshop_connection.connect()

            # Verify with a ping after connect
            logger.debug("Verifying new connection with a ping...")
            _photoshop_connection.send_command("ping")
            logger.info(
                f"Successfully established and verified new Photoshop connection (attempt {attempt}/{max_attempts})."
            )
            return _photoshop_connection
        except PhotoshopMCPError as e:  # Catch errors from connect() or the verification ping
            logger.warning(f"Connection attempt {attempt}/{max_attempts} failed: {type(e).__name__}: {str(e)}")
            if _photoshop_connection:  # Ensure disconnect if object exists but failed
                _photoshop_connection.disconnect()
            _photoshop_connection = None

            # Short delay before retrying
            if attempt < max_attempts:
                time.sleep(1)

    # If we get here, all attempts failed
    logger.error(f"Failed to establish Photoshop connection after {max_attempts} attempts.")
    raise PhotoshopConnectionError(f"Failed to establish Photoshop connection after {max_attempts} attempts.")


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    try:
        logger.info("Photoshop MCP Server starting up...")

        # First do a quick check if Photoshop is likely running with the addon active
        if not check_photoshop_running():
            logger.warning("Cannot connect to Photoshop. Please ensure Photoshop is running and the addon is active.")
            logger.warning("1. Open Photoshop")
            logger.warning("2. Install the addon/plugin")
            logger.warning("3. Enable the Lightfast MCP addon for Photoshop")
            logger.warning("4. Start the MCP Server from the Lightfast MCP panel")
            logger.warning("Proceeding with server startup despite Photoshop connection failure.")
            # Continue startup despite failure - the server may be able to connect later
            # when Photoshop is started
        else:
            # Attempt to establish connection on startup to verify Photoshop is accessible
            try:
                get_photoshop_connection()  # This will raise PhotoshopConnectionError etc. if fails
                logger.info("Initial connection to Photoshop successful and verified during startup.")
            except PhotoshopTimeoutError as e:
                logger.warning(f"Connection to Photoshop timed out. Photoshop may be busy: {e}")
                logger.warning("Proceeding with server startup, but verification failed. Client operations may fail.")
                # Continue startup despite timeout - the server may still be able to connect later
            except PhotoshopMCPError as e:
                logger.warning(f"Could not connect to Photoshop during startup: {type(e).__name__}: {str(e)}")
                logger.warning("Proceeding with server startup despite Photoshop connection failure.")
                # Continue startup despite failure - the server may be able to connect later

        yield {}  # Context for lifespan, not used by tools directly
    except Exception as e:  # Catch any other unexpected errors
        logger.error(f"Unexpected error during Photoshop MCP server startup: {type(e).__name__}: {str(e)}")
        raise PhotoshopMCPError(f"Fatal server startup error: {str(e)}") from e
    finally:
        global _photoshop_connection
        if _photoshop_connection:
            logger.info("Photoshop MCP Server shutting down. Disconnecting from Photoshop.")
            _photoshop_connection.disconnect()
            _photoshop_connection = None
        else:
            logger.info("Photoshop MCP Server shutting down. No active Photoshop connection to close.")


mcp = FastMCP(
    "PhotoshopMCP",
    description="A simplified MCP server for basic Photoshop interaction.",
    lifespan=server_lifespan,
)


@mcp.tool()
async def get_document_info(ctx: Context) -> str:
    """
    Get detailed information about the current Photoshop document.
    This corresponds to the 'get_document_info' command in the Photoshop addon.
    """
    loop = asyncio.get_event_loop()
    try:
        logger.info("Executing get_document_info command.")
        # Run synchronous get_photoshop_connection and send_command in executor
        photoshop_conn = await loop.run_in_executor(None, get_photoshop_connection)
        result = await loop.run_in_executor(None, photoshop_conn.send_command, "get_document_info")

        # Add diagnostic information about the connection
        result["_connection_info"] = {
            "host": photoshop_conn.host,
            "port": photoshop_conn.port,
            "connected": photoshop_conn.sock is not None,
        }

        return json.dumps(result)
    except PhotoshopMCPError as e:
        logger.error(f"Error getting document info: {str(e)}")
        # Return error information as JSON
        error_result = {"status": "error", "message": str(e), "error_type": type(e).__name__}
        return json.dumps(error_result)


@mcp.tool()
async def execute_jsx(ctx: Context, jsx_code: str) -> str:
    """
    Execute JSX code in Photoshop.
    This allows running arbitrary JavaScript code in the Photoshop environment.
    """
    loop = asyncio.get_event_loop()
    try:
        logger.info("Executing execute_jsx command.")
        # Run synchronous get_photoshop_connection and send_command in executor
        photoshop_conn = await loop.run_in_executor(None, get_photoshop_connection)
        result = await loop.run_in_executor(None, photoshop_conn.send_command, "execute_jsx", {"code": jsx_code})

        return json.dumps(result)
    except PhotoshopMCPError as e:
        logger.error(f"Error executing JSX code: {str(e)}")
        # Return error information as JSON
        error_result = {"status": "error", "message": str(e), "error_type": type(e).__name__}
        return json.dumps(error_result)


def main():
    """Start the Photoshop MCP server."""
    import sys

    from mcp.server.fastmcp import start_server

    # Set default port
    port = 35750

    # Check if port is specified in command line args
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            sys.exit(1)

    print(f"Starting Photoshop MCP server on port {port}...")
    start_server(mcp, port)


if __name__ == "__main__":
    main()
