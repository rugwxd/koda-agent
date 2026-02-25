"""Tree-sitter based AST parser for Python code analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Symbol:
    """A code symbol extracted from AST parsing."""

    name: str
    kind: str  # "function", "class", "method", "import"
    line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    parent: str | None = None
    children: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        """Full qualified name including parent (e.g., 'MyClass.my_method')."""
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name


@dataclass
class ParsedFile:
    """Result of parsing a single Python file."""

    path: str
    symbols: list[Symbol]
    imports: list[str]
    errors: list[str] = field(default_factory=list)

    @property
    def classes(self) -> list[Symbol]:
        return [s for s in self.symbols if s.kind == "class"]

    @property
    def functions(self) -> list[Symbol]:
        return [s for s in self.symbols if s.kind in ("function", "method")]

    def get_symbol(self, name: str) -> Symbol | None:
        """Look up a symbol by name or qualified name."""
        for sym in self.symbols:
            if sym.name == name or sym.qualified_name == name:
                return sym
        return None


class PythonParser:
    """Parses Python files using tree-sitter for structural analysis.

    Extracts functions, classes, methods, imports, signatures, and docstrings.
    Falls back to Python's built-in ast module if tree-sitter is unavailable.
    """

    def __init__(self) -> None:
        self._ts_available = False
        self._parser = None
        self._language = None
        self._init_tree_sitter()

    def _init_tree_sitter(self) -> None:
        """Initialize tree-sitter parser if available."""
        try:
            import tree_sitter_python as tspython
            from tree_sitter import Language, Parser

            self._language = Language(tspython.language())
            self._parser = Parser(self._language)
            self._ts_available = True
            logger.debug("Tree-sitter initialized for Python")
        except ImportError:
            logger.info("Tree-sitter not available, falling back to ast module")

    def parse_file(self, path: str | Path) -> ParsedFile:
        """Parse a Python file and extract symbols.

        Args:
            path: Path to a Python file.

        Returns:
            ParsedFile with extracted symbols and imports.
        """
        path = Path(path)
        if not path.exists():
            return ParsedFile(path=str(path), symbols=[], imports=[], errors=["File not found"])

        try:
            source = path.read_text(encoding="utf-8")
        except (PermissionError, OSError) as e:
            return ParsedFile(path=str(path), symbols=[], imports=[], errors=[str(e)])

        if self._ts_available:
            return self._parse_with_tree_sitter(str(path), source)
        return self._parse_with_ast(str(path), source)

    def _parse_with_tree_sitter(self, path: str, source: str) -> ParsedFile:
        """Parse using tree-sitter for more robust handling."""
        tree = self._parser.parse(source.encode("utf-8"))
        root = tree.root_node

        symbols: list[Symbol] = []
        imports: list[str] = []
        errors: list[str] = []

        for node in self._walk(root):
            if node.type == "function_definition":
                sym = self._extract_function(node, source)
                symbols.append(sym)

            elif node.type == "class_definition":
                class_sym = self._extract_class(node, source)
                symbols.append(class_sym)

                # Extract methods
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "function_definition":
                            method = self._extract_function(child, source)
                            method.kind = "method"
                            method.parent = class_sym.name
                            class_sym.children.append(method.name)
                            symbols.append(method)

            elif node.type in ("import_statement", "import_from_statement"):
                imports.append(source[node.start_byte : node.end_byte])

        if root.has_error:
            errors.append("File contains syntax errors")

        return ParsedFile(path=path, symbols=symbols, imports=imports, errors=errors)

    def _extract_function(self, node: Any, source: str) -> Symbol:
        """Extract a function symbol from a tree-sitter node."""
        name_node = node.child_by_field_name("name")
        name = source[name_node.start_byte : name_node.end_byte] if name_node else "<unknown>"

        params_node = node.child_by_field_name("parameters")
        params = source[params_node.start_byte : params_node.end_byte] if params_node else "()"

        return_node = node.child_by_field_name("return_type")
        return_type = ""
        if return_node:
            return_type = f" -> {source[return_node.start_byte : return_node.end_byte]}"

        signature = f"def {name}{params}{return_type}"
        docstring = self._extract_docstring(node, source)

        return Symbol(
            name=name,
            kind="function",
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            docstring=docstring,
        )

    def _extract_class(self, node: Any, source: str) -> Symbol:
        """Extract a class symbol from a tree-sitter node."""
        name_node = node.child_by_field_name("name")
        name = source[name_node.start_byte : name_node.end_byte] if name_node else "<unknown>"

        superclasses = node.child_by_field_name("superclasses")
        bases = ""
        if superclasses:
            bases = source[superclasses.start_byte : superclasses.end_byte]

        signature = f"class {name}{bases}"
        docstring = self._extract_docstring(node, source)

        return Symbol(
            name=name,
            kind="class",
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
            docstring=docstring,
        )

    @staticmethod
    def _extract_docstring(node: Any, source: str) -> str:
        """Extract docstring from the first expression statement in a body."""
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return ""

        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                raw = source[expr.start_byte : expr.end_byte]
                # Strip triple quotes
                for prefix in ('"""', "'''", 'r"""', "r'''"):
                    if raw.startswith(prefix):
                        return raw[len(prefix) : -3].strip()
                return raw.strip("\"'").strip()
        return ""

    @staticmethod
    def _walk(node: Any):
        """Walk tree-sitter nodes depth-first, yielding only top-level definitions."""
        for child in node.children:
            yield child

    def _parse_with_ast(self, path: str, source: str) -> ParsedFile:
        """Fallback parser using Python's built-in ast module."""
        import ast as ast_mod

        symbols: list[Symbol] = []
        imports: list[str] = []
        errors: list[str] = []

        try:
            tree = ast_mod.parse(source, filename=path)
        except SyntaxError as e:
            return ParsedFile(path=path, symbols=[], imports=[], errors=[f"Syntax error: {e}"])

        for node in ast_mod.iter_child_nodes(tree):
            if isinstance(node, ast_mod.FunctionDef | ast_mod.AsyncFunctionDef):
                sig = f"def {node.name}({ast_mod.dump(node.args)})"
                doc = ast_mod.get_docstring(node) or ""
                symbols.append(
                    Symbol(
                        name=node.name,
                        kind="function",
                        line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        signature=sig,
                        docstring=doc,
                    )
                )

            elif isinstance(node, ast_mod.ClassDef):
                bases = ", ".join(ast_mod.dump(b) for b in node.bases)
                sig = f"class {node.name}({bases})" if bases else f"class {node.name}"
                doc = ast_mod.get_docstring(node) or ""
                class_sym = Symbol(
                    name=node.name,
                    kind="class",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    docstring=doc,
                )

                for child in ast_mod.iter_child_nodes(node):
                    if isinstance(child, ast_mod.FunctionDef | ast_mod.AsyncFunctionDef):
                        method_doc = ast_mod.get_docstring(child) or ""
                        method = Symbol(
                            name=child.name,
                            kind="method",
                            line=child.lineno,
                            end_line=child.end_lineno or child.lineno,
                            signature=f"def {child.name}(...)",
                            docstring=method_doc,
                            parent=node.name,
                        )
                        class_sym.children.append(child.name)
                        symbols.append(method)

                symbols.append(class_sym)

            elif isinstance(node, ast_mod.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")

            elif isinstance(node, ast_mod.ImportFrom):
                names = ", ".join(a.name for a in node.names)
                imports.append(f"from {node.module} import {names}")

        return ParsedFile(path=path, symbols=symbols, imports=imports, errors=errors)
