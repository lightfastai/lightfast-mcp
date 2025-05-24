#!/usr/bin/env python3
"""
Test runner for the lightfast-mcp modular architecture.

This script provides convenient ways to run different test suites.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle the result."""
    print(f"🧪 {description}")
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
    else:
        print(f"❌ {description} - FAILED")

    print()
    return result.returncode == 0


def main():
    """Main test runner."""
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root / "src"))

    print("🔬 Lightfast MCP Test Suite")
    print("=" * 50)
    print()

    # Check if we have pytest installed
    try:
        import pytest
    except ImportError:
        print("❌ pytest not found. Install it with: uv add pytest pytest-asyncio")
        return False

    all_passed = True

    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        test_type = "all"

    if test_type in ["unit", "all"]:
        # Run unit tests
        unit_cmd = ["uv", "run", "pytest", "tests/unit", "-v", "--tb=short"]
        if not run_command(unit_cmd, "Unit Tests"):
            all_passed = False

    if test_type in ["integration", "all"]:
        # Run integration tests
        integration_cmd = ["uv", "run", "pytest", "tests/integration", "-v", "--tb=short", "-m", "integration"]
        if not run_command(integration_cmd, "Integration Tests"):
            all_passed = False

    if test_type == "fast":
        # Run fast tests only (exclude slow ones)
        fast_cmd = ["uv", "run", "pytest", "tests/", "-v", "--tb=short", "-m", "not slow"]
        if not run_command(fast_cmd, "Fast Tests"):
            all_passed = False

    if test_type == "slow":
        # Run slow tests only
        slow_cmd = ["uv", "run", "pytest", "tests/", "-v", "--tb=short", "-m", "slow"]
        if not run_command(slow_cmd, "Slow Tests"):
            all_passed = False

    if test_type == "coverage":
        # Run tests with coverage
        try:
            import coverage
        except ImportError:
            print("❌ coverage not found. Install it with: uv add coverage")
            return False

        coverage_cmd = [
            "uv",
            "run",
            "pytest",
            "tests/",
            "--cov=lightfast_mcp",
            "--cov-report=html",
            "--cov-report=term",
            "-v",
        ]
        if not run_command(coverage_cmd, "Tests with Coverage"):
            all_passed = False
        else:
            print("📊 Coverage report generated in htmlcov/index.html")

    # Summary
    print("🏁 Test Summary")
    print("=" * 30)
    if all_passed:
        print("✅ All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False


def show_help():
    """Show help information."""
    print("""
🔬 Lightfast MCP Test Runner

Usage: python run_tests.py [test_type]

Test types:
  all         - Run all tests (default)
  unit        - Run unit tests only
  integration - Run integration tests only
  fast        - Run fast tests only (excludes slow tests)
  slow        - Run slow tests only
  coverage    - Run tests with coverage report

Examples:
  uv run python run_tests.py                 # Run all tests
  uv run python run_tests.py unit            # Run unit tests
  uv run python run_tests.py coverage        # Run with coverage
  uv run python run_tests.py fast            # Run fast tests only
""")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        show_help()
        sys.exit(0)

    success = main()
    sys.exit(0 if success else 1)
