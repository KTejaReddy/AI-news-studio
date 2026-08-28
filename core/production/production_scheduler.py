"""ProductionScheduler for the AI Production Orchestrator.

Manages the production job queue, dispatches jobs to background worker threads,
and enforces concurrency limits.
"""

import logging
import queue
import threading
from typing import Callable, Dict, List, Optional

from core.production.production_job import ProductionJob
from core.production.production_pipeline import ProductionPipeline, ProgressCallback
from core.production.production_state import ProductionState, PipelineStage
from core.production.dependency_resolver import DependencyResolver


class ProductionScheduler:
    """Manages the lifecycle of queued production jobs and dispatches them
    to background threads via ProductionPipeline.

    Supports:
    - Configurable max concurrent job slots (default: 1)
    - Priority-based queuing (higher priority runs first)
    - Per-job cancellation
    - Global pause / resume of all queued work
    """

    def __init__(
        self,
        pipeline: ProductionPipeline,
        resolver: DependencyResolver,
        max_concurrent: int = 1,
    ) -> None:
        """Initialize the ProductionScheduler.

        Args:
            pipeline: The shared ProductionPipeline instance.
            resolver: DependencyResolver for cache analysis.
            max_concurrent: Maximum jobs to run simultaneously.
        """
        self.pipeline = pipeline
        self.resolver = resolver
        self.max_concurrent = max_concurrent

        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._active_jobs: Dict[str, threading.Thread] = {}
        self._all_jobs: Dict[str, ProductionJob] = {}
        self._lock = threading.Lock()
        self._paused = threading.Event()
        self._paused.set()  # Start unpaused
        self._shutdown_flag = False

        self._progress_callbacks: List[ProgressCallback] = []
        self._logger = logging.getLogger(self.__class__.__name__)

        # Start dispatcher thread
        self._dispatcher_thread = threading.Thread(
            target=self._dispatch_loop,
            daemon=True,
            name="ProductionScheduler-Dispatcher",
        )
        self._dispatcher_thread.start()
        self._logger.info("ProductionScheduler started.")

    # ── Public API ──────────────────────────────────────────────────────────

    def submit(self, job: ProductionJob, priority: int = 5) -> ProductionJob:
        """Add a job to the production queue.

        Args:
            job: The ProductionJob to schedule.
            priority: Queue priority (lower int = higher priority; default 5).

        Returns:
            The submitted job instance.
        """
        job.mark_queued()
        with self._lock:
            self._all_jobs[job.job_id] = job
        # PriorityQueue uses (priority, seq, job) for stable ordering
        seq = id(job)
        self._queue.put((priority, seq, job))
        self._logger.info(f"Scheduled production job {job.job_id[:8]} (priority={priority}).")
        return job

    def cancel(self, job_id: str) -> bool:
        """Request cancellation of a queued or running job.

        Args:
            job_id: Target job UUID.

        Returns:
            True if the job was found and cancellation was requested.
        """
        with self._lock:
            job = self._all_jobs.get(job_id)
        if not job:
            return False

        if not job.is_terminal:
            job.mark_cancelled()
            self._logger.info(f"Cancellation requested for job {job_id[:8]}.")
            return True
        return False

    def pause_all(self) -> None:
        """Pause dispatching of new jobs from the queue."""
        self._paused.clear()
        self._logger.info("ProductionScheduler paused.")

    def resume_all(self) -> None:
        """Resume dispatching queued jobs."""
        self._paused.set()
        self._logger.info("ProductionScheduler resumed.")

    def shutdown(self, timeout: float = 5.0) -> None:
        """Gracefully stop the scheduler and wait for the dispatcher thread.

        Args:
            timeout: Maximum seconds to wait for dispatcher thread join.
        """
        self._logger.info("Shutting down ProductionScheduler...")
        self._shutdown_flag = True
        self._paused.set()  # Unblock paused dispatcher
        self._dispatcher_thread.join(timeout=timeout)
        self._logger.info("ProductionScheduler shutdown complete.")

    def register_progress_callback(self, callback: ProgressCallback) -> None:
        """Register a callback invoked on every job state change.

        Args:
            callback: Callable receiving the updated ProductionJob.
        """
        self._progress_callbacks.append(callback)

    def get_job(self, job_id: str) -> Optional[ProductionJob]:
        """Retrieve a job by its ID.

        Args:
            job_id: Target job UUID.

        Returns:
            ProductionJob or None.
        """
        with self._lock:
            return self._all_jobs.get(job_id)

    def get_queue_snapshot(self) -> List[ProductionJob]:
        """Return a list of all known jobs, sorted by creation time.

        Returns:
            List of all ProductionJob instances.
        """
        with self._lock:
            jobs = list(self._all_jobs.values())
        jobs.sort(key=lambda j: j.created_at)
        return jobs

    def get_active_jobs(self) -> List[ProductionJob]:
        """Return currently running jobs.

        Returns:
            List of ProductionJob instances in RUNNING state.
        """
        with self._lock:
            return [
                self._all_jobs[jid]
                for jid in self._active_jobs
                if jid in self._all_jobs
            ]

    # ── Internal Dispatcher ─────────────────────────────────────────────────

    def _dispatch_loop(self) -> None:
        """Background thread loop that picks jobs from the queue and runs them."""
        while not self._shutdown_flag:
            # Block until unpaused
            self._paused.wait()

            if self._shutdown_flag:
                break

            # Check capacity
            with self._lock:
                active_count = len(self._active_jobs)

            if active_count >= self.max_concurrent:
                # Wait a short moment before checking again
                threading.Event().wait(0.5)
                continue

            # Attempt to dequeue a non-cancelled job
            try:
                _, _, job = self._queue.get(block=True, timeout=0.5)
            except queue.Empty:
                continue

            # Skip already-cancelled jobs
            if job.progress.state == ProductionState.CANCELLED:
                self._queue.task_done()
                continue

            # Dispatch job to a worker thread
            worker = threading.Thread(
                target=self._run_job,
                args=(job,),
                daemon=True,
                name=f"ProductionWorker-{job.job_id[:8]}",
            )
            with self._lock:
                self._active_jobs[job.job_id] = worker
            worker.start()
            self._queue.task_done()

    def _run_job(self, job: ProductionJob) -> None:
        """Execute a single production job and clean up after completion.

        Args:
            job: The ProductionJob to run.
        """
        self._logger.info(f"Starting production job {job.job_id[:8]}...")
        job.mark_running()
        self._emit_progress(job)

        try:
            # Determine cached stages using the dependency resolver
            num_scenes = 0  # Will be populated after director stage
            storyboard_file = self.resolver.workspace_dir / "projects" / job.config.project_id / "storyboard.json"
            if storyboard_file.exists():
                try:
                    import json
                    with open(storyboard_file, "r", encoding="utf-8") as f:
                        storyboard_data = json.load(f)
                        num_scenes = len(storyboard_data)
                except Exception:
                    pass

            cached = self.resolver.resolve_cached_stages(
                project_id=job.config.project_id,
                num_scenes=num_scenes,
                skip_stages=job.config.skip_stages,
            )

            self.pipeline.execute(
                job=job,
                cached_stages=cached,
                progress_callback=self._emit_progress,
            )

        except Exception as e:
            self._logger.error(f"Unhandled exception in job {job.job_id[:8]}: {e}")
            if not job.is_terminal:
                job.mark_failed(f"Unhandled error: {e}")
        finally:
            with self._lock:
                self._active_jobs.pop(job.job_id, None)

            self._emit_progress(job)
            self._logger.info(
                f"Job {job.job_id[:8]} finished with state: {job.status}"
            )

    def _emit_progress(self, job: ProductionJob) -> None:
        """Invoke all registered progress callbacks with the updated job.

        Args:
            job: The updated ProductionJob.
        """
        for cb in self._progress_callbacks:
            try:
                cb(job)
            except Exception:
                pass
