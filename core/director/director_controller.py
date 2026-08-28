"""DirectorController class for managing script analysis background queue registry.
"""

import logging
import threading
from typing import Dict, List, Optional

from core.director.director_config import DirectorConfig
from core.director.director_job import DirectorJob
from core.director.director_worker import DirectorWorker


class DirectorController:
    """Manages active script analysis workers and serves as a thread-safe jobs register."""

    def __init__(self) -> None:
        """Initialize the DirectorController."""
        self._jobs: Dict[str, DirectorJob] = {}
        self._active_workers: Dict[str, DirectorWorker] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def submit_job(self, config: DirectorConfig) -> DirectorJob:
        """Create and start a new background script analysis job.

        Args:
            config: Job configuration settings.

        Returns:
            The created DirectorJob instance.
        """
        with self._lock:
            job = DirectorJob(config=config)
            self._jobs[job.job_id] = job

            # Start worker thread
            worker = DirectorWorker(job=job, on_complete_callback=self._on_job_completed)
            self._active_workers[job.job_id] = worker

            self._logger.info(f"Submitting director analysis job: {job.job_id}")
            worker.start()

            return job

    def get_job(self, job_id: str) -> Optional[DirectorJob]:
        """Retrieve job tracker instance by ID.

        Args:
            job_id: Unique UUID identifier.

        Returns:
            DirectorJob instance or None if not registered.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active director script analysis job.

        Args:
            job_id: ID of the job.

        Returns:
            True if job was found and terminated, False otherwise.
        """
        with self._lock:
            worker = self._active_workers.get(job_id)
            if worker:
                self._logger.info(f"Cancelling director job: {job_id}")
                worker.cancel()
                self._active_workers.pop(job_id, None)
                return True
            return False

    def list_jobs(self) -> List[DirectorJob]:
        """List all submitted director jobs.

        Returns:
            List of DirectorJob items.
        """
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _on_job_completed(self, job: DirectorJob) -> None:
        """Cleanup worker thread reference from active index.

        Args:
            job: The finished DirectorJob context.
        """
        with self._lock:
            self._active_workers.pop(job.job_id, None)
            self._logger.info(f"Active director worker thread released for job: {job.job_id} [Status: {job.status}]")
