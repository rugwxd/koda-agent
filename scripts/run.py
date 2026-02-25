"""CLI entry point for the Koda agent."""

from __future__ import annotations

import argparse
import os
import sys
import uuid

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from src.agent.loop import AgentLoop
from src.agent.planner import Planner
from src.agent.router import ComplexityRouter
from src.cache.task_cache import TaskCache
from src.code.repo_map import RepoMapBuilder
from src.config import load_config, setup_logging
from src.cost.tracker import CostTracker
from src.critic.verifier import Verifier
from src.llm.client import LLMClient
from src.memory.working import WorkingMemory
from src.tools.code import ASTCheckTool, LintTool, TestRunnerTool
from src.tools.filesystem import GlobTool, ListDirectoryTool, ReadFileTool, WriteFileTool
from src.tools.git import GitCommitTool, GitDiffTool, GitLogTool, GitStatusTool
from src.tools.registry import ToolRegistry
from src.tools.search import GrepTool
from src.tools.shell import ShellTool
from src.trace.collector import TraceCollector

console = Console()


def build_tool_registry(settings, trace_collector) -> ToolRegistry:
    """Register all available tools."""
    registry = ToolRegistry(trace_collector=trace_collector)

    # Filesystem tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirectoryTool())
    registry.register(GlobTool())

    # Search
    registry.register(GrepTool())

    # Shell
    registry.register(ShellTool(config=settings.tools))

    # Git
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitLogTool())
    registry.register(GitCommitTool())

    # Code
    registry.register(ASTCheckTool())
    registry.register(LintTool())
    registry.register(TestRunnerTool())

    return registry


def display_result(result, cost_tracker, console):
    """Display the agent result with rich formatting."""
    # Response panel
    console.print()
    console.print(Panel(
        result.response or "(no response)",
        title="Koda",
        border_style="green" if result.success else "red",
    ))

    # Stats table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Iterations", str(result.iterations))
    table.add_row("Tool calls", str(len(result.tool_calls_made)))
    table.add_row("Files modified", str(len(result.files_modified)))
    table.add_row("Tokens", f"{result.total_tokens:,}")
    table.add_row("Cost", f"${result.total_cost_usd:.4f}")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")

    if cost_tracker.cache_savings > 0:
        table.add_row("Cache savings", f"${cost_tracker.cache_savings:.4f}")

    console.print(table)


def run_interactive(settings, llm_client, tool_registry, cost_tracker, trace_collector):
    """Run in interactive REPL mode."""
    working_memory = WorkingMemory(max_items=settings.memory.max_working_items)
    agent = AgentLoop(
        settings=settings,
        llm_client=llm_client,
        tool_registry=tool_registry,
        cost_tracker=cost_tracker,
        trace_collector=trace_collector,
        working_memory=working_memory,
    )

    console.print(Panel("Koda — AI Coding Agent", style="bold blue"))
    console.print("[dim]Type your task, or 'quit' to exit.[/dim]\n")

    while True:
        try:
            task = console.input("[bold green]> [/bold green]")
        except (EOFError, KeyboardInterrupt):
            break

        task = task.strip()
        if not task:
            continue
        if task.lower() in ("quit", "exit", "q"):
            break

        with console.status("[bold blue]Thinking...[/bold blue]"):
            result = agent.run(task)

        display_result(result, cost_tracker, console)

        # Save trace after each task
        if trace_collector:
            saved = trace_collector.save()
            if saved:
                console.print(f"[dim]Trace saved: {saved}[/dim]")

        console.print()


def run_single(task, settings, llm_client, tool_registry, cost_tracker, trace_collector):
    """Run a single task and exit."""
    working_memory = WorkingMemory(max_items=settings.memory.max_working_items)

    # Build repo context
    repo_map_builder = RepoMapBuilder()
    repo_map = repo_map_builder.build(".")
    context = repo_map.render(max_tokens=1500)

    agent = AgentLoop(
        settings=settings,
        llm_client=llm_client,
        tool_registry=tool_registry,
        cost_tracker=cost_tracker,
        trace_collector=trace_collector,
        working_memory=working_memory,
    )

    with console.status("[bold blue]Working...[/bold blue]"):
        result = agent.run(task, context=context)

    display_result(result, cost_tracker, console)

    # Save trace
    if trace_collector:
        trace_collector.save()

    return 0 if result.success else 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Koda — AI Coding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", nargs="?", help="Task to execute (omit for interactive mode)")
    parser.add_argument("--config", default=None, help="Path to config YAML file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    # Load configuration
    settings = load_config(args.config)
    if args.verbose:
        settings.logging.level = "DEBUG"
    setup_logging(settings.logging)

    # Validate API key
    if not settings.anthropic_api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY not set.[/red]")
        console.print("Set it via environment variable or in configs/default.yaml")
        sys.exit(1)

    # Initialize components
    task_id = uuid.uuid4().hex[:8]
    trace_collector = TraceCollector(
        task_id=task_id,
        log_dir=settings.trace.log_dir if settings.trace.enabled else None,
    )
    cost_tracker = CostTracker(config=settings.cost)
    llm_client = LLMClient(
        config=settings.llm,
        api_key=settings.anthropic_api_key,
        cost_tracker=cost_tracker,
        trace_collector=trace_collector,
    )
    tool_registry = build_tool_registry(settings, trace_collector)

    console.print(f"[dim]Loaded {len(tool_registry)} tools[/dim]")

    if args.task:
        exit_code = run_single(
            args.task, settings, llm_client, tool_registry, cost_tracker, trace_collector
        )
        sys.exit(exit_code)
    else:
        run_interactive(settings, llm_client, tool_registry, cost_tracker, trace_collector)


if __name__ == "__main__":
    main()
