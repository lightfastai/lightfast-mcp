"""Tests for the clients CLI module."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from lightfast_mcp.clients.cli import app, async_chat, async_test, print_step_info
from lightfast_mcp.clients.multi_server_ai_client import Step, ToolCall, ToolResult


class TestClientsCLI:
    """Test the clients CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("lightfast_mcp.clients.cli.load_server_configs")
    @patch("lightfast_mcp.clients.cli.create_multi_server_client_from_config")
    def test_chat_command_no_servers(self, mock_create_client, mock_load_configs):
        """Test chat command when no servers are configured."""
        mock_load_configs.return_value = {}

        result = self.runner.invoke(app, ["chat"])

        assert result.exit_code == 0
        mock_load_configs.assert_called_once()
        mock_create_client.assert_not_called()

    @patch("lightfast_mcp.clients.cli.load_server_configs")
    @patch("lightfast_mcp.clients.cli.create_multi_server_client_from_config")
    def test_test_command_no_servers(self, mock_create_client, mock_load_configs):
        """Test test command when no servers are configured."""
        mock_load_configs.return_value = {}

        result = self.runner.invoke(app, ["test"])

        assert result.exit_code == 0
        mock_load_configs.assert_called_once()
        mock_create_client.assert_not_called()

    def test_print_step_info_text_only(self, capsys):
        """Test printing step info with text only."""
        step = Step(step_number=0, text="Hello world")

        print_step_info(step)

        # Just verify it doesn't crash - output testing is complex with Rich
        captured = capsys.readouterr()
        # Rich output is complex, just ensure no exceptions

    def test_print_step_info_with_tool_calls(self, capsys):
        """Test printing step info with tool calls."""
        tool_call = ToolCall(
            id="test-id",
            tool_name="test_tool",
            arguments={"param": "value"},
            server_name="test_server",
        )

        tool_result = ToolResult(
            id="test-id",
            tool_name="test_tool",
            arguments={"param": "value"},
            result="success",
            server_name="test_server",
        )

        step = Step(
            step_number=0,
            text="Tool execution",
            tool_calls=[tool_call],
            tool_results=[tool_result],
        )

        print_step_info(step)

        # Just verify it doesn't crash
        captured = capsys.readouterr()

    def test_print_step_info_with_error(self, capsys):
        """Test printing step info with tool error."""
        tool_call = ToolCall(
            id="test-id", tool_name="test_tool", arguments={"param": "value"}
        )

        tool_result = ToolResult(
            id="test-id",
            tool_name="test_tool",
            arguments={"param": "value"},
            error="Something went wrong",
        )

        step = Step(step_number=0, tool_calls=[tool_call], tool_results=[tool_result])

        print_step_info(step)

        # Just verify it doesn't crash
        captured = capsys.readouterr()

    @pytest.mark.asyncio
    @patch("lightfast_mcp.clients.cli.load_server_configs")
    @patch("lightfast_mcp.clients.cli.create_multi_server_client_from_config")
    async def test_async_chat_with_servers(self, mock_create_client, mock_load_configs):
        """Test async chat with configured servers."""
        # Mock server configs
        mock_load_configs.return_value = {"test_server": {"type": "mock", "port": 8000}}

        # Mock client
        mock_client = AsyncMock()
        mock_client.get_connected_servers.return_value = ["test_server"]
        mock_client.get_all_tools.return_value = {"test_server": ["test_tool"]}
        mock_client.disconnect_from_servers = AsyncMock()
        mock_create_client.return_value = mock_client

        # Mock input to exit immediately
        with patch("lightfast_mcp.clients.cli.console.input", return_value="quit"):
            await async_chat("config.yaml", "claude", 5, None)

        mock_load_configs.assert_called_once_with("config.yaml")
        mock_create_client.assert_called_once()
        mock_client.disconnect_from_servers.assert_called_once()

    @pytest.mark.asyncio
    @patch("lightfast_mcp.clients.cli.load_server_configs")
    @patch("lightfast_mcp.clients.cli.create_multi_server_client_from_config")
    async def test_async_test_with_servers(self, mock_create_client, mock_load_configs):
        """Test async test with configured servers."""
        # Mock server configs
        mock_load_configs.return_value = {"test_server": {"type": "mock", "port": 8000}}

        # Mock client
        mock_client = AsyncMock()
        mock_client.get_connected_servers.return_value = ["test_server"]
        mock_client.get_all_tools.return_value = {"test_server": ["test_tool"]}
        mock_client.chat_with_steps.return_value = [
            Step(step_number=0, text="Test response")
        ]
        mock_client.disconnect_from_servers = AsyncMock()
        mock_create_client.return_value = mock_client

        await async_test("config.yaml", "claude", 3, "Hello")

        mock_load_configs.assert_called_once_with("config.yaml")
        mock_create_client.assert_called_once()
        mock_client.chat_with_steps.assert_called_once_with("Hello", max_steps=3)
        mock_client.disconnect_from_servers.assert_called_once()

    @pytest.mark.asyncio
    @patch("lightfast_mcp.clients.cli.load_server_configs")
    async def test_async_chat_no_servers(self, mock_load_configs):
        """Test async chat with no servers configured."""
        mock_load_configs.return_value = {}

        await async_chat("config.yaml", "claude", 5, None)

        mock_load_configs.assert_called_once_with("config.yaml")

    @pytest.mark.asyncio
    @patch("lightfast_mcp.clients.cli.load_server_configs")
    async def test_async_test_no_servers(self, mock_load_configs):
        """Test async test with no servers configured."""
        mock_load_configs.return_value = {}

        await async_test("config.yaml", "claude", 3, "Hello")

        mock_load_configs.assert_called_once_with("config.yaml")
