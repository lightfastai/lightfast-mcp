# lightfast-mcp - MCP Server Implementations for Creative Applications

**Production-ready MCP server implementations for creative applications** - Control Blender and other creative tools through the Model Context Protocol.

Lightfast MCP provides reliable, well-tested MCP server implementations for creative applications, with optional management and AI client tools.

## 🎯 Core MCP Servers

- **🎨 Blender MCP Server**: Control Blender through MCP protocol for 3D modeling, animation, and rendering
- **🧪 Mock MCP Server**: Testing and development server for MCP protocol validation

## 🔧 Optional Features

- **Multi-Server Orchestration**: Run and coordinate multiple MCP servers simultaneously
- **AI Integration**: Built-in AI tools for testing and interacting with servers  
- **Configuration-Driven**: YAML/JSON configuration for easy server management
- **Flexible Transport**: Support for both stdio and HTTP-based transports

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

### 🎯 Core Usage (MCP Servers Only)

```bash
# Install core package
pip install lightfast-mcp

# Run individual servers
lightfast-blender-server    # Blender MCP server
lightfast-mock-server       # Mock MCP server for testing
```

### 🔧 Development Tools (Orchestration + AI)

```bash
# Install with development tools
pip install lightfast-mcp[tools]

# Multi-server orchestration
lightfast-mcp-manager init
lightfast-mcp-manager start

# AI integration for testing
lightfast-mcp-ai chat
```

### 🧪 Development

```bash
# Development setup
uv pip install -e ".[dev]"
nox  # Run tests
```

For comprehensive development documentation, testing guide, and architecture details, see [DEV.md](DEV.md).
