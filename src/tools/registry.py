"""Tool registry for managing and looking up available tools."""

from __future__ import annotations

import logging
from typing import Any

from src.llm.models import ToolDefinition
from src.tools.base import BaseTool, ToolResult
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry that manages available tools and dispatches execution.

    Maintains a name → tool mapping, generates API-compatible tool definitions,
    and handles tool execution with tracing.
    """

    def __init__(self, trace_collector: TraceCollector | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        self.trace = trace_collector

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: Tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def execute(self, name: str, input_data: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given input.

        Args:
            name: Registered tool name.
            input_data: Raw input parameters from the LLM.

        Returns:
            ToolResult from the tool execution.
        """
        tool = self._tools.get(name)
        if not tool:
            error_msg = f"Unknown tool: {name}"
            logger.error(error_msg)
            return ToolResult(output="", success=False, error=error_msg)

        # Record tool call in trace
        if self.trace:
            self.trace.record(
                EventType.TOOL_CALL,
                {
                    "tool": name,
                    "input": input_data,
                },
            )

        result = tool.safe_execute(**input_data)

        # Record tool result in trace
        if self.trace:
            self.trace.record(
                EventType.TOOL_RESULT,
                {
                    "tool": name,
                    "success": result.success,
                    "output_length": len(result.output),
                    "error": result.error,
                },
            )

        return result

    def get_definitions(self) -> list[ToolDefinition]:
        """Generate tool definitions for all registered tools."""
        return [tool.to_tool_definition() for tool in self._tools.values()]

    @property
    def tool_names(self) -> list[str]:
        """List of all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
