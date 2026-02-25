"""Trace event and span models for observability."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of trace events."""

    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THOUGHT = "thought"
    PLAN_STEP = "plan_step"
    CRITIC_CHECK = "critic_check"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    MEMORY_STORE = "memory_store"
    MEMORY_RECALL = "memory_recall"
    ERROR = "error"
    BUDGET_WARNING = "budget_warning"


@dataclass
class TraceEvent:
    """A single trace event within a span."""

    event_type: EventType
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class TraceSpan:
    """A span representing a logical unit of work (e.g., one agent iteration)."""

    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    events: list[TraceEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_event(self, event: TraceEvent) -> None:
        """Add an event to this span."""
        self.events.append(event)

    def close(self) -> None:
        """Mark the span as complete."""
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float | None:
        """Duration in milliseconds, or None if still open."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "span_id": self.span_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
        }
