# Koda

Production-grade AI coding agent built from scratch — no LangChain, no CrewAI. Powered by Claude's tool_use API with full reasoning trace visualization, self-verification, and adaptive cost optimization.

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

## Key Features

**Full Reasoning Traces** — Every thought, tool call, and decision is captured as structured trace events within hierarchical spans. Visualize the agent's complete reasoning chain in the Streamlit dashboard.

**Self-Verification Critic** — Generated code passes through a four-stage verification pipeline before being returned: AST syntax check → ruff lint → pytest execution → LLM rubric evaluation (correctness, style, edge cases, simplicity).

**Adaptive Cost Optimization** — Successful tool chains are cached with semantic embeddings. When a similar task arrives, the cached chain is replayed instead of running full LLM reasoning. Tracks cost savings and cache hit rates.

**Three-Layer Memory** — Working memory (in-context dict) for the current task, episodic memory (SQLite) for past task summaries, and semantic memory (FAISS) for distilled patterns. Consolidation extracts reusable lessons from episodes automatically.

**ReAct + Plan-and-Execute Hybrid** — A complexity router classifies incoming tasks. Simple tasks go through the ReAct loop directly. Complex multi-step tasks are decomposed by the planner, executed step-by-step, and replanned on failure.

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

## Quick Start

```bash
# Clone and setup
git clone https://github.com/rugwxd/koda-agent.git
cd koda-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Run interactive mode
python scripts/run.py

# Run single task
python scripts/run.py "read the README and summarize it"

# Launch trace dashboard
streamlit run dashboard/app.py
```

## Docker

```bash
# Build and run
docker compose up --build

# Agent only
docker build -t koda-agent .
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -it koda-agent

# Dashboard at http://localhost:8501
```

## How It Works

### The Agent Loop

```
User task
    │
    ▼
┌─ Complexity Router ─────────────────────────┐
│  keyword analysis · length · file refs       │
│  multi-step indicators · LLM borderline      │
└──────┬──────────────────────────┬────────────┘
       │ simple                   │ complex
       ▼                          ▼
   ReAct Loop              Plan-and-Execute
   while True:             1. Decompose into steps
     response = llm()      2. Execute each step via ReAct
     if tool_use:          3. Replan on failure
       execute(tools)
       feed results back
     else:
       return response
```

### Tool Auto-Schema

Tools are defined as Python classes with Pydantic input models. The registry auto-generates Claude-compatible JSON schemas — no manual schema writing:

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

## Testing

```bash
# Run all 113 tests
python -m pytest tests/ -v

# Run specific module tests
python -m pytest tests/test_tools.py -v
python -m pytest tests/test_memory.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## Configuration

All settings in `configs/default.yaml`:

| Section | Key Settings |
|---------|-------------|
| `llm` | model, max_tokens, temperature, max_tool_iterations |
| `planner` | complexity_threshold, max_plan_steps, replan_after_failures |
| `tools` | shell_timeout, sandbox_enabled, allowed_commands |
| `memory` | episodic_db_path, embedding_model, consolidation_threshold |
| `critic` | max_iterations, run_tests, run_lint, ast_check |
| `cache` | similarity_threshold, enabled, max_entries |
| `cost` | budget_per_task_usd, per-model pricing |
| `trace` | enabled, log_dir, stream_to_dashboard |

## Tech Stack

- **Claude API** — LLM backbone with tool_use protocol
- **tree-sitter** — AST parsing for Python code analysis
- **FAISS** — Vector similarity search for semantic memory and cache
- **sentence-transformers** — Embedding generation (all-MiniLM-L6-v2)
- **SQLite** — Episodic memory and cache persistence
- **Rich** — Terminal UI with live output
- **Streamlit** — Trace visualization dashboard
- **Pydantic** — Config validation and tool schema generation

## License

MIT
