# 🤖 AI Integration with Blender MCP Server

This guide shows you how to integrate AI models (Claude, OpenAI, etc.) with your Blender MCP server for programmatic control.

## 🎯 Overview

Instead of using Claude Desktop, this setup allows you to:
- **Build custom applications** that use AI to control Blender
- **Integrate with multiple AI providers** (Claude, OpenAI, etc.)
- **Create programmatic workflows** for Blender automation
- **Build web services** or desktop apps with AI-powered Blender control

## 🏗️ Architecture

```
AI Model API (Claude/OpenAI) 
       ↓
AI Blender Client 
       ↓
Blender MCP Server (HTTP)
       ↓
Blender Addon (Socket)
       ↓
Blender Application
```

## ⚡ Quick Start

### 1. Set up API Keys

```bash
# Copy the environment template
cp env_template.txt .env

# Edit .env with your actual API keys
# For Claude:
ANTHROPIC_API_KEY=sk-ant-...
# For OpenAI:
OPENAI_API_KEY=sk-...
# Choose provider:
AI_PROVIDER=claude
```

### 2. Start Blender MCP HTTP Server

In **Terminal 1**:
```bash
./scripts/test_blender.sh http
```

This starts the MCP server at `http://localhost:8000/mcp`

### 3. Start AI Client

In **Terminal 2**:
```bash
./scripts/test_blender.sh ai
```

### 4. Chat with AI about Blender!

```
You: What objects are in my Blender scene?
🤖 AI: I can see your Blender scene has 3 objects: Camera, Cube, and Light...

You: Add a new cube to the scene
🤖 AI: I'll add a cube to your Blender scene...
🔧 Executing Blender tool: execute_command
```

## 🛠️ Manual Setup

### Start HTTP Server
```bash
uv run python run_blender_http.py
```

### Use AI Client
```bash
# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Start the AI client
uv run python ai_blender_client.py
```

## 🔌 Supported AI Providers

### Claude (Anthropic)
- **Model**: `claude-3-5-sonnet-20241022`
- **API Key**: `ANTHROPIC_API_KEY`
- **Cost**: ~$3-15 per 1M tokens

### OpenAI
- **Model**: `gpt-4o`
- **API Key**: `OPENAI_API_KEY`  
- **Cost**: ~$2.50-10 per 1M tokens

### Adding New Providers

Extend the `AIBlenderClient` class:

```python
async def _call_your_provider_api(self, prompt: str) -> str:
    # Implement your provider's API call
    pass
```

## 🎮 Usage Examples

### Basic Scene Inspection
```
You: What's in my Blender scene?
AI: Your scene contains 3 objects: Camera, Cube, and Light. The active object is "Cube".
```

### Object Creation
```
You: Create a red sphere at position (2, 0, 0)
AI: {"action": "blender_tool", "tool": "execute_command", "arguments": {"code_to_execute": "import bpy; bpy.ops.mesh.primitive_uv_sphere_add(location=(2, 0, 0))"}}
```

### Material Creation
```
You: Create a shiny gold material
AI: I'll create a gold material with metallic and roughness properties...
```

## 🔧 API Reference

### AIBlenderClient

```python
from ai_blender_client import AIBlenderClient

client = AIBlenderClient(
    mcp_server_url="http://localhost:8000/mcp",
    ai_provider="claude",  # or "openai"
    api_key="your-key"
)

# Connect to Blender
await client.connect_to_blender()

# Chat with AI
response = await client.chat_with_ai("Add a cube to the scene")

# Execute Blender tools directly
result = await client.execute_blender_tool("get_state")
```

### Available Blender Tools

- **`get_state`**: Get current scene information
- **`execute_command`**: Execute Python code in Blender

## 🌐 Building Web Services

### FastAPI Integration

```python
from fastapi import FastAPI
from ai_blender_client import AIBlenderClient

app = FastAPI()
ai_client = AIBlenderClient()

@app.post("/blender/chat")
async def chat_with_blender(message: str):
    response = await ai_client.chat_with_ai(message)
    return {"response": response}
```

### Webhook Integration

```python
@app.post("/webhook/blender")
async def blender_webhook(request):
    # Process incoming requests
    # Use AI to understand intent
    # Execute Blender actions
    pass
```

## 🔒 Security Considerations

- **API Keys**: Keep API keys secure, use environment variables
- **Network**: Run HTTP server on localhost only in development
- **Validation**: Validate AI responses before executing Blender code
- **Rate Limiting**: Implement rate limiting for production use

## 🚀 Production Deployment

### Docker Setup

```dockerfile
FROM python:3.13
COPY . /app
WORKDIR /app
RUN pip install -e .
CMD ["python", "run_blender_http.py"]
```

### Environment Variables

```bash
ANTHROPIC_API_KEY=your-key
BLENDER_MCP_HOST=0.0.0.0
BLENDER_MCP_PORT=8000
```

## 🐛 Troubleshooting

### Connection Issues
```bash
# Check Blender addon is running
./scripts/test_blender.sh check

# Test MCP server directly
./scripts/test_blender.sh test
```

### API Key Issues
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Test API access
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     https://api.anthropic.com/v1/messages
```

### Debug Mode
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 💡 Advanced Use Cases

- **Blender Automation**: Batch processing with AI guidance
- **Creative AI**: AI-assisted 3D modeling and animation
- **Educational Tools**: Interactive Blender learning with AI
- **Production Pipelines**: AI-powered asset generation
- **Game Development**: Procedural content with AI input

## 🤝 Contributing

Add support for new AI providers by extending the `AIBlenderClient` class. Pull requests welcome!

## 📄 License

MIT License - see LICENSE file for details. 