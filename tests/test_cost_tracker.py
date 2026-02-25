"""Tests for cost tracking and budget enforcement."""

import pytest

from src.config import CostConfig, ModelPricing
from src.cost.tracker import BudgetExceededError, CostTracker


@pytest.fixture
def tracker():
    config = CostConfig(
        budget_per_task_usd=0.10,
        pricing={
            "test-model": ModelPricing(input_per_1k=0.003, output_per_1k=0.015),
        },
    )
    return CostTracker(config=config)


class TestCostTracker:
    def test_record_call(self, tracker):
        record = tracker.record_call("test-model", input_tokens=1000, output_tokens=500)
        assert record.input_cost == pytest.approx(0.003)
        assert record.output_cost == pytest.approx(0.0075)
        assert record.total_cost == pytest.approx(0.0105)

    def test_total_cost(self, tracker):
        tracker.record_call("test-model", input_tokens=1000, output_tokens=500)
        tracker.record_call("test-model", input_tokens=2000, output_tokens=1000)
        assert tracker.total_cost == pytest.approx(0.0315)

    def test_budget_exceeded(self, tracker):
        # Budget is $0.10; first call under budget, second pushes over
        tracker.record_call("test-model", input_tokens=5000, output_tokens=2000)
        with pytest.raises(BudgetExceededError) as exc:
            tracker.record_call("test-model", input_tokens=10000, output_tokens=5000)
        assert exc.value.budget == 0.10

    def test_unknown_model(self, tracker):
        record = tracker.record_call("unknown-model", input_tokens=1000, output_tokens=500)
        assert record.input_cost == 0.0
        assert record.output_cost == 0.0

    def test_cache_savings(self, tracker):
        tracker.record_call("test-model", input_tokens=1000, output_tokens=500, cached_tokens=500)
        assert tracker.cache_savings == pytest.approx(0.0015)

    def test_summary(self, tracker):
        tracker.record_call("test-model", input_tokens=1000, output_tokens=500)
        summary = tracker.summary()
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert summary["api_calls"] == 1
        assert summary["total_tokens"] == 1500

    def test_call_count(self, tracker):
        assert tracker.call_count == 0
        tracker.record_call("test-model", input_tokens=100, output_tokens=50)
        tracker.record_call("test-model", input_tokens=200, output_tokens=100)
        assert tracker.call_count == 2
