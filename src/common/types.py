"""Shared types for lightfast-mcp core and tools."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OperationStatus(Enum):
    """Standard operation status codes."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ServerState(Enum):
    """Server lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ToolCallState(Enum):
    """States of tool call execution."""

    CALL = "call"
    RESULT = "result"
    ERROR = "error"


class HealthStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ServerInfo:
    """Unified server information for both core and tools usage.

    This class supports both lightweight usage (core) and comprehensive usage (tools).
    Core servers can use minimal fields, while orchestration tools can use all fields.
    """

    # Core fields (always required)
    name: str = ""
    server_type: str = "unknown"
    state: ServerState = ServerState.STOPPED

    # Network configuration
    host: str = "localhost"
    port: int = 8000
    transport: str = "stdio"
    url: Optional[str] = None

    # Runtime information (optional for core, used by tools)
    pid: Optional[int] = None
    start_time: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_status: HealthStatus = HealthStatus.UNKNOWN
    error_message: str = ""
    error_count: int = 0

    # Tool information
    tools: List[str] = field(default_factory=list)
    tool_count: int = 0

    # Legacy support for old ServerInfo interface
    config: Optional[Any] = None

    def __post_init__(self):
        """Update computed fields."""
        self.tool_count = len(self.tools)

    @property
    def is_running(self) -> bool:
        """Check if server is in running state."""
        return self.state == ServerState.RUNNING

    @is_running.setter
    def is_running(self, value: bool):
        """Set running state (legacy support)."""
        self.state = ServerState.RUNNING if value else ServerState.STOPPED

    @property
    def is_healthy(self) -> bool:
        """Check if server is healthy."""
        return self.health_status == HealthStatus.HEALTHY

    @is_healthy.setter
    def is_healthy(self, value: bool):
        """Set healthy status (legacy support)."""
        self.health_status = HealthStatus.HEALTHY if value else HealthStatus.UNHEALTHY

    @property
    def uptime_seconds(self) -> Optional[float]:
        """Calculate uptime in seconds."""
        if self.start_time:
            return (datetime.utcnow() - self.start_time).total_seconds()
        return None

    @classmethod
    def from_core_config(
        cls, config, state: ServerState = ServerState.STOPPED
    ) -> "ServerInfo":
        """Create ServerInfo from core ServerConfig for lightweight usage."""
        return cls(
            name=config.name,
            server_type=config.config.get("type", "unknown"),
            state=state,
            host=config.host,
            port=config.port,
            transport=config.transport,
            url=f"http://{config.host}:{config.port}{config.path}"
            if config.transport in ["http", "streamable-http"]
            else None,
            config=config,  # Store the original config for legacy support
        )


@dataclass
class ToolCall:
    """Represents a tool call at the application level."""

    id: str
    tool_name: str
    arguments: Dict[str, Any]
    server_name: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class ToolResult:
    """Represents a tool call result at the application level."""

    id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    server_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    duration_ms: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    @property
    def state(self) -> ToolCallState:
        """Get the current state of this tool result."""
        if self.error:
            return ToolCallState.ERROR
        elif self.result is not None:
            return ToolCallState.RESULT
        else:
            return ToolCallState.CALL

    @property
    def is_success(self) -> bool:
        return self.state == ToolCallState.RESULT

    @property
    def is_error(self) -> bool:
        return self.state == ToolCallState.ERROR
