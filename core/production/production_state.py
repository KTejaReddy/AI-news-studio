"""ProductionState and ProductionProgress for the AI Production Orchestrator.

Defines shared enumerations and data structures for tracking production job state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ProductionState(Enum):
    """Enumerated lifecycle states for a production job."""

    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class PipelineStage(Enum):
    """Enumerated ordered stages of the production pipeline."""

    PARSE_SCRIPT = "parse_script"
    DIRECTOR_PLAN = "director_plan"
    ASSIGN_PRESENTER = "assign_presenter"
    GENERATE_VOICE = "generate_voice"
    GENERATE_MOTION = "generate_motion"
    GENERATE_LIPSYNC = "generate_lipsync"
    GENERATE_BROLL = "generate_broll"
    ASSEMBLE_TIMELINE = "assemble_timeline"
    RENDER_PREVIEW = "render_preview"
    EXPORT_FINAL = "export_final"

    @classmethod
    def ordered(cls) -> List["PipelineStage"]:
        """Return all stages in correct execution order."""
        return [
            cls.PARSE_SCRIPT,
            cls.DIRECTOR_PLAN,
            cls.ASSIGN_PRESENTER,
            cls.GENERATE_VOICE,
            cls.GENERATE_MOTION,
            cls.GENERATE_LIPSYNC,
            cls.GENERATE_BROLL,
            cls.ASSEMBLE_TIMELINE,
            cls.RENDER_PREVIEW,
            cls.EXPORT_FINAL,
        ]

    @classmethod
    def label(cls, stage: "PipelineStage") -> str:
        """Human-readable label for a stage."""
        labels = {
            cls.PARSE_SCRIPT: "Parsing Script",
            cls.DIRECTOR_PLAN: "Director Planning Scenes",
            cls.ASSIGN_PRESENTER: "Assigning Presenter",
            cls.GENERATE_VOICE: "Generating Voice Track",
            cls.GENERATE_MOTION: "Generating Body Motion",
            cls.GENERATE_LIPSYNC: "Applying Lip Sync",
            cls.GENERATE_BROLL: "Generating B-Roll",
            cls.ASSEMBLE_TIMELINE: "Assembling Timeline",
            cls.RENDER_PREVIEW: "Rendering Preview",
            cls.EXPORT_FINAL: "Exporting Final Video",
        }
        return labels.get(stage, stage.value)


@dataclass
class StageResult:
    """Result and timing metadata for a single pipeline stage execution."""

    stage: PipelineStage
    status: str = "pending"   # pending | running | completed | failed | skipped
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    error_message: str = ""
    output_data: Dict[str, Any] = field(default_factory=dict)
    was_cached: bool = False

    def start(self) -> None:
        """Mark stage as started and record start timestamp."""
        self.status = "running"
        self.started_at = datetime.now().isoformat()

    def complete(self, output_data: Optional[Dict[str, Any]] = None, cached: bool = False) -> None:
        """Mark stage as completed and record elapsed duration.

        Args:
            output_data: Optional dictionary of stage outputs (paths, metadata, etc.).
            cached: True if result was served from cache.
        """
        self.status = "completed"
        self.finished_at = datetime.now().isoformat()
        self.was_cached = cached
        if output_data:
            self.output_data = output_data
        if self.started_at:
            start_dt = datetime.fromisoformat(self.started_at)
            self.duration_seconds = (datetime.now() - start_dt).total_seconds()

    def fail(self, error_message: str) -> None:
        """Mark stage as failed.

        Args:
            error_message: Description of the failure.
        """
        self.status = "failed"
        self.finished_at = datetime.now().isoformat()
        self.error_message = error_message
        if self.started_at:
            start_dt = datetime.fromisoformat(self.started_at)
            self.duration_seconds = (datetime.now() - start_dt).total_seconds()

    def skip(self, reason: str = "") -> None:
        """Mark stage as skipped.

        Args:
            reason: Explanation for skipping (e.g. 'cached').
        """
        self.status = "skipped"
        self.error_message = reason

    def to_dict(self) -> Dict[str, Any]:
        """Serialize stage result to a dictionary."""
        return {
            "stage": self.stage.value,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "was_cached": self.was_cached,
        }


@dataclass
class ProductionProgress:
    """Aggregated progress snapshot for a production job."""

    job_id: str
    state: ProductionState = ProductionState.IDLE
    current_stage: Optional[PipelineStage] = None
    stage_index: int = 0
    total_stages: int = len(PipelineStage.ordered())
    overall_progress: float = 0.0   # 0.0 to 1.0
    stage_progress: float = 0.0     # 0.0 to 1.0 within current stage
    stage_results: List[StageResult] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: str = ""

    @property
    def is_terminal(self) -> bool:
        """True if the job has reached a terminal state (done/failed/cancelled)."""
        return self.state in (
            ProductionState.COMPLETED,
            ProductionState.FAILED,
            ProductionState.CANCELLED,
        )

    def advance_to_stage(self, stage: PipelineStage) -> StageResult:
        """Move progress tracker to the next pipeline stage.

        Args:
            stage: The PipelineStage that is starting.

        Returns:
            A fresh StageResult object for the stage.
        """
        ordered = PipelineStage.ordered()
        if stage in ordered:
            self.stage_index = ordered.index(stage)
        self.current_stage = stage
        self.stage_progress = 0.0
        self.overall_progress = self.stage_index / self.total_stages

        result = StageResult(stage=stage)
        result.start()
        self.stage_results.append(result)
        return result

    def get_stage_result(self, stage: PipelineStage) -> Optional[StageResult]:
        """Retrieve the StageResult for a given stage.

        Args:
            stage: Target PipelineStage.

        Returns:
            StageResult or None if stage hasn't been recorded.
        """
        for r in self.stage_results:
            if r.stage == stage:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize progress snapshot to a dictionary."""
        return {
            "job_id": self.job_id,
            "state": self.state.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "stage_index": self.stage_index,
            "total_stages": self.total_stages,
            "overall_progress": self.overall_progress,
            "stage_progress": self.stage_progress,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error_message": self.error_message,
            "stage_results": [r.to_dict() for r in self.stage_results],
        }
