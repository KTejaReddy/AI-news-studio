"""LipSyncController class for managing scheduling and worker threads of lip sync tasks.
"""

import logging
import threading
from typing import Dict, List, Optional

from core.lipsync.lipsync_config import LipSyncConfig
from core.lipsync.lipsync_job import LipSyncJob
from core.lipsync.lipsync_worker import LipSyncWorker


class LipSyncController:
    """Manages active lip sync worker threads and serves as a thread-safe jobs register."""

    def __init__(self) -> None:
        """Initialize the LipSyncController."""
        self._jobs: Dict[str, LipSyncJob] = {}
        self._active_workers: Dict[str, LipSyncWorker] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def submit_job(self, config: LipSyncConfig) -> LipSyncJob:
        """Create and start a new background lip sync synchronization job.

        Args:
            config: Job configuration settings.

        Returns:
            The created LipSyncJob instance.
        """
        with self._lock:
            job = LipSyncJob(config=config)
            self._jobs[job.job_id] = job

            # Start worker thread
            worker = LipSyncWorker(job=job, on_complete_callback=self._on_job_completed)
            self._active_workers[job.job_id] = worker

            self._logger.info(f"Submitting lip sync job: {job.job_id}")
            worker.start()

            return job

    def get_job(self, job_id: str) -> Optional[LipSyncJob]:
        """Retrieve job tracker instance by ID.

        Args:
            job_id: Unique UUID identifier.

        Returns:
            LipSyncJob instance or None if not registered.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active lip sync job.

        Args:
            job_id: ID of the job.

        Returns:
            True if job was found and terminated, False otherwise.
        """
        with self._lock:
            worker = self._active_workers.get(job_id)
            if worker:
                self._logger.info(f"Cancelling lip sync job: {job_id}")
                worker.cancel()
                self._active_workers.pop(job_id, None)
                return True
            return False

    def list_jobs(self) -> List[LipSyncJob]:
        """List all submitted lip sync jobs.

        Returns:
            List of LipSyncJob items.
        """
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _on_job_completed(self, job: LipSyncJob) -> None:
        """Cleanup worker thread reference from active index.

        Args:
            job: The finished LipSyncJob context.
        """
        with self._lock:
            self._active_workers.pop(job.job_id, None)
            self._logger.info(f"Active lip sync worker thread released for job: {job.job_id} [Status: {job.status}]")
