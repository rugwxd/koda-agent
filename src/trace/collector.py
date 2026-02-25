"""Trace collector for aggregating spans and events."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.trace.models import EventType, TraceEvent, TraceSpan

logger = logging.getLogger(__name__)


class TraceCollector:
    """Collects and manages trace spans for a single task execution.

    Provides structured observability into agent behavior: every LLM call,
    tool execution, thought, and decision is recorded as a trace event
    within hierarchical spans.
    """

    def __init__(self, task_id: str, log_dir: str | None = None) -> None:
        self.task_id = task_id
        self.log_dir = Path(log_dir) if log_dir else None
        self.spans: list[TraceSpan] = []
        self._active_span: TraceSpan | None = None

    def start_span(self, name: str, parent_id: str | None = None, **metadata: Any) -> TraceSpan:
        """Start a new trace span.

        Args:
            name: Human-readable span name (e.g., "iteration_3", "critic_pass").
            parent_id: Optional parent span ID for nesting.
            **metadata: Additional metadata to attach to the span.

        Returns:
            The newly created span.
        """
        span = TraceSpan(name=name, parent_id=parent_id, metadata=metadata)
        self.spans.append(span)
        self._active_span = span
        logger.debug("Started span: %s (%s)", name, span.span_id)
        return span

    def end_span(self, span: TraceSpan | None = None) -> None:
        """Close a span. Defaults to the most recently started span."""
        target = span or self._active_span
        if target:
            target.close()
            logger.debug("Closed span: %s (%.1fms)", target.name, target.duration_ms or 0)
            if target == self._active_span:
                self._active_span = None

    def record(self, event_type: EventType, data: dict[str, Any]) -> TraceEvent:
        """Record an event in the current active span.

        Args:
            event_type: The type of event being recorded.
            data: Event payload data.

        Returns:
            The recorded trace event.
        """
        event = TraceEvent(event_type=event_type, data=data)

        if self._active_span:
            self._active_span.add_event(event)
        else:
            # Create an orphan span for events outside any span
            orphan = self.start_span("orphan")
            orphan.add_event(event)

        return event

    @property
    def active_span(self) -> TraceSpan | None:
        """Currently active span."""
        return self._active_span

    @property
    def event_count(self) -> int:
        """Total number of events across all spans."""
        return sum(len(s.events) for s in self.spans)

    def get_events_by_type(self, event_type: EventType) -> list[TraceEvent]:
        """Retrieve all events of a specific type across spans."""
        events = []
        for span in self.spans:
            for event in span.events:
                if event.event_type == event_type:
                    events.append(event)
        return events

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full trace to a dictionary."""
        return {
            "task_id": self.task_id,
            "spans": [s.to_dict() for s in self.spans],
            "total_events": self.event_count,
        }

    def save(self) -> Path | None:
        """Persist trace to disk as JSON.

        Returns:
            Path to the saved trace file, or None if no log_dir configured.
        """
        if not self.log_dir:
            return None

        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"trace_{self.task_id}.json"

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info("Saved trace to %s (%d events)", path, self.event_count)
        return path
