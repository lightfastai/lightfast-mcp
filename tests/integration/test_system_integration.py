"""
Integration tests for the complete lightfast-mcp system.

These tests verify that components work together correctly in realistic scenarios.
They use real servers and connections but with controlled environments.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
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
        assert "blender" in available_types
        assert "mock" in available_types

        # Test getting server info for all types
        info = registry.get_server_info()
        assert isinstance(info, dict)
        assert len(info) > 0

        # Verify each server type has required metadata
        for server_type, server_info in info.items():
            assert "version" in server_info
            assert "description" in server_info
            assert "class_name" in server_info

    @pytest.mark.asyncio
    async def test_full_server_lifecycle_integration(self):
        """Test complete server lifecycle through the orchestrator."""
        orchestrator = get_orchestrator()

        # Create test configuration
        test_config = ServerConfig(
            name="integration-test-server",
            description="Integration test server",
            port=8097,  # Use unique port
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.1},
        )

        try:
            # 1. Start server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success, f"Failed to start server: {result.error}"

            # 2. Wait for server to initialize
            await asyncio.sleep(0.5)

            # 3. Verify server is running
            running_servers = orchestrator.get_running_servers()
            assert "integration-test-server" in running_servers

            # 4. Test server health and accessibility
            server_info = running_servers["integration-test-server"]
            assert server_info.name == "integration-test-server"
            assert server_info.url is not None
            assert "8097" in server_info.url

            # 5. Test server can be stopped
            stop_result = orchestrator.stop_server("integration-test-server")
            assert stop_result is True

            # 6. Verify server is no longer running
            await asyncio.sleep(0.2)  # Give time for cleanup
            running_servers = orchestrator.get_running_servers()
            assert "integration-test-server" not in running_servers

        finally:
            # Cleanup - ensure server is stopped
            orchestrator.stop_server("integration-test-server")

    @pytest.mark.asyncio
    async def test_multi_server_integration(self):
        """Test running multiple servers simultaneously."""
        orchestrator = get_orchestrator()

        configs = [
            ServerConfig(
                name="multi-server-1",
                description="Multi test server 1",
                port=8098,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.05},
            ),
            ServerConfig(
                name="multi-server-2",
                description="Multi test server 2",
                port=8099,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.05},
            ),
        ]

        try:
            # Start multiple servers concurrently
            result = await orchestrator.start_multiple_servers(configs, background=True)
            assert result.is_success

            startup_results = result.data
            assert all(startup_results.values()), (
                f"Some servers failed to start: {startup_results}"
            )

            # Wait for servers to initialize
            await asyncio.sleep(0.8)

            # Verify all servers are running
            running_servers = orchestrator.get_running_servers()
            for config in configs:
                assert config.name in running_servers
                server_info = running_servers[config.name]
                assert server_info.url is not None

        finally:
            # Cleanup
            orchestrator.shutdown_all()

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
                    "transport": "streamable-http",
                },
                {
                    "name": "test-mock",
                    "description": "Test Mock server",
                    "type": "mock",
                    "host": "localhost",
                    "port": 8002,
                    "transport": "streamable-http",
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

    @pytest.mark.asyncio
    async def test_server_startup_performance_integration(self):
        """Test server startup performance in integration environment."""
        orchestrator = get_orchestrator()

        config = ServerConfig(
            name="perf-test-server",
            description="Performance test server",
            port=8096,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        try:
            start_time = time.time()
            result = await orchestrator.start_server(config, background=True)
            startup_time = time.time() - start_time

            assert result.is_success
            assert startup_time < 3.0, f"Server startup took too long: {startup_time}s"

            # Verify server is actually accessible
            await asyncio.sleep(0.3)
            running_servers = orchestrator.get_running_servers()
            assert "perf-test-server" in running_servers

        finally:
            orchestrator.stop_server("perf-test-server")


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling across the system."""

    @pytest.mark.asyncio
    async def test_server_startup_failure_integration(self):
        """Test handling of server startup failures in integration."""
        orchestrator = get_orchestrator()

        # Create config with invalid configuration that should fail validation
        invalid_config = ServerConfig(
            name="invalid-server",
            description="Invalid server",
            port=99999,  # Port out of valid range
            transport="streamable-http",
            config={"type": "nonexistent"},  # Invalid server type
        )

        result = await orchestrator.start_server(invalid_config)
        # Should fail due to invalid server type or port validation
        assert result.is_failed or "nonexistent" in str(result.error) or result.error

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
            transport="streamable-http",
            config={"type": "mock"},
        )

        config2 = ServerConfig(
            name="server2",
            description="Server 2",
            host="localhost",
            port=8000,
            transport="streamable-http",
            config={"type": "mock"},
        )

        # Create first server
        registry.create_server("mock", config1)

        # Try to validate second server with same port
        is_valid, message = registry.validate_server_config("mock", config2)
        assert is_valid is False
        assert "already in use" in message

    @pytest.mark.asyncio
    async def test_graceful_shutdown_integration(self):
        """Test graceful shutdown of multiple servers."""
        orchestrator = get_orchestrator()

        configs = [
            ServerConfig(
                name=f"shutdown-test-{i}",
                description=f"Shutdown test server {i}",
                port=8090 + i,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            )
            for i in range(3)
        ]

        try:
            # Start multiple servers
            result = await orchestrator.start_multiple_servers(configs, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)  # Let servers initialize

            # Verify all are running
            running_servers = orchestrator.get_running_servers()
            for config in configs:
                assert config.name in running_servers

            # Test graceful shutdown
            orchestrator.shutdown_all()

            # Verify all servers are stopped
            await asyncio.sleep(0.3)  # Give time for shutdown
            running_servers = orchestrator.get_running_servers()
            for config in configs:
                assert config.name not in running_servers

        finally:
            # Ensure cleanup
            orchestrator.shutdown_all()


@pytest.mark.integration
class TestRealWorldScenarios:
    """Integration tests for real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_server_manager_cli_simulation(self):
        """Simulate CLI usage patterns with real orchestrator."""
        # Use the orchestrator directly instead of CLI sync wrappers to avoid event loop conflicts
        orchestrator = get_orchestrator()

        # Create test configuration
        config = ServerConfig(
            name="cli-test-server",
            description="CLI test server",
            port=8095,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.05},
        )

        try:
            # Test server startup
            result = await orchestrator.start_server(config, background=True)
            assert result.is_success, f"Failed to start server: {result.error}"

            await asyncio.sleep(0.3)

            # Test getting server status
            running_servers = orchestrator.get_running_servers()
            assert "cli-test-server" in running_servers

            # Test getting URLs
            server_info = running_servers["cli-test-server"]
            assert server_info.url is not None
            assert "8095" in server_info.url

        finally:
            # Cleanup
            orchestrator.shutdown_all()

    def test_configuration_file_workflow(self):
        """Test complete configuration file workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            config_loader = ConfigLoader(config_dir=config_dir)

            # 1. Create sample configuration
            sample_created = config_loader.create_sample_config("servers.yaml")
            assert sample_created is True

            # 2. Verify file was created and has content
            config_file = config_dir / "servers.yaml"
            assert config_file.exists()
            assert config_file.stat().st_size > 0

            # 3. Load the configuration
            configs = config_loader.load_servers_config()
            assert len(configs) >= 2

            # 4. Verify configuration structure
            for config in configs:
                assert config.name
                assert config.config
                assert "type" in config.config

            # 5. Test with orchestrator validation
            orchestrator = get_orchestrator()
            for config in configs:
                server_type = config.config.get("type")
                is_valid, message = orchestrator.registry.validate_server_config(
                    server_type, config
                )
                # Should be valid or have a clear reason why not
                if not is_valid:
                    assert message  # Should have error message

    @pytest.mark.asyncio
    async def test_health_monitoring_workflow(self):
        """Test health monitoring workflow."""
        orchestrator = get_orchestrator()

        config = ServerConfig(
            name="health-test-server",
            description="Health monitoring test server",
            port=8094,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        try:
            # Start server
            result = await orchestrator.start_server(config, background=True)
            assert result.is_success

            await asyncio.sleep(0.3)

            # Test health monitoring
            running_servers = orchestrator.get_running_servers()
            assert "health-test-server" in running_servers

            server_info = running_servers["health-test-server"]
            assert server_info.name == "health-test-server"
            assert server_info.url is not None

            # Test server is responsive (basic check)
            assert server_info.state.name in ["RUNNING", "HEALTHY"]

        finally:
            orchestrator.stop_server("health-test-server")

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

    @pytest.mark.asyncio
    async def test_concurrent_server_operations(self):
        """Test concurrent server operations under load."""
        orchestrator = get_orchestrator()

        # Create multiple configs for concurrent testing
        configs = [
            ServerConfig(
                name=f"concurrent-{i}",
                description=f"Concurrent test server {i}",
                port=8080 + i,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            )
            for i in range(5)
        ]

        try:
            # Test concurrent startup
            start_time = time.time()
            result = await orchestrator.start_multiple_servers(configs, background=True)
            startup_time = time.time() - start_time

            assert result.is_success
            assert startup_time < 10.0  # Should complete within reasonable time

            startup_results = result.data
            successful_starts = sum(
                1 for success in startup_results.values() if success
            )
            assert successful_starts >= 3  # At least most should succeed

            await asyncio.sleep(0.8)  # Let servers initialize

            # Test concurrent status checks
            running_servers = orchestrator.get_running_servers()
            assert len(running_servers) >= 3

            # Test concurrent shutdown
            shutdown_start = time.time()
            orchestrator.shutdown_all()
            shutdown_time = time.time() - shutdown_start

            assert shutdown_time < 5.0  # Should shutdown quickly

        finally:
            orchestrator.shutdown_all()

    def test_environment_configuration_integration(self):
        """Test environment-based configuration integration."""
        import json

        env_config = {
            "servers": [
                {
                    "name": "env-test-server",
                    "type": "mock",
                    "transport": "streamable-http",
                    "port": 8093,
                    "config": {"type": "mock", "delay_seconds": 0.1},
                }
            ]
        }

        with patch.dict(os.environ, {"LIGHTFAST_MCP_SERVERS": json.dumps(env_config)}):
            from tools.orchestration.config_loader import load_config_from_env

            configs = load_config_from_env()
            assert len(configs) == 1
            assert configs[0].name == "env-test-server"
            assert configs[0].port == 8093
