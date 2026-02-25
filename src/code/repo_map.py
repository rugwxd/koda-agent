"""Repository map generator — Aider-style overview of codebase structure.

Builds a concise map of a repository showing file structure with function/class
signatures, ranked by importance using a reference graph.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from src.code.parser import ParsedFile, PythonParser

logger = logging.getLogger(__name__)


@dataclass
class FileEntry:
    """A file's contribution to the repo map."""

    path: str
    symbols: list[str]
    import_count: int = 0
    reference_score: float = 0.0


@dataclass
class RepoMap:
    """A structured overview of repository contents."""

    entries: list[FileEntry] = field(default_factory=list)
    total_files: int = 0
    total_symbols: int = 0

    def render(self, max_tokens: int = 2000) -> str:
        """Render the repo map as a compact text representation.

        Args:
            max_tokens: Approximate token budget (4 chars per token).

        Returns:
            Formatted repo map string.
        """
        max_chars = max_tokens * 4
        lines = ["Repository Map", "=" * 40]
        current_chars = sum(len(line) for line in lines)

        # Sort by reference score (most important files first)
        sorted_entries = sorted(self.entries, key=lambda e: e.reference_score, reverse=True)

        for entry in sorted_entries:
            header = f"\n{entry.path}"
            if current_chars + len(header) > max_chars:
                lines.append(f"\n... and {len(sorted_entries) - len(lines) + 2} more files")
                break

            lines.append(header)
            current_chars += len(header)

            for sig in entry.symbols:
                line = f"  {sig}"
                if current_chars + len(line) > max_chars:
                    lines.append("  ...")
                    break
                lines.append(line)
                current_chars += len(line)

        lines.append(f"\n({self.total_files} files, {self.total_symbols} symbols)")
        return "\n".join(lines)


class RepoMapBuilder:
    """Builds a repository map by parsing all Python files and ranking by importance.

    Uses a simple reference graph: files that are imported more frequently
    get higher scores, making them appear first in the map.
    """

    def __init__(self, parser: PythonParser | None = None) -> None:
        self.parser = parser or PythonParser()

    def build(self, repo_path: str | Path, max_files: int = 100) -> RepoMap:
        """Build a repo map from the given repository path.

        Args:
            repo_path: Root directory of the repository.
            max_files: Maximum number of files to include.

        Returns:
            RepoMap with ranked file entries.
        """
        root = Path(repo_path)
        py_files = self._collect_python_files(root, max_files)

        # Parse all files
        parsed: list[ParsedFile] = []
        for f in py_files:
            result = self.parser.parse_file(f)
            parsed.append(result)

        # Build reference graph
        reference_counts = self._build_reference_graph(parsed, root)

        # Create entries
        entries = []
        total_symbols = 0
        for pf in parsed:
            rel_path = str(Path(pf.path).relative_to(root))
            sigs = []
            for sym in pf.symbols:
                if sym.kind in ("function", "class"):
                    sigs.append(sym.signature)
                elif sym.kind == "method" and sym.parent:
                    sigs.append(f"  {sym.signature}")

            total_symbols += len(pf.symbols)
            entries.append(
                FileEntry(
                    path=rel_path,
                    symbols=sigs,
                    import_count=len(pf.imports),
                    reference_score=reference_counts.get(rel_path, 0.0),
                )
            )

        repo_map = RepoMap(
            entries=entries,
            total_files=len(entries),
            total_symbols=total_symbols,
        )

        logger.info("Built repo map: %d files, %d symbols", len(entries), total_symbols)
        return repo_map

    @staticmethod
    def _collect_python_files(root: Path, max_files: int) -> list[Path]:
        """Collect Python files, excluding hidden dirs and common non-source dirs."""
        skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv", ".tox", "dist"}
        files = []
        for path in root.rglob("*.py"):
            parts = path.relative_to(root).parts
            if any(part in skip_dirs or part.startswith(".") for part in parts):
                continue
            files.append(path)
            if len(files) >= max_files:
                break
        return sorted(files)

    @staticmethod
    def _build_reference_graph(parsed: list[ParsedFile], root: Path) -> dict[str, float]:
        """Count how often each module is imported by other files."""
        counts: dict[str, float] = defaultdict(float)

        # Map module names to file paths
        module_to_path: dict[str, str] = {}
        for pf in parsed:
            rel = str(Path(pf.path).relative_to(root))
            module = rel.replace("/", ".").removesuffix(".py")
            module_to_path[module] = rel
            # Also map the last component
            parts = module.split(".")
            if parts:
                module_to_path[parts[-1]] = rel

        for pf in parsed:
            for imp in pf.imports:
                # Extract module name from import statement
                parts = imp.split()
                if "from" in parts:
                    idx = parts.index("from") + 1
                    if idx < len(parts):
                        module = parts[idx]
                else:
                    idx = parts.index("import") + 1 if "import" in parts else -1
                    module = parts[idx] if idx >= 0 and idx < len(parts) else ""

                # Check all possible module path matches
                for mod_name, file_path in module_to_path.items():
                    if module.endswith(mod_name) or mod_name.endswith(module):
                        counts[file_path] += 1.0

        return dict(counts)
