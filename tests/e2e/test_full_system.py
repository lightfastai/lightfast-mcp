"""
End-to-end tests for the complete Lightfast MCP system.

These tests cover full workflows from CLI to server orchestration.
Updated to use the new ServerOrchestrator architecture.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lightfast_mcp.core.base_server import ServerConfig
from tools.orchestration import ConfigLoader, get_orchestrator, get_registry
from tools.orchestration.cli import main as cli_main


class TestFullSystemWorkflow:
    """Test complete system workflows."""

    def test_system_startup_and_discovery(self):
        """Test complete system startup and server discovery."""
        # Test registry discovery
        registry = get_registry()
        server_types = registry.get_available_server_types()

        # Should discover at least mock and blender servers
        assert "mock" in server_types
        assert "blender" in server_types

        # Test server info retrieval
        server_info = registry.get_server_info()
        assert len(server_info) >= 2

        for server_type, info in server_info.items():
            assert "version" in info
            assert "description" in info

    def test_config_creation_and_loading_workflow(self):
        """Test complete configuration workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            # 1. Create sample configuration
            success = loader.create_sample_config("servers.yaml")
            assert success is True

            # 2. Verify file was created
            config_file = config_dir / "servers.yaml"
            assert config_file.exists()

            # 3. Load configuration
            configs = loader.load_servers_config()
            assert len(configs) >= 2

            # 4. Verify configuration structure
            for config in configs:
                assert config.name
                assert config.config
                assert "type" in config.config

    @pytest.mark.asyncio
    async def test_server_lifecycle_management(self):
        """Test complete server lifecycle management using new ServerOrchestrator."""
        # Create test configuration
        test_config = ServerConfig(
            name="e2e-test-server",
            description="End-to-end test server",
            port=8099,  # Use unique port
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.1},
        )

        orchestrator = get_orchestrator()

        # 1. Start server
        result = await orchestrator.start_server(test_config, background=True)
        assert result.is_success

        # 2. Wait for server to fully initialize
        await asyncio.sleep(0.5)  # Give server time to start up

        # 3. Check server is running
        running_servers = orchestrator.get_running_servers()
        assert "e2e-test-server" in running_servers

        # 4. Get server status
        server_info = running_servers["e2e-test-server"]
        assert server_info is not None
        assert server_info.name == "e2e-test-server"

        # 5. Verify server accessibility through URLs
        if server_info.url:
            assert "8099" in server_info.url

        # 6. Stop server
        success = orchestrator.stop_server("e2e-test-server")
        assert success is True

        # Verify server is no longer running
        running_servers = orchestrator.get_running_servers()
        assert "e2e-test-server" not in running_servers

    def test_cli_integration_workflow(self):
        """Test CLI integration workflow."""
        with patch("tools.orchestration.cli.ConfigLoader") as mock_config_loader:
            mock_loader = MagicMock()
            mock_loader.create_sample_config.return_value = True
            mock_config_loader.return_value = mock_loader

            # Test init command
            with patch("sys.argv", ["cli.py", "init"]):
                cli_main()

            mock_loader.create_sample_config.assert_called_once()

    @pytest.mark.skip(reason="AI client tests deprecated - use new ConversationClient")
    async def test_ai_client_workflow_simulation(self):
        """DEPRECATED: AI client workflow test."""
        pytest.skip("AI client tests deprecated - use new ConversationClient")

    def test_error_handling_workflows(self):
        """Test error handling in various workflows."""
        # Test invalid configuration
        loader = ConfigLoader()

        with pytest.raises(ValueError):
            loader._parse_server_config({"type": "mock"})  # Missing name

        # Test orchestrator with invalid server
        orchestrator = get_orchestrator()
        invalid_config = ServerConfig(
            name="invalid-server",
            description="Invalid server",
            port=-1,  # Invalid port
            config={"type": "nonexistent"},
        )

        # This should be tested with async
        async def test_invalid_server():
            result = await orchestrator.start_server(invalid_config)
            assert result.is_failed

        asyncio.run(test_invalid_server())

    @pytest.mark.asyncio
    async def test_multi_server_coordination(self):
        """Test coordinating multiple servers using new ServerOrchestrator."""
        configs = [
            ServerConfig(
                name="coord-server-1",
                description="Coordination test server 1",
                port=8097,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.1},
            ),
            ServerConfig(
                name="coord-server-2",
                description="Coordination test server 2",
                port=8098,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.1},
            ),
        ]

        orchestrator = get_orchestrator()

        # Start multiple servers concurrently
        result = await orchestrator.start_multiple_servers(configs, background=True)
        assert result.is_success

        startup_results = result.data
        assert all(startup_results.values())

        # Wait for servers to fully initialize
        await asyncio.sleep(0.8)  # Give servers time to start up

        # Check all are running
        running_servers = orchestrator.get_running_servers()
        for config in configs:
            assert config.name in running_servers

        # Verify server URLs are accessible
        for config in configs:
            server_info = running_servers[config.name]
            if server_info.url:
                assert str(config.port) in server_info.url

        # Stop all
        orchestrator.shutdown_all()

        # Verify all stopped
        running_servers = orchestrator.get_running_servers()
        for config in configs:
            assert config.name not in running_servers


class TestSystemIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_development_workflow_scenario(self):
        """Test a typical development workflow scenario."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)

            # 1. Developer initializes project
            loader = ConfigLoader(config_dir=config_dir)
            success = loader.create_sample_config("servers.yaml")
            assert success is True

            # 2. Developer loads and modifies configuration
            configs = loader.load_servers_config()
            assert len(configs) >= 2

            # 3. Developer starts servers for testing (using sync wrapper functions)
            from tools.orchestration.cli import (
                get_server_urls_sync,
                shutdown_all_sync,
                start_multiple_servers_sync,
            )

            mock_configs = [c for c in configs if c.config.get("type") == "mock"]

            if mock_configs:
                # Modify port to avoid conflicts
                mock_configs[0].port = 8096

                results = start_multiple_servers_sync(mock_configs[:1], background=True)
                assert any(results.values())

                # 4. Developer checks server status
                urls = get_server_urls_sync()
                assert len(urls) >= 1

                # 5. Developer shuts down when done
                shutdown_all_sync()

    @pytest.mark.asyncio
    async def test_production_deployment_scenario(self):
        """Test a production deployment scenario using new ServerOrchestrator."""
        # Create production-like configuration
        prod_config = ServerConfig(
            name="prod-mock-server",
            description="Production mock server",
            host="0.0.0.0",  # Listen on all interfaces
            port=8095,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.05},  # Fast response
        )

        orchestrator = get_orchestrator()

        # 1. Start server
        result = await orchestrator.start_server(prod_config, background=True)
        assert result.is_success

        # 2. Verify server is running
        await asyncio.sleep(0.5)  # Give more time for production startup
        running_servers = orchestrator.get_running_servers()
        assert "prod-mock-server" in running_servers

        # 3. Verify accessibility
        server_info = running_servers["prod-mock-server"]
        assert server_info.url is not None

        # 4. Graceful shutdown
        orchestrator.shutdown_all()

    def test_configuration_management_scenario(self):
        """Test configuration management scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            loader = ConfigLoader(config_dir=config_dir)

            # 1. Create initial configuration
            success = loader.create_sample_config("servers.yaml")
            assert success is True

            # 2. Load and verify configuration
            configs = loader.load_servers_config()
            assert len(configs) >= 2  # Verify we have initial configs

            # 3. Test environment override
            env_config = {
                "servers": [
                    {
                        "name": "env-override-server",
                        "type": "mock",
                        "config": {"type": "mock"},
                    }
                ]
            }

            with patch.dict(
                os.environ, {"LIGHTFAST_MCP_SERVERS": str(env_config).replace("'", '"')}
            ):
                # Use the environment-specific loader function
                from tools.orchestration.config_loader import load_config_from_env

                env_configs = load_config_from_env()
                # Should load from environment instead of file
                assert len(env_configs) == 1
                assert env_configs[0].name == "env-override-server"

    @pytest.mark.xfail(
        reason="Port conflict detection timing issue with subprocess startup - test infrastructure issue"
    )
    @pytest.mark.asyncio
    async def test_error_recovery_scenario(self):
        """Test system error recovery scenarios using new ServerOrchestrator."""
        orchestrator = get_orchestrator()

        # 1. Try to start server with conflicting port
        config1 = ServerConfig(
            name="conflict-server-1",
            description="Conflict test server 1",
            port=8094,
            transport="streamable-http",
            config={"type": "mock"},
        )

        config2 = ServerConfig(
            name="conflict-server-2",
            description="Conflict test server 2",
            port=8094,  # Same port
            transport="streamable-http",
            config={"type": "mock"},
        )

        # Start first server
        result1 = await orchestrator.start_server(config1, background=True)
        assert result1.is_success

        # Try to start second server on same port (should fail gracefully)
        result2 = await orchestrator.start_server(config2, background=True)
        assert result2.is_failed

        # First server should still be running
        running_servers = orchestrator.get_running_servers()
        assert "conflict-server-1" in running_servers
        assert "conflict-server-2" not in running_servers

        # Cleanup
        orchestrator.shutdown_all()


class TestSystemPerformance:
    """Test system performance characteristics."""

    @pytest.mark.asyncio
    async def test_startup_performance(self):
        """Test system startup performance using new ServerOrchestrator."""
        import time

        # Measure server startup time
        config = ServerConfig(
            name="perf-test-server",
            description="Performance test server",
            port=8093,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        orchestrator = get_orchestrator()

        start_time = time.time()
        result = await orchestrator.start_server(config, background=True)
        startup_time = time.time() - start_time

        assert result.is_success
        assert startup_time < 5.0  # Should start within 5 seconds

        # Cleanup
        orchestrator.shutdown_all()

    @pytest.mark.asyncio
    async def test_concurrent_server_management(self):
        """Test managing multiple servers concurrently using new ServerOrchestrator."""
        configs = []
        for i in range(3):
            configs.append(
                ServerConfig(
                    name=f"concurrent-server-{i}",
                    description=f"Concurrent test server {i}",
                    port=8090 + i,
                    transport="streamable-http",
                    config={"type": "mock", "delay_seconds": 0.01},
                )
            )

        orchestrator = get_orchestrator()

        # Start all servers concurrently
        import time

        start_time = time.time()
        result = await orchestrator.start_multiple_servers(configs, background=True)
        total_time = time.time() - start_time

        # All should start successfully
        assert result.is_success
        startup_results = result.data
        assert all(startup_results.values())

        # Should be faster than starting sequentially
        assert total_time < 10.0  # Reasonable timeout

        # All should be running
        running_servers = orchestrator.get_running_servers()
        for config in configs:
            assert config.name in running_servers

        # Cleanup
        orchestrator.shutdown_all()
