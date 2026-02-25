"""Tests for the task chain cache."""

import pytest

from src.cache.task_cache import TaskCache
from src.config import CacheConfig


class TestTaskCache:
    def test_store_and_size(self, tmp_path):
        config = CacheConfig(db_path=str(tmp_path / "cache.db"), enabled=True)
        cache = TaskCache(config=config)

        cache.store(
            task="Fix the login bug",
            tool_chain=[{"name": "read_file", "input": {"path": "auth.py"}}],
            files_modified=["auth.py"],
            cost_usd=0.02,
        )
        assert cache.size == 1
        cache.close()

    def test_disabled_cache(self, tmp_path):
        config = CacheConfig(db_path=str(tmp_path / "cache.db"), enabled=False)
        cache = TaskCache(config=config)

        # Store should be no-op when disabled
        cache.store("task", [], [], 0.0)
        assert cache.size == 0

        # Lookup should return None when disabled
        assert cache.lookup("task") is None
        cache.close()

    def test_max_entries_eviction(self, tmp_path):
        config = CacheConfig(db_path=str(tmp_path / "cache.db"), enabled=True, max_entries=2)
        cache = TaskCache(config=config)

        cache.store("task1", [{"name": "t1"}], [], 0.01)
        cache.store("task2", [{"name": "t2"}], [], 0.02)
        cache.store("task3", [{"name": "t3"}], [], 0.03)

        assert cache.size == 2
        cache.close()

    def test_total_hits(self, tmp_path):
        config = CacheConfig(db_path=str(tmp_path / "cache.db"), enabled=True)
        cache = TaskCache(config=config)
        assert cache.total_hits == 0
        cache.close()
