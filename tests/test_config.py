"""Tests for configuration loading and validation."""

from pathlib import Path

import pytest

from src.config import LLMConfig, Settings, load_config


class TestSettings:
    def test_default_settings(self):
        settings = Settings()
        assert settings.llm.model == "claude-sonnet-4-20250514"
        assert settings.llm.max_tokens == 4096
        assert settings.llm.temperature == 0.0
        assert settings.cost.budget_per_task_usd == 0.50
        assert settings.trace.enabled is True

    def test_custom_settings(self):
        settings = Settings(
            llm=LLMConfig(model="custom-model", max_tokens=2048),
            anthropic_api_key="sk-test",
        )
        assert settings.llm.model == "custom-model"
        assert settings.llm.max_tokens == 2048
        assert settings.anthropic_api_key == "sk-test"


class TestLoadConfig:
    def test_load_default_config(self):
        settings = load_config()
        assert isinstance(settings, Settings)
        assert settings.llm.model is not None

    def test_load_missing_config(self, tmp_path):
        settings = load_config(tmp_path / "nonexistent.yaml")
        assert isinstance(settings, Settings)

    def test_load_custom_config(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text("llm:\n  model: test-model\n  max_tokens: 512\n")
        settings = load_config(config_file)
        assert settings.llm.model == "test-model"
        assert settings.llm.max_tokens == 512

    def test_env_var_override(self, monkeypatch, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text("llm:\n  model: test\n")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        settings = load_config(config_file)
        assert settings.anthropic_api_key == "sk-from-env"
