"""ExportHistory manager for saving, loading, and listing completed exports history metadata.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from core.export.export_job import ExportJob


class ExportHistory:
    """Manages history registry logs of all successfully processed outputs."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize ExportHistory.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.history_dir = self.workspace_dir / "core" / "export" / "history"
        self.history_file = self.history_dir / "export_history.json"
        
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(self.__class__.__name__)
        self.entries: List[Dict[str, Any]] = []
        self.load_history()

    def load_history(self) -> None:
        """Load history list from JSON file."""
        if not self.history_file.exists():
            self.entries = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
            self._logger.info(f"Loaded {len(self.entries)} entries from export history.")
        except Exception as e:
            self._logger.error(f"Failed to load export history: {e}")
            self.entries = []

    def save_history(self) -> None:
        """Save history list to JSON file."""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=4)
        except Exception as e:
            self._logger.error(f"Failed to save export history: {e}")

    def add_entry(self, job: ExportJob) -> None:
        """Add a completed job details entry.

        Args:
            job: ExportJob to record.
        """
        entry = {
            "job_id": job.job_id,
            "output_path": str(job.output_path),
            "preset": job.settings.preset,
            "resolution": f"{job.settings.width}x{job.settings.height}",
            "codec": job.settings.codec,
            "fps": job.settings.fps,
            "container": job.settings.container,
            "completed_at": job.completed_at.isoformat() if job.completed_at else "",
            "file_size_bytes": 0  # will verify in worker run
        }

        # Try to resolve actual file size on disk
        abs_path = self.workspace_dir / job.output_path
        if abs_path.exists():
            entry["file_size_bytes"] = abs_path.stat().st_size
        else:
            # check direct absolute path
            try:
                p = Path(job.output_path)
                if p.exists():
                    entry["file_size_bytes"] = p.stat().st_size
            except Exception:
                pass

        self.entries.insert(0, entry) # Prepend to show newest first
        self.save_history()

    def list_entries(self) -> List[Dict[str, Any]]:
        """List all historical entries.

        Returns:
            List of dictionaries.
        """
        return self.entries

    def clear_history(self) -> None:
        """Reset the export history file."""
        self.entries = []
        if self.history_file.exists():
            try:
                self.history_file.unlink()
            except Exception as e:
                self._logger.error(f"Failed to delete history file: {e}")
        self.save_history()
        self._logger.info("Export history cleared.")
