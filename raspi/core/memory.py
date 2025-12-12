"""
Memory module for AdaptLight.

Persistent key-value store for agent memory (location, preferences, etc.)
Saves to JSON file so memories persist across restarts.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _get_storage_dir():
    """Get the storage directory path (raspi/storage)."""
    # Get the directory containing this file (raspi/core/)
    current_dir = Path(__file__).parent
    # Go up one level to raspi/, then into storage/
    raspi_dir = current_dir.parent
    storage_dir = raspi_dir / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


class Memory:
    """Persistent memory store for the agent."""

    def __init__(self, filepath: str = None):
        """
        Initialize memory store.

        Args:
            filepath: Path to JSON file for persistence.
                      Defaults to raspi/storage/memory.json
        """
        if filepath is None:
            storage_dir = _get_storage_dir()
            filepath = str(storage_dir / "memory.json")

        self.filepath = filepath
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load memory from file."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self._data = json.load(f)
                print(f"Memory loaded: {len(self._data)} items from {self.filepath}")
            except Exception as e:
                print(f"Error loading memory: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        """Save memory to file."""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in memory.

        Args:
            key: Memory key (e.g., "location", "favorite_color")
            value: Value to store (any JSON-serializable type)
        """
        self._data[key] = value
        self._save()
        print(f"Memory set: {key} = {value}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from memory.

        Args:
            key: Memory key to retrieve
            default: Default value if key not found

        Returns:
            Stored value or default
        """
        return self._data.get(key, default)

    def delete(self, key: str) -> bool:
        """
        Delete a value from memory.

        Args:
            key: Memory key to delete

        Returns:
            True if deleted, False if key not found
        """
        if key in self._data:
            del self._data[key]
            self._save()
            print(f"Memory deleted: {key}")
            return True
        return False

    def list(self) -> Dict[str, Any]:
        """
        List all memories.

        Returns:
            Dict of all stored key-value pairs
        """
        return dict(self._data)

    def clear(self) -> None:
        """Clear all memories."""
        self._data = {}
        self._save()
        print("Memory cleared")


# Global singleton instance
_memory_instance: Optional[Memory] = None


def get_memory() -> Memory:
    """Get the global memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = Memory()
    return _memory_instance
