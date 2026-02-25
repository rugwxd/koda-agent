"""Tests for the planner step parsing."""

import pytest

from src.agent.planner import ExecutionPlan, Planner, PlanStep, StepStatus


class TestPlanStep:
    def test_default_status(self):
        step = PlanStep(index=1, description="Do something")
        assert step.status == StepStatus.PENDING

    def test_status_transitions(self):
        step = PlanStep(index=1, description="Test step")
        step.status = StepStatus.IN_PROGRESS
        assert step.status == StepStatus.IN_PROGRESS
        step.status = StepStatus.COMPLETED
        step.result = "Done"
        assert step.status == StepStatus.COMPLETED


class TestExecutionPlan:
    def test_current_step(self):
        plan = ExecutionPlan(
            task="test task",
            steps=[
                PlanStep(index=1, description="Step 1", status=StepStatus.COMPLETED),
                PlanStep(index=2, description="Step 2", status=StepStatus.PENDING),
                PlanStep(index=3, description="Step 3", status=StepStatus.PENDING),
            ],
        )
        assert plan.current_step.index == 2

    def test_is_complete(self):
        plan = ExecutionPlan(
            task="test",
            steps=[
                PlanStep(index=1, description="S1", status=StepStatus.COMPLETED),
                PlanStep(index=2, description="S2", status=StepStatus.COMPLETED),
            ],
        )
        assert plan.is_complete

    def test_not_complete(self):
        plan = ExecutionPlan(
            task="test",
            steps=[
                PlanStep(index=1, description="S1", status=StepStatus.COMPLETED),
                PlanStep(index=2, description="S2", status=StepStatus.PENDING),
            ],
        )
        assert not plan.is_complete

    def test_progress_summary(self):
        plan = ExecutionPlan(
            task="test",
            steps=[
                PlanStep(index=1, description="S1", status=StepStatus.COMPLETED),
                PlanStep(index=2, description="S2", status=StepStatus.FAILED),
                PlanStep(index=3, description="S3", status=StepStatus.PENDING),
            ],
        )
        summary = plan.progress_summary
        assert "1/3" in summary
        assert "1 failed" in summary

    def test_to_context_string(self):
        plan = ExecutionPlan(
            task="build feature",
            steps=[
                PlanStep(index=1, description="Read code", status=StepStatus.COMPLETED, result="OK"),
                PlanStep(index=2, description="Write tests", status=StepStatus.PENDING),
            ],
        )
        ctx = plan.to_context_string()
        assert "[x]" in ctx
        assert "[ ]" in ctx
        assert "Read code" in ctx


class TestPlannerParsing:
    def test_parse_numbered_steps(self):
        text = """Here's the plan:
1. Read the configuration file
2. Update the database connection settings
3. Run the test suite
4. Commit changes
"""
        steps = Planner._parse_steps(text)
        assert len(steps) == 4
        assert steps[0].description == "Read the configuration file"
        assert steps[3].description == "Commit changes"

    def test_parse_with_dots(self):
        text = "1) First step\n2) Second step\n3) Third step"
        steps = Planner._parse_steps(text)
        assert len(steps) == 3

    def test_parse_empty(self):
        steps = Planner._parse_steps("No steps here")
        assert len(steps) == 0
