# Development Environment Setup

This guide outlines the steps to set up your development environment for the `lightfast-mcp` project using `uv` as the package and environment manager.

## Prerequisites

*   **Git**: For cloning the repository.
*   **A Python installation (Optional for `uv` but good to have for system tools)**: While `uv` can install Python versions for your project, having a system Python or a global Python managed by a tool like `pyenv` can be useful. If you use `pyenv`, ensure it's configured correctly in your shell (see "Shell Configuration Notes" below).

## 1. Install `uv`

`uv` is an extremely fast Python package installer and resolver, written in Rust.

If you don't have `uv` installed, you can install it using `pip` (from an existing Python environment) or other methods as described in the [official uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

```bash
pip install uv
```

## 2. Clone the Repository

Clone the project repository to your local machine:

```bash
git clone <repository_url>
cd lightfast-mcp
```
*(Replace `<repository_url>` with the actual URL of your repository)*

## 3. Set Up Python Version

This project is configured to use Python 3.13.2.

*   **Using `uv` to install Python (Recommended for consistency):**
    If you don't have Python 3.13.2 available, `uv` can install it for you:
    ```bash
    uv python install 3.13.2
    ```
    This command downloads and installs the specified Python version, managed by `uv`.

*   **Using `.python-version` with `pyenv` (If you prefer `pyenv` for global Python management):**
    The project includes a `.python-version` file specifying `3.13.2`. If you use `pyenv` and have it correctly configured, `pyenv` will attempt to use this version when you enter the project directory.
    If `pyenv` reports that version `3.13.2` is not installed, you can install it via:
    ```bash
    pyenv install 3.13.2
    ```
    **Note**: `uv` will manage the Python version *within* the virtual environment regardless of your global `pyenv` setup, once the virtual environment is created and activated.

## 4. Create Virtual Environment

Create a virtual environment for the project using `uv`. This environment will use Python 3.13.2.

```bash
# Ensure you are in the project root directory
uv venv --python 3.13.2
```
This will create a `.venv` directory in your project root, containing the Python interpreter and installed packages.

## 5. Install Dependencies

Install all project dependencies, including the project itself in editable mode, using `uv sync`. This command reads the `pyproject.toml` file.

```bash
uv sync
```

## 6. Activate Virtual Environment

Before running the project or development scripts, activate the virtual environment:

```bash
source .venv/bin/activate
```
Your shell prompt should change to indicate that the virtual environment is active (e.g., `(.venv) your-prompt$`).

## 7. Running the Application

With the virtual environment activated, you can run the application script defined in `pyproject.toml`:

```bash
lightfast-mcp
```
(Or any other scripts/commands specific to the project).

To verify the Python version within the activated environment:
```bash
python -V
# Expected output: Python 3.13.2
```

## 8. Deactivating the Virtual Environment

When you're done working, you can deactivate the virtual environment:

```bash
deactivate
```

## Shell Configuration Notes (Especially for `pyenv` Users on Zsh/Bash)

If you use `pyenv` and experience issues where `pyenv` shims take precedence even after activating the `.venv` (e.g., `python -V` still shows a `pyenv` error or the wrong version), your `pyenv` initialization in your shell configuration file (e.g., `~/.zshrc` or `~/.bashrc`) might need adjustment.

A common fix for Zsh (`~/.zshrc`) is to ensure `pyenv init -` is structured correctly:

```zsh
# Example for .zshrc
export PYENV_ROOT="$HOME/.pyenv"
[[ -d "$PYENV_ROOT/bin" ]] && export PATH="$PYENV_ROOT/bin:$PATH"

if command -v pyenv 1>/dev/null 2>&1; then
  eval "$(pyenv init --path)" # Adds shims to PATH
  eval "$(pyenv init -)"      # Initializes pyenv shell integration
fi
```
**Important**: After modifying your shell configuration file, close and reopen your terminal or source the file (e.g., `source ~/.zshrc`) for changes to take effect.

This setup ensures that `uv`-managed virtual environments can correctly override the global Python version when activated. 