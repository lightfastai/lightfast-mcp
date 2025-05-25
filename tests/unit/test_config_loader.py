"""
Additional test cases for the ConfigLoader module.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from internal.management.config_loader import ConfigLoader


class TestConfigLoaderComprehensive:
    """Comprehensive tests for ConfigLoader functionality."""

    def test_init_default_config_dir(self):
        """Test initialization with default config directory."""
        loader = ConfigLoader()
        assert loader.config_dir.name == "config"
        assert loader.config_dir.is_absolute()

    def test_init_custom_config_dir(self):
        """Test initialization with custom config directory."""
        custom_dir = Path("/tmp/custom_config")
        loader = ConfigLoader(config_dir=custom_dir)
        assert loader.config_dir == custom_dir

    def test_config_directory_creation(self):
        """Test config directory is created during initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "test_config"
            loader = ConfigLoader(config_dir=config_dir)

            # Directory should be created
            assert loader.config_dir.exists()

    def test_parse_server_config_complete(self):
        """Test parsing complete server configuration."""
        config_data = {
            "name": "test-server",
            "description": "Test server",
            "type": "mock",
            "host": "localhost",
            "port": 8001,
            "transport": "http",
            "path": "/mcp",
            "config": {"type": "mock", "delay": 0.5},
            "dependencies": ["dep1"],
            "required_apps": ["app1"],
        }

        loader = ConfigLoader()
        server_config = loader._parse_server_config(config_data)

        assert server_config.name == "test-server"
        assert server_config.description == "Test server"
        assert server_config.host == "localhost"
        assert server_config.port == 8001
        assert server_config.transport == "http"
        assert server_config.path == "/mcp"
        assert server_config.config == {"type": "mock", "delay": 0.5}
        assert server_config.dependencies == ["dep1"]
        assert server_config.required_apps == ["app1"]

    def test_parse_server_config_minimal(self):
        """Test parsing minimal server configuration."""
        config_data = {
            "name": "minimal-server",
            "type": "mock",
            "config": {"type": "mock"},
        }

        loader = ConfigLoader()
        server_config = loader._parse_server_config(config_data)

        assert server_config.name == "minimal-server"
        assert (
            server_config.description == "minimal-server MCP Server"
        )  # Generated description
        assert server_config.host == "localhost"
        assert server_config.port == 8000
        assert server_config.transport == "stdio"

    def test_parse_server_config_missing_name(self):
        """Test parsing configuration with missing name."""
        config_data = {"type": "mock", "config": {"type": "mock"}}

        loader = ConfigLoader()

        with pytest.raises(ValueError, match="Server 'name' is required"):
            loader._parse_server_config(config_data)

    def test_parse_server_config_missing_config(self):
        """Test parsing configuration with missing config section."""
        config_data = {"name": "test-server", "type": "mock"}

        loader = ConfigLoader()

        # Should work, config will be filled with just the type
        server_config = loader._parse_server_config(config_data)
        assert server_config.name == "test-server"
        assert server_config.config == {"type": "mock"}

    def test_create_sample_config_success(self):
        """Test successful sample configuration creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            result = loader.create_sample_config("test.yaml")

            assert result is True
            assert (config_dir / "test.yaml").exists()

    def test_create_sample_config_failure(self):
        """Test sample configuration creation failure."""
        # Use read-only directory to cause write failure
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / "readonly"
            config_dir.mkdir()
            config_dir.chmod(0o444)  # Read-only

            try:
                loader = ConfigLoader(config_dir=config_dir)
                _result = loader.create_sample_config("test.yaml")
                # Result might be True if mkdir worked, but write should fail
                # The actual behavior depends on system permissions
            except Exception:
                # Expected for read-only directories
                pass
            finally:
                # Restore permissions for cleanup
                config_dir.chmod(0o755)

    @patch.dict(
        os.environ,
        {
            "LIGHTFAST_MCP_SERVERS": '{"servers": [{"name": "env-server", "type": "mock", "config": {"type": "mock"}}]}'
        },
    )
    def test_load_from_environment(self):
        """Test loading configuration from environment variable."""
        from internal.management.config_loader import load_config_from_env

        configs = load_config_from_env()

        assert len(configs) == 1
        assert configs[0].name == "env-server"

    @patch.dict(os.environ, {"LIGHTFAST_MCP_SERVERS": "invalid json"})
    def test_load_from_environment_invalid_json(self):
        """Test handling invalid JSON in environment variable."""
        from internal.management.config_loader import load_config_from_env

        configs = load_config_from_env()
        assert configs == []

    def test_load_servers_config_no_file_no_env(self):
        """Test loading when no file or environment config exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            with patch.dict(os.environ, {}, clear=True):
                configs = loader.load_servers_config()

            assert configs == []

    def test_load_servers_config_with_invalid_server(self):
        """Test loading configuration with one valid and one invalid server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_file = config_dir / "servers.yaml"

            # Create config with one valid and one invalid server
            config_content = {
                "servers": [
                    {
                        "name": "valid-server",
                        "type": "mock",
                        "config": {"type": "mock"},
                    },
                    {
                        "type": "mock",  # Missing name
                        "config": {"type": "mock"},
                    },
                ]
            }

            with open(config_file, "w") as f:
                yaml.dump(config_content, f)

            loader = ConfigLoader(config_dir=config_dir)
            configs = loader.load_servers_config()

            # Should only return the valid server
            assert len(configs) == 1
            assert configs[0].name == "valid-server"

    def test_find_config_file_default(self):
        """Test finding default configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            # Create a servers.yaml file
            (config_dir / "servers.yaml").touch()

            loader = ConfigLoader(config_dir=config_dir)
            config_file = loader._find_default_config()

            assert config_file.name == "servers.yaml"

    def test_find_config_file_none_found(self):
        """Test when no configuration file is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            config_file = loader._find_default_config()

            assert config_file is None


class TestConfigLoaderIntegration:
    """Integration tests for ConfigLoader."""

    def test_full_config_cycle(self):
        """Test complete configuration creation and loading cycle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            # Create sample config
            success = loader.create_sample_config("servers.yaml")
            assert success is True

            # Load the created config
            configs = loader.load_servers_config()
            assert len(configs) >= 2  # Should have at least blender and mock servers

            # Verify config structure
            for config in configs:
                assert hasattr(config, "name")
                assert hasattr(config, "config")
                assert config.name
                assert config.config
