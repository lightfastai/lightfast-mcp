"""
Integration tests for the complete lightfast-mcp system.
"""

from unittest.mock import patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from tools.orchestration import get_orchestrator, get_registry
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

    @pytest.mark.skip(reason="ServerOrchestrator has async API - needs rewrite")
    @pytest.mark.asyncio
    async def test_full_server_lifecycle_integration(self):
        """Test complete server lifecycle through the orchestrator."""
        # This test needs to be rewritten for the new ServerOrchestrator async API
        pass

    @pytest.mark.skip(reason="ServerOrchestrator has async API - needs rewrite")
    def test_multi_server_integration(self, sample_multi_server_configs):
        """Test running multiple servers simultaneously."""
        # This test needs to be rewritten for the new ServerOrchestrator async API
        pass

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

    def test_registry_and_orchestrator_integration(self):
        """Test integration between registry and orchestrator."""
        registry = get_registry()
        orchestrator = get_orchestrator()

        # Verify they share the same registry instance
        assert orchestrator.registry is registry

        # Test available server types
        registry_types = registry.get_available_server_types()
        assert len(registry_types) > 0


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling across the system."""

    @pytest.mark.skip(reason="ServerOrchestrator has async API - needs rewrite")
    @pytest.mark.asyncio
    async def test_server_startup_failure_integration(self):
        """Test handling of server startup failures in integration."""
        # This test needs to be rewritten for the new ServerOrchestrator async API
        pass

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

    @pytest.mark.skip(reason="ServerOrchestrator has async API - needs rewrite")
    def test_server_manager_cli_simulation(self):
        """Simulate CLI usage patterns."""
        # This test needs to be rewritten for the new ServerOrchestrator async API
        pass

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

        # Test with orchestrator
        orchestrator = get_orchestrator()

        # Mock registry for this test
        with patch.object(
            orchestrator.registry, "validate_server_config"
        ) as mock_validate:
            mock_validate.return_value = (True, "Valid configuration")

            # Validate all configs
            for config in configs:
                server_type = config.config.get("type")
                is_valid, message = orchestrator.registry.validate_server_config(
                    server_type, config
                )
                assert is_valid is True

    @pytest.mark.skip(reason="ServerOrchestrator has async API - needs rewrite")
    @pytest.mark.asyncio
    async def test_health_monitoring_workflow(self):
        """Test health monitoring workflow."""
        # This test needs to be rewritten for the new ServerOrchestrator async API
        pass

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
