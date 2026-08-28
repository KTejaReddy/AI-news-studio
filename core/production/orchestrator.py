"""ProductionOrchestrator — master controller for the AI News Studio production pipeline.

This is the primary public API for the production module. It wires together all
existing engines (Director, B-Roll, Voice, Motion, LipSync, Presenter, Timeline, Export)
into a single coordinated pipeline without modifying or replacing them.

Usage example:
    orchestrator = ProductionOrchestrator(
        workspace_dir=config_mgr.workspace_dir,
        director_engine=director_engine,
        broll_engine=broll_engine,
        voice_engine=voice_engine,
        motion_engine=motion_engine,
        lipsync_engine=lipsync_engine,
        presenter_engine=presenter_engine,
        timeline_engine=timeline_engine,
        export_engine=export_engine,
    )

    config = ProductionJobConfig(
        project_id=project.id,
        script=project.script,
        presenter_id=project.presenter_id,
        voice_id=project.voice_id,
    )
    job = orchestrator.produce(config)
    # job.progress.state, job.progress.overall_progress, job.output_path
"""

import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.director.director_engine import DirectorEngine
from core.broll.broll_engine import BrollEngine
from core.voice.voice_engine import VoiceEngine
from core.motion.motion_engine import MotionEngine
from core.lipsync.lipsync_engine import LipSyncEngine
from core.presenter.presenter_engine import PresenterEngine
from core.timeline.timeline_engine import TimelineEngine
from core.export.export_engine import ExportEngine

from core.production.production_job import ProductionJob, ProductionJobConfig
from core.production.production_pipeline import ProductionPipeline
from core.production.production_scheduler import ProductionScheduler
from core.production.production_history import ProductionHistory
from core.production.dependency_resolver import DependencyResolver
from core.production.production_state import ProductionState, PipelineStage


class ProductionOrchestrator:
    """Master controller that wires all engines into a unified production pipeline.

    Responsibilities:
    - Accept job submissions from the GUI or CLI
    - Resolve dependency/caching state for intelligent resumption
    - Schedule and dispatch jobs via ProductionScheduler
    - Report live progress through registered callbacks
    - Persist job history for session recall

    This class does NOT modify, replace, or duplicate any existing engine. It
    exclusively uses their public APIs.
    """

    def __init__(
        self,
        workspace_dir: Path,
        director_engine: DirectorEngine,
        broll_engine: BrollEngine,
        voice_engine: VoiceEngine,
        motion_engine: MotionEngine,
        lipsync_engine: LipSyncEngine,
        presenter_engine: PresenterEngine,
        timeline_engine: TimelineEngine,
        export_engine: ExportEngine,
        max_concurrent_jobs: int = 1,
    ) -> None:
        """Initialize the ProductionOrchestrator.

        Args:
            workspace_dir: Root application workspace directory.
            director_engine: DirectorEngine — scene planning.
            broll_engine: BrollEngine — B-roll asset generation.
            voice_engine: VoiceEngine — voice cloning / synthesis.
            motion_engine: MotionEngine — body motion animation.
            lipsync_engine: LipSyncEngine — mouth-to-audio synchronization.
            presenter_engine: PresenterEngine — portrait animation.
            timeline_engine: TimelineEngine — multi-track timeline assembly.
            export_engine: ExportEngine — final video encoding.
            max_concurrent_jobs: Maximum number of jobs to run simultaneously.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)

        # Shared sub-systems
        self.history = ProductionHistory(self.workspace_dir)
        self.resolver = DependencyResolver(self.workspace_dir)

        # Production pipeline (stateless executor)
        self.pipeline = ProductionPipeline(
            workspace_dir=self.workspace_dir,
            director_engine=director_engine,
            broll_engine=broll_engine,
            voice_engine=voice_engine,
            motion_engine=motion_engine,
            lipsync_engine=lipsync_engine,
            presenter_engine=presenter_engine,
            timeline_engine=timeline_engine,
            export_engine=export_engine,
        )

        # Job scheduler / queue manager
        self.scheduler = ProductionScheduler(
            pipeline=self.pipeline,
            resolver=self.resolver,
            max_concurrent=max_concurrent_jobs,
        )

        # Wire history recording to the scheduler's completion events
        self.scheduler.register_progress_callback(self._on_job_progress)

        self._logger.info(
            f"ProductionOrchestrator initialized "
            f"(workspace={self.workspace_dir}, max_concurrent={max_concurrent_jobs})."
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def produce(
        self,
        config: ProductionJobConfig,
        priority: int = 5,
        on_progress: Optional[Callable[[ProductionJob], None]] = None,
    ) -> ProductionJob:
        """Submit a new production job to the pipeline queue.

        Args:
            config: Configuration describing the project, presenter, voice, and
                    quality settings for the production run.
            priority: Scheduling priority (lower value = higher priority; default 5).
            on_progress: Optional per-job callback that is invoked on every state
                         transition and stage completion.

        Returns:
            The created ProductionJob. Progress can be monitored through
            ``job.progress`` or the ``on_progress`` callback.
        """
        job = ProductionJob(config)
        self._logger.info(
            f"Submitting production job {job.job_id[:8]} "
            f"for project '{config.project_id}' (priority={priority})."
        )

        if on_progress:
            # Wrap callback to only fire for this specific job
            def _filtered_callback(updated_job: ProductionJob) -> None:
                if updated_job.job_id == job.job_id:
                    on_progress(updated_job)

            self.scheduler.register_progress_callback(_filtered_callback)

        return self.scheduler.submit(job, priority=priority)

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a queued or running production job.

        Args:
            job_id: Target job UUID.

        Returns:
            True if the cancellation request was accepted.
        """
        result = self.scheduler.cancel(job_id)
        if result:
            self._logger.info(f"Cancellation accepted for job {job_id[:8]}.")
        else:
            self._logger.warning(f"Cannot cancel job {job_id[:8]} — not found or already terminal.")
        return result

    def pause_queue(self) -> None:
        """Pause processing of all queued jobs. Running jobs continue until complete."""
        self.scheduler.pause_all()

    def resume_queue(self) -> None:
        """Resume processing of paused queued jobs."""
        self.scheduler.resume_all()

    def get_job(self, job_id: str) -> Optional[ProductionJob]:
        """Retrieve a job's current state by its ID.

        Args:
            job_id: Target job UUID.

        Returns:
            ProductionJob or None if not found.
        """
        return self.scheduler.get_job(job_id)

    def get_queue(self) -> List[ProductionJob]:
        """Return all known jobs in submission order.

        Returns:
            List of all ProductionJob instances.
        """
        return self.scheduler.get_queue_snapshot()

    def get_active_jobs(self) -> List[ProductionJob]:
        """Return currently executing production jobs.

        Returns:
            List of ProductionJob instances in the RUNNING state.
        """
        return self.scheduler.get_active_jobs()

    def get_history(
        self,
        project_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Return recent completed job records.

        Args:
            project_id: Optional project filter.
            limit: Maximum records to return.

        Returns:
            List of job record dictionaries, newest first.
        """
        return self.history.get_recent(project_id=project_id, limit=limit)

    def register_progress_callback(
        self, callback: Callable[[ProductionJob], None]
    ) -> None:
        """Register a global progress callback for all jobs.

        Args:
            callback: Callable receiving the updated ProductionJob on every event.
        """
        self.scheduler.register_progress_callback(callback)

    def shutdown(self) -> None:
        """Gracefully shut down the orchestrator and all background threads."""
        self._logger.info("Shutting down ProductionOrchestrator...")
        self.scheduler.shutdown()
        self._logger.info("ProductionOrchestrator shutdown complete.")

    # ── Stage Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def list_stages() -> List[Dict]:
        """Return metadata for all pipeline stages in execution order.

        Returns:
            List of dicts with 'stage', 'label', and 'index' keys.
        """
        return [
            {
                "index": i,
                "stage": stage.value,
                "label": PipelineStage.label(stage),
            }
            for i, stage in enumerate(PipelineStage.ordered())
        ]

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_job_progress(self, job: ProductionJob) -> None:
        """Internal callback for all job transitions — records history on completion.

        Args:
            job: Updated ProductionJob.
        """
        if job.is_terminal:
            try:
                self.history.record_job(job.to_dict())
            except Exception as e:
                self._logger.error(f"Failed to record job history: {e}")
