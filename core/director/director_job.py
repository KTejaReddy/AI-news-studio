"""Execution job structure for AI Director script analysis tasks.
"""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from core.director.director_config import DirectorConfig
from core.director.scene_timeline import SceneTimeline


class DirectorJob:
    """Tracks state and progress parameters for a background script analysis task."""

    def __init__(self, config: DirectorConfig, job_id: Optional[str] = None) -> None:
        """Initialize DirectorJob.

        Args:
            config: Job configuration settings.
            job_id: Unique UUID identifier, created if None.
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.config = config
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.error_message: Optional[str] = None
        self.output_timeline: Optional[SceneTimeline] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def update_status(
        self,
        status: str,
        progress: float,
        error_message: Optional[str] = None,
        timeline: Optional[SceneTimeline] = None
    ) -> None:
        """Update job status and progress parameters."""
        self.status = status
        self.progress = max(0.0, min(1.0, progress))

        if status == "running" and self.started_at is None:
            self.started_at = datetime.now()

        if status in ["completed", "failed"]:
            self.completed_at = datetime.now()
            if status == "completed" and timeline:
                self.output_timeline = timeline

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
            "output_timeline": self.output_timeline.to_json() if self.output_timeline else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
