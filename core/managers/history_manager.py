"""HistoryManager for AI News Studio.

Tracks historical operations, generation logs, and metadata for finished videos
in a central records file.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List


class HistoryManager:
    """Manages project execution logs and lists generation history logs."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the HistoryManager.

        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.history_file = self.workspace_dir / "projects" / "history.json"
        
        # Ensure directory path exists
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._entries: List[Dict[str, Any]] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load history log entries from disk json file."""
        if not self.history_file.exists():
            self._entries = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except Exception as e:
            self._logger.error(f"Failed to read history logs from {self.history_file}: {e}")
            self._entries = []

    def _save_history(self) -> None:
        """Save history log entries to disk json file."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
        except Exception as e:
            self._logger.error(f"Failed to write history logs to {self.history_file}: {e}")

    def add_entry(self, project_id: str, project_name: str, status: str, details: str) -> None:
        """Add a history run log entry.

        Args:
            project_id: Unique project ID mapping.
            project_name: Display name of the project.
            status: Status (e.g. Success, Failed, Started).
            details: Narrative summary or debug detail.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "project_name": project_name,
            "status": status,
            "details": details
        }
        self._entries.insert(0, entry)  # Prepend for newest-first order
        self._save_history()

    def get_entries(self) -> List[Dict[str, Any]]:
        """Retrieve all recorded run actions.

        Returns:
            List of dictionary items outlining task historical details.
        """
        return self._entries.copy()

    def clear_history(self) -> None:
        """Clear all historical run traces from file."""
        self._entries = []
        self._save_history()
        self._logger.info("Generation history log records successfully cleared.")
