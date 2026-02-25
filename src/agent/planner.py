"""Plan-and-Execute strategy for complex multi-step tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from src.config import PlannerConfig
from src.llm.client import LLMClient
from src.llm.models import Conversation
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """You are a task planner for an AI coding agent. Given a complex task,
decompose it into a sequence of concrete, actionable steps.

Rules:
- Each step should be independently executable
- Steps should be ordered by dependency
- Each step should be specific enough to execute without ambiguity
- Include verification steps (run tests, check output) where appropriate
- Maximum {max_steps} steps

Output format — return ONLY a numbered list, one step per line:
1. First step description
2. Second step description
...

Task: {task}

Context: {context}
"""


class StepStatus(str, Enum):
    """Status of a plan step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in the execution plan."""

    index: int
    description: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""


@dataclass
class ExecutionPlan:
    """A decomposed plan for executing a complex task."""

    task: str
    steps: list[PlanStep] = field(default_factory=list)
    failure_count: int = 0

    @property
    def current_step(self) -> PlanStep | None:
        """Get the next pending step."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    @property
    def is_complete(self) -> bool:
        """Check if all steps are done (completed, failed, or skipped)."""
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self.steps
        )

    @property
    def progress_summary(self) -> str:
        """Human-readable progress summary."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        total = len(self.steps)
        return f"Progress: {completed}/{total} completed, {failed} failed"

    def to_context_string(self) -> str:
        """Render plan as context for the agent."""
        lines = [f"Execution Plan for: {self.task}", ""]
        for step in self.steps:
            status_icon = {
                StepStatus.PENDING: "[ ]",
                StepStatus.IN_PROGRESS: "[>]",
                StepStatus.COMPLETED: "[x]",
                StepStatus.FAILED: "[!]",
                StepStatus.SKIPPED: "[-]",
            }[step.status]
            lines.append(f"{status_icon} {step.index}. {step.description}")
            if step.result:
                lines.append(f"    Result: {step.result[:100]}")
            if step.error:
                lines.append(f"    Error: {step.error[:100]}")

        return "\n".join(lines)


class Planner:
    """Decomposes complex tasks into executable step sequences.

    Uses the LLM to generate a plan, then tracks execution progress
    with support for replanning on failures.
    """

    def __init__(
        self,
        config: PlannerConfig,
        llm_client: LLMClient,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self.config = config
        self.llm = llm_client
        self.trace = trace_collector

    def create_plan(self, task: str, context: str = "") -> ExecutionPlan:
        """Generate an execution plan for a complex task.

        Args:
            task: The complex task to decompose.
            context: Additional context about the codebase.

        Returns:
            ExecutionPlan with ordered steps.
        """
        prompt = PLANNER_PROMPT.format(
            max_steps=self.config.max_plan_steps,
            task=task,
            context=context or "(no additional context)",
        )

        conversation = Conversation(system_prompt="You are a precise task planner.")
        conversation.add_user_message(prompt)

        response = self.llm.chat(conversation, max_tokens_override=1024)

        # Parse numbered steps from response
        steps = self._parse_steps(response.text)

        plan = ExecutionPlan(task=task, steps=steps)

        if self.trace:
            self.trace.record(
                EventType.PLAN_STEP,
                {
                    "action": "created",
                    "task": task,
                    "step_count": len(steps),
                    "steps": [s.description for s in steps],
                },
            )

        logger.info("Created plan with %d steps for: %s", len(steps), task[:80])
        return plan

    def replan(self, plan: ExecutionPlan, context: str = "") -> ExecutionPlan:
        """Generate a new plan after failures, incorporating lessons learned.

        Args:
            plan: The current (partially failed) plan.
            context: Additional context.

        Returns:
            New ExecutionPlan with adjusted steps.
        """
        # Build context from previous attempt
        attempt_context = [context, "", "Previous attempt results:"]
        for step in plan.steps:
            if step.status == StepStatus.COMPLETED:
                attempt_context.append(f"  Completed: {step.description}")
            elif step.status == StepStatus.FAILED:
                attempt_context.append(f"  Failed: {step.description} — {step.error}")

        new_plan = self.create_plan(plan.task, "\n".join(attempt_context))
        new_plan.failure_count = plan.failure_count + 1

        if self.trace:
            self.trace.record(
                EventType.PLAN_STEP,
                {
                    "action": "replanned",
                    "attempt": new_plan.failure_count,
                    "new_step_count": len(new_plan.steps),
                },
            )

        return new_plan

    @staticmethod
    def _parse_steps(text: str) -> list[PlanStep]:
        """Parse numbered steps from LLM output."""
        import re

        steps = []
        for match in re.finditer(r"^\s*(\d+)[.)]\s*(.+)$", text, re.MULTILINE):
            idx = int(match.group(1))
            description = match.group(2).strip()
            if description:
                steps.append(PlanStep(index=idx, description=description))

        return steps
