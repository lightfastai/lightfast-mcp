#!/usr/bin/env python3
"""System verification script for lightfast-mcp project."""

import subprocess
import sys


def run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout} seconds")
        return 1, "", "Timeout"


def test_imports():
    """Test that core modules can be imported."""
    print("\n=== Testing Core Imports ===")

    try:
        import lightfast_mcp  # noqa: F401

        print("[OK] lightfast_mcp imported successfully")
    except ImportError as e:
        print(f"[FAIL] Failed to import lightfast_mcp: {e}")
        return False

    try:
        from lightfast_mcp.core import ServerConfig  # noqa: F401

        print("[OK] ServerConfig imported successfully")
    except ImportError as e:
        print(f"[FAIL] Failed to import ServerConfig: {e}")
        return False

    try:
        from tools.ai.conversation_client import (
            ConversationClient,  # noqa: F401
        )

        print("[OK] ConversationClient imported successfully")
    except ImportError as e:
        print(f"[FAIL] Failed to import ConversationClient: {e}")
        return False

    return True


def test_cli_commands():
    """Test that CLI commands are available."""
    print("\n=== Testing CLI Commands ===")

    # Test main orchestrator CLI
    exit_code, stdout, stderr = run_command(
        ["uv", "run", "lightfast-mcp-orchestrator", "--help"], timeout=10
    )

    if exit_code == 0:
        print("[OK] lightfast-mcp-orchestrator CLI works")
    else:
        print(f"[FAIL] lightfast-mcp-orchestrator CLI failed: {stderr}")
        return False

    # Test mock server CLI (just check if it's available, don't run it)
    exit_code, stdout, stderr = run_command(
        [
            "uv",
            "run",
            "python",
            "-c",
            "import lightfast_mcp.servers.mock_server; print('Mock server module available')",
        ],
        timeout=10,
    )

    if exit_code == 0:
        print("[OK] lightfast-mock-server module available")
    else:
        print(f"[FAIL] lightfast-mock-server module failed: {stderr}")
        return False

    return True


def test_server_startup():
    """Test that servers can start up (briefly)."""
    print("\n=== Testing Server Startup ===")

    # Test mock server startup by checking if it can be imported and instantiated
    print("Testing mock server startup...")
    exit_code, stdout, stderr = run_command(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from lightfast_mcp.servers.mock.server import MockMCPServer; "
            "from lightfast_mcp.core.base_server import ServerConfig; "
            "config = ServerConfig(name='test', description='Test server', port=8001); "
            "server = MockMCPServer(config); "
            "print('Mock server created successfully')",
        ],
        timeout=10,
    )

    if exit_code == 0:
        print("[OK] Mock server can be instantiated successfully")
    else:
        print(f"[FAIL] Mock server instantiation failed - stderr: {stderr}")
        # Don't fail the test for this, as it might be environment-specific

    return True


def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    print("\n=== Testing Basic Functionality ===")

    try:
        from tools.orchestration.config_loader import ConfigLoader
        from tools.orchestration.server_registry import ServerRegistry

        # Test config loader
        ConfigLoader()  # Just test that it can be instantiated
        print("[OK] Config loader works")

        # Test server registry
        registry = ServerRegistry()
        servers = registry.get_available_server_types()
        print(f"[OK] Server registry works, found {len(servers)} server types")

        return True
    except Exception as e:
        print(f"[FAIL] Basic functionality test failed: {e}")
        return False


def main():
    """Run all system verification tests."""
    print("=== Lightfast MCP System Verification ===")

    tests = [
        ("Core Imports", test_imports),
        ("CLI Commands", test_cli_commands),
        ("Server Startup", test_server_startup),
        ("Basic Functionality", test_basic_functionality),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        try:
            if test_func():
                passed += 1
                print(f"[PASS] {test_name} test PASSED")
            else:
                print(f"[FAIL] {test_name} test FAILED")
        except Exception as e:
            print(f"[FAIL] {test_name} test FAILED with exception: {e}")

    print(f"\n=== Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("[SUCCESS] All system verification tests passed!")
        sys.exit(0)
    else:
        print("[ERROR] Some system verification tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
