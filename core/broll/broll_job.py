"""Execution job structure for B-roll generation tasks.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from core.director.scene_plan import ScenePlan
from core.broll.broll_config import BrollConfig
from core.broll.scene_asset import SceneAsset


class BrollJob:
    """Tracks state and progress parameters for a background B-roll generation task."""

    def __init__(self, scene_plan: ScenePlan, config: BrollConfig, job_id: Optional[str] = None) -> None:
        """Initialize BrollJob.

        Args:
            scene_plan: ScenePlan configurations.
            config: Job configuration settings.
            job_id: Unique UUID identifier, created if None.
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.scene_plan = scene_plan
        self.config = config
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.error_message: Optional[str] = None
        self.output_asset: Optional[SceneAsset] = None
        self.output_path: Optional[Path] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def update_status(self, status: str, progress: float, error_message: Optional[str] = None, output_asset: Optional[SceneAsset] = None) -> None:
        """Update job status and progress parameters.

        Args:
            status: Active state name.
            progress: Progress ratio (0.0 to 1.0).
            error_message: Optional traceback or explanation if failed.
            output_asset: Optional generated SceneAsset.
        """
        self.status = status
        self.progress = max(0.0, min(1.0, progress))

        if status == "running" and self.started_at is None:
            self.started_at = datetime.now()

        if status in ["completed", "failed"]:
            self.completed_at = datetime.now()
            if status == "completed" and output_asset:
                self.output_asset = output_asset
                self.output_path = Path(output_asset.file_path)

        if error_message:
            self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert job details to a dictionary."""
        return {
            "job_id": self.job_id,
            "scene_plan": self.scene_plan.to_dict(),
            "config": self.config.to_dict(),
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "output_asset": self.output_asset.to_dict() if self.output_asset else None,
            "output_path": str(self.output_path) if self.output_path else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
