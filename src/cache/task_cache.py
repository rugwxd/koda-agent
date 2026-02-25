"""Task chain caching — store and replay proven tool sequences."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.config import CacheConfig
from src.trace.collector import TraceCollector
from src.trace.models import EventType

logger = logging.getLogger(__name__)


@dataclass
class CachedChain:
    """A cached tool chain from a previously successful task."""

    task_description: str
    tool_chain: list[dict]  # [{name, input_template}, ...]
    files_modified: list[str]
    cost_usd: float
    hit_count: int = 0
    similarity: float = 0.0


class TaskCache:
    """Caches successful tool chains for cost optimization.

    When a new task arrives, embeds the description and searches for similar
    past tasks. If a match is found above the similarity threshold, returns
    the cached tool chain for replay.

    This is the core mechanism behind "gets cheaper over time":
    - First time: full LLM reasoning (expensive)
    - Subsequent similar tasks: cached chain replay (near-free)
    """

    def __init__(
        self,
        config: CacheConfig,
        trace_collector: TraceCollector | None = None,
    ) -> None:
        self.config = config
        self.trace = trace_collector
        self._model = None
        self._dimension = 384

        # SQLite storage for cached chains
        self.db_path = Path(config.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._create_table()

        # In-memory embedding index
        self._embeddings: list[np.ndarray] = []
        self._chain_ids: list[int] = []
        self._load_embeddings()

    def _create_table(self) -> None:
        """Create cache table."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS task_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_description TEXT NOT NULL,
                tool_chain TEXT NOT NULL,
                files_modified TEXT NOT NULL,
                cost_usd REAL,
                hit_count INTEGER DEFAULT 0,
                embedding BLOB
            )
        """)
        self._conn.commit()

    def _get_model(self):
        """Lazy-load embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                logger.warning("sentence-transformers not available for cache embeddings")
        return self._model

    def _embed(self, text: str) -> np.ndarray:
        """Generate embedding for a text."""
        model = self._get_model()
        if model:
            return model.encode([text], normalize_embeddings=True)[0].astype(np.float32)
        return np.random.randn(self._dimension).astype(np.float32)

    def _load_embeddings(self) -> None:
        """Load cached embeddings into memory for fast search."""
        cursor = self._conn.execute("SELECT id, embedding FROM task_chains")
        for row in cursor.fetchall():
            chain_id, emb_bytes = row
            if emb_bytes:
                emb = np.frombuffer(emb_bytes, dtype=np.float32)
                self._embeddings.append(emb)
                self._chain_ids.append(chain_id)

    def lookup(self, task: str) -> CachedChain | None:
        """Search for a similar cached task chain.

        Args:
            task: The new task description.

        Returns:
            CachedChain if a similar task is found, None otherwise.
        """
        if not self.config.enabled or not self._embeddings:
            return None

        query_emb = self._embed(task)

        # Cosine similarity search (embeddings are already normalized)
        embeddings_matrix = np.stack(self._embeddings)
        similarities = embeddings_matrix @ query_emb

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score < self.config.similarity_threshold:
            if self.trace:
                self.trace.record(
                    EventType.CACHE_MISS,
                    {
                        "task": task[:100],
                        "best_score": round(best_score, 3),
                        "threshold": self.config.similarity_threshold,
                    },
                )
            return None

        # Fetch the cached chain
        chain_id = self._chain_ids[best_idx]
        cursor = self._conn.execute(
            "SELECT task_description, tool_chain, files_modified, cost_usd, hit_count FROM task_chains WHERE id = ?",
            (chain_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Increment hit count
        self._conn.execute(
            "UPDATE task_chains SET hit_count = hit_count + 1 WHERE id = ?", (chain_id,)
        )
        self._conn.commit()

        cached = CachedChain(
            task_description=row[0],
            tool_chain=json.loads(row[1]),
            files_modified=json.loads(row[2]),
            cost_usd=row[3],
            hit_count=row[4] + 1,
            similarity=best_score,
        )

        if self.trace:
            self.trace.record(
                EventType.CACHE_HIT,
                {
                    "task": task[:100],
                    "matched_task": cached.task_description[:100],
                    "similarity": round(best_score, 3),
                    "hit_count": cached.hit_count,
                    "saved_cost": round(cached.cost_usd, 4),
                },
            )

        logger.info(
            "Cache hit (%.2f): '%s' matched '%s'",
            best_score,
            task[:50],
            cached.task_description[:50],
        )
        return cached

    def store(
        self,
        task: str,
        tool_chain: list[dict],
        files_modified: list[str],
        cost_usd: float,
    ) -> None:
        """Cache a successful tool chain for future reuse.

        Args:
            task: Task description.
            tool_chain: Sequence of tool calls [{name, input}, ...].
            files_modified: List of files that were modified.
            cost_usd: Total cost of the task execution.
        """
        if not self.config.enabled:
            return

        # Enforce max entries
        count = self._conn.execute("SELECT COUNT(*) FROM task_chains").fetchone()[0]
        if count >= self.config.max_entries:
            # Evict least-used entry
            self._conn.execute(
                "DELETE FROM task_chains WHERE id = (SELECT id FROM task_chains ORDER BY hit_count ASC LIMIT 1)"
            )

        embedding = self._embed(task)

        self._conn.execute(
            """INSERT INTO task_chains (task_description, tool_chain, files_modified, cost_usd, embedding)
               VALUES (?, ?, ?, ?, ?)""",
            (
                task,
                json.dumps(tool_chain),
                json.dumps(files_modified),
                cost_usd,
                embedding.tobytes(),
            ),
        )
        self._conn.commit()

        # Update in-memory index
        self._embeddings.append(embedding)
        self._chain_ids.append(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        logger.debug("Cached tool chain for: %s", task[:80])

    @property
    def size(self) -> int:
        """Number of cached entries."""
        return self._conn.execute("SELECT COUNT(*) FROM task_chains").fetchone()[0]

    @property
    def total_hits(self) -> int:
        """Total cache hits across all entries."""
        result = self._conn.execute(
            "SELECT COALESCE(SUM(hit_count), 0) FROM task_chains"
        ).fetchone()
        return result[0]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
