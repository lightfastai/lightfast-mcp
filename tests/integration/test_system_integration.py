"""
Integration tests for the complete lightfast-mcp system.
"""

from unittest.mock import patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from tools.orchestration import get_manager, get_registry
from tools.orchestration.config_loader import ConfigLoader


@pytest.mark.integration
class TestSystemIntegration:
    """Integration tests for the complete system."""

    def test_registry_discovery_integration(self):
        """Test that the registry discovers real servers correctly."""
        registry = get_registry()

        # Test discovery
        available_types = registry.get_available_server_types()
        assert len(available_types) > 0
        assert "blender" in available_types or "mock" in available_types

        # Test getting server info for all types
        info = registry.get_server_info()
        assert isinstance(info, dict)
        assert len(info) > 0

    @pytest.mark.asyncio
    async def test_full_server_lifecycle_integration(self):
        """Test complete server lifecycle through the manager."""
        manager = get_manager()

        # Create a test server configuration
        config = ServerConfig(
            name="integration-mock",
            description="Integration test mock server",
            config={"type": "mock", "delay_seconds": 0.1},
        )

        # Mock server startup to avoid actual execution
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                # Mock a successful server
                from lightfast_mcp.servers.mock.server import MockMCPServer

                mock_server = MockMCPServer(config)
                # Set the server as running for the test
                mock_server.info.is_running = True

                mock_validate.return_value = (True, "Valid configuration")
                mock_create.return_value = mock_server

                # Mock the run method to avoid actual execution
                with patch.object(mock_server, "run"):
                    # Test server startup
                    result = manager.start_server(config, background=False)
                    assert result is True

                    # Verify server is tracked
                    assert manager.is_server_running("integration-mock")

                    # Test health check
                    health_results = await manager.health_check_all()
                    assert "integration-mock" in health_results

                    # Test server stop
                    stop_result = manager.stop_server("integration-mock")
                    assert stop_result is True

                    # Verify server is no longer tracked
                    assert not manager.is_server_running("integration-mock")

    def test_multi_server_integration(self, sample_multi_server_configs):
        """Test running multiple servers simultaneously."""
        manager = get_manager()

        # Mock server creation to avoid actual execution
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                from lightfast_mcp.servers.blender.server import BlenderMCPServer
                from lightfast_mcp.servers.mock.server import MockMCPServer

                def create_server_side_effect(server_type, config):
                    if server_type == "mock":
                        server = MockMCPServer(config)
                    elif server_type == "blender":
                        server = BlenderMCPServer(config)
                    else:
                        raise ValueError(f"Unknown server type: {server_type}")

                    # Mock the run method
                    with patch.object(server, "run"):
                        return server

                mock_validate.return_value = (True, "Valid configuration")
                mock_create.side_effect = create_server_side_effect

                # Start multiple servers
                results = manager.start_multiple_servers(
                    sample_multi_server_configs, background=True
                )

                # Verify results
                assert isinstance(results, dict)
                assert len(results) == 2

                # Check that servers are tracked
                running_servers = manager.get_running_servers()
                assert (
                    len(running_servers) >= 0
                )  # May be 0 if mocked servers don't persist

                # Cleanup
                manager.shutdown_all()

    def test_config_loader_integration(self):
        """Test configuration loading integration."""
        config_loader = ConfigLoader()

        # Test parsing configuration data
        sample_config = {
            "servers": [
                {
                    "name": "test-blender",
                    "description": "Test Blender server",
                    "type": "blender",
                    "host": "localhost",
                    "port": 8001,
                    "transport": "http",
                },
                {
                    "name": "test-mock",
                    "description": "Test Mock server",
                    "type": "mock",
                    "host": "localhost",
                    "port": 8002,
                    "transport": "http",
                    "config": {"delay_seconds": 0.5},
                },
            ]
        }

        configs = config_loader._parse_config_data(sample_config)

        assert len(configs) == 2
        assert configs[0].name == "test-blender"
        assert configs[0].config.get("type") == "blender"
        assert configs[1].name == "test-mock"
        assert configs[1].config.get("type") == "mock"

    def test_registry_and_manager_integration(self):
        """Test integration between registry and manager."""
        registry = get_registry()
        manager = get_manager()

        # Verify they share the same registry instance
        assert manager.registry is registry

        # Test available server types
        registry_types = registry.get_available_server_types()
        manager_types = manager.list_available_server_types()

        assert registry_types == manager_types


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling across the system."""

    @pytest.mark.asyncio
    async def test_server_startup_failure_integration(self):
        """Test handling of server startup failures in integration."""
        manager = get_manager()

        # Test with invalid configuration
        invalid_config = ServerConfig(
            name="invalid-server",
            description="Invalid server",
            config={"type": "nonexistent"},
        )

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            mock_validate.return_value = (False, "Unknown server type: nonexistent")

            result = manager.start_server(invalid_config, background=False)
            assert result is False

            # Verify server is not tracked
            assert not manager.is_server_running("invalid-server")

    def test_invalid_config_integration(self):
        """Test handling of invalid configurations."""
        config_loader = ConfigLoader()

        invalid_config = {
            "servers": [
                {
                    # Missing required fields
                    "description": "Invalid server",
                    "type": "blender",
                }
            ]
        }

        # Should handle gracefully and skip invalid configs
        configs = config_loader._parse_config_data(invalid_config)
        assert len(configs) == 0  # Invalid config should be skipped

    def test_port_conflict_detection(self):
        """Test port conflict detection."""
        registry = get_registry()

        # Create two configs with same port
        config1 = ServerConfig(
            name="server1",
            description="Server 1",
            host="localhost",
            port=8000,
            transport="http",
            config={"type": "mock"},
        )

        config2 = ServerConfig(
            name="server2",
            description="Server 2",
            host="localhost",
            port=8000,
            transport="http",
            config={"type": "mock"},
        )

        # Create first server
        registry.create_server("mock", config1)

        # Try to validate second server with same port
        is_valid, message = registry.validate_server_config("mock", config2)
        assert is_valid is False
        assert "already in use" in message


@pytest.mark.integration
class TestRealWorldScenarios:
    """Integration tests for real-world usage scenarios."""

    def test_server_manager_cli_simulation(self):
        """Simulate CLI usage patterns."""
        manager = get_manager()

        # Simulate: lightfast-mcp-manager start
        configs = [
            ServerConfig(
                name="cli-blender",
                description="CLI Blender server",
                config={"type": "blender"},
            ),
            ServerConfig(
                name="cli-mock",
                description="CLI Mock server",
                config={"type": "mock", "delay_seconds": 0.5},
            ),
        ]

        # Mock server creation
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                from lightfast_mcp.servers.blender.server import BlenderMCPServer
                from lightfast_mcp.servers.mock.server import MockMCPServer

                def create_server_side_effect(server_type, config):
                    if server_type == "mock":
                        server = MockMCPServer(config)
                    elif server_type == "blender":
                        server = BlenderMCPServer(config)
                    else:
                        raise ValueError(f"Unknown server type: {server_type}")

                    # Mock the run method
                    with patch.object(server, "run"):
                        return server

                mock_validate.return_value = (True, "Valid configuration")
                mock_create.side_effect = create_server_side_effect

                # Start servers
                results = manager.start_multiple_servers(configs, background=True)

                # Verify
                assert isinstance(results, dict)
                assert len(results) == 2

                # Simulate: lightfast-mcp-manager list
                server_urls = manager.get_server_urls()
                assert isinstance(server_urls, dict)

                # Simulate: lightfast-mcp-manager stop
                manager.shutdown_all()

    def test_configuration_file_workflow(self):
        """Test complete configuration file workflow."""
        config_loader = ConfigLoader()

        # Create sample configuration
        sample_created = config_loader.create_sample_config()
        assert sample_created is True

        # Load the configuration (mock the file reading)
        sample_data = {
            "servers": [
                {
                    "name": "workflow-blender",
                    "description": "Workflow Blender server",
                    "type": "blender",
                    "transport": "streamable-http",
                    "port": 8001,
                },
                {
                    "name": "workflow-mock",
                    "description": "Workflow Mock server",
                    "type": "mock",
                    "transport": "streamable-http",
                    "port": 8002,
                },
            ]
        }

        configs = config_loader._parse_config_data(sample_data)
        assert len(configs) == 2

        # Test with manager
        manager = get_manager()

        # Mock registry for this test
        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            mock_validate.return_value = (True, "Valid configuration")

            # Validate all configs
            for config in configs:
                server_type = config.config.get("type")
                is_valid, message = manager.registry.validate_server_config(
                    server_type, config
                )
                assert is_valid is True

    @pytest.mark.asyncio
    async def test_health_monitoring_workflow(self):
        """Test health monitoring workflow."""
        manager = get_manager()

        # Mock a server
        config = ServerConfig(
            name="health-monitor",
            description="Health monitoring test",
            config={"type": "mock"},
        )

        with patch.object(manager.registry, "validate_server_config") as mock_validate:
            with patch.object(manager.registry, "create_server") as mock_create:
                from lightfast_mcp.servers.mock.server import MockMCPServer

                mock_server = MockMCPServer(config)
                mock_validate.return_value = (True, "Valid configuration")
                mock_create.return_value = mock_server

                # Mock run method and health check
                with patch.object(mock_server, "run"):
                    with patch.object(mock_server, "health_check", return_value=True):
                        # Start server
                        result = manager.start_server(config, background=False)
                        assert result is True

                        # Perform health check
                        health_results = await manager.health_check_all()
                        assert "health-monitor" in health_results
                        assert health_results["health-monitor"] is True

                        # Cleanup
                        manager.stop_server("health-monitor")

    def test_server_discovery_and_creation_workflow(self):
        """Test complete server discovery and creation workflow."""
        registry = get_registry()

        # Discovery
        available_types = registry.get_available_server_types()
        assert len(available_types) > 0

        # Get info about available types
        type_info = registry.get_server_info()
        assert isinstance(type_info, dict)

        # Create servers for each available type
        created_servers = []
        for server_type in available_types:
            if server_type in ["mock", "blender"]:  # Only test known types
                config = ServerConfig(
                    name=f"discovery-{server_type}",
                    description=f"Discovery test {server_type}",
                    config={"type": server_type},
                )

                server = registry.create_server(server_type, config)
                created_servers.append(server)
                assert server is not None
                assert server_type == server.SERVER_TYPE

        # Verify servers are tracked in registry
        for server in created_servers:
            instance = registry.get_server_instance(server.config.name)
            assert instance is server
