"""Search tools: grep and symbol search."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# File extensions to search by default
SEARCHABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    ".yaml", ".yml", ".toml", ".json", ".md", ".txt", ".cfg",
    ".sh", ".bash", ".zsh", ".sql", ".html", ".css", ".scss",
}


class GrepTool(BaseTool):
    """Search file contents for a regex pattern."""

    name = "grep"
    description = "Search file contents for a regular expression pattern. Returns matching lines with file paths and line numbers."

    class InputModel(BaseModel):
        pattern: str = Field(description="Regular expression pattern to search for")
        path: str = Field(default=".", description="Directory or file to search in")
        file_pattern: str = Field(default="", description="Glob to filter files (e.g., '*.py')")
        max_results: int = Field(default=50, description="Maximum number of matching lines")
        case_insensitive: bool = Field(default=False, description="Case-insensitive search")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        root = Path(params.path)

        if not root.exists():
            return ToolResult(output="", success=False, error=f"Path not found: {root}")

        flags = re.IGNORECASE if params.case_insensitive else 0
        try:
            regex = re.compile(params.pattern, flags)
        except re.error as e:
            return ToolResult(output="", success=False, error=f"Invalid regex: {e}")

        matches = []

        if root.is_file():
            files = [root]
        else:
            files = self._collect_files(root, params.file_pattern)

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(root) if root.is_dir() else file_path
                        matches.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                        if len(matches) >= params.max_results:
                            break
            except (PermissionError, OSError):
                continue

            if len(matches) >= params.max_results:
                break

        if not matches:
            return ToolResult(output=f"No matches for '{params.pattern}' in {root}")

        output = "\n".join(matches)
        return ToolResult(output=output)

    @staticmethod
    def _collect_files(root: Path, file_pattern: str) -> list[Path]:
        """Collect searchable files from a directory."""
        if file_pattern:
            return sorted(root.rglob(file_pattern))

        files = []
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in SEARCHABLE_EXTENSIONS:
                # Skip hidden directories
                if not any(part.startswith(".") for part in path.relative_to(root).parts):
                    files.append(path)
        return sorted(files)
