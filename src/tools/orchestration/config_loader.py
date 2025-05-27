"""Configuration loader for MCP servers."""

import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.utils.logging_utils import get_logger

logger = get_logger("ConfigLoader")


class ConfigLoader:
    """Loader for server configurations from files."""

    def __init__(self, config_dir: str | Path | None = None):
        """Initialize the config loader."""
        self.config_dir = Path(config_dir) if config_dir else Path.cwd() / "config"

        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)

        logger.info(f"Config directory: {self.config_dir}")

    def load_servers_config(
        self, config_file: str | Path | None = None
    ) -> list[ServerConfig]:
        """Load server configurations from a file."""
        if config_file is None:
            # Look for default config files
            config_file = self._find_default_config()

        if not config_file:
            logger.warning("No configuration file found, returning empty list")
            return []

        config_path = Path(config_file)
        if not config_path.is_absolute():
            config_path = self.config_dir / config_path

        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return []

        logger.info(f"Loading server configurations from: {config_path}")

        try:
            if config_path.suffix.lower() in [".yaml", ".yml"]:
                return self._load_yaml_config(config_path)
            elif config_path.suffix.lower() == ".json":
                return self._load_json_config(config_path)
            else:
                logger.error(f"Unsupported config file format: {config_path.suffix}")
                return []
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return []

    def _find_default_config(self) -> Path | None:
        """Find the default configuration file."""
        possible_files = [
            "servers.yaml",
            "servers.yml",
            "servers.json",
            "lightfast-mcp.yaml",
            "lightfast-mcp.yml",
            "lightfast-mcp.json",
        ]

        for filename in possible_files:
            config_path = self.config_dir / filename
            if config_path.exists():
                logger.info(f"Found default config file: {config_path}")
                return config_path

        return None

    def _load_yaml_config(self, config_path: Path) -> list[ServerConfig]:
        """Load configuration from YAML file."""
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required to load YAML configuration files. Install with: pip install pyyaml"
            )

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return self._parse_config_data(data)

    def _load_json_config(self, config_path: Path) -> list[ServerConfig]:
        """Load configuration from JSON file."""
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        return self._parse_config_data(data)

    def _parse_config_data(self, data: dict[str, Any]) -> list[ServerConfig]:
        """Parse configuration data into ServerConfig objects."""
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a dictionary")

        servers_data = data.get("servers", [])
        if not isinstance(servers_data, list):
            raise ValueError("'servers' must be a list")

        server_configs = []

        for i, server_data in enumerate(servers_data):
            try:
                server_config = self._parse_server_config(server_data)
                server_configs.append(server_config)
            except Exception as e:
                logger.error(f"Error parsing server config at index {i}: {e}")
                continue

        logger.info(f"Loaded {len(server_configs)} server configurations")
        return server_configs

    def _parse_server_config(self, server_data: dict[str, Any]) -> ServerConfig:
        """Parse a single server configuration."""
        if not isinstance(server_data, dict):
            raise ValueError("Server configuration must be a dictionary")

        # Required fields
        name = server_data.get("name")
        if not name:
            raise ValueError("Server 'name' is required")

        description = server_data.get("description", f"{name} MCP Server")

        # Optional fields with defaults
        version = server_data.get("version", "1.0.0")
        host = server_data.get("host", "localhost")
        port = server_data.get("port", 8000)
        transport = server_data.get("transport", "stdio")
        path = server_data.get("path", "/mcp")

        # Server-specific configuration
        config = server_data.get("config", {})

        # Add server type to config if not present
        if "type" not in config:
            # Try to infer from name or set a default
            config["type"] = server_data.get("type", "unknown")

        # Inject environment variables into config
        config = self._inject_environment_variables(config)

        # Dependencies and requirements
        dependencies = server_data.get("dependencies", [])
        required_apps = server_data.get("required_apps", [])

        return ServerConfig(
            name=name,
            description=description,
            version=version,
            host=host,
            port=port,
            transport=transport,
            path=path,
            config=config,
            dependencies=dependencies,
            required_apps=required_apps,
        )

    def _inject_environment_variables(self, config: dict[str, Any]) -> dict[str, Any]:
        """Inject environment variables into configuration values."""
        # Create a copy to avoid modifying the original
        config = config.copy()

        # Define environment variable mappings for different server types
        env_mappings = {
            "figma": {"api_token": "FIGMA_API_TOKEN"},
            "github": {
                "api_token": "GITHUB_TOKEN",
                "personal_access_token": "GITHUB_PERSONAL_ACCESS_TOKEN",
            },
            "openai": {"api_key": "OPENAI_API_KEY"},
            "anthropic": {"api_key": "ANTHROPIC_API_KEY"},
        }

        server_type = config.get("type", "")
        if server_type in env_mappings:
            for config_key, env_var in env_mappings[server_type].items():
                # If the config value is null/None or missing, try to get from environment
                if config.get(config_key) is None:
                    env_value = os.getenv(env_var)
                    if env_value:
                        config[config_key] = env_value
                        logger.info(
                            f"Injected {env_var} environment variable into {server_type}.{config_key}"
                        )

        return config

    def save_servers_config(
        self, server_configs: list[ServerConfig], config_file: str | Path | None = None
    ) -> bool:
        """Save server configurations to a file."""
        if config_file is None:
            config_file = self.config_dir / "servers.yaml"
        else:
            config_file = Path(config_file)
            if not config_file.is_absolute():
                config_file = self.config_dir / config_file

        try:
            # Convert server configs to dictionary format
            data = {
                "servers": [
                    self._server_config_to_dict(config) for config in server_configs
                ]
            }

            # Save based on file extension
            if config_file.suffix.lower() in [".yaml", ".yml"]:
                self._save_yaml_config(config_file, data)
            elif config_file.suffix.lower() == ".json":
                self._save_json_config(config_file, data)
            else:
                logger.error(
                    f"Unsupported config file format for saving: {config_file.suffix}"
                )
                return False

            logger.info(
                f"Saved {len(server_configs)} server configurations to: {config_file}"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def _server_config_to_dict(self, server_config: ServerConfig) -> dict[str, Any]:
        """Convert ServerConfig to dictionary."""
        return {
            "name": server_config.name,
            "description": server_config.description,
            "version": server_config.version,
            "type": server_config.config.get("type", "unknown"),
            "host": server_config.host,
            "port": server_config.port,
            "transport": server_config.transport,
            "path": server_config.path,
            "config": server_config.config,
            "dependencies": server_config.dependencies,
            "required_apps": server_config.required_apps,
        }

    def _save_yaml_config(self, config_file: Path, data: dict[str, Any]):
        """Save configuration to YAML file."""
        if not YAML_AVAILABLE:
            raise ImportError(
                "PyYAML is required to save YAML configuration files. Install with: pip install pyyaml"
            )

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    def _save_json_config(self, config_file: Path, data: dict[str, Any]):
        """Save configuration to JSON file."""
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def create_sample_config(self, config_file: str | Path | None = None) -> bool:
        """Create a sample configuration file."""
        sample_configs = [
            ServerConfig(
                name="blender-server",
                description="Blender MCP Server for 3D modeling and animation",
                version="1.0.0",
                host="localhost",
                port=8001,
                transport="streamable-http",
                path="/mcp",
                config={
                    "type": "blender",
                    "blender_host": "localhost",
                    "blender_port": 9876,
                },
                dependencies=[],
                required_apps=["Blender"],
            ),
            ServerConfig(
                name="mock-server",
                description="Mock MCP Server for testing and development",
                version="1.0.0",
                host="localhost",
                port=8002,
                transport="streamable-http",
                path="/mcp",
                config={
                    "type": "mock",
                },
                dependencies=[],
                required_apps=[],
            ),
        ]

        if config_file is None:
            config_file = self.config_dir / "servers.yaml"

        return self.save_servers_config(sample_configs, config_file)


# Environment variable support
def load_config_from_env() -> list[ServerConfig]:
    """Load configuration from environment variables."""
    configs = []

    # Check for environment-based configuration
    env_config = os.getenv("LIGHTFAST_MCP_SERVERS")
    if env_config:
        try:
            data = json.loads(env_config)
            loader = ConfigLoader()
            configs = loader._parse_config_data(data)
            logger.info(f"Loaded {len(configs)} server configs from environment")
        except Exception as e:
            logger.error(f"Error parsing environment configuration: {e}")

    return configs


def load_server_configs(
    config_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Convenience function to load server configs in the format expected by ConversationClient."""
    # If config_path is provided and starts with 'config/', treat it as relative to project root
    if config_path and str(config_path).startswith("config/"):
        # Don't create a ConfigLoader with config_dir, let it be relative to current directory
        loader = ConfigLoader(config_dir=Path.cwd())
        server_configs = loader.load_servers_config(config_path)
    else:
        # Use default behavior
        loader = ConfigLoader()
        server_configs = loader.load_servers_config(config_path)

    # Convert ServerConfig objects to dictionary format expected by ConversationClient
    servers = {}
    for config in server_configs:
        server_dict = {
            "name": config.name,
            "version": config.version,
            "type": config.transport,  # Use transport type for connection
            "host": config.host,
            "port": config.port,
            "path": config.path,
        }

        # For stdio transport, we need command and args
        if config.transport == "stdio":
            # Try to get from config, otherwise use defaults
            server_dict["command"] = config.config.get(
                "command", f"lightfast-{config.name.replace('-', '_')}"
            )
            server_dict["args"] = config.config.get("args", [])
        elif config.transport in ["sse", "streamable-http"]:
            # For HTTP-based transports, construct URL
            server_dict["url"] = f"http://{config.host}:{config.port}{config.path}"
            # Map streamable-http to sse for MCP client
            if config.transport == "streamable-http":
                server_dict["type"] = "sse"

        # Add any additional config (but don't override the type we set above)
        for key, value in config.config.items():
            if key != "type":  # Don't override the transport type
                server_dict[key] = value

        servers[config.name] = server_dict

    return servers
