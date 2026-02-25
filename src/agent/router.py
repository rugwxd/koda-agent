"""Complexity router — decides between ReAct and Plan-and-Execute."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from src.config import PlannerConfig

logger = logging.getLogger(__name__)

# Keywords that suggest multi-step, complex tasks
COMPLEX_KEYWORDS = {
    "refactor", "migrate", "restructure", "redesign", "overhaul",
    "add feature", "implement", "build", "create new",
    "across files", "multiple files", "entire codebase",
    "test suite", "end to end", "integration",
    "optimize", "performance", "benchmark",
}

# Keywords that suggest simple, single-step tasks
SIMPLE_KEYWORDS = {
    "fix typo", "rename", "add import", "remove unused",
    "update version", "change value", "read file",
    "what is", "explain", "show me", "find",
}


class TaskComplexity(str, Enum):
    """Task complexity classification."""

    SIMPLE = "simple"
    COMPLEX = "complex"


@dataclass
class RoutingDecision:
    """Result of the complexity routing decision."""

    complexity: TaskComplexity
    confidence: float
    reason: str

    @property
    def needs_planning(self) -> bool:
        return self.complexity == TaskComplexity.COMPLEX


class ComplexityRouter:
    """Routes tasks to either the ReAct loop or Plan-and-Execute based on complexity.

    Uses heuristic signals:
    - Task length and keyword matching
    - Number of files/concepts mentioned
    - Presence of multi-step indicators

    Simple tasks → direct ReAct loop
    Complex tasks → decomposition via Planner, then step-by-step execution
    """

    def __init__(self, config: PlannerConfig) -> None:
        self.config = config

    def route(self, task: str) -> RoutingDecision:
        """Classify task complexity and decide execution strategy.

        Args:
            task: The user's task description.

        Returns:
            RoutingDecision with complexity level and reasoning.
        """
        score = 0.0
        reasons = []

        task_lower = task.lower()

        # Check for complex keywords
        complex_matches = [kw for kw in COMPLEX_KEYWORDS if kw in task_lower]
        if complex_matches:
            score += 0.3 * len(complex_matches)
            reasons.append(f"Complex keywords: {', '.join(complex_matches)}")

        # Check for simple keywords
        simple_matches = [kw for kw in SIMPLE_KEYWORDS if kw in task_lower]
        if simple_matches:
            score -= 0.3 * len(simple_matches)
            reasons.append(f"Simple keywords: {', '.join(simple_matches)}")

        # Task length (longer tasks tend to be more complex)
        word_count = len(task.split())
        if word_count > 50:
            score += 0.2
            reasons.append(f"Long task description ({word_count} words)")
        elif word_count < 10:
            score -= 0.2
            reasons.append(f"Short task description ({word_count} words)")

        # Count file references
        file_refs = re.findall(r"[\w/]+\.\w{1,4}", task)
        if len(file_refs) > 2:
            score += 0.2
            reasons.append(f"Multiple file references ({len(file_refs)})")

        # Multi-step indicators
        step_indicators = re.findall(r"(?:then|after that|next|also|and then|finally)", task_lower)
        if step_indicators:
            score += 0.15 * len(step_indicators)
            reasons.append(f"Multi-step indicators ({len(step_indicators)})")

        # Normalize to [0, 1]
        score = max(0.0, min(1.0, score + 0.5))

        complexity = (
            TaskComplexity.COMPLEX if score >= self.config.complexity_threshold
            else TaskComplexity.SIMPLE
        )

        decision = RoutingDecision(
            complexity=complexity,
            confidence=abs(score - 0.5) * 2,  # Higher when further from threshold
            reason="; ".join(reasons) if reasons else "Default classification",
        )

        logger.info("Routed task as %s (score=%.2f, confidence=%.2f)",
                     complexity.value, score, decision.confidence)

        return decision
