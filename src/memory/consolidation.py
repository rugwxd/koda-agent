"""Memory consolidation — extract reusable lessons from episodic memory."""

from __future__ import annotations

import logging

from src.memory.episodic import Episode, EpisodicMemory
from src.memory.semantic import SemanticEntry, SemanticMemory

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """Extracts reusable patterns from episodic memory into semantic memory.

    After enough successful task episodes accumulate, the consolidator
    analyzes common patterns (tool chains, file patterns, strategies)
    and distills them into semantic entries for future task guidance.
    """

    def __init__(
        self,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        consolidation_threshold: int = 5,
    ) -> None:
        self.episodic = episodic
        self.semantic = semantic
        self.consolidation_threshold = consolidation_threshold
        self._last_consolidated_count = 0

    def should_consolidate(self) -> bool:
        """Check if enough new episodes have accumulated for consolidation."""
        current = self.episodic.count
        return (current - self._last_consolidated_count) >= self.consolidation_threshold

    def consolidate(self) -> list[SemanticEntry]:
        """Extract patterns from recent successful episodes.

        Analyzes tool chain patterns, common file modifications,
        and successful strategies to create semantic entries.

        Returns:
            List of newly created semantic entries.
        """
        episodes = self.episodic.get_successful(limit=self.consolidation_threshold * 2)
        if not episodes:
            return []

        new_entries: list[SemanticEntry] = []

        # Extract tool chain patterns
        tool_patterns = self._extract_tool_patterns(episodes)
        for pattern_desc, task_ids in tool_patterns:
            entry = SemanticEntry(
                content=pattern_desc,
                category="pattern",
                source_task_ids=task_ids,
            )
            self.semantic.store(entry)
            new_entries.append(entry)

        # Extract file modification patterns
        file_patterns = self._extract_file_patterns(episodes)
        for pattern_desc, task_ids in file_patterns:
            entry = SemanticEntry(
                content=pattern_desc,
                category="pattern",
                source_task_ids=task_ids,
            )
            self.semantic.store(entry)
            new_entries.append(entry)

        # Extract lessons from summaries
        lessons = self._extract_lessons(episodes)
        for lesson, task_ids in lessons:
            entry = SemanticEntry(
                content=lesson,
                category="lesson",
                source_task_ids=task_ids,
            )
            self.semantic.store(entry)
            new_entries.append(entry)

        self._last_consolidated_count = self.episodic.count
        self.semantic.save()

        logger.info(
            "Consolidated %d new semantic entries from %d episodes",
            len(new_entries),
            len(episodes),
        )
        return new_entries

    @staticmethod
    def _extract_tool_patterns(episodes: list[Episode]) -> list[tuple[str, list[str]]]:
        """Find common tool chain sequences across episodes."""
        from collections import Counter

        chain_counter: Counter[str] = Counter()
        chain_to_tasks: dict[str, list[str]] = {}

        for ep in episodes:
            # Normalize tool chain to a signature
            chain_key = " -> ".join(ep.tool_chain[:5])  # First 5 tools
            if chain_key:
                chain_counter[chain_key] += 1
                chain_to_tasks.setdefault(chain_key, []).append(ep.task_id)

        patterns = []
        for chain, count in chain_counter.most_common(3):
            if count >= 2:
                desc = f"Common tool chain pattern ({count} occurrences): {chain}"
                patterns.append((desc, chain_to_tasks[chain]))

        return patterns

    @staticmethod
    def _extract_file_patterns(episodes: list[Episode]) -> list[tuple[str, list[str]]]:
        """Find commonly modified file groups."""
        from collections import Counter

        file_counter: Counter[str] = Counter()
        file_to_tasks: dict[str, list[str]] = {}

        for ep in episodes:
            for f in ep.files_modified:
                file_counter[f] += 1
                file_to_tasks.setdefault(f, []).append(ep.task_id)

        patterns = []
        for file_path, count in file_counter.most_common(5):
            if count >= 2:
                desc = f"Frequently modified file ({count} times): {file_path}"
                patterns.append((desc, file_to_tasks[file_path]))

        return patterns

    @staticmethod
    def _extract_lessons(episodes: list[Episode]) -> list[tuple[str, list[str]]]:
        """Extract key lessons from episode summaries."""
        lessons = []
        for ep in episodes:
            if ep.summary and len(ep.summary) > 20:
                lesson = f"Lesson from task '{ep.task_description[:50]}': {ep.summary}"
                lessons.append((lesson, [ep.task_id]))

        return lessons[:5]  # Limit to prevent flooding
