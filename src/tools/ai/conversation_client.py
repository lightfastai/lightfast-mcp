"""Conversation client for managing AI conversations across multiple MCP servers."""

import os
import uuid
from typing import Any, Dict, List, Optional

import mcp.types as mcp_types

from tools.common import (
    AIProviderError,
    ConversationResult,
    ConversationStep,
    OperationStatus,
    Result,
    ToolCall,
    ToolResult,
    get_connection_pool,
    get_logger,
    with_correlation_id,
    with_operation_context,
)

from .conversation_session import ConversationSession
from .providers.base_provider import BaseAIProvider
from .providers.claude_provider import ClaudeProvider
from .providers.openai_provider import OpenAIProvider
from .tool_executor import ToolExecutor

logger = get_logger("ConversationClient")


class ConversationClient:
    """Manages AI conversations across multiple MCP servers."""

    def __init__(
        self,
        servers: Dict[str, Dict[str, Any]],
        ai_provider: str = "claude",
        api_key: Optional[str] = None,
        max_steps: int = 5,
        max_concurrent_tools: int = 5,
    ):
        """Initialize the conversation client."""
        self.servers = servers
        self.ai_provider_name = ai_provider.lower()
        self.api_key = api_key or self._get_api_key()
        self.max_steps = max_steps
        self.max_concurrent_tools = max_concurrent_tools

        # Initialize components
        self.ai_provider = self._create_ai_provider()
        self.tool_executor = ToolExecutor(max_concurrent=max_concurrent_tools)
        self.connection_pool = None

        # Server and tool tracking
        self.connected_servers: Dict[str, Dict[str, Any]] = {}
        self.available_tools: Dict[str, tuple[mcp_types.Tool, str]] = {}

        # Active sessions
        self.active_sessions: Dict[str, ConversationSession] = {}

    def _get_api_key(self) -> str:
        """Get API key from environment variables."""
        if self.ai_provider_name == "claude":
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise AIProviderError(
                    "ANTHROPIC_API_KEY environment variable required for Claude",
                    provider="claude",
                    error_code="MISSING_API_KEY",
                )
        elif self.ai_provider_name == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise AIProviderError(
                    "OPENAI_API_KEY environment variable required for OpenAI",
                    provider="openai",
                    error_code="MISSING_API_KEY",
                )
        else:
            raise AIProviderError(
                f"Unsupported AI provider: {self.ai_provider_name}",
                provider=self.ai_provider_name,
                error_code="UNSUPPORTED_PROVIDER",
            )
        return key

    def _create_ai_provider(self) -> BaseAIProvider:
        """Create the appropriate AI provider."""
        if self.ai_provider_name == "claude":
            return ClaudeProvider(api_key=self.api_key)
        elif self.ai_provider_name == "openai":
            return OpenAIProvider(api_key=self.api_key)
        else:
            raise AIProviderError(
                f"Unsupported AI provider: {self.ai_provider_name}",
                provider=self.ai_provider_name,
                error_code="UNSUPPORTED_PROVIDER",
            )

    @with_correlation_id
    @with_operation_context(operation="connect_to_servers")
    async def connect_to_servers(self) -> Result[Dict[str, bool]]:
        """Connect to all configured servers."""
        self.connection_pool = await get_connection_pool()
        connection_results = {}

        for server_name, server_config in self.servers.items():
            try:
                logger.info(f"Connecting to {server_name}")

                # Register server with connection pool
                await self.connection_pool.register_server(server_name, server_config)

                # Test connection by getting tools
                async with self.connection_pool.get_connection(server_name) as client:
                    tools_result = await client.list_tools()

                    # Handle different response formats
                    if hasattr(tools_result, "tools"):
                        mcp_tools = tools_result.tools
                    elif isinstance(tools_result, list):
                        mcp_tools = tools_result
                    else:
                        mcp_tools = []

                    # Store tools
                    for mcp_tool in mcp_tools:
                        self.available_tools[mcp_tool.name] = (mcp_tool, server_name)
                        logger.debug(f"Added tool {mcp_tool.name} from {server_name}")

                self.connected_servers[server_name] = server_config
                connection_results[server_name] = True
                logger.info(f"Successfully connected to {server_name}")

            except Exception as e:
                logger.error(f"Failed to connect to {server_name}", error=e)
                connection_results[server_name] = False

        # Update tool executor with available tools
        await self.tool_executor.update_tools(
            self.available_tools, self.connection_pool
        )

        successful_connections = sum(
            1 for success in connection_results.values() if success
        )
        logger.info(
            f"Connected to {successful_connections}/{len(self.servers)} servers"
        )

        return Result(status=OperationStatus.SUCCESS, data=connection_results)

    @with_correlation_id
    @with_operation_context(operation="start_conversation")
    async def start_conversation(
        self,
        initial_message: Optional[str] = None,
        max_steps: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Result[ConversationSession]:
        """Start a new conversation session."""
        if session_id is None:
            session_id = str(uuid.uuid4())

        if session_id in self.active_sessions:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Session {session_id} already exists",
                error_code="SESSION_EXISTS",
            )

        session = ConversationSession(
            session_id=session_id,
            max_steps=max_steps or self.max_steps,
            ai_provider=self.ai_provider,
            tool_executor=self.tool_executor,
            available_tools=self.available_tools,
        )

        self.active_sessions[session_id] = session

        # If initial message provided, process it
        if initial_message:
            result = await session.process_message(initial_message)
            if not result.is_success:
                # Clean up session on failure
                del self.active_sessions[session_id]
                return Result(
                    status=OperationStatus.FAILED,
                    error=f"Failed to process initial message: {result.error}",
                    error_code="INITIAL_MESSAGE_FAILED",
                )

        logger.info(f"Started conversation session {session_id}")
        return Result(status=OperationStatus.SUCCESS, data=session)

    @with_correlation_id
    @with_operation_context(operation="chat")
    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> Result[ConversationResult]:
        """Send a message and get a complete conversation result."""
        # Create session if none provided
        if session_id is None:
            session_result = await self.start_conversation(max_steps=max_steps)
            if not session_result.is_success:
                return Result(
                    status=OperationStatus.FAILED,
                    error=f"Failed to create session: {session_result.error}",
                    error_code="SESSION_CREATION_FAILED",
                )
            session = session_result.data
            session_id = session.session_id
        else:
            session = self.active_sessions.get(session_id)
            if not session:
                return Result(
                    status=OperationStatus.FAILED,
                    error=f"Session {session_id} not found",
                    error_code="SESSION_NOT_FOUND",
                )

        # Process the message
        result = await session.process_message(message)
        if not result.is_success:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Failed to process message: {result.error}",
                error_code="MESSAGE_PROCESSING_FAILED",
            )

        # Create conversation result
        conversation_result = ConversationResult(
            session_id=session_id,
            steps=session.steps.copy(),
            total_duration_ms=sum(step.duration_ms or 0 for step in session.steps),
        )

        return Result(status=OperationStatus.SUCCESS, data=conversation_result)

    @with_correlation_id
    async def continue_conversation(
        self, session_id: str, message: str
    ) -> Result[ConversationResult]:
        """Continue an existing conversation."""
        return await self.chat(message, session_id=session_id)

    async def get_conversation_history(
        self, session_id: str
    ) -> Result[List[ConversationStep]]:
        """Get the conversation history for a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Session {session_id} not found",
                error_code="SESSION_NOT_FOUND",
            )

        return Result(status=OperationStatus.SUCCESS, data=session.steps.copy())

    async def execute_tools(
        self, tool_calls: List[ToolCall]
    ) -> Result[List[ToolResult]]:
        """Execute a list of tool calls."""
        if not tool_calls:
            return Result(status=OperationStatus.SUCCESS, data=[])

        results = await self.tool_executor.execute_tools_concurrently(tool_calls)

        return Result(status=OperationStatus.SUCCESS, data=results)

    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return list(self.connected_servers.keys())

    def get_available_tools(self) -> Dict[str, List[str]]:
        """Get all available tools organized by server."""
        tools_by_server: Dict[str, List[str]] = {}
        for tool_name, (mcp_tool, server_name) in self.available_tools.items():
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool_name)
        return tools_by_server

    def find_tool_server(self, tool_name: str) -> Optional[str]:
        """Find which server has a specific tool."""
        if tool_name in self.available_tools:
            return self.available_tools[tool_name][1]
        return None

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all servers."""
        status = {}
        for server_name in self.connected_servers:
            server_tools = [
                tool
                for tool, (_, srv) in self.available_tools.items()
                if srv == server_name
            ]
            status[server_name] = {
                "connected": True,
                "tools_count": len(server_tools),
                "tools": server_tools,
            }
        return status

    def get_active_sessions(self) -> Dict[str, ConversationSession]:
        """Get all active conversation sessions."""
        return self.active_sessions.copy()

    async def close_session(self, session_id: str) -> Result[None]:
        """Close a conversation session."""
        if session_id not in self.active_sessions:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Session {session_id} not found",
                error_code="SESSION_NOT_FOUND",
            )

        session = self.active_sessions[session_id]
        await session.close()
        del self.active_sessions[session_id]

        logger.info(f"Closed conversation session {session_id}")
        return Result(status=OperationStatus.SUCCESS)

    async def disconnect_from_servers(self) -> Result[None]:
        """Disconnect from all servers and clean up resources."""
        logger.info("Disconnecting from all servers...")

        # Close all active sessions
        for session_id in list(self.active_sessions.keys()):
            await self.close_session(session_id)

        # Clear server and tool data
        self.connected_servers.clear()
        self.available_tools.clear()

        # Shutdown connection pool if we have one
        if self.connection_pool:
            from tools.common.async_utils import shutdown_connection_pool

            await shutdown_connection_pool()
            self.connection_pool = None

        logger.info("Disconnected from all servers")
        return Result(status=OperationStatus.SUCCESS)


async def create_conversation_client(
    servers: Dict[str, Dict[str, Any]],
    ai_provider: str = "claude",
    api_key: Optional[str] = None,
    max_steps: int = 5,
) -> Result[ConversationClient]:
    """Create and connect a conversation client from configuration."""
    try:
        client = ConversationClient(
            servers=servers,
            ai_provider=ai_provider,
            api_key=api_key,
            max_steps=max_steps,
        )

        connection_result = await client.connect_to_servers()
        if not connection_result.is_success:
            return Result(
                status=OperationStatus.FAILED,
                error=f"Failed to connect to servers: {connection_result.error}",
                error_code="CONNECTION_FAILED",
            )

        return Result(status=OperationStatus.SUCCESS, data=client)

    except Exception as e:
        logger.error("Failed to create conversation client", error=e)
        return Result(
            status=OperationStatus.FAILED, error=str(e), error_code=type(e).__name__
        )
