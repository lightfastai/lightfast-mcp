# Developer Guide for lightfast-mcp

This guide provides instructions for setting up and developing the `lightfast-mcp` project.

## Prerequisites

- Python 3.10 or newer
- `uv` package manager ([Installation Guide](https://docs.astral.sh/uv/getting-started/installation/))

## Project Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/lightfastai/lightfast-mcp.git
    cd lightfast-mcp
    ```

2.  **Create and Activate a Virtual Environment (using `uv`):
    ```bash
    uv venv
    source .venv/bin/activate  # On macOS/Linux
    # .venv\Scripts\activate    # On Windows
    ```

3.  **Install Dependencies (including development tools):
    ```bash
    uv pip install -e ".[dev]"
    ```
    This installs the project in editable mode (`-e`) along with all runtime dependencies and development dependencies (like `ruff` and `taskipy`) specified in `pyproject.toml` under the `[dev]` group.

## Development Tasks with `taskipy`

We use `taskipy` to manage common development tasks. These tasks are defined in the `[tool.taskipy.tasks]` section of `pyproject.toml`.

To list available tasks, run:
```bash
task --list
```

Common tasks include:

*   **`task lint`**: Check for linting errors using Ruff.
*   **`task format`**: Auto-format code using Ruff.
*   **`task check_format`**: Check if code formatting is correct without modifying files.
*   **`task fix`**: Apply all auto-fixable linting errors and then format the code.
*   **`task mock_server`**: Run the mock MCP server located in `src/lightfast_mcp/mock_server.py`.

Ensure your virtual environment is activated before running `task` commands.

## Linting and Formatting with Ruff

This project uses [Ruff](https://docs.astral.sh/ruff/) for fast Python linting and formatting.

-   **Configuration**: Ruff is configured in the `[tool.ruff]` section of `pyproject.toml`.
-   **Manual Checks**: You can run Ruff manually (with your virtual environment activated):
    ```bash
    ruff check .  # Check for linting errors
    ruff format . # Auto-format files
    ruff check . --fix # Apply auto-fixes
    ```

## VS Code Integration

For an optimal development experience in VS Code:

1.  **Install Recommended Extensions**:
    This project includes a `.vscode/extensions.json` file with recommended extensions. When you open the project, VS Code should prompt you to install them if you haven't already. Key extensions include:
    *   `ms-python.python` (Python support by Microsoft)
    *   `charliermarsh.ruff` (Ruff linter and formatter integration)
    *   `tamasfe.even-better-toml` (TOML language support for `pyproject.toml`)

2.  **Select the Python Interpreter**:
    *   Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
    *   Search for and select "Python: Select Interpreter".
    *   Choose the Python interpreter located in your project's virtual environment (e.g., `./.venv/bin/python`). This ensures VS Code uses the correct environment with all installed dependencies, including Ruff.

3.  **Ruff Integration Settings**:
    The `.vscode/settings.json` file is pre-configured to use Ruff for formatting and linting, including format-on-save and auto-fixing for Python files.

## Running the Mock MCP Server

There are two main ways to run the mock server for testing:

1.  **Using `taskipy` (Recommended for Development)**:
    (Ensure your virtual environment is activated)
    ```bash
    task mock_server
    ```

2.  **Directly via Python (if `taskipy` is not used or for specific debugging)**:
    (Ensure your virtual environment is activated)
    ```bash
    python -m lightfast_mcp.mock_server
    ```

3.  **Via the installed script (after `uv pip install -e .`)**:
    (Ensure your virtual environment is activated)
    ```bash
    lightfast-mock-server
    ```
    This is also how MCP Host applications like Claude Desktop will launch the server if configured to use this script name.

## Development Tasks with `nox`

We also use [`nox`](https://nox.thea.codes/) for automated testing in multiple Python environments. Nox helps ensure our code works across different environments and provides a consistent way to run tests, linting, and other development tasks.

### Installing nox

If you haven't installed nox yet:

```bash
pip install nox
```

It's also included in the dev dependencies when you run `uv pip install -e ".[dev]"`.

### Available nox sessions

To list all available sessions:

```bash
nox --list
```

Common sessions include:

* **`nox -s lint`**: Run linting with Ruff.
* **`nox -s typecheck`**: Run type checking with mypy.
* **`nox -s test`**: Run tests with pytest.
* **`nox -s format`**: Format code with Ruff.
* **`nox -s build`**: Build the package.
* **`nox -s dev`**: Set up a development environment.

### Benefits of using nox

- **Environment isolation**: Each session runs in its own virtual environment.
- **CI/CD integration**: The same nox sessions can be run in CI/CD pipelines.
- **Reproducibility**: Nox ensures consistent testing environments.
- **Multiple Python versions**: Can test against multiple Python versions (Python 3.10 through 3.13 currently).

### Nox vs. taskipy

- **taskipy** is simpler and runs commands in your current environment. It's great for quick development tasks.
- **nox** creates isolated environments and is better for thorough testing, especially in CI/CD pipelines.

Use whichever tool best fits your current development needs.

## Contributing

(Details about contributing, pull requests, code style if not covered by Ruff, etc. can be added here later.)

## Troubleshooting

-   **`command not found: task`**: Make sure your virtual environment is activated and you have run `uv pip install -e ".[dev]"`.
-   **`command not found: ruff`**: Same as above.
-   **Ruff not working in VS Code**: Ensure the Ruff extension is installed and you've selected the Python interpreter from your project's virtual environment. 