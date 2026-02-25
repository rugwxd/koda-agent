"""Filesystem tools: read, write, list, and glob."""

from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ReadFileTool(BaseTool):
    """Read the contents of a file."""

    name = "read_file"
    description = "Read the contents of a file at the given path. Returns the file content as text with line numbers."

    class InputModel(BaseModel):
        path: str = Field(description="Absolute or relative file path to read")
        max_lines: int = Field(default=500, description="Maximum number of lines to return")
        offset: int = Field(default=0, description="Line number to start reading from (0-indexed)")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        path = Path(params.path)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")

        if not path.is_file():
            return ToolResult(output="", success=False, error=f"Not a file: {path}")

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            return ToolResult(output="", success=False, error=f"Permission denied: {path}")

        lines = content.splitlines()
        sliced = lines[params.offset : params.offset + params.max_lines]

        numbered = []
        for i, line in enumerate(sliced, start=params.offset + 1):
            numbered.append(f"{i:>5}| {line}")

        output = "\n".join(numbered)
        total = len(lines)
        shown = len(sliced)

        if shown < total:
            output += f"\n\n[Showing lines {params.offset + 1}-{params.offset + shown} of {total}]"

        return ToolResult(output=output)


class WriteFileTool(BaseTool):
    """Write content to a file, creating directories as needed."""

    name = "write_file"
    description = "Write text content to a file. Creates parent directories if they don't exist. Overwrites existing files."

    class InputModel(BaseModel):
        path: str = Field(description="File path to write to")
        content: str = Field(description="Content to write to the file")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        path = Path(params.path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params.content, encoding="utf-8")
            return ToolResult(output=f"Written {len(params.content)} chars to {path}")
        except PermissionError:
            return ToolResult(output="", success=False, error=f"Permission denied: {path}")
        except OSError as e:
            return ToolResult(output="", success=False, error=f"Write failed: {e}")


class ListDirectoryTool(BaseTool):
    """List contents of a directory."""

    name = "list_directory"
    description = "List files and subdirectories in a directory. Shows file sizes and types."

    class InputModel(BaseModel):
        path: str = Field(default=".", description="Directory path to list")
        max_entries: int = Field(default=100, description="Maximum number of entries to return")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        path = Path(params.path)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"Directory not found: {path}")

        if not path.is_dir():
            return ToolResult(output="", success=False, error=f"Not a directory: {path}")

        entries = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for item in items[: params.max_entries]:
                if item.is_dir():
                    entries.append(f"  [dir]  {item.name}/")
                else:
                    size = item.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f}KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f}MB"
                    entries.append(f"  {size_str:>8}  {item.name}")

            total = len(list(path.iterdir()))
            output = f"{path}/  ({total} items)\n" + "\n".join(entries)

            if total > params.max_entries:
                output += f"\n\n[Showing {params.max_entries} of {total} entries]"

            return ToolResult(output=output)
        except PermissionError:
            return ToolResult(output="", success=False, error=f"Permission denied: {path}")


class GlobTool(BaseTool):
    """Find files matching a glob pattern."""

    name = "glob"
    description = "Find files matching a glob pattern (e.g., '**/*.py' for all Python files). Returns matching file paths."

    class InputModel(BaseModel):
        pattern: str = Field(description="Glob pattern to match (e.g., '**/*.py', 'src/**/*.ts')")
        path: str = Field(default=".", description="Root directory to search from")
        max_results: int = Field(default=50, description="Maximum number of results")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        root = Path(params.path)

        if not root.exists():
            return ToolResult(output="", success=False, error=f"Path not found: {root}")

        matches = []
        try:
            for match in root.glob(params.pattern):
                if not any(part.startswith(".") for part in match.parts[len(root.parts) :]):
                    matches.append(str(match))
                    if len(matches) >= params.max_results:
                        break

            if not matches:
                return ToolResult(output=f"No files matching '{params.pattern}' in {root}")

            output = "\n".join(sorted(matches))
            return ToolResult(output=output)
        except OSError as e:
            return ToolResult(output="", success=False, error=f"Glob failed: {e}")
