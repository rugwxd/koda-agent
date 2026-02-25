"""Tests for filesystem, search, and shell tools."""

from pathlib import Path

from src.config import ToolsConfig
from src.tools.filesystem import GlobTool, ListDirectoryTool, ReadFileTool, WriteFileTool
from src.tools.search import GrepTool
from src.tools.shell import ShellTool


class TestReadFileTool:
    def test_read_existing_file(self, sample_python_file):
        tool = ReadFileTool()
        result = tool.execute(path=str(sample_python_file))
        assert result.success
        assert "def greet" in result.output
        assert "class Calculator" in result.output

    def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = tool.execute(path="/nonexistent/file.py")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_read_with_offset(self, sample_python_file):
        tool = ReadFileTool()
        result = tool.execute(path=str(sample_python_file), offset=5, max_lines=3)
        assert result.success
        lines = result.output.strip().split("\n")
        assert len([ln for ln in lines if ln.strip() and not ln.startswith("[")]) <= 3


class TestWriteFileTool:
    def test_write_new_file(self, tmp_path):
        tool = WriteFileTool()
        file_path = str(tmp_path / "new_file.txt")
        result = tool.execute(path=file_path, content="hello world")
        assert result.success
        assert Path(file_path).read_text() == "hello world"

    def test_write_creates_directories(self, tmp_path):
        tool = WriteFileTool()
        file_path = str(tmp_path / "a" / "b" / "c.txt")
        result = tool.execute(path=file_path, content="nested")
        assert result.success
        assert Path(file_path).exists()


class TestListDirectoryTool:
    def test_list_directory(self, tmp_path):
        (tmp_path / "file1.py").write_text("x")
        (tmp_path / "file2.txt").write_text("y")
        (tmp_path / "subdir").mkdir()

        tool = ListDirectoryTool()
        result = tool.execute(path=str(tmp_path))
        assert result.success
        assert "subdir/" in result.output
        assert "file1.py" in result.output

    def test_list_nonexistent(self):
        tool = ListDirectoryTool()
        result = tool.execute(path="/nonexistent/dir")
        assert not result.success


class TestGlobTool:
    def test_glob_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")

        tool = GlobTool()
        result = tool.execute(pattern="*.py", path=str(tmp_path))
        assert result.success
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output


class TestGrepTool:
    def test_grep_pattern(self, sample_python_file):
        tool = GrepTool()
        result = tool.execute(pattern="def \\w+", path=str(sample_python_file))
        assert result.success
        assert "greet" in result.output

    def test_grep_no_match(self, sample_python_file):
        tool = GrepTool()
        result = tool.execute(pattern="nonexistent_function", path=str(sample_python_file))
        assert result.success  # No error, just no matches
        assert "No matches" in result.output

    def test_grep_case_insensitive(self, sample_python_file):
        tool = GrepTool()
        result = tool.execute(
            pattern="CALCULATOR", path=str(sample_python_file), case_insensitive=True
        )
        assert result.success
        assert "Calculator" in result.output


class TestShellTool:
    def test_allowed_command(self):
        config = ToolsConfig(sandbox_enabled=True, allowed_commands=["echo"])
        tool = ShellTool(config=config)
        result = tool.execute(command="echo hello")
        assert result.success
        assert "hello" in result.output

    def test_blocked_command(self):
        config = ToolsConfig(sandbox_enabled=True, allowed_commands=["echo"])
        tool = ShellTool(config=config)
        result = tool.execute(command="rm -rf /")
        assert not result.success
        assert "not in allowed list" in result.error

    def test_sandbox_disabled(self):
        config = ToolsConfig(sandbox_enabled=False)
        tool = ShellTool(config=config)
        result = tool.execute(command="echo 'sandbox off'")
        assert result.success
