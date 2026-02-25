"""Tests for the LLM evaluator response parsing."""

from src.critic.evaluator import Evaluator


class TestEvaluatorParsing:
    def test_parse_valid_json(self):
        """Test parsing a well-formed evaluation response."""
        from unittest.mock import MagicMock

        from src.config import CriticConfig

        config = CriticConfig(rubric_enabled=True)
        evaluator = Evaluator(config=config, llm_client=MagicMock())

        text = """{
            "correctness": {"score": 4, "reasoning": "Logic is sound"},
            "style": {"score": 5, "reasoning": "Clean code"},
            "edge_cases": {"score": 3, "reasoning": "Missing null check"},
            "simplicity": {"score": 4, "reasoning": "Well focused"},
            "overall_verdict": "pass",
            "suggestions": ["Add null check for input"]
        }"""

        result = evaluator._parse_evaluation(text)
        assert result.passed
        assert len(result.scores) == 4
        assert result.average_score == 4.0
        assert len(result.suggestions) == 1

    def test_parse_invalid_json(self):
        from unittest.mock import MagicMock

        from src.config import CriticConfig

        config = CriticConfig()
        evaluator = Evaluator(config=config, llm_client=MagicMock())

        result = evaluator._parse_evaluation("not json at all")
        # Should default to pass on parse failure
        assert result.passed

    def test_parse_markdown_wrapped_json(self):
        from unittest.mock import MagicMock

        from src.config import CriticConfig

        config = CriticConfig()
        evaluator = Evaluator(config=config, llm_client=MagicMock())

        text = """```json
{
    "correctness": {"score": 5, "reasoning": "Perfect"},
    "style": {"score": 4, "reasoning": "Good"},
    "edge_cases": {"score": 4, "reasoning": "Handles well"},
    "simplicity": {"score": 5, "reasoning": "Minimal"},
    "overall_verdict": "pass",
    "suggestions": []
}
```"""

        result = evaluator._parse_evaluation(text)
        assert result.passed
        assert result.average_score == 4.5

    def test_score_clamping(self):
        from unittest.mock import MagicMock

        from src.config import CriticConfig

        config = CriticConfig()
        evaluator = Evaluator(config=config, llm_client=MagicMock())

        text = '{"correctness": {"score": 10, "reasoning": "x"}, "overall_verdict": "pass"}'
        result = evaluator._parse_evaluation(text)
        # Score should be clamped to 5
        assert result.scores[0].score == 5

    def test_summary(self):
        from unittest.mock import MagicMock

        from src.config import CriticConfig

        config = CriticConfig()
        evaluator = Evaluator(config=config, llm_client=MagicMock())

        text = """{
            "correctness": {"score": 4, "reasoning": "Good"},
            "overall_verdict": "pass",
            "suggestions": ["Test more"]
        }"""
        result = evaluator._parse_evaluation(text)
        summary = result.summary
        assert "PASS" in summary
        assert "Test more" in summary
