"""Tests for the agent loop (unit tests without LLM calls)."""

import pytest

from src.agent.loop import AgentResult


class TestAgentResult:
    def test_successful_result(self):
        result = AgentResult(
            success=True,
            response="Done! I fixed the bug.",
            iterations=3,
            tool_calls_made=["read_file", "write_file", "run_tests"],
            files_modified=["src/auth.py"],
            total_tokens=5000,
            total_cost_usd=0.03,
            duration_seconds=12.5,
        )
        assert result.success
        assert len(result.tool_calls_made) == 3
        assert len(result.files_modified) == 1

    def test_failed_result(self):
        result = AgentResult(
            success=False,
            response="Agent encountered an error: connection timeout",
            iterations=1,
            total_tokens=1000,
            total_cost_usd=0.005,
            duration_seconds=5.0,
        )
        assert not result.success
        assert "error" in result.response.lower()

    def test_empty_result(self):
        result = AgentResult(
            success=False,
            response="",
            iterations=0,
        )
        assert not result.success
        assert result.total_tokens == 0
        assert result.files_modified == []
