"""Tests for the tool registry."""

import pytest
from pydantic import BaseModel, Field

from src.tools.base import BaseTool, ToolResult
from src.tools.registry import ToolRegistry


class DummyTool(BaseTool):
    """A test tool."""

    name = "dummy"
    description = "A dummy tool for testing"

    class InputModel(BaseModel):
        message: str = Field(description="Input message")
        count: int = Field(default=1, description="Repeat count")

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        return ToolResult(output=params.message * params.count)


class FailingTool(BaseTool):
    """A tool that always fails."""

    name = "failing"
    description = "Always fails"

    class InputModel(BaseModel):
        trigger: str = Field(description="Failure trigger")

    def execute(self, **kwargs) -> ToolResult:
        raise RuntimeError("Intentional failure")


class TestToolRegistry:
    def test_register_and_lookup(self):
        registry = ToolRegistry()
        tool = DummyTool()
        registry.register(tool)
        assert registry.get("dummy") is tool
        assert "dummy" in registry
        assert len(registry) == 1

    def test_duplicate_registration(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(DummyTool())

    def test_execute(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        result = registry.execute("dummy", {"message": "hi", "count": 3})
        assert result.success
        assert result.output == "hihihi"

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.execute("nonexistent", {})
        assert not result.success
        assert "Unknown tool" in result.error

    def test_execute_failing_tool(self):
        registry = ToolRegistry()
        registry.register(FailingTool())
        result = registry.execute("failing", {"trigger": "boom"})
        assert not result.success
        assert "Intentional failure" in result.error

    def test_get_definitions(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "dummy"
        assert "message" in str(defs[0].input_schema)

    def test_tool_names(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        registry.register(FailingTool())
        assert sorted(registry.tool_names) == ["dummy", "failing"]


class TestAutoSchema:
    def test_schema_generation(self):
        definition = DummyTool.to_tool_definition()
        assert definition.name == "dummy"
        assert definition.description == "A dummy tool for testing"
        schema = definition.input_schema
        assert "properties" in schema
        assert "message" in schema["properties"]
        assert "count" in schema["properties"]
