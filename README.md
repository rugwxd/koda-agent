# Koda

Production-grade AI coding agent built from scratch — no LangChain, no CrewAI. Powered by Claude's tool_use API with full reasoning trace visualization, self-verification, and adaptive cost optimization.

## Quick Start (3 commands)

```bash
git clone https://github.com/rugwed9/koda-agent.git && cd koda-agent
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key" && python3 scripts/run.py
```

Get your API key at [console.anthropic.com](https://console.anthropic.com). That's it — you're in the agent REPL. Type a task and hit enter.

## What It Does

You type a task in natural language. Koda reads your codebase, writes code, runs tests, and verifies its own output — all autonomously through Claude's tool_use API.

```
> Write a fibonacci generator with tests

⠼ Thinking... (iteration 1)
⠼ Using write_file → fibonacci.py
⠼ Using write_file → test_fibonacci.py
⠼ Using shell → python -m pytest test_fibonacci.py
⠼ Thinking... (iteration 4)

╭── Koda ──────────────────────────────────────────────╮
│ Created fibonacci.py with 4 implementations:         │
│ - Iterative, recursive, generator, and memoized      │
│ - All tests passing                                  │
╰──────────────────────────────────────────────────────╯
  Iterations     7
  Tool calls     4
  Tokens         48,740
  Cost           $0.19
  Duration       15.3s
```

## Real Usage: Cost Benchmarks

These are actual results from running Koda on real tasks:

| Task | Iterations | Tool Calls | Tokens | Cost | Time |
|------|-----------|------------|--------|------|------|
| "Write a fibonacci generator" | 7 | 4 | 48,740 | $0.19 | 15s |
| "What files are in this project?" | 5 | 4 | 48,740 | $0.19 | 15s |
| "Build a Twitter clone" | 14 | 13 | 131,815 | $0.52 | 198s |

Key takeaways:
- **Simple tasks** (read files, write small scripts): ~$0.15-0.20, under 20 seconds
- **Medium tasks** (multi-file features): ~$0.30-0.50, 1-2 minutes
- **Large tasks** (full app scaffolding): $0.50+ — the budget cap kicks in to protect your wallet

The default budget is **$0.50 per task**. Change it in `configs/default.yaml` under `cost.budget_per_task_usd`.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      CLI / Dashboard                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│   ┌─────────────┐    ┌──────────────────────────────┐   │
│   │  Complexity  │    │        Agent Loop             │   │
│   │   Router     │───▶│  ReAct: observe → think →     │   │
│   │              │    │         act → observe          │   │
│   └─────────────┘    └──────────┬───────────────────┘   │
│         │                        │                        │
│         │ complex                │ tool_use               │
│         ▼                        ▼                        │
│   ┌─────────────┐    ┌──────────────────────────────┐   │
│   │   Planner    │    │      Tool Registry            │   │
│   │  decompose → │    │  filesystem · shell · git     │   │
│   │  execute →   │    │  grep · AST · lint · test     │   │
│   │  replan      │    └──────────────────────────────┘   │
│   └─────────────┘                                        │
│                                                           │
├───────────────────────┬───────────────────────────────────┤
│   Memory              │   Verification                    │
│  ┌────────────────┐   │  ┌────────────────────────────┐  │
│  │ Working (dict)  │   │  │ AST check → ruff lint →    │  │
│  │ Episodic (SQL)  │   │  │ pytest → LLM rubric       │  │
│  │ Semantic (FAISS)│   │  │                            │  │
│  └────────────────┘   │  └────────────────────────────┘  │
├───────────────────────┼───────────────────────────────────┤
│   Cost Tracker        │   Task Cache                      │
│  per-call tokens      │  embed → similarity search →      │
│  budget enforcement   │  replay proven tool chains        │
│  cache savings        │  gets cheaper over time           │
├───────────────────────┴───────────────────────────────────┤
│                    Trace Collector                         │
│  structured spans · events · JSON persistence · dashboard │
└─────────────────────────────────────────────────────────┘
```

## Three Standout Features

### 1. Full Reasoning Traces

Every thought, tool call, and decision is captured as structured trace events. View them in the Streamlit dashboard:

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

The dashboard shows:
- **Timeline**: Step-by-step execution with thoughts, tool calls, results
- **Cost**: Token usage and API call breakdown per task
- **Tools**: Usage stats and success rates across sessions

### 2. Self-Verification Critic

Generated code passes through a four-stage pipeline before being returned:

```
Code generated
    │
    ├── 1. AST syntax check (instant — catches parse errors)
    ├── 2. ruff lint (catches style and logic issues)
    ├── 3. pytest (catches runtime errors and regressions)
    └── 4. LLM rubric (scores correctness, style, edge cases, simplicity)
          │
          ├── Pass → return to user
          └── Fail → feed errors back to agent, retry (max 3 attempts)
```

### 3. Gets Cheaper Over Time

Successful tool chains are cached with semantic embeddings. When a similar task arrives:

```
New task: "write a sorting function"
    │
    ├── Embed task description
    ├── Search FAISS index for similar past tasks
    │     → Match: "write a fibonacci function" (similarity: 0.87)
    │
    ├── Replay cached tool chain (read → write → test)
    └── Skip full LLM reasoning → near-zero cost
```

## How It Works Under the Hood

### The ReAct Loop

The core is a while loop — nothing magical:

```python
while iteration < max_iterations:
    response = claude.chat(conversation, tools=tool_definitions)

    if response.stop_reason == "tool_use":
        # Claude wants to use a tool
        for tool_call in response.tool_calls:
            result = registry.execute(tool_call.name, tool_call.input)
            # Feed result back to Claude
        conversation.add_tool_results(results)
    else:
        # Claude is done — return the response
        return response.text
```

Claude decides which tools to use. The agent just orchestrates the loop.

### Tool Auto-Schema

Tools are Python classes with Pydantic models. The registry auto-generates Claude-compatible JSON schemas:

```python
class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read contents of a file"

    class InputModel(BaseModel):
        path: str = Field(description="File path to read")
        max_lines: int = Field(default=500)

    def execute(self, **kwargs) -> ToolResult:
        params = self.InputModel(**kwargs)
        content = Path(params.path).read_text()
        return ToolResult(output=content)
```

Adding a new tool = one class. The schema is derived from the Pydantic model automatically.

### Memory Architecture

```
Working Memory          Episodic Memory         Semantic Memory
(in-context dict)       (SQLite)                (FAISS + embeddings)
     │                       │                        ▲
     │ current task          │ task summaries          │ distilled
     │ context               │ tool chains             │ patterns
     │                       │ outcomes                │
     │                       │                         │
     │                       └──── consolidation ──────┘
     │                             (after N successes)
     └── injected into system prompt each iteration
```

## Project Structure

```
src/
├── agent/          # Core loop, planner, complexity router
├── tools/          # Filesystem, shell, git, code, search tools
├── llm/            # Claude API client with tool_use protocol
├── code/           # Tree-sitter parser, repo map, symbol search
├── memory/         # Working, episodic (SQLite), semantic (FAISS)
├── critic/         # AST + lint + test verifier, LLM evaluator
├── cache/          # Task chain caching with similarity matching
├── cost/           # Token tracking, pricing, budget enforcement
└── trace/          # Structured event/span collection
dashboard/          # Streamlit trace visualization
scripts/            # CLI entry point
tests/              # 113 tests covering all modules
```

## Configuration

All settings in `configs/default.yaml`:

| Setting | Default | What It Controls |
|---------|---------|-----------------|
| `cost.budget_per_task_usd` | `0.50` | Max spend per task before auto-stop |
| `llm.model` | `claude-sonnet-4-20250514` | Which Claude model to use |
| `llm.max_tool_iterations` | `25` | Max ReAct loop iterations |
| `critic.run_tests` | `true` | Run pytest on generated code |
| `critic.run_lint` | `true` | Run ruff on generated code |
| `cache.enabled` | `true` | Cache successful tool chains |
| `cache.similarity_threshold` | `0.85` | How similar a task must be for cache hit |
| `tools.sandbox_enabled` | `true` | Restrict shell to allowed commands |

## Running Tests

```bash
python3 -m pytest tests/ -v          # All 113 tests
python3 -m pytest tests/test_tools.py # Just tool tests
python3 -m pytest tests/ --cov=src    # With coverage
```

## Docker

```bash
docker compose up --build             # Agent + dashboard
docker build -t koda-agent .          # Build image
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -it koda-agent  # Run
```

Dashboard available at `http://localhost:8501` when using docker compose.

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM | Claude API (tool_use) | Core reasoning engine |
| AST Parsing | tree-sitter | Python code structure analysis |
| Vector Search | FAISS | Semantic memory + cache lookup |
| Embeddings | sentence-transformers | Task similarity matching |
| Storage | SQLite | Episodic memory + cache persistence |
| Terminal UI | Rich | Live status, panels, tables |
| Dashboard | Streamlit | Trace visualization |
| Validation | Pydantic | Config + tool schema generation |

## License

MIT
