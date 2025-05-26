"""Server selector for choosing which MCP servers to start."""

from typing import Any

from lightfast_mcp.core.base_server import ServerConfig
from lightfast_mcp.utils.logging_utils import get_logger

from .config_loader import ConfigLoader
from .server_registry import get_registry

logger = get_logger("ServerSelector")


class ServerSelector:
    """Interactive server selector for choosing which servers to start."""

    def __init__(self):
        self.registry = get_registry()
        self.config_loader = ConfigLoader()
        self.available_configs: list[ServerConfig] = []
        self.selected_configs: list[ServerConfig] = []

    def load_available_servers(
        self, config_file: str | None = None
    ) -> list[ServerConfig]:
        """Load available server configurations."""
        self.available_configs = self.config_loader.load_servers_config(config_file)
        logger.info(f"Loaded {len(self.available_configs)} server configurations")
        return self.available_configs

    def get_server_info(self) -> dict[str, dict[str, Any]]:
        """Get detailed information about available server types."""
        return self.registry.get_server_info()

    def select_servers_interactive(self) -> list[ServerConfig]:
        """Interactive server selection via console."""
        if not self.available_configs:
            print("❌ No server configurations available.")
            print(
                "   Create a configuration file first or check your config directory."
            )
            return []

        print("🚀 Lightfast MCP Server Selection")
        print("=" * 50)
        print("Available servers:")

        # Display available servers
        for i, config in enumerate(self.available_configs, 1):
            server_type = config.config.get("type", "unknown")
            status = "✅" if self._check_server_requirements(config) else "⚠️ "
            print(
                f"  {i}. {status} {config.name} ({server_type}) - {config.description}"
            )
            if not self._check_server_requirements(config):
                issues = self._get_requirement_issues(config)
                for issue in issues:
                    print(f"      🔸 {issue}")

        print()
        print(
            "Enter server numbers to start (comma-separated), 'all' for all servers, or 'none' to cancel:"
        )

        try:
            selection = input("Selection: ").strip()

            if selection.lower() == "none":
                return []

            if selection.lower() == "all":
                self.selected_configs = self.available_configs.copy()
            else:
                # Parse comma-separated numbers
                selected_indices = []
                for part in selection.split(","):
                    try:
                        index = int(part.strip()) - 1  # Convert to 0-based
                        if 0 <= index < len(self.available_configs):
                            selected_indices.append(index)
                        else:
                            print(f"⚠️  Invalid selection: {part.strip()}")
                    except ValueError:
                        print(f"⚠️  Invalid number: {part.strip()}")

                self.selected_configs = [
                    self.available_configs[i] for i in selected_indices
                ]

            print(f"\n✅ Selected {len(self.selected_configs)} servers:")
            for config in self.selected_configs:
                print(f"   • {config.name} ({config.config.get('type', 'unknown')})")

            return self.selected_configs

        except KeyboardInterrupt:
            print("\n❌ Selection cancelled.")
            return []
        except Exception as e:
            print(f"❌ Error during selection: {e}")
            return []

    def select_servers_by_names(self, server_names: list[str]) -> list[ServerConfig]:
        """Select servers by their names."""
        selected = []
        for name in server_names:
            config = self.find_server_config(name)
            if config:
                selected.append(config)
            else:
                logger.warning(f"Server configuration not found: {name}")

        self.selected_configs = selected
        return selected

    def select_servers_by_type(self, server_types: list[str]) -> list[ServerConfig]:
        """Select servers by their types."""
        selected = []
        for config in self.available_configs:
            server_type = config.config.get("type", "unknown")
            if server_type in server_types:
                selected.append(config)

        self.selected_configs = selected
        return selected

    def find_server_config(self, name: str) -> ServerConfig | None:
        """Find a server configuration by name."""
        for config in self.available_configs:
            if config.name == name:
                return config
        return None

    def _check_server_requirements(self, config: ServerConfig) -> bool:
        """Check if server requirements are met."""
        server_type = config.config.get("type", "unknown")

        # Check if server type is available
        server_class = self.registry.get_server_class(server_type)
        if not server_class:
            return False

        # Basic validation
        is_valid, _ = self.registry.validate_server_config(server_type, config)
        return is_valid

    def _get_requirement_issues(self, config: ServerConfig) -> list[str]:
        """Get list of requirement issues for a server."""
        issues = []
        server_type = config.config.get("type", "unknown")

        # Check if server type exists
        server_class = self.registry.get_server_class(server_type)
        if not server_class:
            issues.append(f"Server type '{server_type}' not found")
            return issues

        # Check validation
        is_valid, error_msg = self.registry.validate_server_config(server_type, config)
        if not is_valid:
            issues.append(error_msg)

        # Check dependencies and required apps
        server_info = self.registry.get_server_info().get(server_type, {})

        required_deps = server_info.get("required_dependencies", [])
        for dep in required_deps:
            try:
                __import__(dep)
            except ImportError:
                issues.append(f"Missing dependency: {dep}")

        required_apps = server_info.get("required_apps", [])
        for app in required_apps:
            issues.append(f"Requires {app} to be running")

        return issues

    def display_selection_summary(self):
        """Display a summary of the current selection."""
        if not self.selected_configs:
            print("No servers selected.")
            return

        print(f"\n📋 Selected Servers ({len(self.selected_configs)}):")
        print("-" * 40)

        for config in self.selected_configs:
            server_type = config.config.get("type", "unknown")
            transport = config.transport

            if transport in ["http", "streamable-http"]:
                url = f"http://{config.host}:{config.port}{config.path}"
                print(f"• {config.name} ({server_type}) - {url}")
            else:
                print(f"• {config.name} ({server_type}) - {transport}")

        print()

    def get_selected_servers(self) -> list[ServerConfig]:
        """Get the currently selected server configurations."""
        return self.selected_configs.copy()

    def clear_selection(self):
        """Clear the current selection."""
        self.selected_configs = []

    def create_sample_configuration(self, filename: str = "servers.yaml") -> bool:
        """Create a sample configuration file."""
        success = self.config_loader.create_sample_config(filename)
        if success:
            print(f"✅ Created sample configuration: {filename}")
            print("   Edit this file to customize your server settings.")
        else:
            print(f"❌ Failed to create sample configuration: {filename}")
        return success


def interactive_server_selection(config_file: str | None = None) -> list[ServerConfig]:
    """Convenience function for interactive server selection."""
    selector = ServerSelector()

    # Load available servers
    configs = selector.load_available_servers(config_file)

    if not configs:
        print("📝 Would you like to create a sample configuration file? (y/n)")
        try:
            create_sample = input().strip().lower()
            if create_sample in ["y", "yes"] and selector.create_sample_configuration():
                print("Edit the configuration file and run the command again.")
        except KeyboardInterrupt:
            pass
        return []

    # Interactive selection
    selected = selector.select_servers_interactive()

    # Display summary
    selector.display_selection_summary()

    return selected
