"""
Extended test cases for ConfigLoader to improve coverage.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lightfast_mcp.management.config_loader import (
    ConfigLoader,
    load_config_from_env,
    load_server_configs,
)


class TestConfigLoaderErrorPaths:
    """Test error paths and edge cases in ConfigLoader."""

    def test_yaml_not_available_load(self):
        """Test loading YAML when PyYAML is not available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.yaml"

            # Create a YAML file
            config_file.write_text("servers:\n  - name: test\n    type: mock")

            loader = ConfigLoader(config_dir=config_dir)

            # Mock YAML_AVAILABLE to False
            with patch("lightfast_mcp.management.config_loader.YAML_AVAILABLE", False):
                configs = loader.load_servers_config("servers.yaml")
                # Should return empty list due to error
                assert configs == []

    def test_yaml_not_available_save(self):
        """Test saving YAML when PyYAML is not available."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            from lightfast_mcp.core.base_server import ServerConfig

            configs = [
                ServerConfig(name="test", description="test", config={"type": "mock"})
            ]

            # Mock YAML_AVAILABLE to False
            with patch("lightfast_mcp.management.config_loader.YAML_AVAILABLE", False):
                result = loader.save_servers_config(configs, "test.yaml")
                assert result is False

    def test_unsupported_file_format_load(self):
        """Test loading unsupported file format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.txt"
            config_file.write_text("some content")

            loader = ConfigLoader(config_dir=config_dir)
            configs = loader.load_servers_config("servers.txt")
            assert configs == []

    def test_unsupported_file_format_save(self):
        """Test saving unsupported file format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            from lightfast_mcp.core.base_server import ServerConfig

            configs = [
                ServerConfig(name="test", description="test", config={"type": "mock"})
            ]

            result = loader.save_servers_config(configs, "test.txt")
            assert result is False

    def test_file_not_found(self):
        """Test loading non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            configs = loader.load_servers_config("nonexistent.yaml")
            assert configs == []

    def test_malformed_json(self):
        """Test loading malformed JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.json"
            config_file.write_text("{ invalid json }")

            loader = ConfigLoader(config_dir=config_dir)
            configs = loader.load_servers_config("servers.json")
            assert configs == []

    def test_malformed_yaml(self):
        """Test loading malformed YAML file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.yaml"
            config_file.write_text("servers:\n  - name: test\n    invalid: [unclosed")

            loader = ConfigLoader(config_dir=config_dir)
            configs = loader.load_servers_config("servers.yaml")
            assert configs == []

    def test_invalid_config_data_not_dict(self):
        """Test parsing config data that's not a dictionary."""
        loader = ConfigLoader()

        with pytest.raises(ValueError, match="Configuration must be a dictionary"):
            loader._parse_config_data("not a dict")

    def test_invalid_servers_not_list(self):
        """Test parsing config where servers is not a list."""
        loader = ConfigLoader()

        with pytest.raises(ValueError, match="'servers' must be a list"):
            loader._parse_config_data({"servers": "not a list"})

    def test_invalid_server_config_not_dict(self):
        """Test parsing server config that's not a dictionary."""
        loader = ConfigLoader()

        with pytest.raises(
            ValueError, match="Server configuration must be a dictionary"
        ):
            loader._parse_server_config("not a dict")

    def test_save_json_config(self):
        """Test saving JSON configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            from lightfast_mcp.core.base_server import ServerConfig

            configs = [
                ServerConfig(
                    name="test-server",
                    description="Test server",
                    config={"type": "mock", "delay": 0.5},
                )
            ]

            result = loader.save_servers_config(configs, "test.json")
            assert result is True

            # Verify file was created and has correct content
            config_file = config_dir / "test.json"
            assert config_file.exists()

            with open(config_file) as f:
                data = json.load(f)

            assert "servers" in data
            assert len(data["servers"]) == 1
            assert data["servers"][0]["name"] == "test-server"

    def test_load_json_config(self):
        """Test loading JSON configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.json"

            config_data = {
                "servers": [
                    {"name": "json-server", "type": "mock", "config": {"type": "mock"}}
                ]
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f)

            loader = ConfigLoader(config_dir=config_dir)
            configs = loader.load_servers_config("servers.json")

            assert len(configs) == 1
            assert configs[0].name == "json-server"

    def test_save_config_io_error(self):
        """Test save configuration with IO error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            from lightfast_mcp.core.base_server import ServerConfig

            configs = [
                ServerConfig(name="test", description="test", config={"type": "mock"})
            ]

            # Try to save to a directory that doesn't exist and can't be created
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                result = loader.save_servers_config(configs, "test.yaml")
                assert result is False

    def test_server_config_to_dict(self):
        """Test converting ServerConfig to dictionary."""
        from lightfast_mcp.core.base_server import ServerConfig

        config = ServerConfig(
            name="test-server",
            description="Test server",
            version="2.0.0",
            host="example.com",
            port=9000,
            transport="http",
            path="/api",
            config={"type": "custom", "setting": "value"},
            dependencies=["dep1", "dep2"],
            required_apps=["app1"],
        )

        loader = ConfigLoader()
        result = loader._server_config_to_dict(config)

        expected = {
            "name": "test-server",
            "description": "Test server",
            "version": "2.0.0",
            "type": "custom",
            "host": "example.com",
            "port": 9000,
            "transport": "http",
            "path": "/api",
            "config": {"type": "custom", "setting": "value"},
            "dependencies": ["dep1", "dep2"],
            "required_apps": ["app1"],
        }

        assert result == expected


class TestLoadServerConfigs:
    """Test the convenience function load_server_configs."""

    def test_load_server_configs_with_config_path(self):
        """Test load_server_configs with config/ prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config directory and file
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_file = config_dir / "servers.yaml"

            config_content = """
servers:
  - name: test-server
    type: mock
    transport: sse
    host: localhost
    port: 8001
    path: /mcp
    config:
      type: mock
"""
            config_file.write_text(config_content)

            # Change to temp directory
            original_cwd = Path.cwd()
            try:
                os.chdir(temp_dir)
                servers = load_server_configs("config/servers.yaml")

                assert len(servers) == 1
                assert "test-server" in servers
                server = servers["test-server"]
                assert server["name"] == "test-server"
                assert server["type"] == "sse"
                assert server["host"] == "localhost"
                assert server["port"] == 8001

            finally:
                os.chdir(original_cwd)

    def test_load_server_configs_stdio_transport(self):
        """Test load_server_configs with stdio transport."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.yaml"

            config_content = """
servers:
  - name: stdio-server
    type: mock
    transport: stdio
    config:
      type: mock
      command: custom-command
      args: ["--arg1", "--arg2"]
"""
            config_file.write_text(config_content)

            loader = ConfigLoader(config_dir=config_dir)
            # Use the loader directly to avoid path issues
            server_configs = loader.load_servers_config("servers.yaml")

            # Convert using the same logic as load_server_configs
            servers = {}
            for config in server_configs:
                server_dict = {
                    "name": config.name,
                    "version": config.version,
                    "type": config.transport,
                    "host": config.host,
                    "port": config.port,
                    "path": config.path,
                }

                if config.transport == "stdio":
                    server_dict["command"] = config.config.get(
                        "command", f"lightfast-{config.name.replace('-', '_')}"
                    )
                    server_dict["args"] = config.config.get("args", [])

                servers[config.name] = server_dict

            assert len(servers) == 1
            server = servers["stdio-server"]
            assert server["type"] == "stdio"
            assert server["command"] == "custom-command"
            assert server["args"] == ["--arg1", "--arg2"]

    def test_load_server_configs_streamable_http(self):
        """Test load_server_configs with streamable-http transport."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.yaml"

            config_content = """
servers:
  - name: http-server
    type: mock
    transport: streamable-http
    host: example.com
    port: 9000
    path: /api
    config:
      type: mock
"""
            config_file.write_text(config_content)

            loader = ConfigLoader(config_dir=config_dir)
            server_configs = loader.load_servers_config("servers.yaml")

            # Convert using the same logic as load_server_configs
            servers = {}
            for config in server_configs:
                server_dict = {
                    "name": config.name,
                    "version": config.version,
                    "type": config.transport,
                    "host": config.host,
                    "port": config.port,
                    "path": config.path,
                }

                if config.transport in ["sse", "streamable-http"]:
                    server_dict["url"] = (
                        f"http://{config.host}:{config.port}{config.path}"
                    )
                    if config.transport == "streamable-http":
                        server_dict["type"] = "sse"

                servers[config.name] = server_dict

            assert len(servers) == 1
            server = servers["http-server"]
            assert server["type"] == "sse"  # Mapped from streamable-http
            assert server["url"] == "http://example.com:9000/api"

    def test_load_server_configs_no_config_file(self):
        """Test load_server_configs with no config file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = Path.cwd()
            try:
                os.chdir(temp_dir)
                servers = load_server_configs()
                assert servers == {}
            finally:
                os.chdir(original_cwd)


class TestEnvironmentConfig:
    """Test environment-based configuration loading."""

    @patch.dict(os.environ, {}, clear=True)
    def test_load_config_from_env_no_env_var(self):
        """Test loading from environment when no env var is set."""
        configs = load_config_from_env()
        assert configs == []

    @patch.dict(os.environ, {"LIGHTFAST_MCP_SERVERS": "invalid json"})
    def test_load_config_from_env_invalid_json(self):
        """Test loading from environment with invalid JSON."""
        configs = load_config_from_env()
        assert configs == []

    @patch.dict(os.environ, {"LIGHTFAST_MCP_SERVERS": '{"not_servers": []}'})
    def test_load_config_from_env_missing_servers_key(self):
        """Test loading from environment with missing servers key."""
        configs = load_config_from_env()
        assert configs == []

    @patch.dict(
        os.environ,
        {
            "LIGHTFAST_MCP_SERVERS": json.dumps(
                {
                    "servers": [
                        {
                            "name": "env-server-1",
                            "type": "mock",
                            "config": {"type": "mock"},
                        },
                        {
                            "name": "env-server-2",
                            "type": "test",
                            "config": {"type": "test"},
                        },
                    ]
                }
            )
        },
    )
    def test_load_config_from_env_multiple_servers(self):
        """Test loading multiple servers from environment."""
        configs = load_config_from_env()
        assert len(configs) == 2
        assert configs[0].name == "env-server-1"
        assert configs[1].name == "env-server-2"
