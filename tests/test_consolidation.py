"""Tests for memory consolidation."""

import time

import pytest

from src.memory.consolidation import MemoryConsolidator
from src.memory.episodic import Episode, EpisodicMemory
from src.memory.semantic import SemanticMemory


class TestMemoryConsolidator:
    def test_should_consolidate(self, tmp_path):
        episodic = EpisodicMemory(db_path=str(tmp_path / "ep.db"))
        semantic = SemanticMemory(
            index_path=str(tmp_path / "sem.faiss"),
            embedding_model="none",
        )
        consolidator = MemoryConsolidator(episodic, semantic, consolidation_threshold=2)

        assert not consolidator.should_consolidate()

        # Add episodes
        for i in range(2):
            episodic.store(Episode(
                task_id=f"t{i}",
                task_description=f"Task {i}",
                outcome="success",
                summary=f"Did thing {i}",
                tool_chain=["read_file", "write_file"],
                files_modified=["src/main.py"],
                duration_seconds=10,
                cost_usd=0.01,
                timestamp=time.time(),
            ))

        assert consolidator.should_consolidate()
        episodic.close()

    def test_extract_tool_patterns(self):
        episodes = [
            Episode(
                task_id="t1", task_description="Fix bug",
                outcome="success", summary="Fixed",
                tool_chain=["read_file", "write_file", "run_tests"],
                files_modified=[], duration_seconds=10,
                cost_usd=0.01, timestamp=time.time(),
            ),
            Episode(
                task_id="t2", task_description="Fix other bug",
                outcome="success", summary="Fixed too",
                tool_chain=["read_file", "write_file", "run_tests"],
                files_modified=[], duration_seconds=10,
                cost_usd=0.01, timestamp=time.time(),
            ),
        ]

        patterns = MemoryConsolidator._extract_tool_patterns(episodes)
        assert len(patterns) > 0
        assert "read_file" in patterns[0][0]

    def test_extract_file_patterns(self):
        episodes = [
            Episode(
                task_id="t1", task_description="Task 1",
                outcome="success", summary="Done",
                tool_chain=[], files_modified=["src/config.py", "src/main.py"],
                duration_seconds=10, cost_usd=0.01, timestamp=time.time(),
            ),
            Episode(
                task_id="t2", task_description="Task 2",
                outcome="success", summary="Done",
                tool_chain=[], files_modified=["src/config.py"],
                duration_seconds=10, cost_usd=0.01, timestamp=time.time(),
            ),
        ]

        patterns = MemoryConsolidator._extract_file_patterns(episodes)
        assert len(patterns) > 0
        assert "config.py" in patterns[0][0]
