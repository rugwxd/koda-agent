"""Tests for the Python AST parser."""

import pytest

from src.code.parser import PythonParser


class TestPythonParser:
    def test_parse_file(self, sample_python_file):
        parser = PythonParser()
        result = parser.parse_file(sample_python_file)
        assert result.path == str(sample_python_file)
        assert len(result.errors) == 0

        # Check functions
        funcs = result.functions
        func_names = [f.name for f in funcs]
        assert "greet" in func_names

        # Check classes
        classes = result.classes
        class_names = [c.name for c in classes]
        assert "Calculator" in class_names

        # Check imports
        assert any("os" in imp for imp in result.imports)

    def test_parse_nonexistent(self):
        parser = PythonParser()
        result = parser.parse_file("/nonexistent.py")
        assert len(result.errors) > 0

    def test_extract_methods(self, sample_python_file):
        parser = PythonParser()
        result = parser.parse_file(sample_python_file)
        methods = [s for s in result.symbols if s.kind == "method"]
        method_names = [m.name for m in methods]
        assert "add" in method_names
        assert "subtract" in method_names

    def test_method_parent(self, sample_python_file):
        parser = PythonParser()
        result = parser.parse_file(sample_python_file)
        add_method = result.get_symbol("add")
        assert add_method is not None
        assert add_method.parent == "Calculator"
        assert add_method.qualified_name == "Calculator.add"

    def test_parse_syntax_error(self, tmp_path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n")
        parser = PythonParser()
        result = parser.parse_file(bad_file)
        assert len(result.errors) > 0

    def test_docstring_extraction(self, sample_python_file):
        parser = PythonParser()
        result = parser.parse_file(sample_python_file)
        greet = result.get_symbol("greet")
        assert greet is not None
        assert "greeting" in greet.docstring.lower()
