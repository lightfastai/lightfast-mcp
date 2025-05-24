# lightfast-mcp - Model Context Protocol for Creative Applications

Lightfast MCP builds, maintains, and ships reliable Model Context Protocols (MCPs) for creative applications. Our goal is to connect AI models to tools like Blender, TouchDesigner, Ableton, Adobe Creative Suite, Unreal Engine, and more, enabling prompt-assisted creation, manipulation, and automation.

## What is Lightfast MCP?

Lightfast MCP provides a simple architecture that allows AI to directly interact with and control creative applications through the Model Context Protocol. This repository contains:

- Implementations of MCPs for various creative applications
- Documentation on how to use and extend these protocols
- Examples and tutorials to get you started quickly
- Tools to help developers build their own MCPs

## Protocol Compliance

Lightfast MCP strictly adheres to the official [Model Context Protocol specification](https://modelcontextprotocol.io/introduction). This ensures compatibility with all MCP clients and provides a standardized way for AI models to interact with creative applications.

For more information about the Model Context Protocol, including core concepts, resources, prompts, tools, and sampling, please refer to the [official MCP documentation](https://modelcontextprotocol.io/introduction).

## Installation

- Python 3.10 or newer
- uv package manager

**If you're on Mac, please install uv as**
```bash
brew install uv
```
**On Windows**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex" 
```
and then
```bash
set Path=C:\Users\nntra\.local\bin;%Path%
```

Otherwise installation instructions are on their website: [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

## Development

For development setup, workflow information, and Cursor IDE integration, please see our [Developer Guide](DEV.md).

## Documentation

For comprehensive documentation, examples, and guides, please visit our [documentation site](https://yourprojecturl.com/docs).

## Contributing

We welcome contributions from the community! Whether you want to add support for a new creative application, improve existing implementations, or enhance documentation, please feel free to submit a pull request.

See our [Contributing Guide](CONTRIBUTING.md) for more information on how to get started.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This is a community-driven project. The integrations provided are third-party and not officially made or endorsed by the respective software vendors.

## Quick Start

```bash
# Install and setup
uv pip install -e ".[dev]"
uv run lightfast-mcp-manager init
uv run lightfast-mcp-manager start

# Run tests
nox  # Fast feedback loop
nox -s test_e2e  # End-to-end tests
```

For comprehensive development documentation, testing guide, and architecture details, see [DEV.md](DEV.md).
