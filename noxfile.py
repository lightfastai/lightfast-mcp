import nox

# Default sessions to run when no session is specified
nox.options.sessions = ["lint", "typecheck", "test"]

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


@nox.session(python="3.13")  # Use latest Python for linting
def lint(session):
    """Run linting with ruff."""
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session(python="3.13")  # Use latest Python for type checking
def typecheck(session):
    """Run type checking with mypy."""
    session.install("mypy", "types-PyYAML")
    session.install("-e", ".[dev]")
    session.run("mypy", "src")


@nox.session(python=PYTHON_VERSIONS)
def test(session):
    """Run comprehensive tests with pytest."""
    session.install("-e", ".[dev]")
    session.run("pytest", "tests", "-v")


@nox.session(python="3.13")
def test_fast(session):
    """Run fast tests (excluding slow tests)."""
    session.install("-e", ".[dev]")
    session.run("pytest", "tests/", "-v", "--tb=short", "-m", "not slow")


@nox.session(python="3.13")
def test_integration(session):
    """Run integration tests."""
    session.install("-e", ".[dev]")
    session.run("pytest", "tests/integration/", "-v", "--tb=short")


@nox.session(python="3.13")
def test_e2e(session):
    """Run end-to-end tests with longer timeout."""
    session.install("-e", ".[dev]")
    session.install("pytest-timeout")
    session.run("pytest", "tests/e2e/", "-v", "--timeout=30")


@nox.session(python="3.13")
def test_all(session):
    """Run all test types: unit, integration, and E2E."""
    session.install("-e", ".[dev]")
    session.install("pytest-timeout")
    session.run("pytest", "tests/", "-v", "--timeout=30")


@nox.session(python="3.13")
def test_coverage(session):
    """Run tests with coverage reporting."""
    session.install("-e", ".[dev]")
    session.run(
        "pytest", "--cov=lightfast_mcp", "--cov-report=html", "--cov-report=term", "-v"
    )


@nox.session(python="3.13")
def verify_system(session):
    """Run system verification test."""
    session.install("-e", ".[dev]")
    session.run("python", "scripts/test_working_system.py")


@nox.session(python="3.13")
def build(session):
    """Build the package."""
    session.install("build", "twine")
    session.run("python", "-m", "build")
    session.run("twine", "check", "dist/*")


@nox.session(python="3.13")
def format(session):
    """Format code with ruff."""
    session.install("ruff")
    session.run("ruff", "format", ".")


@nox.session(python="3.13")
def security(session):
    """Run security scanning."""
    session.install("bandit[toml]", "safety")
    session.run(
        "bandit",
        "-r",
        "src/",
        "-f",
        "json",
        "-o",
        "bandit-report.json",
        success_codes=[0, 1],
    )
    # Use the new 'scan' command instead of deprecated 'check'
    session.run("safety", "scan", "--output", "json", success_codes=[0, 1])


@nox.session(python=PYTHON_VERSIONS)
def dev(session):
    """Set up a development environment."""
    session.install("-e", ".[dev]")
    session.notify("verify_system")


@nox.session(python="3.13")
def demo(session):
    """Run the system demo."""
    session.install("-e", ".[dev]")
    session.run("python", "scripts/test_working_system.py")


@nox.session(python="3.13")
def cli_test(session):
    """Test CLI functionality."""
    session.install("-e", ".[dev]")
    # Test basic CLI commands (new orchestrator)
    session.run("lightfast-mcp-orchestrator", "--help")
    session.run("lightfast-mcp-orchestrator", "init")
    session.run("lightfast-mcp-orchestrator", "list")
    # Test legacy manager alias still works
    session.run("lightfast-mcp-manager", "--help")
