"""Streamlit dashboard for visualizing Koda agent traces."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Koda — Trace Dashboard", page_icon="K", layout="wide")


def load_traces(trace_dir: str) -> list[dict]:
    """Load all trace files from the trace directory."""
    trace_path = Path(trace_dir)
    if not trace_path.exists():
        return []

    traces = []
    for f in sorted(trace_path.glob("trace_*.json"), reverse=True):
        try:
            with open(f) as fh:
                traces.append(json.load(fh))
        except json.JSONDecodeError:
            continue
    return traces


def render_sidebar(traces: list[dict]) -> dict | None:
    """Render trace selector sidebar."""
    st.sidebar.title("Koda Traces")

    if not traces:
        st.sidebar.warning("No traces found. Run the agent to generate traces.")
        return None

    task_ids = [t["task_id"] for t in traces]
    selected = st.sidebar.selectbox("Select trace", task_ids)
    return next((t for t in traces if t["task_id"] == selected), None)


def render_overview(trace: dict) -> None:
    """Render trace overview metrics."""
    st.header(f"Trace: {trace['task_id']}")

    spans = trace.get("spans", [])
    total_events = trace.get("total_events", 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Spans", len(spans))
    col2.metric("Events", total_events)

    # Calculate total duration
    durations = [s.get("duration_ms", 0) for s in spans if s.get("duration_ms")]
    total_ms = sum(durations) if durations else 0
    col3.metric("Duration", f"{total_ms:.0f}ms")


def render_timeline(trace: dict) -> None:
    """Render a timeline of spans and events."""
    st.subheader("Execution Timeline")

    spans = trace.get("spans", [])
    for span in spans:
        duration = span.get("duration_ms", 0)
        with st.expander(f"{span['name']} ({duration:.0f}ms)", expanded=False):
            events = span.get("events", [])
            for event in events:
                event_type = event.get("event_type", "unknown")
                data = event.get("data", {})

                if event_type == "thought":
                    st.markdown(f"**Thought:** {data.get('text', '')}")
                elif event_type == "tool_call":
                    st.code(f"Tool: {data.get('tool', '')} | Input: {json.dumps(data.get('input', {}), indent=2)}")
                elif event_type == "tool_result":
                    status = "OK" if data.get("success") else "FAIL"
                    st.markdown(f"**Result [{status}]:** {data.get('output_length', 0)} chars")
                    if data.get("error"):
                        st.error(data["error"])
                elif event_type == "llm_request":
                    st.markdown(f"**LLM Request:** {data.get('model', '')} ({data.get('message_count', 0)} messages)")
                elif event_type == "llm_response":
                    tokens = f"{data.get('input_tokens', 0)}/{data.get('output_tokens', 0)}"
                    st.markdown(f"**LLM Response:** {tokens} tokens, stop={data.get('stop_reason', '')}")
                elif event_type == "cache_hit":
                    st.success(f"Cache hit! Similarity: {data.get('similarity', 0):.2f}, Saved: ${data.get('saved_cost', 0):.4f}")
                elif event_type == "cache_miss":
                    st.info(f"Cache miss (best score: {data.get('best_score', 0):.2f})")
                elif event_type == "critic_check":
                    if data.get("passed"):
                        st.success(f"Verification passed ({data.get('total_checks', 0)} checks)")
                    else:
                        st.error(f"Verification failed: {data.get('summary', '')}")
                elif event_type == "budget_warning":
                    st.warning(f"Budget warning: {data.get('error', '')}")
                elif event_type == "error":
                    st.error(f"Error: {data.get('error', '')}")
                else:
                    st.json(data)


def render_cost_breakdown(trace: dict) -> None:
    """Render cost analysis from trace events."""
    st.subheader("Cost Breakdown")

    spans = trace.get("spans", [])
    total_input = 0
    total_output = 0
    api_calls = 0

    for span in spans:
        for event in span.get("events", []):
            if event["event_type"] == "llm_response":
                data = event["data"]
                total_input += data.get("input_tokens", 0)
                total_output += data.get("output_tokens", 0)
                api_calls += 1

    col1, col2, col3 = st.columns(3)
    col1.metric("API Calls", api_calls)
    col2.metric("Input Tokens", f"{total_input:,}")
    col3.metric("Output Tokens", f"{total_output:,}")


def render_tool_usage(trace: dict) -> None:
    """Render tool usage statistics."""
    st.subheader("Tool Usage")

    tool_counts: dict[str, int] = {}
    tool_success: dict[str, int] = {}

    spans = trace.get("spans", [])
    for span in spans:
        for event in span.get("events", []):
            if event["event_type"] == "tool_call":
                name = event["data"].get("tool", "unknown")
                tool_counts[name] = tool_counts.get(name, 0) + 1
            elif event["event_type"] == "tool_result":
                name = event["data"].get("tool", "unknown")
                if event["data"].get("success"):
                    tool_success[name] = tool_success.get(name, 0) + 1

    if tool_counts:
        for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
            success = tool_success.get(tool, 0)
            st.progress(success / count if count > 0 else 0, text=f"{tool}: {count} calls ({success} OK)")
    else:
        st.info("No tool calls in this trace")


def main():
    """Main dashboard entry point."""
    trace_dir = st.sidebar.text_input("Trace directory", value="data/traces")
    traces = load_traces(trace_dir)
    selected = render_sidebar(traces)

    if selected:
        render_overview(selected)

        tab1, tab2, tab3 = st.tabs(["Timeline", "Cost", "Tools"])
        with tab1:
            render_timeline(selected)
        with tab2:
            render_cost_breakdown(selected)
        with tab3:
            render_tool_usage(selected)
    else:
        st.title("Koda — Trace Dashboard")
        st.markdown("""
        ### Getting Started

        1. Run the Koda agent with tracing enabled
        2. Traces are saved to `data/traces/`
        3. Select a trace from the sidebar to explore

        The dashboard shows:
        - **Timeline**: Step-by-step execution with thoughts, tool calls, and results
        - **Cost**: Token usage and API call breakdown
        - **Tools**: Usage statistics and success rates
        """)


if __name__ == "__main__":
    main()
