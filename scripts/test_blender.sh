#!/bin/bash

# Quick test runner for Blender MCP development
# Usage: ./scripts/test_blender.sh [command]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  test          - Run basic connection tests"
    echo "  interactive   - Start interactive client"
    echo "  dev           - Start server with MCP Inspector"
    echo "  run           - Run server directly (STDIO)"
    echo "  http          - Run server as HTTP service for AI APIs"
    echo "  ai            - Start AI-integrated client (requires API keys)"
    echo "  client        - Run custom test client"
    echo "  check         - Check if Blender addon is running"
    echo ""
}

check_blender() {
    echo -e "${BLUE}🔍 Checking Blender addon connection...${NC}"
    uv run python -c "
import socket
import json
import time

def check_blender_running(port=9876):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect(('localhost', port))
        
        # Send ping
        ping_cmd = json.dumps({'type': 'ping', 'params': {}})
        sock.sendall(ping_cmd.encode('utf-8'))
        
        # Get response
        response = sock.recv(8192)
        sock.close()
        
        if response:
            print('✅ Blender addon is running on port', port)
            return True
    except Exception as e:
        print('❌ Blender addon not accessible:', str(e))
        print('   Make sure:')
        print('   1. Blender is open')
        print('   2. Lightfast MCP addon is enabled')
        print('   3. MCP Server is started in Blender')
        return False

check_blender_running()
"
}

run_tests() {
    echo -e "${BLUE}🧪 Running Blender MCP tests...${NC}"
    echo -e "${GREEN}Running connection demo...${NC}"
    uv run python examples/demo_ai_integration.py
}

run_interactive() {
    echo -e "${BLUE}🚀 Starting interactive Blender MCP client...${NC}"
    echo -e "${GREEN}Starting MCP Inspector CLI for interactive testing...${NC}"
    run_inspector_cli
}

run_dev() {
    echo -e "${BLUE}🔧 Starting Blender MCP server with inspector...${NC}"
    uv run fastmcp dev src/lightfast_mcp/servers/blender_mcp_server.py
}

run_server() {
    echo -e "${BLUE}⚡ Running Blender MCP server directly...${NC}"
    uv run python -m lightfast_mcp.servers.blender_mcp_server
}

run_inspector_cli() {
    echo -e "${BLUE}🔍 Starting MCP Inspector CLI...${NC}"
    uv run npx @modelcontextprotocol/inspector --cli uv run python -m lightfast_mcp.servers.blender_mcp_server
}

run_http_server() {
    echo -e "${BLUE}🌐 Starting Blender MCP HTTP server for AI APIs...${NC}"
    echo -e "${YELLOW}Note: Use 'uv run lightfast-mcp-manager start' for the new modular system${NC}"
    # Legacy HTTP server functionality - consider using the manager instead
    uv run python -c "
from lightfast_mcp.servers.blender.server import BlenderMCPServer
from lightfast_mcp.core.base_server import ServerConfig

config = ServerConfig(
    name='BlenderMCP-HTTP',
    description='Blender MCP server for AI integration',
    host='127.0.0.1',
    port=8000,
    transport='streamable-http',
    path='/mcp',
    config={'type': 'blender'}
)

server = BlenderMCPServer(config)
print('🚀 Starting Blender MCP server as HTTP service...')
print('📡 Server will be available at: http://localhost:8000/mcp')
print('🔧 Make sure Blender is running with the addon active!')
server.run()
"
}

run_ai_client() {
    echo -e "${BLUE}🤖 Starting AI-integrated Blender client...${NC}"
    if [ ! -f .env ]; then
        echo -e "${YELLOW}⚠️  No .env file found. Please create one with your API keys:${NC}"
        echo "cp env_template.txt .env"
        echo "# Then edit .env with your actual API keys"
        return 1
    fi
    echo -e "${GREEN}Using multi-server AI client (recommended)${NC}"
    echo -e "${YELLOW}Note: Using examples/ai_blender_client.py for single-server demo${NC}"
    uv run python examples/ai_blender_client.py
}



case "${1:-}" in
    "test")
        check_blender && run_tests
        ;;
    "interactive")
        check_blender && run_interactive
        ;;
    "dev")
        run_dev
        ;;
    "run")
        run_server
        ;;
    "http")
        run_http_server
        ;;
    "ai")
        run_ai_client
        ;;
    "client")
        run_tests
        ;;
    "check")
        check_blender
        ;;
    "inspector")
        run_inspector_cli
        ;;
    "help"|"-h"|"--help")
        print_usage
        ;;
    "")
        echo -e "${YELLOW}No command specified. Running basic tests...${NC}"
        check_blender && run_tests
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        print_usage
        exit 1
        ;;
esac 