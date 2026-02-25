"""Configuration management for Koda agent."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "configs" / "default.yaml"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    max_tool_iterations: int = 25
    escalation_threshold: int = 3


class PlannerConfig(BaseModel):
    """Planner configuration for complex task decomposition."""

    complexity_threshold: float = 0.6
    max_plan_steps: int = 10
    replan_after_failures: int = 2


class ToolsConfig(BaseModel):
    """Tool execution configuration."""

    shell_timeout: int = 30
    max_file_size: int = 1_048_576
    sandbox_enabled: bool = True
    allowed_commands: list[str] = Field(
        default_factory=lambda: [
            "python",
            "pytest",
            "ruff",
            "git",
            "ls",
            "cat",
            "grep",
            "find",
            "echo",
        ]
    )


class MemoryConfig(BaseModel):
    """Memory system configuration."""

    episodic_db_path: str = "data/episodic.db"
    semantic_index_path: str = "data/semantic.faiss"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_working_items: int = 20
    consolidation_threshold: int = 5


class CriticConfig(BaseModel):
    """Self-verification critic configuration."""

    max_iterations: int = 3
    run_tests: bool = True
    run_lint: bool = True
    ast_check: bool = True
    rubric_enabled: bool = True


class CacheConfig(BaseModel):
    """Task chain caching configuration."""

    db_path: str = "data/cache.db"
    similarity_threshold: float = 0.85
    enabled: bool = True
    max_entries: int = 1000


class ModelPricing(BaseModel):
    """Per-model token pricing."""

    input_per_1k: float
    output_per_1k: float


class CostConfig(BaseModel):
    """Cost tracking and budget configuration."""

    budget_per_task_usd: float = 0.50
    pricing: dict[str, ModelPricing] = Field(default_factory=dict)


class TraceConfig(BaseModel):
    """Trace and observability configuration."""

    enabled: bool = True
    log_dir: str = "data/traces"
    stream_to_dashboard: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    file: str = "data/koda.log"


class Settings(BaseModel):
    """Root configuration for the Koda agent."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    planner: PlannerConfig = Field(default_factory=PlannerConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    critic: CriticConfig = Field(default_factory=CriticConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    trace: TraceConfig = Field(default_factory=TraceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    anthropic_api_key: str = ""


def load_config(path: str | Path | None = None) -> Settings:
    """Load configuration from YAML file with environment variable overrides.

    Args:
        path: Path to YAML config file. Uses default if not provided.

    Returns:
        Validated Settings instance.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    raw: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", config_path)
    else:
        logger.warning("Config file not found at %s, using defaults", config_path)

    # Environment variable overrides
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        raw["anthropic_api_key"] = api_key

    return Settings(**raw)


def setup_logging(config: LoggingConfig) -> None:
    """Configure logging from settings."""
    log_file = Path(config.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Suppress noisy HTTP client logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    logging.basicConfig(
        level=getattr(logging, config.level.upper(), logging.INFO),
        format=config.format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )
