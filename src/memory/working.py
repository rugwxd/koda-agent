"""Working memory — in-context key-value store for the current task."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkingMemory:
    """In-context working memory for the current agent session.

    Stores key-value pairs that persist within a single task execution.
    Used for tracking: current file being edited, recent tool outputs,
    discovered code patterns, and accumulated context.

    Automatically evicts oldest entries when max_items is exceeded.
    """

    max_items: int = 20
    _store: dict[str, Any] = field(default_factory=dict)
    _access_order: list[str] = field(default_factory=list)

    def set(self, key: str, value: Any) -> None:
        """Store a key-value pair in working memory.

        Args:
            key: Memory key (e.g., "current_file", "test_results").
            value: Any value to store.
        """
        if key in self._store:
            self._access_order.remove(key)

        self._store[key] = value
        self._access_order.append(key)

        # Evict oldest entries if over capacity
        while len(self._store) > self.max_items:
            oldest = self._access_order.pop(0)
            del self._store[oldest]
            logger.debug("Evicted working memory key: %s", oldest)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from working memory."""
        if key in self._store:
            # Move to end (most recently accessed)
            self._access_order.remove(key)
            self._access_order.append(key)
        return self._store.get(key, default)

    def delete(self, key: str) -> bool:
        """Remove a key from working memory. Returns True if key existed."""
        if key in self._store:
            del self._store[key]
            self._access_order.remove(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all working memory."""
        self._store.clear()
        self._access_order.clear()

    def to_context_string(self) -> str:
        """Render working memory as a string for injection into system prompt.

        Returns:
            Formatted string representation of current memory state.
        """
        if not self._store:
            return "Working memory: (empty)"

        lines = ["Working memory:"]
        for key in self._access_order:
            value = self._store[key]
            # Truncate long values
            val_str = str(value)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            lines.append(f"  {key}: {val_str}")

        return "\n".join(lines)

    @property
    def keys(self) -> list[str]:
        return list(self._store.keys())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store
