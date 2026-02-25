"""Code tools: AST validation, lint, and test execution."""

from __future__ import annotations

import ast
import logging
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ASTCheckTool(BaseTool):
    """Validate Python syntax using AST parsing."""

    name = "ast_check"
    description = (
        "Check if a Python file has valid syntax by parsing its AST. Returns syntax errors if any."
    )

    class InputModel(BaseModel):
        path: str = Field(description="Path to the Python file to check")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        path = Path(params.path)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")

        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
            return ToolResult(output=f"Syntax OK: {path}")
        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.rstrip()}"
            return ToolResult(output=error_msg, success=False, error=error_msg)


class LintTool(BaseTool):
    """Run ruff linter on Python files."""

    name = "lint"
    description = "Run ruff linter on a file or directory to check for code quality issues."

    class InputModel(BaseModel):
        path: str = Field(description="File or directory to lint")
        fix: bool = Field(default=False, description="Auto-fix issues where possible")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)

        args = ["ruff", "check", params.path]
        if params.fix:
            args.append("--fix")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout.strip()
            if result.stderr:
                output += f"\n{result.stderr.strip()}" if output else result.stderr.strip()

            if result.returncode == 0:
                return ToolResult(output=output or "All checks passed")
            else:
                return ToolResult(output=output, success=False, error="Lint issues found")

        except FileNotFoundError:
            return ToolResult(output="", success=False, error="ruff not found on PATH")
        except subprocess.TimeoutExpired:
            return ToolResult(output="", success=False, error="Lint timed out")


class TestRunnerTool(BaseTool):
    """Run pytest on specified files or directories."""

    name = "run_tests"
    description = "Run pytest on a file or directory and return the results."

    class InputModel(BaseModel):
        path: str = Field(default="tests/", description="File or directory to test")
        verbose: bool = Field(default=True, description="Show verbose output")
        specific_test: str = Field(
            default="", description="Specific test name to run (e.g., test_foo)"
        )

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)

        args = ["python", "-m", "pytest", params.path]
        if params.verbose:
            args.append("-v")
        args.extend(["--tb", "short"])

        if params.specific_test:
            args.extend(["-k", params.specific_test])

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=120,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}" if output else result.stderr

            return ToolResult(
                output=output.strip(),
                success=result.returncode == 0,
                error="Tests failed" if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(output="", success=False, error="Tests timed out after 120s")
