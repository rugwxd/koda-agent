"""Tests for working and episodic memory."""

import time

import pytest

from src.memory.episodic import Episode, EpisodicMemory
from src.memory.working import WorkingMemory


class TestWorkingMemory:
    def test_set_and_get(self):
        mem = WorkingMemory(max_items=10)
        mem.set("key1", "value1")
        assert mem.get("key1") == "value1"

    def test_default_value(self):
        mem = WorkingMemory()
        assert mem.get("missing", "default") == "default"

    def test_eviction(self):
        mem = WorkingMemory(max_items=3)
        mem.set("a", 1)
        mem.set("b", 2)
        mem.set("c", 3)
        mem.set("d", 4)  # Should evict "a"
        assert "a" not in mem
        assert mem.get("d") == 4
        assert len(mem) == 3

    def test_lru_order(self):
        mem = WorkingMemory(max_items=3)
        mem.set("a", 1)
        mem.set("b", 2)
        mem.set("c", 3)
        mem.get("a")  # Access "a", making "b" oldest
        mem.set("d", 4)  # Should evict "b"
        assert "a" in mem
        assert "b" not in mem

    def test_delete(self):
        mem = WorkingMemory()
        mem.set("x", 1)
        assert mem.delete("x")
        assert "x" not in mem
        assert not mem.delete("y")

    def test_clear(self):
        mem = WorkingMemory()
        mem.set("a", 1)
        mem.set("b", 2)
        mem.clear()
        assert len(mem) == 0

    def test_to_context_string(self):
        mem = WorkingMemory()
        mem.set("file", "main.py")
        ctx = mem.to_context_string()
        assert "file: main.py" in ctx

    def test_empty_context_string(self):
        mem = WorkingMemory()
        assert "empty" in mem.to_context_string().lower()


class TestEpisodicMemory:
    def test_store_and_retrieve(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        mem = EpisodicMemory(db_path=db_path)

        episode = Episode(
            task_id="task-001",
            task_description="Fix the login bug",
            outcome="success",
            summary="Fixed null check in auth handler",
            tool_chain=["read_file", "write_file", "run_tests"],
            files_modified=["src/auth.py"],
            duration_seconds=15.0,
            cost_usd=0.02,
            timestamp=time.time(),
        )
        mem.store(episode)
        assert mem.count == 1

        recent = mem.get_recent(limit=5)
        assert len(recent) == 1
        assert recent[0].task_id == "task-001"
        assert recent[0].tool_chain == ["read_file", "write_file", "run_tests"]
        mem.close()

    def test_search(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        mem = EpisodicMemory(db_path=db_path)

        mem.store(Episode(
            task_id="t1", task_description="Fix login bug",
            outcome="success", summary="Fixed auth",
            tool_chain=[], files_modified=[], duration_seconds=10,
            cost_usd=0.01, timestamp=time.time(),
        ))
        mem.store(Episode(
            task_id="t2", task_description="Add tests for API",
            outcome="success", summary="Added pytest cases",
            tool_chain=[], files_modified=[], duration_seconds=20,
            cost_usd=0.02, timestamp=time.time(),
        ))

        results = mem.search("login")
        assert len(results) == 1
        assert results[0].task_id == "t1"
        mem.close()

    def test_get_successful(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        mem = EpisodicMemory(db_path=db_path)

        mem.store(Episode(
            task_id="s1", task_description="Success task",
            outcome="success", summary="Worked",
            tool_chain=[], files_modified=[], duration_seconds=5,
            cost_usd=0.01, timestamp=time.time(),
        ))
        mem.store(Episode(
            task_id="f1", task_description="Failed task",
            outcome="failure", summary="Broke",
            tool_chain=[], files_modified=[], duration_seconds=5,
            cost_usd=0.01, timestamp=time.time(),
        ))

        successful = mem.get_successful()
        assert len(successful) == 1
        assert successful[0].outcome == "success"
        mem.close()
