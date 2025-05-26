"""Conversation session management for AI interactions."""

import time
from typing import Any, Dict, List

import mcp.types as mcp_types

from tools.common import (
    ConversationError,
    ConversationStep,
    OperationStatus,
    Result,
    ToolResult,
    get_logger,
    with_correlation_id,
    with_operation_context,
)

from .providers.base_provider import BaseAIProvider
from .tool_executor import ToolExecutor

logger = get_logger("ConversationSession")


class ConversationSession:
    """Manages a single conversation session with AI and tool execution."""

    def __init__(
        self,
        session_id: str,
        max_steps: int,
        ai_provider: BaseAIProvider,
        tool_executor: ToolExecutor,
        available_tools: Dict[str, tuple[mcp_types.Tool, str]],
    ):
        """Initialize a conversation session."""
        self.session_id = session_id
        self.max_steps = max_steps
        self.ai_provider = ai_provider
        self.tool_executor = tool_executor
        self.available_tools = available_tools

        # Conversation state
        self.messages: List[Dict[str, Any]] = []
        self.steps: List[ConversationStep] = []
        self.current_step_number = 0
        self.is_complete = False

        logger.info(f"Created conversation session {session_id}")

    @with_correlation_id
    @with_operation_context(operation="process_message")
    async def process_message(self, message: str) -> Result[List[ConversationStep]]:
        """Process a user message and generate response steps."""
        if self.is_complete:
            return Result(
                status=OperationStatus.FAILED,
                error="Conversation session is already complete",
                error_code="SESSION_COMPLETE",
            )

        # Add user message to conversation
        self.messages.append({"role": "user", "content": message})

        logger.info(
            f"Processing message in session {self.session_id}",
            session_id=self.session_id,
            message_length=len(message),
        )

        new_steps: List[ConversationStep] = []

        try:
            # Generate steps until completion or max steps reached
            for step_num in range(self.current_step_number, self.max_steps):
                if self.is_complete:
                    break

                step_result = await self._generate_step(step_num)
                if not step_result.is_success:
                    return Result(
                        status=OperationStatus.FAILED,
                        error=f"Failed to generate step {step_num}: {step_result.error}",
                        error_code="STEP_GENERATION_FAILED",
                    )

                step = step_result.data
                if step is None:
                    return Result(
                        status=OperationStatus.FAILED,
                        error=f"Step {step_num} returned None data",
                        error_code="NULL_STEP_DATA",
                    )

                self.steps.append(step)
                new_steps.append(step)
                self.current_step_number += 1

                # Update conversation messages
                await self._update_conversation_messages(step)

                # Check if conversation should continue
                if not step.tool_calls or step.finish_reason == "stop":
                    self.is_complete = True
                    break

            # Mark as complete if we've reached max steps
            if self.current_step_number >= self.max_steps:
                self.is_complete = True

            logger.info(
                f"Processed message with {len(new_steps)} steps",
                session_id=self.session_id,
                steps_generated=len(new_steps),
                is_complete=self.is_complete,
            )

            return Result(status=OperationStatus.SUCCESS, data=new_steps)

        except Exception as e:
            error = ConversationError(
                f"Error processing message: {e}",
                session_id=self.session_id,
                step_number=self.current_step_number,
                cause=e,
            )
            logger.error("Message processing failed", error=error)
            return Result(
                status=OperationStatus.FAILED,
                error=str(error),
                error_code=error.error_code,
            )

    async def _generate_step(self, step_number: int) -> Result[ConversationStep]:
        """Generate a single conversation step."""
        start_time = time.time()

        try:
            # Generate AI response
            step_result = await self.ai_provider.generate_step(
                messages=self.messages,
                available_tools=self.available_tools,
                step_number=step_number,
            )

            if not step_result.is_success:
                return step_result

            step = step_result.data
            if step is None:
                return Result(
                    status=OperationStatus.FAILED,
                    error=f"AI provider returned None step data for step {step_number}",
                    error_code="NULL_AI_STEP_DATA",
                )

            # Execute any tool calls
            if step.tool_calls:
                logger.debug(
                    f"Executing {len(step.tool_calls)} tool calls",
                    session_id=self.session_id,
                    step_number=step_number,
                )

                tool_results = await self.tool_executor.execute_tools_concurrently(
                    step.tool_calls
                )

                # Add results to step
                for result in tool_results:
                    step.add_tool_result(result)

            # Calculate step duration
            step.duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                f"Generated step {step_number}",
                session_id=self.session_id,
                step_number=step_number,
                has_text=bool(step.text),
                tool_calls=len(step.tool_calls),
                tool_results=len(step.tool_results),
                duration_ms=step.duration_ms,
            )

            return Result(status=OperationStatus.SUCCESS, data=step)

        except Exception as e:
            error = ConversationError(
                f"Error generating step {step_number}: {e}",
                session_id=self.session_id,
                step_number=step_number,
                cause=e,
            )
            logger.error("Step generation failed", error=error)
            return Result(
                status=OperationStatus.FAILED,
                error=str(error),
                error_code=error.error_code,
            )

    async def _update_conversation_messages(self, step: ConversationStep):
        """Update conversation messages with step results."""
        if self.ai_provider.provider_name == "claude":
            await self._update_messages_claude_format(step)
        elif self.ai_provider.provider_name == "openai":
            await self._update_messages_openai_format(step)
        else:
            # Generic format
            await self._update_messages_generic_format(step)

    async def _update_messages_claude_format(self, step: ConversationStep):
        """Update messages in Claude format."""
        if step.tool_calls:
            # Claude format: tool calls and results in assistant message content
            content_blocks: List[Dict[str, Any]] = []

            # Add text content if any
            if step.text:
                content_blocks.append({"type": "text", "text": step.text})

            # Add tool use blocks
            for tc in step.tool_calls:
                tool_use_block = {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.tool_name,
                    "input": tc.arguments,
                }
                content_blocks.append(tool_use_block)

            assistant_message = {
                "role": "assistant",
                "content": content_blocks,
            }
            self.messages.append(assistant_message)

            # Add user message with tool results
            tool_result_blocks: List[Dict[str, Any]] = []
            for result in step.tool_results:
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": result.id,
                        "content": self._format_tool_result_content(result),
                    }
                )

            if tool_result_blocks:
                user_message = {
                    "role": "user",
                    "content": tool_result_blocks,
                }
                self.messages.append(user_message)
        else:
            # Regular text response
            self.messages.append({"role": "assistant", "content": step.text})

    async def _update_messages_openai_format(self, step: ConversationStep):
        """Update messages in OpenAI format."""
        if step.tool_calls:
            # OpenAI format: separate tool call and tool result messages
            assistant_message = {
                "role": "assistant",
                "content": step.text or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": str(tc.arguments),  # OpenAI expects string
                        },
                    }
                    for tc in step.tool_calls
                ],
            }
            self.messages.append(assistant_message)

            # Add tool result messages
            for result in step.tool_results:
                tool_message = {
                    "role": "tool",
                    "tool_call_id": result.id,
                    "content": self._format_tool_result_content(result),
                }
                self.messages.append(tool_message)
        else:
            # Regular text response
            self.messages.append({"role": "assistant", "content": step.text})

    async def _update_messages_generic_format(self, step: ConversationStep):
        """Update messages in generic format."""
        # Simple format for unknown providers
        content = step.text or ""

        if step.tool_calls:
            content += f"\n\nTool calls executed: {len(step.tool_calls)}"
            for result in step.tool_results:
                if result.result:
                    content += f"\n- {result.tool_name}: {result.result}"
                elif result.error:
                    content += f"\n- {result.tool_name}: Error - {result.error}"

        self.messages.append({"role": "assistant", "content": content})

    def _format_tool_result_content(self, result: ToolResult) -> str:
        """Format tool result content for messages."""
        if result.result is not None:
            if isinstance(result.result, (dict, list)):
                import json

                return json.dumps(result.result)
            else:
                return str(result.result)
        elif result.error:
            return f"Error: {result.error}"
        else:
            return "No result"

    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get a summary of the conversation session."""
        total_tool_calls = sum(len(step.tool_calls) for step in self.steps)
        successful_tool_calls = sum(
            len([r for r in step.tool_results if not r.error]) for step in self.steps
        )

        return {
            "session_id": self.session_id,
            "steps": len(self.steps),
            "messages": len(self.messages),
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls,
            "is_complete": self.is_complete,
            "max_steps": self.max_steps,
        }

    async def close(self):
        """Close the conversation session and clean up resources."""
        logger.info(f"Closing conversation session {self.session_id}")
        self.is_complete = True
        # Could add cleanup logic here if needed
