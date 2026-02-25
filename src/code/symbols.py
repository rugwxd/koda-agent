"""Symbol search across a parsed codebase."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.code.parser import ParsedFile, PythonParser, Symbol

logger = logging.getLogger(__name__)


@dataclass
class SymbolMatch:
    """A symbol search result with context."""

    symbol: Symbol
    file_path: str
    relevance: float = 1.0

    @property
    def display(self) -> str:
        """Human-readable display string."""
        kind = self.symbol.kind
        name = self.symbol.qualified_name
        return f"{self.file_path}:{self.symbol.line} [{kind}] {name}"


class SymbolIndex:
    """Index of all symbols in a codebase for fast lookup.

    Parses all Python files and builds an in-memory index supporting
    name search, fuzzy matching, and filtering by kind.
    """

    def __init__(self, parser: PythonParser | None = None) -> None:
        self.parser = parser or PythonParser()
        self._files: dict[str, ParsedFile] = {}
        self._symbols: list[SymbolMatch] = []

    def index_directory(self, path: str | Path) -> int:
        """Index all Python files in a directory.

        Args:
            path: Root directory to index.

        Returns:
            Number of symbols indexed.
        """
        root = Path(path)
        skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv"}

        count = 0
        for py_file in root.rglob("*.py"):
            parts = py_file.relative_to(root).parts
            if any(part in skip_dirs or part.startswith(".") for part in parts):
                continue

            parsed = self.parser.parse_file(py_file)
            rel_path = str(py_file.relative_to(root))
            self._files[rel_path] = parsed

            for sym in parsed.symbols:
                self._symbols.append(SymbolMatch(symbol=sym, file_path=rel_path))
                count += 1

        logger.info("Indexed %d symbols from %d files", count, len(self._files))
        return count

    def search(
        self,
        query: str,
        kind: str | None = None,
        max_results: int = 20,
    ) -> list[SymbolMatch]:
        """Search for symbols matching a query.

        Args:
            query: Name or partial name to search for.
            kind: Filter by symbol kind ("function", "class", "method").
            max_results: Maximum number of results to return.

        Returns:
            List of matching SymbolMatch results, ranked by relevance.
        """
        query_lower = query.lower()
        matches = []

        for sm in self._symbols:
            if kind and sm.symbol.kind != kind:
                continue

            name_lower = sm.symbol.name.lower()
            qualified_lower = sm.symbol.qualified_name.lower()

            # Exact match
            if name_lower == query_lower or qualified_lower == query_lower:
                matches.append(SymbolMatch(
                    symbol=sm.symbol, file_path=sm.file_path, relevance=1.0
                ))
            # Prefix match
            elif name_lower.startswith(query_lower):
                matches.append(SymbolMatch(
                    symbol=sm.symbol, file_path=sm.file_path, relevance=0.8
                ))
            # Substring match
            elif query_lower in name_lower or query_lower in qualified_lower:
                matches.append(SymbolMatch(
                    symbol=sm.symbol, file_path=sm.file_path, relevance=0.5
                ))

        matches.sort(key=lambda m: (-m.relevance, m.symbol.name))
        return matches[:max_results]

    def get_file_symbols(self, path: str) -> list[Symbol]:
        """Get all symbols from a specific file."""
        parsed = self._files.get(path)
        return parsed.symbols if parsed else []

    @property
    def total_symbols(self) -> int:
        return len(self._symbols)

    @property
    def total_files(self) -> int:
        return len(self._files)
