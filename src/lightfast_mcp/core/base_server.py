"""Base server interface for all MCP servers in the lightfast-mcp ecosystem."""

# Import shared types from common module
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from fastmcp import FastMCP

# Import shared types from common module
from common import HealthStatus, ServerInfo, ServerState

from ..utils.logging_utils import get_logger


@dataclass
class ServerConfig:
    """Configuration for an MCP server."""

    # Basic server info
    name: str
    description: str
    version: str = "1.0.0"

    # Network configuration
    host: str = "localhost"
    port: int = 8000
    transport: str = "stdio"  # stdio, http, or streamable-http
    path: str = "/mcp"

    # Server-specific configuration
    config: dict[str, Any] = field(default_factory=dict)

    # Dependencies and requirements
    dependencies: list[str] = field(default_factory=list)
    required_apps: list[str] = field(
        default_factory=list
    )  # e.g., ["Blender", "TouchDesigner"]


class BaseServer(ABC):
    """Base class for all MCP servers in the lightfast-mcp ecosystem."""

    # Server metadata - subclasses should override these
    SERVER_TYPE: ClassVar[str] = "base"
    SERVER_VERSION: ClassVar[str] = "1.0.0"
    REQUIRED_DEPENDENCIES: ClassVar[list[str]] = []
    REQUIRED_APPS: ClassVar[list[str]] = []

    def __init__(self, config: ServerConfig):
        """Initialize the base server with configuration."""
        self.config = config
        self.logger = get_logger(f"{self.__class__.__name__}")
        self.mcp: FastMCP | None = None
        self.info = ServerInfo.from_core_config(config)

        # Initialize the FastMCP instance
        self._init_mcp()

    def _init_mcp(self):
        """Initialize the FastMCP instance with lifespan management."""
        self.mcp = FastMCP(
            self.config.name,
            description=self.config.description,
            lifespan=self._server_lifespan,
        )

        # Register tools
        self._register_tools()

    @abstractmethod
    def _register_tools(self):
        """Register server-specific tools. Must be implemented by subclasses."""
        pass

    @asynccontextmanager
    async def _server_lifespan(self, server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        """Manage server startup and shutdown lifecycle."""
        try:
            self.logger.info(f"{self.config.name} starting up...")

            # Perform startup checks
            await self._startup_checks()

            # Custom startup logic
            await self._on_startup()

            self.info.state = ServerState.RUNNING
            self.info.health_status = HealthStatus.HEALTHY

            yield {}

        except Exception as e:
            self.logger.error(f"Error during {self.config.name} startup: {e}")
            self.info.error_message = str(e)
            self.info.health_status = HealthStatus.UNHEALTHY
            raise
        finally:
            # Custom shutdown logic
            await self._on_shutdown()

            self.info.state = ServerState.STOPPED
            self.logger.info(f"{self.config.name} shutting down.")

    async def _startup_checks(self):
        """Perform basic startup checks."""
        # Check dependencies
        for dep in self.REQUIRED_DEPENDENCIES:
            if not await self._check_dependency(dep):
                raise RuntimeError(f"Required dependency not available: {dep}")

        # Check required applications
        for app in self.REQUIRED_APPS:
            if not await self._check_application(app):
                self.logger.warning(f"Required application may not be available: {app}")

    async def _check_dependency(self, dependency: str) -> bool:
        """Check if a required dependency is available."""
        try:
            __import__(dependency)
            return True
        except ImportError:
            return False

    async def _check_application(self, app: str) -> bool:
        """Check if a required application is available. Override in subclasses."""
        return True

    async def _on_startup(self):
        """Custom startup logic. Override in subclasses if needed."""
        # Default implementation does nothing
        return

    async def _on_shutdown(self):
        """Custom shutdown logic. Override in subclasses if needed."""
        # Default implementation does nothing
        return

    async def health_check(self) -> bool:
        """Perform a health check on the server."""
        try:
            # Basic health check - can be overridden by subclasses
            is_healthy = await self._perform_health_check()
            self.info.health_status = (
                HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY
            )
            self.info.last_health_check = datetime.utcnow()
            return is_healthy
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self.info.health_status = HealthStatus.UNHEALTHY
            self.info.error_message = str(e)
            return False

    async def _perform_health_check(self) -> bool:
        """Perform server-specific health check. Override in subclasses."""
        return self.info.is_running

    def get_tools(self) -> list[str]:
        """Get list of available tools."""
        if self.mcp:
            # This would need to be implemented based on FastMCP's API
            # For now, we'll store tools in info during registration
            pass
        return self.info.tools

    def run(self, **kwargs):
        """Run the server with the configured transport."""
        if not self.mcp:
            raise RuntimeError("MCP server not initialized")

        # Build URL for HTTP transports
        if self.config.transport in ["http", "streamable-http"]:
            self.info.url = (
                f"http://{self.config.host}:{self.config.port}{self.config.path}"
            )
            self.logger.info(f"Server will be available at: {self.info.url}")

        # Run with appropriate transport
        if self.config.transport == "stdio":
            self.mcp.run()
        elif self.config.transport in ["http", "streamable-http"]:
            self.mcp.run(
                transport=self.config.transport,
                host=self.config.host,
                port=self.config.port,
                path=self.config.path,
                **kwargs,
            )
        else:
            raise ValueError(f"Unsupported transport: {self.config.transport}")

    @classmethod
    def create_from_config(cls, config: ServerConfig) -> "BaseServer":
        """Create a server instance from configuration."""
        return cls(config)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.config.name})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.config.name}', type='{self.SERVER_TYPE}')"
