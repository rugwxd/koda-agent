# CLAUDE.md

## Project Overview

Koda is a production-grade AI coding agent built from scratch (no LangChain, no CrewAI). It uses Claude's tool_use API with a ReAct + Plan-and-Execute hybrid architecture.

## Environment Setup

- Python 3.11+ virtualenv at `venv/`
- Activate: `source venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Set `ANTHROPIC_API_KEY` environment variable

## Commands

```bash
# Activate environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_tools.py -v

# Lint check
ruff check src/ tests/

# Format
ruff format src/ tests/

# Run the agent
python scripts/run.py "your task here"

# Run dashboard
streamlit run dashboard/app.py
```

## Architecture

```
src/
├── agent/    — Core ReAct loop, planner, complexity router
├── tools/    — Filesystem, shell, git, code, search tools
├── llm/      — Claude API client with tool_use protocol
├── code/     — Tree-sitter parser, repo map, symbol search
├── memory/   — Working (dict), episodic (SQLite), semantic (FAISS)
├── critic/   — AST + lint + test verifier, LLM evaluator
├── cache/    — Task chain caching with similarity matching
├── cost/     — Token tracking, pricing, budget enforcement
└── trace/    — Structured event/span collection
```

## Key Dependencies

- anthropic, pydantic, tree-sitter, faiss-cpu, sentence-transformers
- rich, streamlit, ruff, pytest, pyyaml
