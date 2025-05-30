import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lightfast_mcp.servers import photoshop_mcp_server
from lightfast_mcp.servers.photoshop_mcp_server import (
    check_photoshop_connected,
    execute_photoshop_code,
    get_document_info,
    send_to_photoshop,
)

# Mark async tests with asyncio
pytestmark = pytest.mark.asyncio


class TestPhotoshopPerformance:
    """Performance tests for Photoshop MCP server."""

    async def test_high_frequency_commands(self):
        """Test server performance under high frequency command execution."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()
            photoshop_mcp_server.command_id_counter = 0

            command_count = 100
            mock_response = {"status": "success", "data": {"result": "test"}}

            # Mock fast responses
            async def fast_wait_for(future, timeout):
                await asyncio.sleep(0.001)  # 1ms delay
                return mock_response

            with (
                patch("asyncio.wait_for", side_effect=fast_wait_for),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                start_time = time.time()

                # Execute commands sequentially
                for i in range(command_count):
                    result = await send_to_photoshop(f"command{i}", {"param": f"value{i}"})
                    assert result["status"] == "success"

                end_time = time.time()
                duration = end_time - start_time

                # Should complete 100 commands in reasonable time (< 5 seconds)
                assert duration < 5.0
                print(
                    f"Sequential execution: {command_count} commands in {duration:.3f}s ({command_count / duration:.1f} cmd/s)"
                )

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_concurrent_command_performance(self):
        """Test concurrent command execution performance."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()
            photoshop_mcp_server.command_id_counter = 0

            command_count = 50
            mock_response = {"status": "success", "data": {"result": "test"}}

            # Mock responses with slight delay
            async def delayed_wait_for(future, timeout):
                await asyncio.sleep(0.01)  # 10ms delay
                return mock_response

            with (
                patch("asyncio.wait_for", side_effect=delayed_wait_for),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                start_time = time.time()

                # Execute commands concurrently
                tasks = [send_to_photoshop(f"command{i}", {"param": f"value{i}"}) for i in range(command_count)]

                results = await asyncio.gather(*tasks)

                end_time = time.time()
                duration = end_time - start_time

                # Verify all commands succeeded
                assert len(results) == command_count
                for result in results:
                    assert result["status"] == "success"

                # Concurrent execution should be significantly faster than sequential
                # With 10ms delay per command, concurrent should complete in ~10ms + overhead
                # while sequential would take ~500ms
                assert duration < 1.0  # Should complete in under 1 second
                print(
                    f"Concurrent execution: {command_count} commands in {duration:.3f}s ({command_count / duration:.1f} cmd/s)"
                )

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_memory_usage_with_many_commands(self):
        """Test memory usage doesn't grow excessively with many commands."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()
            photoshop_mcp_server.command_id_counter = 0

            mock_response = {"status": "success", "data": {"result": "test"}}

            with (
                patch("asyncio.wait_for", return_value=mock_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                # Execute many commands in batches
                batch_size = 20
                num_batches = 5

                for batch in range(num_batches):
                    # Execute a batch of commands
                    tasks = [
                        send_to_photoshop(f"command{batch}_{i}", {"param": f"value{i}"}) for i in range(batch_size)
                    ]

                    results = await asyncio.gather(*tasks)

                    # Verify batch completed successfully
                    assert len(results) == batch_size
                    for result in results:
                        assert result["status"] == "success"

                    # Check that responses dict doesn't grow indefinitely
                    # It should be cleaned up after each command completes
                    assert len(photoshop_mcp_server.responses) <= batch_size

                # Verify final state
                print(f"Final responses dict size: {len(photoshop_mcp_server.responses)}")
                print(f"Final command counter: {photoshop_mcp_server.command_id_counter}")

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter

    async def test_large_payload_performance(self):
        """Test performance with large JavaScript payloads."""
        # Generate a large JavaScript payload
        large_js = """
        const largeData = {
        """

        # Add many properties to create a large payload
        for i in range(1000):
            large_js += f'    "property{i}": "This is a long string value for property {i} with some additional text to make it larger",\n'

        large_js += """
        };
        return { status: "success", dataSize: Object.keys(largeData).length };
        """

        mock_response = {"status": "success", "data": {"dataSize": 1000}}

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()

            start_time = time.time()
            result_str = await execute_photoshop_code(ctx=ctx_mock, uxp_javascript_code=large_js)
            end_time = time.time()

            duration = end_time - start_time

            # Large payload should still execute quickly
            assert duration < 1.0

            import json

            result = json.loads(result_str)
            assert result["status"] == "success"
            assert result["data"]["dataSize"] == 1000

            print(f"Large payload ({len(large_js)} chars) executed in {duration:.3f}s")

    async def test_rapid_connection_checks(self):
        """Test performance of rapid connection status checks."""
        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()

        try:
            # Setup with one connected client
            mock_ws = MagicMock()
            mock_ws.remote_address = ("127.0.0.1", 54321)
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)

            check_count = 1000

            with patch("lightfast_mcp.servers.photoshop_mcp_server.logger"):
                start_time = time.time()

                # Perform many rapid connection checks
                results = []
                for i in range(check_count):
                    result = await check_photoshop_connected()
                    results.append(result)

                end_time = time.time()
                duration = end_time - start_time

                # All checks should return True
                assert all(results)
                assert len(results) == check_count

                # Connection checks should be very fast
                assert duration < 1.0  # Should complete 1000 checks in under 1 second
                print(
                    f"Connection checks: {check_count} checks in {duration:.3f}s ({check_count / duration:.1f} checks/s)"
                )

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients

    async def test_document_info_performance_under_load(self):
        """Test document info retrieval performance under load."""
        mock_response = {
            "status": "success",
            "title": "Performance Test Document",
            "width": 1920,
            "height": 1080,
            "resolution": 300,
            "layerCount": 50,
            "colorMode": "RGB",
            "bitDepth": 8,
        }

        request_count = 30

        with (
            patch("lightfast_mcp.servers.photoshop_mcp_server.send_to_photoshop", return_value=mock_response),
            patch("lightfast_mcp.servers.photoshop_mcp_server.check_photoshop_connected", return_value=True),
        ):
            ctx_mock = MagicMock()

            start_time = time.time()

            # Execute multiple document info requests concurrently
            tasks = [get_document_info(ctx=ctx_mock) for _ in range(request_count)]

            results = await asyncio.gather(*tasks)

            end_time = time.time()
            duration = end_time - start_time

            # Verify all requests succeeded
            assert len(results) == request_count

            import json

            for result_str in results:
                result = json.loads(result_str)
                assert result["status"] == "success"
                assert result["title"] == "Performance Test Document"

            # Should complete quickly even under load
            assert duration < 2.0
            print(
                f"Document info requests: {request_count} requests in {duration:.3f}s ({request_count / duration:.1f} req/s)"
            )

    async def test_command_id_counter_performance(self):
        """Test performance implications of command ID counter increments."""
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.remote_address = ("127.0.0.1", 54321)

        # Store original state
        original_clients = photoshop_mcp_server.connected_clients.copy()
        original_responses = photoshop_mcp_server.responses.copy()
        original_counter = photoshop_mcp_server.command_id_counter

        try:
            # Setup test state
            photoshop_mcp_server.connected_clients.clear()
            photoshop_mcp_server.connected_clients.add(mock_ws)
            photoshop_mcp_server.responses.clear()

            # Start with a high counter value
            photoshop_mcp_server.command_id_counter = 999990

            mock_response = {"status": "success"}
            command_count = 20  # This will push counter over 1 million

            with (
                patch("asyncio.wait_for", return_value=mock_response),
                patch("lightfast_mcp.servers.photoshop_mcp_server.logger"),
            ):
                start_time = time.time()

                # Execute commands that will increment counter significantly
                tasks = [send_to_photoshop(f"command{i}", {}) for i in range(command_count)]

                results = await asyncio.gather(*tasks)

                end_time = time.time()
                duration = end_time - start_time

                # Verify all commands succeeded
                assert len(results) == command_count
                for result in results:
                    assert result["status"] == "success"

                # High counter values shouldn't impact performance significantly
                assert duration < 1.0
                print(
                    f"High counter commands: {command_count} commands in {duration:.3f}s, final counter: {photoshop_mcp_server.command_id_counter}"
                )

        finally:
            # Restore original state
            photoshop_mcp_server.connected_clients = original_clients
            photoshop_mcp_server.responses = original_responses
            photoshop_mcp_server.command_id_counter = original_counter
