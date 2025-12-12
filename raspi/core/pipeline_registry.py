"""
Pipeline Registry for AdaptLight.

Stores defined pipelines that can be triggered by rules or executed directly.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


def _get_storage_dir():
    """Get the storage directory path (raspi/storage)."""
    # Get the directory containing this file (raspi/core/)
    current_dir = Path(__file__).parent
    # Go up one level to raspi/, then into storage/
    raspi_dir = current_dir.parent
    storage_dir = raspi_dir / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


class PipelineRegistry:
    """Registry for storing and managing pipelines."""

    def __init__(self, filepath: str = None):
        """
        Initialize pipeline registry.

        Args:
            filepath: Path to JSON file for persistence.
                      Defaults to raspi/storage/pipelines.json
        """
        if filepath is None:
            storage_dir = _get_storage_dir()
            filepath = str(storage_dir / "pipelines.json")

        self.filepath = filepath
        self._pipelines: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        """Load pipelines from file."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f:
                    self._pipelines = json.load(f)
                print(f"Pipelines loaded: {len(self._pipelines)} from {self.filepath}")
            except Exception as e:
                print(f"Error loading pipelines: {e}")
                self._pipelines = {}
        else:
            self._pipelines = {}

    def _save(self):
        """Save pipelines to file."""
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self._pipelines, f, indent=2)
        except Exception as e:
            print(f"Error saving pipelines: {e}")

    def register(self, name: str, steps: List[Dict[str, Any]], description: str = "") -> None:
        """
        Register a pipeline.

        Args:
            name: Pipeline name
            steps: List of step definitions
            description: Human-readable description
        """
        self._pipelines[name] = {
            "name": name,
            "steps": steps,
            "description": description
        }
        self._save()
        print(f"Pipeline registered: {name} ({len(steps)} steps)")

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a pipeline by name.

        Args:
            name: Pipeline name

        Returns:
            Pipeline definition or None
        """
        return self._pipelines.get(name)

    def delete(self, name: str) -> bool:
        """
        Delete a pipeline.

        Args:
            name: Pipeline name

        Returns:
            True if deleted, False if not found
        """
        if name in self._pipelines:
            del self._pipelines[name]
            self._save()
            print(f"Pipeline deleted: {name}")
            return True
        return False

    def list(self) -> List[Dict[str, Any]]:
        """
        List all pipelines.

        Returns:
            List of pipeline summaries
        """
        return [
            {
                "name": p["name"],
                "description": p.get("description", ""),
                "steps": len(p["steps"])
            }
            for p in self._pipelines.values()
        ]

    def clear(self) -> None:
        """Clear all pipelines."""
        self._pipelines = {}
        self._save()
        print("All pipelines cleared")


# Global singleton instance
_registry_instance: Optional[PipelineRegistry] = None


def get_pipeline_registry() -> PipelineRegistry:
    """Get the global pipeline registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = PipelineRegistry()
    return _registry_instance
