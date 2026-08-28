"""ProductionHistory for the AI Production Orchestrator.

Maintains a persistent record of all past production jobs for a project,
including their final state, timing, and output paths.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ProductionHistory:
    """Manages serialized records of completed, failed, and cancelled production jobs.

    Records are stored as a JSONL file per project directory so the history
    survives application restarts.
    """

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize ProductionHistory.

        Args:
            workspace_dir: Application workspace root path.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._in_memory: List[Dict[str, Any]] = []

    def record_job(self, job_dict: Dict[str, Any]) -> None:
        """Append a completed/failed job record to history.

        Args:
            job_dict: Serialized job dictionary from ``ProductionJob.to_dict()``.
        """
        record = dict(job_dict)
        record.setdefault("recorded_at", datetime.now().isoformat())
        self._in_memory.append(record)

        # Persist to project-specific history file
        project_id = record.get("config", {}).get("project_id", "unknown")
        history_file = self._get_history_file(project_id)
        try:
            with open(history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            self._logger.error(f"Failed to write production history: {e}")

    def get_recent(self, project_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent job history records.

        Args:
            project_id: Optional filter by project ID.
            limit: Maximum number of entries to return.

        Returns:
            List of job record dictionaries, newest first.
        """
        records = self._load_all(project_id)
        records.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)
        return records[:limit]

    def get_job_record(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Look up a specific job record by ID.

        Args:
            job_id: The target job UUID.

        Returns:
            Job record dictionary or None if not found.
        """
        for record in self._in_memory:
            if record.get("job_id") == job_id:
                return record
        return None

    def clear_project_history(self, project_id: str) -> None:
        """Delete the history file for a specific project.

        Args:
            project_id: Target project UUID.
        """
        history_file = self._get_history_file(project_id)
        if history_file.exists():
            try:
                history_file.unlink()
                self._logger.info(f"Cleared production history for project {project_id}.")
            except Exception as e:
                self._logger.error(f"Failed to clear history for {project_id}: {e}")

        # Remove matching in-memory records
        self._in_memory = [
            r for r in self._in_memory
            if r.get("config", {}).get("project_id") != project_id
        ]

    # --- Internal ---

    def _get_history_file(self, project_id: str) -> Path:
        """Return path to the project history JSONL file.

        Args:
            project_id: Target project UUID.

        Returns:
            Path to the history file.
        """
        history_dir = self.workspace_dir / "projects" / project_id / "logs"
        history_dir.mkdir(parents=True, exist_ok=True)
        return history_dir / "production_history.jsonl"

    def _load_all(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load all history records from disk for a given project.

        Args:
            project_id: Project filter, or None to use in-memory records only.

        Returns:
            Combined list of job record dictionaries.
        """
        if project_id is None:
            return list(self._in_memory)

        history_file = self._get_history_file(project_id)
        if not history_file.exists():
            return []

        records: List[Dict[str, Any]] = []
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self._logger.error(f"Error reading history file {history_file}: {e}")

        return records
