"""MotionController class for managing scheduling, worker threads, and queue registries.
"""

import logging
import threading
from typing import Dict, List, Optional

from core.motion.motion_config import MotionConfig
from core.motion.motion_job import MotionJob
from core.motion.motion_worker import MotionWorker


class MotionController:
    """Manages active body motion worker threads and serves as a job queue manager."""

    def __init__(self) -> None:
        """Initialize the MotionController."""
        self._jobs: Dict[str, MotionJob] = {}
        self._active_workers: Dict[str, MotionWorker] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def submit_job(self, config: MotionConfig) -> MotionJob:
        """Create and launch a new background body motion generation task.

        Args:
            config: Job configuration settings.

        Returns:
            The created MotionJob instance.
        """
        with self._lock:
            job = MotionJob(config=config)
            self._jobs[job.job_id] = job
            
            # Start worker thread
            worker = MotionWorker(job=job, on_complete_callback=self._on_job_completed)
            self._active_workers[job.job_id] = worker
            
            self._logger.info(f"Submitting motion job: {job.job_id} [preset: {config.motion_style}]")
            worker.start()
            
            return job

    def get_job(self, job_id: str) -> Optional[MotionJob]:
        """Retrieve job tracker instance by ID.

        Args:
            job_id: Unique UUID identifier.

        Returns:
            MotionJob instance or None if not registered.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active body motion generation task.

        Args:
            job_id: ID of the job.

        Returns:
            True if job was found and terminated, False otherwise.
        """
        with self._lock:
            worker = self._active_workers.get(job_id)
            if worker:
                self._logger.info(f"Cancelling motion job: {job_id}")
                worker.cancel()
                self._active_workers.pop(job_id, None)
                return True
            return False

    def list_jobs(self) -> List[MotionJob]:
        """List all submitted motion jobs.

        Returns:
            List of MotionJob items.
        """
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _on_job_completed(self, job: MotionJob) -> None:
        """Cleanup worker thread reference from active index.

        Args:
            job: The finished MotionJob context.
        """
        with self._lock:
            self._active_workers.pop(job.job_id, None)
            self._logger.info(f"Active motion worker thread released for job: {job.job_id} [Status: {job.status}]")
