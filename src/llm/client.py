"""Claude API client wrapper with tool_use protocol support."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from src.config import LLMConfig
from src.cost.tracker import CostTracker
from src.llm.models import (
    Conversation,
    LLMResponse,
    TextContent,
    ToolDefinition,
    ToolUseContent,
)
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around the Anthropic API with integrated cost tracking and tracing.

    Handles the tool_use protocol: sends messages with tool definitions,
    parses structured responses (text + tool_use blocks), and records
    all interactions for observability.
    """

    def __init__(
        self,
        config: LLMConfig,
        api_key: str,
        cost_tracker: CostTracker,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self.config = config
        self.client = anthropic.Anthropic(api_key=api_key)
        self.cost_tracker = cost_tracker
        self.trace = trace_collector

    def chat(
        self,
        conversation: Conversation,
        tools: list[ToolDefinition] | None = None,
        model_override: str | None = None,
        max_tokens_override: int | None = None,
    ) -> LLMResponse:
        """Send a conversation to the Claude API and parse the response.

        Args:
            conversation: The message history to send.
            tools: Optional list of tool definitions to provide.
            model_override: Override the configured model for this call.
            max_tokens_override: Override max_tokens for this call.

        Returns:
            Parsed LLMResponse with content blocks and usage info.
        """
        model = model_override or self.config.model
        max_tokens = max_tokens_override or self.config.max_tokens

        # Build API request
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": self.config.temperature,
            "messages": conversation.to_api_format(),
        }

        if conversation.system_prompt:
            kwargs["system"] = conversation.system_prompt

        if tools:
            kwargs["tools"] = [t.to_api_format() for t in tools]

        # Record request in trace
        if self.trace:
            self.trace.record(
                EventType.LLM_REQUEST,
                {
                    "model": model,
                    "message_count": len(conversation.messages),
                    "tool_count": len(tools) if tools else 0,
                },
            )

        logger.debug("Sending request to %s (%d messages)", model, len(conversation.messages))

        # Make API call
        response = self.client.messages.create(**kwargs)

        # Parse response content blocks
        content_blocks: list[TextContent | ToolUseContent] = []
        for block in response.content:
            if block.type == "text":
                content_blocks.append(TextContent(text=block.text))
            elif block.type == "tool_use":
                content_blocks.append(
                    ToolUseContent(
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                )

        # Extract usage
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

        # Record cost
        self.cost_tracker.record_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cache_read,
        )

        # Record response in trace
        if self.trace:
            self.trace.record(
                EventType.LLM_RESPONSE,
                {
                    "model": model,
                    "stop_reason": response.stop_reason,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read,
                    "has_tool_calls": response.stop_reason == "tool_use",
                },
            )

        llm_response = LLMResponse(
            content=content_blocks,
            stop_reason=response.stop_reason,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
        )

        logger.debug(
            "Response: stop=%s, tokens=%d/%d",
            llm_response.stop_reason,
            input_tokens,
            output_tokens,
        )

        return llm_response
