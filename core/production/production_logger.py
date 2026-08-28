"""ProductionLogger for the AI Production Orchestrator.

Provides structured, per-job logging with timestamped entries, severity levels,
and both in-memory and file-based persistence.
"""

import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class LogEntry:
    """A single structured log entry in the production log."""

    timestamp: str
    level: str          # INFO | WARNING | ERROR | DEBUG
    stage: str          # PipelineStage.value or "orchestrator"
    message: str
    job_id: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "stage": self.stage,
            "message": self.message,
            "job_id": self.job_id,
        }

    def __str__(self) -> str:
        return f"[{self.timestamp}] [{self.level}] [{self.stage}] {self.message}"


class ProductionLogger:
    """Manages structured per-job log streams with file persistence.

    Each job gets a dedicated log file in the project's logs directory.
    Logs are also mirrored to the standard Python logging system.
    """

    def __init__(self, workspace_dir: Path, job_id: str, project_id: str) -> None:
        """Initialize the ProductionLogger.

        Args:
            workspace_dir: Application workspace path.
            job_id: The unique production job ID.
            project_id: The active project ID.
        """
        self.job_id = job_id
        self.project_id = project_id
        self._entries: List[LogEntry] = []
        self._python_logger = logging.getLogger(f"ProductionJob[{job_id[:8]}]")

        # Establish log file path
        log_dir = workspace_dir / "projects" / project_id / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = log_dir / f"production_{job_id}.jsonl"

    # --- Public Logging Methods ---

    def info(self, message: str, stage: str = "orchestrator") -> None:
        """Log an informational message.

        Args:
            message: Log message content.
            stage: Pipeline stage context label.
        """
        self._log("INFO", stage, message)

    def warning(self, message: str, stage: str = "orchestrator") -> None:
        """Log a warning message.

        Args:
            message: Log message content.
            stage: Pipeline stage context label.
        """
        self._log("WARNING", stage, message)

    def error(self, message: str, stage: str = "orchestrator") -> None:
        """Log an error message.

        Args:
            message: Log message content.
            stage: Pipeline stage context label.
        """
        self._log("ERROR", stage, message)

    def debug(self, message: str, stage: str = "orchestrator") -> None:
        """Log a debug message.

        Args:
            message: Log message content.
            stage: Pipeline stage context label.
        """
        self._log("DEBUG", stage, message)

    def get_entries(self, level: Optional[str] = None) -> List[LogEntry]:
        """Return all log entries, optionally filtered by level.

        Args:
            level: Optional severity level filter (e.g., 'ERROR', 'INFO').

        Returns:
            List of matching LogEntry objects.
        """
        if level:
            return [e for e in self._entries if e.level == level.upper()]
        return list(self._entries)

    def get_log_file_path(self) -> Path:
        """Return path to the JSONL log file for this job.

        Returns:
            Path to the log file.
        """
        return self._log_file

    # --- Internal ---

    def _log(self, level: str, stage: str, message: str) -> None:
        """Create and persist a log entry.

        Args:
            level: Severity level string.
            stage: Stage context string.
            message: Message text.
        """
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            stage=stage,
            message=message,
            job_id=self.job_id,
        )
        self._entries.append(entry)

        # Mirror to Python standard logger
        log_fn = {
            "INFO": self._python_logger.info,
            "WARNING": self._python_logger.warning,
            "ERROR": self._python_logger.error,
            "DEBUG": self._python_logger.debug,
        }.get(level, self._python_logger.info)
        log_fn(f"[{stage}] {message}")

        # Append to file
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception:
            pass  # Don't crash the pipeline due to logging failure
