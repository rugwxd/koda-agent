"""Episodic memory — SQLite-backed storage for past task summaries."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    """A single episode representing a completed task."""

    task_id: str
    task_description: str
    outcome: str  # "success" or "failure"
    summary: str
    tool_chain: list[str]
    files_modified: list[str]
    duration_seconds: float
    cost_usd: float
    timestamp: float
    metadata: dict[str, Any] | None = None

    def to_row(self) -> tuple:
        """Convert to SQLite row format."""
        return (
            self.task_id,
            self.task_description,
            self.outcome,
            self.summary,
            json.dumps(self.tool_chain),
            json.dumps(self.files_modified),
            self.duration_seconds,
            self.cost_usd,
            self.timestamp,
            json.dumps(self.metadata or {}),
        )

    @classmethod
    def from_row(cls, row: tuple) -> Episode:
        """Create from SQLite row."""
        return cls(
            task_id=row[0],
            task_description=row[1],
            outcome=row[2],
            summary=row[3],
            tool_chain=json.loads(row[4]),
            files_modified=json.loads(row[5]),
            duration_seconds=row[6],
            cost_usd=row[7],
            timestamp=row[8],
            metadata=json.loads(row[9]) if row[9] else None,
        )


class EpisodicMemory:
    """SQLite-backed episodic memory for storing past task experiences.

    Stores complete task episodes including tool chains, files modified,
    costs, and outcomes. Supports retrieval by recency and keyword search.
    """

    def __init__(self, db_path: str = "data/episodic.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._create_table()

    def _create_table(self) -> None:
        """Create the episodes table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                task_id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                outcome TEXT NOT NULL,
                summary TEXT NOT NULL,
                tool_chain TEXT NOT NULL,
                files_modified TEXT NOT NULL,
                duration_seconds REAL,
                cost_usd REAL,
                timestamp REAL NOT NULL,
                metadata TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_episodes_timestamp
            ON episodes(timestamp DESC)
        """)
        self._conn.commit()

    def store(self, episode: Episode) -> None:
        """Store a task episode.

        Args:
            episode: The completed episode to store.
        """
        self._conn.execute(
            """INSERT OR REPLACE INTO episodes
               (task_id, task_description, outcome, summary, tool_chain,
                files_modified, duration_seconds, cost_usd, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            episode.to_row(),
        )
        self._conn.commit()
        logger.debug("Stored episode: %s (%s)", episode.task_id, episode.outcome)

    def get_recent(self, limit: int = 10) -> list[Episode]:
        """Retrieve most recent episodes.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            List of episodes ordered by recency.
        """
        cursor = self._conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [Episode.from_row(row) for row in cursor.fetchall()]

    def search(self, query: str, limit: int = 10) -> list[Episode]:
        """Search episodes by keyword in description or summary.

        Args:
            query: Search keyword.
            limit: Maximum results.

        Returns:
            Matching episodes.
        """
        cursor = self._conn.execute(
            """SELECT * FROM episodes
               WHERE task_description LIKE ? OR summary LIKE ?
               ORDER BY timestamp DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        )
        return [Episode.from_row(row) for row in cursor.fetchall()]

    def get_successful(self, limit: int = 20) -> list[Episode]:
        """Retrieve recent successful episodes for pattern extraction."""
        cursor = self._conn.execute(
            "SELECT * FROM episodes WHERE outcome = 'success' ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [Episode.from_row(row) for row in cursor.fetchall()]

    @property
    def count(self) -> int:
        """Total number of stored episodes."""
        cursor = self._conn.execute("SELECT COUNT(*) FROM episodes")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
