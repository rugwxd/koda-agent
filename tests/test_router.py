"""Tests for the complexity router."""

import pytest

from src.agent.router import ComplexityRouter, TaskComplexity
from src.config import PlannerConfig


@pytest.fixture
def router():
    return ComplexityRouter(config=PlannerConfig(complexity_threshold=0.6))


class TestComplexityRouter:
    def test_simple_task(self, router):
        decision = router.route("fix typo in README")
        assert decision.complexity == TaskComplexity.SIMPLE
        assert not decision.needs_planning

    def test_complex_task(self, router):
        decision = router.route(
            "Refactor the authentication module to use JWT tokens, "
            "migrate the database schema, and add integration tests "
            "across multiple files"
        )
        assert decision.complexity == TaskComplexity.COMPLEX
        assert decision.needs_planning

    def test_multi_step_indicators(self, router):
        decision = router.route(
            "First read the config, then update the database connection, "
            "after that run the tests, and finally deploy"
        )
        assert decision.complexity == TaskComplexity.COMPLEX

    def test_short_task_simple(self, router):
        decision = router.route("rename variable x to count")
        assert decision.complexity == TaskComplexity.SIMPLE

    def test_file_references(self, router):
        decision = router.route(
            "Update src/auth.py, src/models.py, src/api.py and tests/test_auth.py "
            "to implement the new permission system"
        )
        assert decision.complexity == TaskComplexity.COMPLEX

    def test_confidence(self, router):
        decision = router.route("explain this function")
        assert 0.0 <= decision.confidence <= 1.0
        assert decision.reason != ""
