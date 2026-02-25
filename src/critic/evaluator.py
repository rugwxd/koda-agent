"""LLM-based code evaluator with structured rubric scoring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.config import CriticConfig
from src.llm.client import LLMClient
from src.llm.models import Conversation

logger = logging.getLogger(__name__)

EVALUATOR_PROMPT = """You are a code reviewer evaluating generated code changes. Score each dimension 1-5.

Code being evaluated:
```
{code}
```

Task that was requested:
{task}

Evaluate on these dimensions:
1. **Correctness** — Does the code do what was requested? Are there logic errors?
2. **Style** — Does it follow Python conventions (PEP 8, naming, structure)?
3. **Edge Cases** — Does it handle errors, empty inputs, and boundary conditions?
4. **Simplicity** — Is the code minimal and focused, or over-engineered?

Respond with ONLY valid JSON:
{{
    "correctness": {{"score": 1-5, "reasoning": "..."}},
    "style": {{"score": 1-5, "reasoning": "..."}},
    "edge_cases": {{"score": 1-5, "reasoning": "..."}},
    "simplicity": {{"score": 1-5, "reasoning": "..."}},
    "overall_verdict": "pass" or "fail",
    "suggestions": ["suggestion 1", "suggestion 2"]
}}
"""


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    name: str
    score: int
    reasoning: str


@dataclass
class EvaluationResult:
    """Full evaluation result from the LLM critic."""

    scores: list[DimensionScore] = field(default_factory=list)
    verdict: str = "fail"
    suggestions: list[str] = field(default_factory=list)
    raw_response: str = ""

    @property
    def average_score(self) -> float:
        """Average score across all dimensions."""
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    @property
    def summary(self) -> str:
        """Human-readable evaluation summary."""
        lines = [f"Verdict: {self.verdict.upper()} (avg: {self.average_score:.1f}/5)"]
        for score in self.scores:
            lines.append(f"  {score.name}: {score.score}/5 — {score.reasoning}")
        if self.suggestions:
            lines.append("Suggestions:")
            for s in self.suggestions:
                lines.append(f"  - {s}")
        return "\n".join(lines)


class Evaluator:
    """LLM-based code evaluator using structured rubric scoring.

    Sends the generated code and task description to the LLM for evaluation
    on correctness, style, edge cases, and simplicity. Returns a structured
    pass/fail verdict with per-dimension scores.
    """

    def __init__(
        self,
        config: CriticConfig,
        llm_client: LLMClient,
    ) -> None:
        self.config = config
        self.llm = llm_client

    def evaluate(self, code: str, task: str) -> EvaluationResult:
        """Evaluate code changes against the task requirements.

        Args:
            code: The code that was generated or modified.
            task: The original task description.

        Returns:
            EvaluationResult with scores and verdict.
        """
        if not self.config.rubric_enabled:
            return EvaluationResult(verdict="pass", suggestions=[])

        prompt = EVALUATOR_PROMPT.format(code=code[:3000], task=task)
        conversation = Conversation(system_prompt="You are a precise code reviewer. Respond only with JSON.")
        conversation.add_user_message(prompt)

        response = self.llm.chat(
            conversation,
            model_override="claude-haiku-4-5-20251001",  # Use cheaper model for evaluation
            max_tokens_override=512,
        )

        return self._parse_evaluation(response.text)

    def _parse_evaluation(self, text: str) -> EvaluationResult:
        """Parse the LLM's JSON evaluation response."""
        result = EvaluationResult(raw_response=text)

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = text.strip()
            if "```" in json_text:
                start = json_text.index("{")
                end = json_text.rindex("}") + 1
                json_text = json_text[start:end]

            data = json.loads(json_text)

            for dimension in ["correctness", "style", "edge_cases", "simplicity"]:
                if dimension in data:
                    dim_data = data[dimension]
                    result.scores.append(DimensionScore(
                        name=dimension,
                        score=max(1, min(5, int(dim_data.get("score", 3)))),
                        reasoning=dim_data.get("reasoning", ""),
                    ))

            result.verdict = data.get("overall_verdict", "fail")
            result.suggestions = data.get("suggestions", [])

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("Failed to parse evaluation response: %s", e)
            # Default to pass if parsing fails (avoid blocking on eval errors)
            result.verdict = "pass"
            result.suggestions = ["Evaluation parsing failed — manual review recommended"]

        return result
