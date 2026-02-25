"""Data models for LLM interactions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Message roles in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"


class ContentType(str, Enum):
    """Types of content blocks in messages."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


@dataclass
class TextContent:
    """A text content block."""

    text: str
    type: str = "text"


@dataclass
class ToolUseContent:
    """A tool_use content block from the assistant."""

    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class ToolResultContent:
    """A tool_result content block sent back to the API."""

    tool_use_id: str
    content: str
    is_error: bool = False
    type: str = "tool_result"


@dataclass
class Message:
    """A conversation message with structured content blocks."""

    role: Role
    content: list[TextContent | ToolUseContent | ToolResultContent]

    def to_api_format(self) -> dict[str, Any]:
        """Convert to Anthropic API message format."""
        formatted_content = []
        for block in self.content:
            if isinstance(block, TextContent):
                formatted_content.append({"type": "text", "text": block.text})
            elif isinstance(block, ToolUseContent):
                formatted_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif isinstance(block, ToolResultContent):
                formatted_content.append({
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": block.content,
                    "is_error": block.is_error,
                })
        return {"role": self.role.value, "content": formatted_content}

    @property
    def text(self) -> str:
        """Extract concatenated text from all text content blocks."""
        parts = []
        for block in self.content:
            if isinstance(block, TextContent):
                parts.append(block.text)
        return "\n".join(parts)

    @property
    def tool_calls(self) -> list[ToolUseContent]:
        """Extract all tool_use blocks from this message."""
        return [b for b in self.content if isinstance(b, ToolUseContent)]


@dataclass
class ToolDefinition:
    """A tool definition for the Anthropic API."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_api_format(self) -> dict[str, Any]:
        """Convert to Anthropic API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class LLMResponse:
    """Parsed response from the LLM API."""

    content: list[TextContent | ToolUseContent]
    stop_reason: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0

    @property
    def has_tool_calls(self) -> bool:
        """Whether the response contains tool_use blocks."""
        return self.stop_reason == "tool_use"

    @property
    def tool_calls(self) -> list[ToolUseContent]:
        """Extract tool_use blocks from the response."""
        return [b for b in self.content if isinstance(b, ToolUseContent)]

    @property
    def text(self) -> str:
        """Extract concatenated text from response."""
        parts = []
        for block in self.content:
            if isinstance(block, TextContent):
                parts.append(block.text)
        return "\n".join(parts)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Conversation:
    """Manages the message history for an agent session."""

    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)

    def add_user_message(self, text: str) -> Message:
        """Add a user text message."""
        msg = Message(role=Role.USER, content=[TextContent(text=text)])
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, content: list[TextContent | ToolUseContent]) -> Message:
        """Add an assistant message from LLM response content."""
        msg = Message(role=Role.ASSISTANT, content=content)
        self.messages.append(msg)
        return msg

    def add_tool_results(self, results: list[ToolResultContent]) -> Message:
        """Add tool results as a user message."""
        msg = Message(role=Role.USER, content=results)
        self.messages.append(msg)
        return msg

    def to_api_format(self) -> list[dict[str, Any]]:
        """Convert full message history to API format."""
        return [m.to_api_format() for m in self.messages]

    @property
    def token_estimate(self) -> int:
        """Rough token count estimate (4 chars per token heuristic)."""
        total_chars = len(self.system_prompt)
        for msg in self.messages:
            for block in msg.content:
                if isinstance(block, TextContent):
                    total_chars += len(block.text)
                elif isinstance(block, ToolResultContent):
                    total_chars += len(block.content)
                elif isinstance(block, ToolUseContent):
                    total_chars += len(str(block.input))
        return total_chars // 4
