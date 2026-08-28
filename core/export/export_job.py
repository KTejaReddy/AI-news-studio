"""ExportJob representing a single background transcode export task.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from core.export.export_settings import ExportSettings


class ExportJob:
    """Tracks compression parameters, speeds, time remaining, and completion status."""

    def __init__(
        self,
        output_path: Path,
        settings: ExportSettings,
        input_path: Optional[Path] = None,
        srt_content: str = "",
        job_id: Optional[str] = None
    ) -> None:
        """Initialize ExportJob.

        Args:
            output_path: Final target file destination.
            settings: ExportSettings object.
            input_path: Optional input video file path to transcode.
            srt_content: Optional SRT subtitle text.
            job_id: Unique UUID identifier.
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.output_path = Path(output_path)
        self.input_path = Path(input_path) if input_path else None
        self.srt_content = srt_content
        self.settings = settings
        
        self.status = "pending"  # pending, running, paused, completed, failed
        self.progress = 0.0
        self.frames_rendered = 0
        self.total_frames = 0
        self.render_speed = 0.0  # fps
        self.time_remaining = 0.0  # seconds
        self.error_message: Optional[str] = None

        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def update_progress(
        self,
        frames_rendered: int,
        total_frames: int,
        render_speed: float,
        time_remaining: float
    ) -> None:
        """Update progress metrics during transcode runs."""
        self.frames_rendered = frames_rendered
        self.total_frames = total_frames
        self.render_speed = render_speed
        self.time_remaining = time_remaining
        
        if total_frames > 0:
            self.progress = max(0.0, min(1.0, frames_rendered / total_frames))
        else:
            self.progress = 0.0

    def update_status(self, status: str, error_message: Optional[str] = None) -> None:
        """Update active state changes."""
        self.status = status

        if status == "running" and self.started_at is None:
            self.started_at = datetime.now()

        if status in ["completed", "failed"]:
            self.completed_at = datetime.now()
            if status == "completed":
                self.progress = 1.0

        if error_message:
            self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert job details to a dictionary."""
        return {
            "job_id": self.job_id,
            "output_path": str(self.output_path),
            "input_path": str(self.input_path) if self.input_path else None,
            "srt_content": self.srt_content,
            "settings": self.settings.to_dict(),
            "status": self.status,
            "progress": self.progress,
            "frames_rendered": self.frames_rendered,
            "total_frames": self.total_frames,
            "render_speed": self.render_speed,
            "time_remaining": self.time_remaining,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportJob":
        """Deserialize an ExportJob instance from a dictionary."""
        settings = ExportSettings.from_dict(data["settings"])
        input_path = Path(data["input_path"]) if data.get("input_path") else None
        job = cls(
            output_path=Path(data["output_path"]),
            settings=settings,
            input_path=input_path,
            srt_content=data.get("srt_content", ""),
            job_id=data["job_id"]
        )
        job.status = data.get("status", "pending")
        job.progress = float(data.get("progress", 0.0))
        job.frames_rendered = int(data.get("frames_rendered", 0))
        job.total_frames = int(data.get("total_frames", 0))
        job.render_speed = float(data.get("render_speed", 0.0))
        job.time_remaining = float(data.get("time_remaining", 0.0))
        job.error_message = data.get("error_message")
        
        # Load times
        if data.get("created_at"):
            job.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            job.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            job.completed_at = datetime.fromisoformat(data["completed_at"])
        return job
