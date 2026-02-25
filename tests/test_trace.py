"""Tests for trace models and collector."""

import json

from src.trace.models import EventType, TraceEvent, TraceSpan


class TestTraceEvent:
    def test_create_event(self):
        event = TraceEvent(event_type=EventType.TOOL_CALL, data={"tool": "read_file"})
        assert event.event_type == EventType.TOOL_CALL
        assert event.data["tool"] == "read_file"
        assert event.event_id is not None

    def test_event_to_dict(self):
        event = TraceEvent(event_type=EventType.THOUGHT, data={"text": "thinking..."})
        d = event.to_dict()
        assert d["event_type"] == "thought"
        assert d["data"]["text"] == "thinking..."
        assert "timestamp" in d


class TestTraceSpan:
    def test_span_lifecycle(self):
        span = TraceSpan(name="test_span")
        assert span.end_time is None
        assert span.duration_ms is None

        span.add_event(TraceEvent(event_type=EventType.THOUGHT, data={}))
        assert len(span.events) == 1

        span.close()
        assert span.end_time is not None
        assert span.duration_ms >= 0

    def test_span_to_dict(self):
        span = TraceSpan(name="iteration_0", metadata={"key": "value"})
        span.add_event(TraceEvent(event_type=EventType.LLM_REQUEST, data={}))
        span.close()
        d = span.to_dict()
        assert d["name"] == "iteration_0"
        assert len(d["events"]) == 1
        assert d["metadata"]["key"] == "value"


class TestTraceCollector:
    def test_start_and_end_span(self, trace_collector):
        span = trace_collector.start_span("test")
        assert trace_collector.active_span == span
        trace_collector.end_span()
        assert trace_collector.active_span is None

    def test_record_event(self, trace_collector):
        trace_collector.start_span("test")
        event = trace_collector.record(EventType.TOOL_CALL, {"tool": "grep"})
        assert event.event_type == EventType.TOOL_CALL
        assert trace_collector.event_count == 1

    def test_orphan_event(self, trace_collector):
        # Recording without an active span creates an orphan span
        trace_collector.record(EventType.ERROR, {"msg": "something"})
        assert len(trace_collector.spans) == 1
        assert trace_collector.spans[0].name == "orphan"

    def test_get_events_by_type(self, trace_collector):
        trace_collector.start_span("test")
        trace_collector.record(EventType.TOOL_CALL, {"tool": "read"})
        trace_collector.record(EventType.THOUGHT, {"text": "hmm"})
        trace_collector.record(EventType.TOOL_CALL, {"tool": "write"})
        tools = trace_collector.get_events_by_type(EventType.TOOL_CALL)
        assert len(tools) == 2

    def test_save_trace(self, trace_collector, tmp_path):
        trace_collector.log_dir = tmp_path
        trace_collector.start_span("test")
        trace_collector.record(EventType.THOUGHT, {"text": "hello"})
        trace_collector.end_span()

        path = trace_collector.save()
        assert path is not None
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["task_id"] == "test-task-001"
        assert data["total_events"] == 1

    def test_to_dict(self, trace_collector):
        trace_collector.start_span("s1")
        trace_collector.record(EventType.LLM_REQUEST, {})
        trace_collector.end_span()
        d = trace_collector.to_dict()
        assert d["task_id"] == "test-task-001"
        assert len(d["spans"]) == 1
