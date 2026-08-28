"""Execution job structure for background video rendering tasks.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid


class TimelineRenderJob:
    """Tracks state and progress parameters for a background timeline compilation render task."""

    def __init__(self, output_path: Path, job_id: Optional[str] = None) -> None:
        """Initialize TimelineRenderJob.

        Args:
            output_path: Target video file path to write composite MP4.
            job_id: Unique UUID identifier, created if None.
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.output_path = Path(output_path)
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.error_message: Optional[str] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def update_status(self, status: str, progress: float, error_message: Optional[str] = None) -> None:
        """Update job status and progress parameters.

        Args:
            status: Active state name.
            progress: Progress ratio (0.0 to 1.0).
            error_message: Optional traceback or explanation if failed.
        """
        self.status = status
        self.progress = max(0.0, min(1.0, progress))

        if status == "running" and self.started_at is None:
            self.started_at = datetime.now()

        if status in ["completed", "failed"]:
            self.completed_at = datetime.now()

        if error_message:
            self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert job details to a dictionary."""
        return {
            "job_id": self.job_id,
            "output_path": str(self.output_path),
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
