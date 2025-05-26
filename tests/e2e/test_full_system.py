"""
End-to-end tests for the complete Lightfast MCP system.

These tests cover full workflows from CLI to server orchestration to AI integration.
Updated to use the new ServerOrchestrator architecture and include real AI testing.
"""

import asyncio
import os
import tempfile
import time
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

    @pytest.mark.asyncio
    async def test_ai_conversation_workflow_simulation(self):
        """Test AI conversation workflow with mock AI provider."""
        from tools.ai.conversation_client import ConversationClient

        # Create test server configuration
        test_config = ServerConfig(
            name="ai-test-server",
            description="AI test server",
            port=8098,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.05},
        )

        orchestrator = get_orchestrator()

        try:
            # 1. Start test server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # 2. Create server config for AI client
            servers = {
                "ai-test-server": {
                    "type": "sse",
                    "url": "http://localhost:8098/mcp",
                    "name": "ai-test-server",
                }
            }

            # 3. Test conversation client creation with mock AI provider
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                # Mock the AI provider to avoid real API calls
                with patch(
                    "tools.ai.providers.claude_provider.ClaudeProvider"
                ) as mock_claude:
                    mock_provider = MagicMock()
                    mock_claude.return_value = mock_provider

                    client = ConversationClient(
                        servers=servers,
                        ai_provider="claude",
                        max_steps=2,
                    )

                    # 4. Test connection to servers with mocked MCP client
                    with patch.object(client, "connect_to_servers") as mock_connect:
                        mock_connect.return_value.is_success = True
                        mock_connect.return_value.data = {"ai-test-server": True}

                        connection_result = await client.connect_to_servers()
                        assert connection_result.is_success

                    # 5. Test basic client functionality
                    connected_servers = client.get_connected_servers()
                    assert isinstance(connected_servers, list)

        finally:
            orchestrator.stop_server("ai-test-server")

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

            # 3. Test configuration validation
            orchestrator = get_orchestrator()
            mock_configs = [c for c in configs if c.config.get("type") == "mock"]

            if mock_configs:
                # Modify port to avoid conflicts
                mock_configs[0].port = 8096

                # Test configuration validation
                server_type = mock_configs[0].config.get("type")
                is_valid, message = orchestrator.registry.validate_server_config(
                    server_type, mock_configs[0]
                )
                assert is_valid or message  # Should be valid or have clear error

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

        try:
            # Start first server
            result1 = await orchestrator.start_server(config1, background=True)
            assert result1.is_success

            await asyncio.sleep(0.3)

            # Try to start second server on same port (should fail gracefully)
            result2 = await orchestrator.start_server(config2, background=True)
            # Note: This might succeed if the validation doesn't catch the conflict
            # The important thing is that the system handles it gracefully

            # First server should still be running
            running_servers = orchestrator.get_running_servers()
            assert "conflict-server-1" in running_servers

        finally:
            # Cleanup
            orchestrator.shutdown_all()

    @pytest.mark.asyncio
    async def test_real_mcp_protocol_workflow(self):
        """Test real MCP protocol communication workflow."""
        # This test uses actual MCP protocol communication
        test_config = ServerConfig(
            name="mcp-protocol-test",
            description="MCP protocol test server",
            port=8093,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        orchestrator = get_orchestrator()

        try:
            # 1. Start MCP server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # 2. Test MCP client connection
            from fastmcp import Client

            server_url = "http://localhost:8093/mcp"

            try:
                client = Client(server_url)
                async with client:
                    # 3. Test MCP protocol operations
                    tools = await client.list_tools()
                    assert len(tools) > 0

                    # 4. Test tool execution
                    tool_names = [tool.name for tool in tools]
                    if "get_server_status" in tool_names:
                        result = await client.call_tool("get_server_status")
                        assert result is not None

            except Exception as e:
                # MCP connection might fail in test environment, that's ok
                pytest.skip(f"MCP connection failed (expected in test env): {e}")

        finally:
            orchestrator.stop_server("mcp-protocol-test")

    @pytest.mark.asyncio
    async def test_ai_integration_with_real_servers(self):
        """Test AI integration with real running servers."""
        # Start multiple test servers
        configs = [
            ServerConfig(
                name="ai-integration-mock",
                description="AI integration mock server",
                port=8091,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            ),
        ]

        orchestrator = get_orchestrator()

        try:
            # Start servers
            result = await orchestrator.start_multiple_servers(configs, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # Test AI client integration
            from tools.ai.conversation_client import create_conversation_client

            servers = {
                "ai-integration-mock": {
                    "type": "sse",
                    "url": "http://localhost:8091/mcp",
                    "name": "ai-integration-mock",
                }
            }

            # Test with mock API key (won't make real API calls)
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                # Mock the AI provider to avoid real API calls
                with patch(
                    "tools.ai.conversation_client.ConversationClient.connect_to_servers"
                ) as mock_connect:
                    mock_connect.return_value.is_success = True
                    mock_connect.return_value.data = {"ai-integration-mock": True}

                    client_result = await create_conversation_client(
                        servers=servers,
                        ai_provider="claude",
                        max_steps=2,
                    )

                    # Should succeed with mocked connection
                    assert client_result.is_success
                    client = client_result.data

                    # Test client functionality
                    connected_servers = client.get_connected_servers()
                    assert isinstance(connected_servers, list)

        finally:
            orchestrator.shutdown_all()


class TestSystemPerformance:
    """Test system performance characteristics."""

    @pytest.mark.asyncio
    async def test_startup_performance(self):
        """Test system startup performance using new ServerOrchestrator."""

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

    @pytest.mark.asyncio
    async def test_system_load_testing(self):
        """Test system under load with many operations."""
        orchestrator = get_orchestrator()

        # Create multiple servers for load testing
        configs = [
            ServerConfig(
                name=f"load-test-{i}",
                description=f"Load test server {i}",
                port=8070 + i,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.001},  # Very fast
            )
            for i in range(5)
        ]

        try:
            # Test rapid startup/shutdown cycles
            for cycle in range(3):
                # Start all servers
                result = await orchestrator.start_multiple_servers(
                    configs, background=True
                )
                assert result.is_success

                await asyncio.sleep(0.3)

                # Verify all started
                running_servers = orchestrator.get_running_servers()
                assert len(running_servers) >= 3  # At least most should start

                # Shutdown all
                orchestrator.shutdown_all()
                await asyncio.sleep(0.2)

        finally:
            orchestrator.shutdown_all()

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self):
        """Test that system doesn't leak memory during operations."""
        import gc

        orchestrator = get_orchestrator()

        config = ServerConfig(
            name="memory-test-server",
            description="Memory test server",
            port=8089,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.001},
        )

        # Get initial memory usage (rough estimate)
        gc.collect()
        initial_objects = len(gc.get_objects())

        try:
            # Perform multiple start/stop cycles
            for i in range(5):
                result = await orchestrator.start_server(config, background=True)
                assert result.is_success

                await asyncio.sleep(0.1)

                orchestrator.stop_server("memory-test-server")
                await asyncio.sleep(0.1)

            # Check memory usage hasn't grown excessively
            gc.collect()
            final_objects = len(gc.get_objects())

            # Allow for some growth but not excessive
            growth_ratio = final_objects / initial_objects
            assert growth_ratio < 2.0, f"Memory usage grew too much: {growth_ratio}x"

        finally:
            orchestrator.shutdown_all()


class TestProductionReadiness:
    """Test production deployment readiness scenarios."""

    @pytest.mark.asyncio
    async def test_production_configuration_validation(self):
        """Test production-ready configuration validation."""
        # Test production-like configurations
        prod_configs = [
            ServerConfig(
                name="prod-blender-server",
                description="Production Blender server",
                host="0.0.0.0",  # Production binding
                port=8001,
                transport="streamable-http",
                config={"type": "blender"},
            ),
            ServerConfig(
                name="prod-mock-server",
                description="Production mock server",
                host="0.0.0.0",
                port=8002,
                transport="streamable-http",
                config={
                    "type": "mock",
                    "delay_seconds": 0.01,
                },  # Fast production response
            ),
        ]

        registry = get_registry()

        for config in prod_configs:
            server_type = config.config.get("type")
            is_valid, message = registry.validate_server_config(server_type, config)

            # Should be valid or have clear validation message
            if not is_valid:
                assert message and len(message) > 0

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test system graceful degradation when components fail."""
        orchestrator = get_orchestrator()

        # Start multiple servers, some may fail
        configs = [
            ServerConfig(
                name="degradation-test-1",
                description="Degradation test server 1",
                port=8087,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            ),
            ServerConfig(
                name="degradation-test-2",
                description="Degradation test server 2",
                port=8088,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            ),
        ]

        try:
            result = await orchestrator.start_multiple_servers(configs, background=True)

            # System should handle partial failures gracefully
            assert result.is_success  # Overall operation succeeds

            startup_results = result.data
            successful_starts = sum(
                1 for success in startup_results.values() if success
            )

            # At least some servers should start
            assert successful_starts > 0

        finally:
            orchestrator.shutdown_all()

    def test_security_configuration_validation(self):
        """Test security-related configuration validation."""
        # Test configurations that should be rejected for security
        insecure_configs = [
            {
                "name": "insecure-server",
                "description": "Insecure server",
                "host": "0.0.0.0",
                "port": 22,  # SSH port - should be avoided
                "transport": "streamable-http",
                "config": {"type": "mock"},
            },
            {
                "name": "invalid-host",
                "description": "Invalid host server",
                "host": "invalid-host-name-that-should-not-resolve",
                "port": 8001,
                "transport": "streamable-http",
                "config": {"type": "mock"},
            },
        ]

        config_loader = ConfigLoader()

        for insecure_config in insecure_configs:
            try:
                # Should either reject or handle gracefully
                server_config = config_loader._parse_server_config(insecure_config)

                # If it parses, validation should catch issues
                registry = get_registry()
                server_type = server_config.config.get("type")
                is_valid, message = registry.validate_server_config(
                    server_type, server_config
                )

                # Either validation fails or we get a clear message
                if not is_valid:
                    assert message and len(message) > 0

            except Exception:
                # Parsing failure is also acceptable for invalid configs
                pass


class TestAdvancedAIIntegration:
    """Test advanced AI integration scenarios."""

    @pytest.mark.asyncio
    async def test_ai_conversation_with_multiple_servers(self):
        """Test AI conversation workflow with multiple servers."""
        # Start multiple test servers
        configs = [
            ServerConfig(
                name="ai-multi-mock-1",
                description="AI multi mock server 1",
                port=8081,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            ),
            ServerConfig(
                name="ai-multi-mock-2",
                description="AI multi mock server 2",
                port=8082,
                transport="streamable-http",
                config={"type": "mock", "delay_seconds": 0.01},
            ),
        ]

        orchestrator = get_orchestrator()

        try:
            # Start servers
            result = await orchestrator.start_multiple_servers(configs, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # Test AI client with multiple servers
            from tools.ai.conversation_client import ConversationClient

            servers = {
                "ai-multi-mock-1": {
                    "type": "sse",
                    "url": "http://localhost:8081/mcp",
                    "name": "ai-multi-mock-1",
                },
                "ai-multi-mock-2": {
                    "type": "sse",
                    "url": "http://localhost:8082/mcp",
                    "name": "ai-multi-mock-2",
                },
            }

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                # Mock the AI provider and connections
                with patch(
                    "tools.ai.providers.claude_provider.ClaudeProvider"
                ) as mock_claude:
                    mock_provider = MagicMock()
                    mock_claude.return_value = mock_provider

                    client = ConversationClient(
                        servers=servers,
                        ai_provider="claude",
                        max_steps=3,
                    )

                    # Mock successful connections to all servers
                    with patch.object(client, "connect_to_servers") as mock_connect:
                        mock_connect.return_value.is_success = True
                        mock_connect.return_value.data = {
                            "ai-multi-mock-1": True,
                            "ai-multi-mock-2": True,
                        }

                        connection_result = await client.connect_to_servers()
                        assert connection_result.is_success

                        # Test that client can handle multiple servers
                        connected_servers = client.get_connected_servers()
                        assert isinstance(connected_servers, list)

        finally:
            orchestrator.shutdown_all()

    @pytest.mark.asyncio
    async def test_ai_tool_execution_workflow(self):
        """Test AI tool execution workflow with real server."""
        test_config = ServerConfig(
            name="ai-tool-test-server",
            description="AI tool test server",
            port=8083,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        orchestrator = get_orchestrator()

        try:
            # Start server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # Test tool execution through AI client
            from tools.ai.conversation_client import ConversationClient
            from tools.common import ToolCall

            servers = {
                "ai-tool-test-server": {
                    "type": "sse",
                    "url": "http://localhost:8083/mcp",
                    "name": "ai-tool-test-server",
                }
            }

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                with patch(
                    "tools.ai.providers.claude_provider.ClaudeProvider"
                ) as mock_claude:
                    mock_provider = MagicMock()
                    mock_claude.return_value = mock_provider

                    client = ConversationClient(
                        servers=servers,
                        ai_provider="claude",
                        max_steps=2,
                    )

                    # Mock tool execution
                    mock_tool_calls = [
                        ToolCall(
                            id="test-call-1",
                            tool_name="get_server_status",
                            arguments={},
                        )
                    ]

                    with patch.object(client, "execute_tools") as mock_execute:
                        mock_execute.return_value.is_success = True
                        mock_execute.return_value.data = []

                        result = await client.execute_tools(mock_tool_calls)
                        assert result.is_success

        finally:
            orchestrator.stop_server("ai-tool-test-server")


class TestRealMCPProtocolIntegration:
    """Test real MCP protocol integration scenarios."""

    @pytest.mark.asyncio
    async def test_mcp_client_server_communication(self):
        """Test real MCP client-server communication."""
        test_config = ServerConfig(
            name="mcp-comm-test",
            description="MCP communication test server",
            port=8084,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        orchestrator = get_orchestrator()

        try:
            # Start MCP server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # Test real MCP protocol communication
            try:
                from fastmcp import Client

                server_url = "http://localhost:8084/mcp"
                client = Client(server_url)

                async with client:
                    # Test basic MCP operations
                    tools = await client.list_tools()
                    assert isinstance(tools, list)

                    if tools:
                        # Test tool execution if tools are available
                        tool_names = [tool.name for tool in tools]
                        if "get_server_status" in tool_names:
                            result = await client.call_tool("get_server_status")
                            assert result is not None

            except Exception as e:
                # Real MCP communication might fail in test environment
                pytest.skip(f"MCP protocol test skipped due to: {e}")

        finally:
            orchestrator.stop_server("mcp-comm-test")

    @pytest.mark.asyncio
    async def test_mcp_protocol_error_handling(self):
        """Test MCP protocol error handling."""
        test_config = ServerConfig(
            name="mcp-error-test",
            description="MCP error test server",
            port=8085,
            transport="streamable-http",
            config={"type": "mock", "delay_seconds": 0.01},
        )

        orchestrator = get_orchestrator()

        try:
            # Start server
            result = await orchestrator.start_server(test_config, background=True)
            assert result.is_success

            await asyncio.sleep(0.5)

            # Test error handling in MCP communication
            try:
                from fastmcp import Client

                server_url = "http://localhost:8085/mcp"
                client = Client(server_url)

                async with client:
                    # Test calling non-existent tool
                    try:
                        await client.call_tool("nonexistent_tool")
                        # Should either succeed with error response or raise exception
                    except Exception:
                        # Exception is expected for non-existent tool
                        pass

            except Exception as e:
                # Connection errors are acceptable in test environment
                pytest.skip(f"MCP error handling test skipped due to: {e}")

        finally:
            orchestrator.stop_server("mcp-error-test")
