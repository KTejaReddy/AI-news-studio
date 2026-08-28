"""ProductionJob model for the AI Production Orchestrator.

Tracks the configuration and lifecycle of a single end-to-end production run.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.production.production_state import ProductionProgress, ProductionState, PipelineStage


@dataclass
class ProductionJobConfig:
    """Input parameters required to start a production job."""

    project_id: str
    script: str
    presenter_id: str
    voice_id: str
    aspect_ratio: str = "16:9"
    quality: str = "High"
    codec: str = "H264"
    fps: int = 30
    output_path: Optional[Path] = None
    device: str = "cuda"
    generate_preview: bool = True
    use_cache: bool = True
    skip_stages: List[PipelineStage] = field(default_factory=list)
    max_retries: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to dictionary."""
        return {
            "project_id": self.project_id,
            "script": self.script[:120] + "..." if len(self.script) > 120 else self.script,
            "presenter_id": self.presenter_id,
            "voice_id": self.voice_id,
            "aspect_ratio": self.aspect_ratio,
            "quality": self.quality,
            "codec": self.codec,
            "fps": self.fps,
            "output_path": str(self.output_path) if self.output_path else None,
            "device": self.device,
            "generate_preview": self.generate_preview,
            "use_cache": self.use_cache,
            "max_retries": self.max_retries,
            "skip_stages": [s.value for s in self.skip_stages],
        }


class ProductionJob:
    """Represents a single submitted production pipeline execution request.

    Encapsulates configuration, progress tracking, stage results, and output references.
    """

    def __init__(self, config: ProductionJobConfig) -> None:
        """Initialize a ProductionJob.

        Args:
            config: Configuration inputs describing what to produce.
        """
        self.job_id: str = str(uuid.uuid4())
        self.config: ProductionJobConfig = config
        self.created_at: str = datetime.now().isoformat()
        self.progress: ProductionProgress = ProductionProgress(job_id=self.job_id)
        self.retry_count: int = 0

        # Intermediate artifact output paths set during execution
        self.scene_plans: List[Any] = []          # List[ScenePlan]
        self.voice_audio_paths: List[Path] = []
        self.motion_video_paths: List[Path] = []
        self.lipsync_video_paths: List[Path] = []
        self.broll_asset_paths: List[Path] = []
        self.preview_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.srt_content: str = ""

    @property
    def status(self) -> str:
        """Current state string of the job."""
        return self.progress.state.value

    @property
    def is_terminal(self) -> bool:
        """True when the job has reached a terminal state."""
        return self.progress.is_terminal

    def _transition_state(self, new_state: ProductionState) -> None:
        """Internal helper to update state with timestamp tracking.

        Args:
            new_state: Target ProductionState.
        """
        self.progress.state = new_state
        if new_state == ProductionState.RUNNING and not self.progress.started_at:
            self.progress.started_at = datetime.now().isoformat()
        if new_state in (
            ProductionState.COMPLETED,
            ProductionState.FAILED,
            ProductionState.CANCELLED,
        ):
            self.progress.finished_at = datetime.now().isoformat()
            self.progress.overall_progress = 1.0 if new_state == ProductionState.COMPLETED else self.progress.overall_progress

    def mark_running(self) -> None:
        """Transition job to the RUNNING state."""
        self._transition_state(ProductionState.RUNNING)

    def mark_completed(self, output_path: Path) -> None:
        """Mark job as successfully completed.

        Args:
            output_path: Final output video path.
        """
        self.output_path = output_path
        self._transition_state(ProductionState.COMPLETED)
        self.progress.overall_progress = 1.0

    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed with an error message.

        Args:
            error_message: Description of the failure.
        """
        self.progress.error_message = error_message
        self._transition_state(ProductionState.FAILED)

    def mark_cancelled(self) -> None:
        """Transition job to the CANCELLED state."""
        self._transition_state(ProductionState.CANCELLED)

    def mark_queued(self) -> None:
        """Transition job to the QUEUED state."""
        self._transition_state(ProductionState.QUEUED)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize job metadata to a dictionary.

        Returns:
            Dictionary containing all job information.
        """
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "config": self.config.to_dict(),
            "progress": self.progress.to_dict(),
            "retry_count": self.retry_count,
            "output_path": str(self.output_path) if self.output_path else None,
            "preview_path": str(self.preview_path) if self.preview_path else None,
        }
