"""Automated code verifier — AST check, lint, and test pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from src.config import CriticConfig
from src.tools.code import ASTCheckTool, LintTool, TestRunnerTool
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Status of a verification check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single verification check."""

    check_name: str
    status: CheckStatus
    message: str
    details: str = ""


@dataclass
class VerificationResult:
    """Aggregated result of the full verification pipeline."""

    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if all non-skipped checks passed."""
        return all(c.status in (CheckStatus.PASSED, CheckStatus.SKIPPED) for c in self.checks)

    @property
    def summary(self) -> str:
        """Human-readable summary of verification results."""
        lines = []
        for check in self.checks:
            icon = {"passed": "OK", "failed": "FAIL", "skipped": "SKIP"}[check.status.value]
            lines.append(f"  [{icon}] {check.check_name}: {check.message}")
        return "\n".join(lines)

    @property
    def errors(self) -> list[CheckResult]:
        """List of failed checks."""
        return [c for c in self.checks if c.status == CheckStatus.FAILED]


class Verifier:
    """Automated verification pipeline for generated code.

    Runs a sequence of checks on modified files:
    1. AST syntax check (fast, catches parse errors)
    2. Ruff lint (catches style and logic issues)
    3. Pytest (catches runtime errors and regressions)

    Each check can be independently enabled/disabled via config.
    """

    def __init__(
        self,
        config: CriticConfig,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self.config = config
        self.trace = trace_collector
        self._ast_tool = ASTCheckTool()
        self._lint_tool = LintTool()
        self._test_tool = TestRunnerTool()

    def verify(self, files: list[str], test_path: str = "tests/") -> VerificationResult:
        """Run the full verification pipeline on modified files.

        Args:
            files: List of file paths that were modified.
            test_path: Path to run tests against.

        Returns:
            VerificationResult with all check outcomes.
        """
        result = VerificationResult()

        # 1. AST check on Python files
        if self.config.ast_check:
            py_files = [f for f in files if f.endswith(".py")]
            for file_path in py_files:
                check = self._run_ast_check(file_path)
                result.checks.append(check)
                if check.status == CheckStatus.FAILED:
                    self._record_check(check)
                    return result  # Fail fast on syntax errors
        else:
            result.checks.append(
                CheckResult(check_name="ast_check", status=CheckStatus.SKIPPED, message="Disabled")
            )

        # 2. Lint check
        if self.config.run_lint:
            for file_path in [f for f in files if f.endswith(".py")]:
                check = self._run_lint_check(file_path)
                result.checks.append(check)
        else:
            result.checks.append(
                CheckResult(check_name="lint", status=CheckStatus.SKIPPED, message="Disabled")
            )

        # 3. Test execution
        if self.config.run_tests:
            check = self._run_tests(test_path)
            result.checks.append(check)
        else:
            result.checks.append(
                CheckResult(check_name="tests", status=CheckStatus.SKIPPED, message="Disabled")
            )

        self._record_check_summary(result)
        return result

    def _run_ast_check(self, file_path: str) -> CheckResult:
        """Run AST syntax check on a single file."""
        tool_result = self._ast_tool.safe_execute(path=file_path)

        if tool_result.success:
            return CheckResult(
                check_name=f"ast_check:{Path(file_path).name}",
                status=CheckStatus.PASSED,
                message="Syntax OK",
            )
        return CheckResult(
            check_name=f"ast_check:{Path(file_path).name}",
            status=CheckStatus.FAILED,
            message="Syntax error",
            details=tool_result.error or tool_result.output,
        )

    def _run_lint_check(self, file_path: str) -> CheckResult:
        """Run ruff lint check on a single file."""
        tool_result = self._lint_tool.safe_execute(path=file_path)

        if tool_result.success:
            return CheckResult(
                check_name=f"lint:{Path(file_path).name}",
                status=CheckStatus.PASSED,
                message="No lint issues",
            )
        return CheckResult(
            check_name=f"lint:{Path(file_path).name}",
            status=CheckStatus.FAILED,
            message="Lint issues found",
            details=tool_result.output,
        )

    def _run_tests(self, test_path: str) -> CheckResult:
        """Run pytest on the test directory."""
        tool_result = self._test_tool.safe_execute(path=test_path)

        if tool_result.success:
            return CheckResult(
                check_name="tests",
                status=CheckStatus.PASSED,
                message="All tests passed",
                details=tool_result.output,
            )
        return CheckResult(
            check_name="tests",
            status=CheckStatus.FAILED,
            message="Tests failed",
            details=tool_result.output,
        )

    def _record_check(self, check: CheckResult) -> None:
        """Record a check result in the trace."""
        if self.trace:
            self.trace.record(
                EventType.CRITIC_CHECK,
                {
                    "check": check.check_name,
                    "status": check.status.value,
                    "message": check.message,
                },
            )

    def _record_check_summary(self, result: VerificationResult) -> None:
        """Record the full verification summary in the trace."""
        if self.trace:
            self.trace.record(
                EventType.CRITIC_CHECK,
                {
                    "summary": result.summary,
                    "passed": result.passed,
                    "total_checks": len(result.checks),
                    "failed_checks": len(result.errors),
                },
            )
