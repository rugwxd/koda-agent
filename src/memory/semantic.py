"""Semantic memory — FAISS vector store for reusable knowledge."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SemanticEntry:
    """A single entry in semantic memory."""

    content: str
    category: str  # "pattern", "lesson", "preference"
    source_task_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """FAISS-backed semantic memory for storing reusable patterns and lessons.

    Stores distilled knowledge extracted from successful task episodes.
    Supports similarity-based retrieval using sentence-transformer embeddings.
    """

    def __init__(
        self,
        index_path: str = "data/semantic.faiss",
        embedding_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.index_path = Path(index_path)
        self.entries_path = self.index_path.with_suffix(".json")
        self._embedding_model_name = embedding_model
        self._model = None
        self._index = None
        self._entries: list[SemanticEntry] = []
        self._dimension = 384  # Default for all-MiniLM-L6-v2

        self._load_state()

    def _get_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._embedding_model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                logger.warning("sentence-transformers not available, using random embeddings")
        return self._model

    def _get_index(self):
        """Lazy-load or create the FAISS index."""
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self._dimension)
            except ImportError:
                logger.warning("faiss not available, semantic search disabled")
        return self._index

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for text inputs."""
        model = self._get_model()
        if model:
            embeddings = model.encode(texts, normalize_embeddings=True)
            return np.array(embeddings, dtype=np.float32)
        # Fallback: random embeddings (for testing without GPU deps)
        return np.random.randn(len(texts), self._dimension).astype(np.float32)

    def store(self, entry: SemanticEntry) -> None:
        """Store a semantic entry with its embedding.

        Args:
            entry: The semantic entry to store.
        """
        index = self._get_index()
        if index is None:
            logger.warning("FAISS not available, skipping semantic store")
            return

        embedding = self._embed([entry.content])
        index.add(embedding)
        self._entries.append(entry)

        logger.debug("Stored semantic entry: %s (%s)", entry.content[:50], entry.category)

    def search(self, query: str, top_k: int = 5) -> list[tuple[SemanticEntry, float]]:
        """Search for similar entries by semantic similarity.

        Args:
            query: Natural language search query.
            top_k: Number of results to return.

        Returns:
            List of (entry, similarity_score) tuples.
        """
        index = self._get_index()
        if index is None or index.ntotal == 0:
            return []

        query_embedding = self._embed([query])
        k = min(top_k, index.ntotal)
        scores, indices = index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._entries):
                results.append((self._entries[idx], float(score)))

        return results

    def save(self) -> None:
        """Persist index and entries to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        index = self._get_index()
        if index and index.ntotal > 0:
            try:
                import faiss
                faiss.write_index(index, str(self.index_path))
            except ImportError:
                pass

        # Save entries as JSON
        entries_data = []
        for e in self._entries:
            entries_data.append({
                "content": e.content,
                "category": e.category,
                "source_task_ids": e.source_task_ids,
                "metadata": e.metadata,
            })

        with open(self.entries_path, "w") as f:
            json.dump(entries_data, f, indent=2)

        logger.info("Saved %d semantic entries", len(self._entries))

    def _load_state(self) -> None:
        """Load persisted index and entries."""
        if self.entries_path.exists():
            try:
                with open(self.entries_path) as f:
                    entries_data = json.load(f)
                self._entries = [
                    SemanticEntry(**ed) for ed in entries_data
                ]
                logger.info("Loaded %d semantic entries", len(self._entries))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load semantic entries: %s", e)

        if self.index_path.exists():
            try:
                import faiss
                self._index = faiss.read_index(str(self.index_path))
            except (ImportError, RuntimeError) as e:
                logger.warning("Failed to load FAISS index: %s", e)

    @property
    def count(self) -> int:
        return len(self._entries)
