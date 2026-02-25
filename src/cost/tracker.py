"""Cost tracking with per-call token recording and budget enforcement."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.config import CostConfig

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when a task exceeds its cost budget."""

    def __init__(self, spent: float, budget: float) -> None:
        self.spent = spent
        self.budget = budget
        super().__init__(f"Budget exceeded: ${spent:.4f} spent of ${budget:.4f} limit")


@dataclass
class APICallRecord:
    """Record of a single API call's token usage and cost."""

    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    cached_tokens: int = 0

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class CostTracker:
    """Tracks API costs per task with budget enforcement.

    Records every API call, calculates costs using the configured pricing
    table, and raises BudgetExceededError when the task budget is exceeded.
    """

    config: CostConfig
    records: list[APICallRecord] = field(default_factory=list)
    _cache_savings: float = 0.0

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> APICallRecord:
        """Record an API call and check budget.

        Args:
            model: Model identifier (e.g., "claude-sonnet-4-20250514").
            input_tokens: Number of input tokens consumed.
            output_tokens: Number of output tokens generated.
            cached_tokens: Number of tokens served from cache (cost savings).

        Returns:
            The recorded APICallRecord.

        Raises:
            BudgetExceededError: If cumulative cost exceeds the task budget.
        """
        pricing = self.config.pricing.get(model)
        if pricing:
            input_cost = (input_tokens / 1000) * pricing.input_per_1k
            output_cost = (output_tokens / 1000) * pricing.output_per_1k
            cache_saving = (cached_tokens / 1000) * pricing.input_per_1k
        else:
            logger.warning("No pricing found for model %s, assuming zero cost", model)
            input_cost = 0.0
            output_cost = 0.0
            cache_saving = 0.0

        self._cache_savings += cache_saving

        record = APICallRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            cached_tokens=cached_tokens,
        )
        self.records.append(record)

        total = self.total_cost
        budget = self.config.budget_per_task_usd

        if total > budget * 0.8:
            logger.warning(
                "Cost warning: $%.4f of $%.4f budget (%.0f%%)",
                total,
                budget,
                (total / budget) * 100,
            )

        if total > budget:
            raise BudgetExceededError(spent=total, budget=budget)

        return record

    @property
    def total_cost(self) -> float:
        """Total cost across all recorded API calls."""
        return sum(r.total_cost for r in self.records)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all recorded API calls."""
        return sum(r.total_tokens for r in self.records)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens across all calls."""
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens across all calls."""
        return sum(r.output_tokens for r in self.records)

    @property
    def cache_savings(self) -> float:
        """Total cost savings from cached tokens."""
        return self._cache_savings

    @property
    def call_count(self) -> int:
        """Number of API calls made."""
        return len(self.records)

    def summary(self) -> dict[str, float | int]:
        """Return a cost summary dictionary."""
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cache_savings_usd": round(self.cache_savings, 6),
            "api_calls": self.call_count,
            "budget_remaining_usd": round(self.config.budget_per_task_usd - self.total_cost, 6),
        }
