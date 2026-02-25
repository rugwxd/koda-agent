"""Shared test fixtures for the Koda agent test suite."""

from __future__ import annotations

import pytest

from src.config import (
    CacheConfig,
    CostConfig,
    CriticConfig,
    LLMConfig,
    LoggingConfig,
    MemoryConfig,
    ModelPricing,
    PlannerConfig,
    Settings,
    ToolsConfig,
    TraceConfig,
)
from src.cost.tracker import CostTracker
from src.trace.collector import TraceCollector


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    content = '''"""Sample module for testing."""

import os
from pathlib import Path


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


class Calculator:
    """Simple calculator class."""

    def __init__(self) -> None:
        self.history: list[float] = []

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self.history.append(result)
        return result

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        result = a - b
        self.history.append(result)
        return result
'''
    file_path = tmp_path / "sample.py"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def test_settings():
    """Create test settings with sensible defaults."""
    return Settings(
        llm=LLMConfig(model="claude-sonnet-4-20250514", max_tokens=1024),
        planner=PlannerConfig(complexity_threshold=0.6),
        tools=ToolsConfig(sandbox_enabled=False),
        memory=MemoryConfig(
            episodic_db_path=":memory:",
            semantic_index_path="/tmp/test_semantic.faiss",
        ),
        critic=CriticConfig(run_tests=False, run_lint=False),
        cache=CacheConfig(db_path=":memory:", enabled=False),
        cost=CostConfig(
            budget_per_task_usd=1.00,
            pricing={
                "claude-sonnet-4-20250514": ModelPricing(input_per_1k=0.003, output_per_1k=0.015),
            },
        ),
        trace=TraceConfig(enabled=True, log_dir="/tmp/test_traces"),
        logging=LoggingConfig(level="DEBUG"),
        anthropic_api_key="test-key",
    )


@pytest.fixture
def cost_tracker(test_settings):
    """Create a cost tracker for testing."""
    return CostTracker(config=test_settings.cost)


@pytest.fixture
def trace_collector():
    """Create a trace collector for testing."""
    return TraceCollector(task_id="test-task-001")
