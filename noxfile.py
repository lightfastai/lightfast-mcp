import nox

# Default sessions to run when no session is specified
nox.options.sessions = ["lint", "typecheck", "test"]

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


@nox.session(python="3.12")  # Only use one version for linting
def lint(session):
    """Run linting with ruff."""
    session.install("ruff")
    session.run("ruff", "check", "src", "tests")
    session.run("ruff", "format", "--check", "src", "tests")


@nox.session(python="3.12")  # Only use one version for type checking
def typecheck(session):
    """Run type checking with mypy."""
    session.install("mypy")
    session.install("-e", ".")
    session.run("mypy", "src")


@nox.session(python=PYTHON_VERSIONS)
def test(session):
    """Run tests with pytest."""
    session.install("pytest", "pytest-asyncio")
    session.install("-e", ".[dev]")
    session.run("pytest", "tests")


@nox.session(python="3.12")  # Only use one version for building
def build(session):
    """Build the package."""
    session.install("build")
    session.run("python", "-m", "build")


@nox.session(python="3.12")  # Only use one version for formatting
def format(session):
    """Format code with ruff."""
    session.install("ruff")
    session.run("ruff", "format", "src", "tests")


@nox.session(python=PYTHON_VERSIONS)
def dev(session):
    """Set up a development environment."""
    session.install("-e", ".[dev]")
