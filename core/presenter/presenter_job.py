"""Execution job structure for tracking presenter animation requests.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from core.presenter.presenter_config import PresenterConfig


class PresenterJob:
    """Tracks state and progress metrics for a single background video animation task."""

    def __init__(self, config: PresenterConfig, job_id: Optional[str] = None) -> None:
        """Initialize PresenterJob.

        Args:
            config: Config containing paths and parameters.
            job_id: Unique identifier, created if None.
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.config = config
        self.status = "pending"  # pending, downloading_code, downloading_weights, running, completed, failed
        self.progress = 0.0
        self.error_message: Optional[str] = None
        self.output_path: Optional[Path] = None
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
            if status == "completed":
                self.output_path = self.config.output_video_path
        
        if error_message:
            self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert job details to a dictionary."""
        return {
            "job_id": self.job_id,
            "config": self.config.to_dict(),
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "output_path": str(self.output_path) if self.output_path else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
