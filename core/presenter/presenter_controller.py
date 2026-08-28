"""PresenterController class for scheduling, queueing, and monitoring presenter animation jobs.
"""

import logging
import threading
from typing import Dict, List, Optional

from core.presenter.presenter_config import PresenterConfig
from core.presenter.presenter_job import PresenterJob
from core.presenter.presenter_worker import PresenterWorker


class PresenterController:
    """Manages active worker threads and serves as a thread-safe jobs register."""

    def __init__(self) -> None:
        """Initialize the PresenterController."""
        self._jobs: Dict[str, PresenterJob] = {}
        self._active_workers: Dict[str, PresenterWorker] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def submit_job(self, config: PresenterConfig) -> PresenterJob:
        """Create and start a new background animation job.

        Args:
            config: Job configuration settings.

        Returns:
            The newly created PresenterJob tracker instance.
        """
        with self._lock:
            job = PresenterJob(config=config)
            self._jobs[job.job_id] = job
            
            # Create worker and register completion callback
            worker = PresenterWorker(job=job, on_complete_callback=self._on_job_completed)
            self._active_workers[job.job_id] = worker
            
            self._logger.info(f"Submitting presenter job: {job.job_id}")
            worker.start()
            
            return job

    def get_job(self, job_id: str) -> Optional[PresenterJob]:
        """Retrieve job tracker instance by ID.

        Args:
            job_id: Unique UUID identifier.

        Returns:
            PresenterJob instance or None if not registered.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active background animation job.

        Args:
            job_id: ID of the job.

        Returns:
            True if job was found and terminated, False otherwise.
        """
        with self._lock:
            worker = self._active_workers.get(job_id)
            if worker:
                self._logger.info(f"Cancelling job: {job_id}")
                worker.cancel()
                # Remove from active lists
                self._active_workers.pop(job_id, None)
                return True
            return False

    def list_jobs(self) -> List[PresenterJob]:
        """List all submitted jobs.

        Returns:
            List of PresenterJob items sorted by creation time.
        """
        with self._lock:
            # Return copies sorted newest first
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _on_job_completed(self, job: PresenterJob) -> None:
        """Cleanup worker thread reference from active index.

        Args:
            job: The finished PresenterJob context.
        """
        with self._lock:
            self._active_workers.pop(job.job_id, None)
            self._logger.info(f"Active worker thread released for job: {job.job_id} [Status: {job.status}]")
