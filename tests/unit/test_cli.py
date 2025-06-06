"""
Test cases for the CLI module.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools.orchestration.cli import (
    create_sample_config,
    list_available_servers,
    main,
    start_servers_by_names,
    start_servers_interactive,
)


class TestCLI:
    """Test CLI functionality."""

    @patch("tools.orchestration.cli.ConfigLoader")
    def test_create_sample_config_success(self, mock_config_loader):
        """Test successful configuration creation."""
        mock_loader = MagicMock()
        mock_loader.create_sample_config.return_value = True
        mock_config_loader.return_value = mock_loader

        with patch("builtins.print") as mock_print:
            create_sample_config()

        mock_loader.create_sample_config.assert_called_once_with("servers.yaml")
        mock_print.assert_any_call(
            "[OK] Sample configuration created at: config/servers.yaml"
        )

    @patch("tools.orchestration.cli.ConfigLoader")
    def test_create_sample_config_failure(self, mock_config_loader):
        """Test configuration creation failure."""
        mock_loader = MagicMock()
        mock_loader.create_sample_config.return_value = False
        mock_config_loader.return_value = mock_loader

        with patch("builtins.print") as mock_print:
            create_sample_config()

        mock_print.assert_any_call("[ERROR] Failed to create sample configuration")

    @patch("tools.orchestration.server_registry.get_registry")
    @patch("tools.orchestration.cli.ConfigLoader")
    def test_list_available_servers(self, mock_config_loader, mock_get_registry):
        """Test listing available servers."""
        # Mock registry
        mock_registry = MagicMock()
        mock_registry.get_server_info.return_value = {
            "mock": {
                "version": "1.0.0",
                "description": "Mock server",
                "required_dependencies": [],
                "required_apps": [],
            }
        }
        mock_get_registry.return_value = mock_registry

        # Mock config loader
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "test-server"
        mock_config.description = "Test server"
        mock_config.transport = "http"
        mock_config.host = "localhost"
        mock_config.port = 8001
        mock_config.path = "/mcp"
        mock_config.config = {"type": "mock"}
        mock_loader.load_servers_config.return_value = [mock_config]
        mock_config_loader.return_value = mock_loader

        with patch("builtins.print") as mock_print:
            list_available_servers()

        # Verify print calls
        assert any("Mock server" in str(call) for call in mock_print.call_args_list)

    @pytest.mark.xfail(
        reason="stdin handling in pytest environment - known test infrastructure issue"
    )
    @patch("tools.orchestration.cli.start_multiple_servers_sync")
    @patch("tools.orchestration.cli.ServerSelector")
    def test_start_servers_interactive_no_configs(
        self, mock_selector, mock_start_servers
    ):
        """Test interactive server start with no configurations."""
        mock_selector_instance = MagicMock()
        mock_selector_instance.load_available_servers.return_value = []
        mock_selector.return_value = mock_selector_instance

        with patch("builtins.print") as mock_print:
            start_servers_interactive()

        mock_print.assert_any_call("[ERROR] No server configurations found.")

    @patch("tools.orchestration.cli.shutdown_all_sync")
    @patch("tools.orchestration.cli.wait_for_shutdown_sync")
    @patch("tools.orchestration.cli.get_server_urls_sync")
    @patch("tools.orchestration.cli.start_multiple_servers_sync")
    @patch("tools.orchestration.cli.ServerSelector")
    def test_start_servers_interactive_success(
        self, mock_selector, mock_start_servers, mock_get_urls, mock_wait, mock_shutdown
    ):
        """Test successful interactive server start."""
        # Mock selector
        mock_selector_instance = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "test-server"
        mock_selector_instance.load_available_servers.return_value = [mock_config]
        mock_selector_instance.select_servers_interactive.return_value = [mock_config]
        mock_selector.return_value = mock_selector_instance

        # Mock sync functions
        mock_start_servers.return_value = {"test-server": True}
        mock_get_urls.return_value = {"test-server": "http://localhost:8001"}
        mock_wait.side_effect = KeyboardInterrupt

        with patch("builtins.print"):
            try:
                start_servers_interactive()
            except KeyboardInterrupt:
                pass

        # Check that start_multiple_servers was called with the expected arguments
        mock_start_servers.assert_called_once()

    @patch("tools.orchestration.cli.ConfigLoader")
    def test_start_servers_by_names_no_configs(self, mock_config_loader):
        """Test starting servers by name when no configs exist."""
        mock_loader = MagicMock()
        mock_loader.load_servers_config.return_value = []
        mock_config_loader.return_value = mock_loader

        with patch("builtins.print") as mock_print:
            start_servers_by_names(["test-server"])

        mock_print.assert_any_call("[ERROR] No server configurations found.")

    @patch("tools.orchestration.cli.shutdown_all_sync")
    @patch("tools.orchestration.cli.wait_for_shutdown_sync")
    @patch("tools.orchestration.cli.get_server_urls_sync")
    @patch("tools.orchestration.cli.start_multiple_servers_sync")
    @patch("tools.orchestration.cli.ConfigLoader")
    def test_start_servers_by_names_success(
        self,
        mock_config_loader,
        mock_start_servers,
        mock_get_urls,
        mock_wait,
        mock_shutdown,
    ):
        """Test successfully starting servers by name."""
        # Mock config
        mock_config = MagicMock()
        mock_config.name = "test-server"
        mock_loader = MagicMock()
        mock_loader.load_servers_config.return_value = [mock_config]
        mock_config_loader.return_value = mock_loader

        # Mock sync functions
        mock_start_servers.return_value = {"test-server": True}
        mock_get_urls.return_value = {"test-server": "http://localhost:8001"}
        mock_wait.side_effect = KeyboardInterrupt

        try:
            start_servers_by_names(["test-server"])
        except KeyboardInterrupt:
            pass

    def test_main_init_command(self):
        """Test main function with init command."""
        with patch("tools.orchestration.cli.create_sample_config") as mock_create:
            with patch("sys.argv", ["cli.py", "init"]):
                main()

        mock_create.assert_called_once()

    def test_main_list_command(self):
        """Test main function with list command."""
        with patch("tools.orchestration.cli.list_available_servers") as mock_list:
            with patch("sys.argv", ["cli.py", "list"]):
                main()

        mock_list.assert_called_once()

    def test_main_start_command_no_servers(self):
        """Test main function with start command and no server names."""
        with patch("tools.orchestration.cli.start_servers_interactive") as mock_start:
            with patch("sys.argv", ["cli.py", "start"]):
                main()

        mock_start.assert_called_once()

    def test_main_start_command_with_servers(self):
        """Test main function with start command and server names."""
        with patch("tools.orchestration.cli.start_servers_by_names") as mock_start:
            with patch("sys.argv", ["cli.py", "start", "server1", "server2"]):
                main()

        mock_start.assert_called_once_with(["server1", "server2"], show_logs=True)

    def test_main_verbose_flag(self):
        """Test main function with verbose flag."""
        with patch("tools.orchestration.cli.configure_logging") as mock_config:
            with patch("tools.orchestration.cli.create_sample_config"):
                with patch("sys.argv", ["cli.py", "init", "--verbose"]):
                    main()

        mock_config.assert_called_with(level="DEBUG")


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def test_argument_parsing(self):
        """Test that arguments are parsed correctly."""
        from tools.orchestration.cli import main

        # Test that main can handle different argument combinations
        test_cases = [
            ["init"],
            ["list"],
            ["start"],
            ["start", "server1"],
            ["init", "--verbose"],
        ]

        for args in test_cases:
            with patch("sys.argv", ["cli.py"] + args):
                with patch("tools.orchestration.cli.create_sample_config"):
                    with patch("tools.orchestration.cli.list_available_servers"):
                        with patch("tools.orchestration.cli.start_servers_interactive"):
                            with patch(
                                "tools.orchestration.cli.start_servers_by_names"
                            ):
                                try:
                                    main()
                                except SystemExit:
                                    pass  # Expected for help/error cases
