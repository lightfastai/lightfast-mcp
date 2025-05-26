"""Common types and data structures for the tools package."""

# Import shared types from common module
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, TypeVar

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common import OperationStatus, ToolCall, ToolResult

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    """Standard result type for all operations."""

    status: OperationStatus
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: Optional[datetime] = None
    duration_ms: Optional[float] = None
    correlation_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.correlation_id is None:
            self.correlation_id = str(uuid.uuid4())

    @property
    def is_success(self) -> bool:
        return self.status == OperationStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == OperationStatus.FAILED

    @property
    def is_pending(self) -> bool:
        return self.status == OperationStatus.PENDING


# ServerInfo, ToolCall, and ToolResult are now imported from common module


@dataclass
class ConversationStep:
    """Represents a single step in a conversation."""

    step_number: int
    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    duration_ms: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def add_tool_call(self, tool_call: ToolCall) -> None:
        """Add a tool call to this step."""
        self.tool_calls.append(tool_call)

    def add_tool_result(self, tool_result: ToolResult) -> None:
        """Add a tool result to this step."""
        self.tool_results.append(tool_result)

    def has_pending_tool_calls(self) -> bool:
        """Check if this step has tool calls that haven't been executed yet."""
        executed_ids = {result.id for result in self.tool_results}
        return any(call.id not in executed_ids for call in self.tool_calls)

    @property
    def has_errors(self) -> bool:
        """Check if any tool results have errors."""
        return any(result.is_error for result in self.tool_results)


@dataclass
class ConversationResult:
    """Result of a conversation interaction."""

    session_id: str
    steps: List[ConversationStep]
    total_duration_ms: Optional[float] = None
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0

    def __post_init__(self):
        # Calculate statistics
        self.total_tool_calls = sum(len(step.tool_calls) for step in self.steps)
        self.successful_tool_calls = sum(
            len([r for r in step.tool_results if r.is_success]) for step in self.steps
        )
        self.failed_tool_calls = sum(
            len([r for r in step.tool_results if r.is_error]) for step in self.steps
        )

    @property
    def final_response(self) -> str:
        """Get the final text response from the conversation."""
        if self.steps:
            return self.steps[-1].text
        return ""

    @property
    def has_errors(self) -> bool:
        """Check if any steps have errors."""
        return any(step.has_errors for step in self.steps)

    @property
    def success_rate(self) -> float:
        """Calculate tool call success rate."""
        if self.total_tool_calls == 0:
            return 1.0
        return self.successful_tool_calls / self.total_tool_calls
