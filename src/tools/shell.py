"""Sandboxed shell execution tool."""

from __future__ import annotations

import logging
import subprocess

from pydantic import BaseModel, Field

from src.config import ToolsConfig
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ShellTool(BaseTool):
    """Execute shell commands in a sandboxed environment."""

    name = "shell"
    description = "Execute a shell command and return its stdout/stderr. Commands are validated against an allowlist for safety."

    class InputModel(BaseModel):
        command: str = Field(description="Shell command to execute")
        working_dir: str = Field(default=".", description="Working directory for the command")
        timeout: int | None = Field(
            default=None, description="Timeout in seconds (uses default if not set)"
        )

    def __init__(self, config: ToolsConfig) -> None:
        self._config = config

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)

        # Validate command against allowlist
        if self._config.sandbox_enabled:
            base_cmd = params.command.strip().split()[0] if params.command.strip() else ""
            if base_cmd not in self._config.allowed_commands:
                return ToolResult(
                    output="",
                    success=False,
                    error=f"Command '{base_cmd}' not in allowed list: {self._config.allowed_commands}",
                )

        timeout = params.timeout or self._config.shell_timeout

        try:
            result = subprocess.run(
                params.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=params.working_dir,
            )

            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")

            output = "\n".join(output_parts) if output_parts else "(no output)"

            if result.returncode != 0:
                return ToolResult(
                    output=output,
                    success=False,
                    error=f"Exit code {result.returncode}",
                )

            return ToolResult(output=output)

        except subprocess.TimeoutExpired:
            return ToolResult(
                output="",
                success=False,
                error=f"Command timed out after {timeout}s",
            )
        except OSError as e:
            return ToolResult(output="", success=False, error=f"Execution failed: {e}")
