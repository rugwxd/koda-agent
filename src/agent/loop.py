"""Core ReAct agent loop — observe, think, act, observe."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from src.config import Settings
from src.cost.tracker import BudgetExceededError, CostTracker
from src.llm.client import LLMClient
from src.llm.models import (
    Conversation,
    ToolResultContent,
)
from src.memory.working import WorkingMemory
from src.tools.registry import ToolRegistry
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Koda, an AI coding agent. You help developers by reading, understanding, and modifying code.

You have access to tools for interacting with the filesystem, running shell commands, searching code, and managing git.

Guidelines:
- Read files before modifying them
- Run tests after making changes
- Explain your reasoning before acting
- If you're unsure, search the codebase first
- Keep changes minimal and focused

{working_memory}
"""


@dataclass
class AgentResult:
    """Result of an agent task execution."""

    success: bool
    response: str
    iterations: int
    tool_calls_made: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_seconds: float = 0.0


class AgentLoop:
    """Core ReAct agent loop that processes user tasks through iterative tool use.

    The loop follows the ReAct pattern:
    1. Send conversation to Claude with available tools
    2. If Claude returns tool_use: execute tools, add results, loop back to 1
    3. If Claude returns end_turn: return the final response

    Integrates working memory, cost tracking, and trace collection.
    """

    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        cost_tracker: CostTracker,
        trace_collector: TraceCollector | None = None,
        working_memory: WorkingMemory | None = None,
        on_status: callable | None = None,
    ) -> None:
        self.settings = settings
        self.llm = llm_client
        self.tools = tool_registry
        self.cost = cost_tracker
        self.trace = trace_collector
        self.memory = working_memory or WorkingMemory(max_items=settings.memory.max_working_items)
        self._on_status = on_status or (lambda msg: None)

    def run(self, task: str, context: str = "") -> AgentResult:
        """Execute a task through the ReAct loop.

        Args:
            task: The user's task description.
            context: Optional additional context (repo map, relevant files).

        Returns:
            AgentResult with the final response and execution metadata.
        """
        start_time = time.time()
        tool_calls_made: list[str] = []
        files_modified: list[str] = []

        # Build system prompt with working memory
        system = SYSTEM_PROMPT.format(working_memory=self.memory.to_context_string())
        if context:
            system += f"\n\nContext:\n{context}"

        conversation = Conversation(system_prompt=system)
        conversation.add_user_message(task)

        # Get tool definitions
        tool_defs = self.tools.get_definitions()
        max_iterations = self.settings.llm.max_tool_iterations

        final_response = ""

        for iteration in range(max_iterations):
            # Start trace span for this iteration
            span = None
            if self.trace:
                span = self.trace.start_span(f"iteration_{iteration}")

            try:
                # Get LLM response
                self._on_status(f"Thinking... (iteration {iteration + 1})")
                response = self.llm.chat(conversation, tools=tool_defs)

                # Add assistant message to conversation
                conversation.add_assistant_message(response.content)

                # Record thinking in trace
                if self.trace and response.text:
                    self.trace.record(EventType.THOUGHT, {"text": response.text[:500]})

                # If no tool calls, we're done
                if not response.has_tool_calls:
                    final_response = response.text
                    if span:
                        self.trace.end_span(span)
                    break

                # Execute tool calls
                tool_results: list[ToolResultContent] = []
                for tool_call in response.tool_calls:
                    tool_calls_made.append(tool_call.name)

                    # Show what tool is being used
                    tool_detail = ""
                    if tool_call.name in ("read_file", "write_file"):
                        tool_detail = f" → {tool_call.input.get('path', '')}"
                    elif tool_call.name == "grep":
                        tool_detail = f" → '{tool_call.input.get('pattern', '')}'"
                    elif tool_call.name == "shell":
                        tool_detail = f" → {tool_call.input.get('command', '')[:40]}"
                    self._on_status(f"Using {tool_call.name}{tool_detail}")

                    result = self.tools.execute(tool_call.name, tool_call.input)

                    # Track file modifications
                    if tool_call.name == "write_file" and result.success:
                        path = tool_call.input.get("path", "")
                        if path and path not in files_modified:
                            files_modified.append(path)

                    # Update working memory with recent tool result
                    self.memory.set(
                        f"last_{tool_call.name}",
                        result.output[:200] if result.output else result.error,
                    )

                    tool_results.append(
                        ToolResultContent(
                            tool_use_id=tool_call.id,
                            content=result.output
                            if result.success
                            else f"Error: {result.error}\n{result.output}",
                            is_error=not result.success,
                        )
                    )

                # Add tool results to conversation
                conversation.add_tool_results(tool_results)

            except BudgetExceededError as e:
                logger.warning("Budget exceeded: %s", e)
                if self.trace:
                    self.trace.record(EventType.BUDGET_WARNING, {"error": str(e)})
                final_response = (
                    f"Task stopped: budget exceeded (${e.spent:.4f} of ${e.budget:.4f})"
                )
                if span:
                    self.trace.end_span(span)
                break

            except Exception as e:
                logger.error("Agent loop error at iteration %d: %s", iteration, e)
                if self.trace:
                    self.trace.record(EventType.ERROR, {"error": str(e)})
                final_response = f"Agent encountered an error: {e}"
                if span:
                    self.trace.end_span(span)
                break

            finally:
                if span and span.end_time is None:
                    self.trace.end_span(span)

        else:
            final_response = f"Task stopped after {max_iterations} iterations (max reached)"

        duration = time.time() - start_time
        cost_summary = self.cost.summary()

        return AgentResult(
            success=bool(final_response and "error" not in final_response.lower()),
            response=final_response,
            iterations=min(iteration + 1, max_iterations),
            tool_calls_made=tool_calls_made,
            files_modified=files_modified,
            total_tokens=cost_summary["total_tokens"],
            total_cost_usd=cost_summary["total_cost_usd"],
            duration_seconds=round(duration, 2),
        )
