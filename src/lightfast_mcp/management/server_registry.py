"""Server registry for discovering and managing MCP servers."""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any

from ..core.base_server import BaseServer, ServerConfig
from ..utils.logging_utils import get_logger

logger = get_logger("ServerRegistry")


class ServerRegistry:
    """Registry for discovering and managing MCP servers."""

    def __init__(self):
        """Initialize the server registry."""
        self._server_classes: dict[str, type[BaseServer]] = {}
        self._server_instances: dict[str, BaseServer] = {}

        # Auto-discover servers on initialization
        self.discover_servers()

    def discover_servers(self):
        """Automatically discover all available server classes."""
        logger.info("Discovering MCP servers...")

        # Discover servers in the servers package
        self._discover_servers_in_package("lightfast_mcp.servers")

        logger.info(
            f"Found {len(self._server_classes)} server types: {list(self._server_classes.keys())}"
        )

    def _discover_servers_in_package(self, package_name: str):
        """Discover servers in a specific package."""
        try:
            # Import the package
            package = importlib.import_module(package_name)

            # Check if package has a file path
            if package.__file__ is None:
                logger.debug(f"Package {package_name} has no __file__ attribute")
                return

            package_path = Path(package.__file__).parent

            # Iterate through all modules in the package
            for _finder, name, ispkg in pkgutil.iter_modules([str(package_path)]):
                if ispkg:
                    # Recursively search subpackages
                    subpackage_name = f"{package_name}.{name}"
                    self._discover_servers_in_package(subpackage_name)
                else:
                    # Import the module and look for server classes
                    try:
                        module_name = f"{package_name}.{name}"
                        module = importlib.import_module(module_name)
                        self._discover_servers_in_module(module)
                    except Exception as e:
                        logger.debug(f"Could not import module {module_name}: {e}")

        except Exception as e:
            logger.debug(f"Could not discover servers in package {package_name}: {e}")

    def _discover_servers_in_module(self, module):
        """Discover server classes in a module."""
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseServer)
                and obj is not BaseServer
                and hasattr(obj, "SERVER_TYPE")
            ):
                server_type = obj.SERVER_TYPE
                if server_type != "base":  # Skip the base class
                    logger.debug(f"Found server class: {name} (type: {server_type})")
                    self._server_classes[server_type] = obj

    def register_server_class(self, server_type: str, server_class: type[BaseServer]):
        """Manually register a server class."""
        logger.info(f"Registering server class: {server_type}")
        self._server_classes[server_type] = server_class

    def get_server_class(self, server_type: str) -> type[BaseServer] | None:
        """Get a server class by type."""
        return self._server_classes.get(server_type)

    def get_available_server_types(self) -> list[str]:
        """Get list of all available server types."""
        return list(self._server_classes.keys())

    def create_server(self, server_type: str, config: ServerConfig) -> BaseServer:
        """Create a server instance from configuration."""
        server_class = self.get_server_class(server_type)
        if not server_class:
            raise ValueError(f"Unknown server type: {server_type}")

        logger.info(f"Creating server instance: {config.name} (type: {server_type})")
        server = server_class.create_from_config(config)

        # Store the instance
        self._server_instances[config.name] = server
        return server

    def get_server_instance(self, name: str) -> BaseServer | None:
        """Get a running server instance by name."""
        return self._server_instances.get(name)

    def get_all_server_instances(self) -> dict[str, BaseServer]:
        """Get all server instances."""
        return self._server_instances.copy()

    def remove_server_instance(self, name: str) -> bool:
        """Remove a server instance."""
        if name in self._server_instances:
            logger.info(f"Removing server instance: {name}")
            del self._server_instances[name]
            return True
        return False

    def get_server_info(self) -> dict[str, dict[str, Any]]:
        """Get information about all available server types."""
        info = {}
        for server_type, server_class in self._server_classes.items():
            info[server_type] = {
                "class_name": server_class.__name__,
                "version": getattr(server_class, "SERVER_VERSION", "1.0.0"),
                "required_dependencies": getattr(
                    server_class, "REQUIRED_DEPENDENCIES", []
                ),
                "required_apps": getattr(server_class, "REQUIRED_APPS", []),
                "description": getattr(
                    server_class, "__doc__", "No description available"
                ),
            }
        return info

    def validate_server_config(
        self, server_type: str, config: ServerConfig
    ) -> tuple[bool, str]:
        """Validate a server configuration."""
        server_class = self.get_server_class(server_type)
        if not server_class:
            return False, f"Unknown server type: {server_type}"

        # Basic validation
        if not config.name:
            return False, "Server name is required"

        if not config.description:
            return False, "Server description is required"

        # Check for port conflicts with existing instances
        for instance in self._server_instances.values():
            if (
                instance.config.port == config.port
                and instance.config.host == config.host
                and instance.config.transport in ["http", "streamable-http"]
                and config.transport in ["http", "streamable-http"]
            ):
                return (
                    False,
                    f"Port {config.port} on {config.host} is already in use by {instance.config.name}",
                )

        return True, "Configuration is valid"


# Global registry instance
_registry: ServerRegistry | None = None


def get_registry() -> ServerRegistry:
    """Get the global server registry instance."""
    global _registry
    if _registry is None:
        _registry = ServerRegistry()
    return _registry


def reset_registry():
    """Reset the global registry (mainly for testing)."""
    global _registry
    _registry = None
