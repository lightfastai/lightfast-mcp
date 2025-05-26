"""Base AI provider interface for different AI services."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

import mcp.types as mcp_types

from tools.common import ConversationStep, Result, ToolCall


class BaseAIProvider(ABC):
    """Base interface for AI providers (Claude, OpenAI, etc.)."""

    def __init__(self, api_key: str):
        """Initialize the AI provider."""
        self.api_key = api_key

    @abstractmethod
    async def generate_step(
        self,
        messages: List[Dict[str, Any]],
        available_tools: Dict[str, tuple[mcp_types.Tool, str]],
        step_number: int,
    ) -> Result[ConversationStep]:
        """Generate a single conversation step with potential tool calls."""
        pass

    @abstractmethod
    def build_tools_context(
        self, available_tools: Dict[str, tuple[mcp_types.Tool, str]]
    ) -> str:
        """Build a context description of available tools."""
        pass

    @abstractmethod
    def format_tool_for_api(
        self, mcp_tool: mcp_types.Tool, server_name: str
    ) -> Dict[str, Any]:
        """Convert MCP tool to provider-specific format."""
        pass

    @abstractmethod
    def parse_tool_calls(self, response: Any) -> List[ToolCall]:
        """Parse tool calls from provider response."""
        pass

    @abstractmethod
    def format_messages_for_api(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format messages for the provider's API."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider."""
        pass
