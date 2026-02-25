"""Git tools: status, diff, log, commit."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


def _run_git(args: list[str], cwd: str = ".") -> tuple[str, int]:
    """Run a git command and return (output, return_code)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n{result.stderr}" if output else result.stderr
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "Git command timed out", 1
    except FileNotFoundError:
        return "git not found on PATH", 1


class GitStatusTool(BaseTool):
    """Show the working tree status."""

    name = "git_status"
    description = "Show the git working tree status including staged, unstaged, and untracked files."

    class InputModel(BaseModel):
        repo_path: str = Field(default=".", description="Path to the git repository")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        output, code = _run_git(["status", "--short"], cwd=params.repo_path)
        if code != 0:
            return ToolResult(output="", success=False, error=output)
        return ToolResult(output=output or "(clean working tree)")


class GitDiffTool(BaseTool):
    """Show changes in the working tree or between commits."""

    name = "git_diff"
    description = "Show git diff for staged or unstaged changes, or between two refs."

    class InputModel(BaseModel):
        repo_path: str = Field(default=".", description="Path to the git repository")
        staged: bool = Field(default=False, description="Show staged changes (--cached)")
        ref: str = Field(default="", description="Git ref to diff against (e.g., HEAD~1, main)")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)

        args = ["diff"]
        if params.staged:
            args.append("--cached")
        if params.ref:
            args.append(params.ref)

        output, code = _run_git(args, cwd=params.repo_path)
        if code != 0:
            return ToolResult(output="", success=False, error=output)
        return ToolResult(output=output or "(no changes)")


class GitLogTool(BaseTool):
    """Show recent commit history."""

    name = "git_log"
    description = "Show recent git commit log with short hashes and messages."

    class InputModel(BaseModel):
        repo_path: str = Field(default=".", description="Path to the git repository")
        count: int = Field(default=10, description="Number of commits to show")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        output, code = _run_git(
            ["log", f"-{params.count}", "--oneline", "--no-decorate"],
            cwd=params.repo_path,
        )
        if code != 0:
            return ToolResult(output="", success=False, error=output)
        return ToolResult(output=output or "(no commits)")


class GitCommitTool(BaseTool):
    """Stage files and create a commit."""

    name = "git_commit"
    description = "Stage specified files and create a git commit with the given message."

    class InputModel(BaseModel):
        repo_path: str = Field(default=".", description="Path to the git repository")
        files: list[str] = Field(description="List of file paths to stage")
        message: str = Field(description="Commit message")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)

        # Stage files
        for file_path in params.files:
            output, code = _run_git(["add", file_path], cwd=params.repo_path)
            if code != 0:
                return ToolResult(
                    output="", success=False, error=f"Failed to stage {file_path}: {output}"
                )

        # Commit
        output, code = _run_git(["commit", "-m", params.message], cwd=params.repo_path)
        if code != 0:
            return ToolResult(output="", success=False, error=output)

        return ToolResult(output=output)
