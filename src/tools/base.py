"""Base tool class with automatic JSON schema generation from Pydantic models."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from src.llm.models import ToolDefinition

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Standard result from tool execution."""

    output: str
    success: bool = True
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all agent tools.

    Subclasses define an InputModel (Pydantic BaseModel) for their parameters.
    The registry auto-generates Claude-compatible JSON schemas from InputModel
    using Pydantic's model_json_schema().

    Example:
        class ReadFileTool(BaseTool):
            name = "read_file"
            description = "Read contents of a file"

            class InputModel(BaseModel):
                path: str = Field(description="Absolute file path")
                max_lines: int = Field(default=500, description="Max lines to read")

            def execute(self, **kwargs) -> ToolResult:
                validated = self.InputModel(**kwargs)
                content = Path(validated.path).read_text()
                return ToolResult(output=content)
    """

    name: ClassVar[str]
    description: ClassVar[str]
    InputModel: ClassVar[type[BaseModel]]

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with validated input parameters.

        Args:
            **kwargs: Raw input parameters (will be validated against InputModel).

        Returns:
            ToolResult with output string and success status.
        """

    def validate_input(self, raw_input: dict[str, Any]) -> BaseModel:
        """Validate raw input against the tool's InputModel.

        Args:
            raw_input: Dictionary of input parameters from the LLM.

        Returns:
            Validated Pydantic model instance.
        """
        return self.InputModel(**raw_input)

    def safe_execute(self, **kwargs: Any) -> ToolResult:
        """Execute with error handling.

        Validates input, runs execute(), and catches any exceptions
        to return a structured error result instead of crashing.
        """
        try:
            self.validate_input(kwargs)
            return self.execute(**kwargs)
        except Exception as e:
            logger.error("Tool %s failed: %s", self.name, e)
            return ToolResult(output="", success=False, error=str(e))

    @classmethod
    def to_tool_definition(cls) -> ToolDefinition:
        """Generate a Claude-compatible tool definition from the InputModel.

        Uses Pydantic's model_json_schema() to auto-generate the input_schema,
        ensuring the schema always matches the actual validation logic.
        """
        schema = cls.InputModel.model_json_schema()

        # Clean up schema for Claude API compatibility
        schema.pop("title", None)

        return ToolDefinition(
            name=cls.name,
            description=cls.description,
            input_schema=schema,
        )
