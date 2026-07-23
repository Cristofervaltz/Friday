"""Persistent workspace memory storage for Friday."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class WorkspaceMemory:
    """Manages persistent project and user memory stored in JSON file."""

    DEFAULT_MEMORY_PATH = Path(".friday") / "memory.json"

    def __init__(self, memory_path: Path | str | None = None) -> None:
        """Initialize WorkspaceMemory.

        Args:
            memory_path: Custom file path for memory persistence.
        """
        if memory_path is None:
            self.memory_path = self.DEFAULT_MEMORY_PATH
        else:
            self.memory_path = Path(memory_path)

        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load memory from JSON file if it exists."""
        if self.memory_path.exists():
            try:
                with open(self.memory_path, encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._data = json.loads(content)
                    else:
                        self._data = {}
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        """Save current memory data to JSON file."""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def set(self, key: str, value: Any) -> None:
        """Set a key-value pair in memory and persist.

        Args:
            key: Memory key identifier.
            value: Value to store (must be JSON serializable).
        """
        self._data[key] = value
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key.

        Args:
            key: Memory key identifier.
            default: Fallback value if key is not found.

        Returns:
            Stored value or default.
        """
        return self._data.get(key, default)

    def delete(self, key: str) -> bool:
        """Delete a key from memory and persist.

        Args:
            key: Memory key identifier.

        Returns:
            True if key was present and deleted, False otherwise.
        """
        if key in self._data:
            del self._data[key]
            self.save()
            return True
        return False

    def has(self, key: str) -> bool:
        """Check if key exists in memory.

        Args:
            key: Memory key identifier.

        Returns:
            True if key exists.
        """
        return key in self._data

    def clear(self) -> None:
        """Clear all stored workspace memory and persist."""
        self._data.clear()
        self.save()

    def list_keys(self) -> list[str]:
        """List all stored keys in memory.

        Returns:
            List of key names.
        """
        return list(self._data.keys())

    def build_system_context(self) -> str:
        """Format stored workspace memory as a system prompt context snippet.

        Returns:
            Formatted string representation of workspace memory.
        """
        if not self._data:
            return ""

        lines = ["--- Workspace Context Memory ---"]
        for k, v in self._data.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
