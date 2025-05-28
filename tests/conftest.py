"""
Pytest configuration and shared fixtures for lightfast-mcp tests.
"""

import sys
from pathlib import Path

import pytest

# Add src to Python path for testing
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


# Use pytest-asyncio's built-in event loop management
# Remove custom event_loop fixture to avoid deprecation warnings


@pytest.fixture
def sample_server_config():
    """Provide a sample server configuration for testing."""
    from lightfast_mcp.core.base_server import ServerConfig

    return ServerConfig(
        name="test-server",
        description="A test server for unit testing",
        config={"type": "test", "host": "localhost", "port": 8000},
    )


@pytest.fixture
def sample_blender_config():
    """Provide a sample Blender server configuration."""
    from lightfast_mcp.core.base_server import ServerConfig

    return ServerConfig(
        name="test-blender",
        description="Test Blender server",
        config={"type": "blender", "blender_host": "localhost", "blender_port": 9876},
    )


@pytest.fixture
def sample_mock_config():
    """Provide a sample Mock server configuration."""
    from lightfast_mcp.core.base_server import ServerConfig

    return ServerConfig(
        name="test-mock",
        description="Test Mock server",
        config={"type": "mock", "delay_seconds": 0.1},
    )


@pytest.fixture
def sample_figma_config():
    """Provide a sample Figma server configuration."""
    from lightfast_mcp.core.base_server import ServerConfig

    return ServerConfig(
        name="test-figma",
        description="Test Figma server",
        config={"type": "figma", "figma_host": "localhost", "figma_port": 9003},
    )


@pytest.fixture
def sample_multi_server_configs():
    """Provide multiple server configurations for testing."""
    from lightfast_mcp.core.base_server import ServerConfig

    return [
        ServerConfig(
            name="multi-blender",
            description="Multi test Blender",
            config={"type": "blender"},
        ),
        ServerConfig(
            name="multi-mock",
            description="Multi test Mock",
            config={"type": "mock", "delay_seconds": 0.1},
        ),
    ]


@pytest.fixture(autouse=True)
def clean_singletons():
    """Clean singleton instances between tests to avoid state leakage."""
    yield

    # Clean up registry singleton
    try:
        from tools.orchestration.server_registry import reset_registry

        reset_registry()
    except ImportError:
        pass

    # Clean up orchestrator singleton
    try:
        from tools.orchestration.server_orchestrator import reset_orchestrator

        reset_orchestrator()
    except ImportError:
        pass


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
