"""VoiceController class for managing scheduling and worker threads of speech synthesis tasks.
"""

import logging
import threading
from typing import Dict, List, Optional

from core.voice.voice_config import VoiceConfig
from core.voice.voice_job import VoiceJob
from core.voice.voice_worker import VoiceWorker


class VoiceController:
    """Manages active speech worker threads and serves as a thread-safe jobs register."""

    def __init__(self) -> None:
        """Initialize the VoiceController."""
        self._jobs: Dict[str, VoiceJob] = {}
        self._active_workers: Dict[str, VoiceWorker] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def submit_job(self, config: VoiceConfig) -> VoiceJob:
        """Create and start a new background speech synthesis job.

        Args:
            config: Job configuration settings.

        Returns:
            The created VoiceJob instance.
        """
        with self._lock:
            job = VoiceJob(config=config)
            self._jobs[job.job_id] = job
            
            # Start worker thread
            worker = VoiceWorker(job=job, on_complete_callback=self._on_job_completed)
            self._active_workers[job.job_id] = worker
            
            self._logger.info(f"Submitting voice synthesis job: {job.job_id}")
            worker.start()
            
            return job

    def get_job(self, job_id: str) -> Optional[VoiceJob]:
        """Retrieve job tracker instance by ID.

        Args:
            job_id: Unique UUID identifier.

        Returns:
            VoiceJob instance or None if not registered.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel an active speech synthesis job.

        Args:
            job_id: ID of the job.

        Returns:
            True if job was found and terminated, False otherwise.
        """
        with self._lock:
            worker = self._active_workers.get(job_id)
            if worker:
                self._logger.info(f"Cancelling voice job: {job_id}")
                worker.cancel()
                self._active_workers.pop(job_id, None)
                return True
            return False

    def list_jobs(self) -> List[VoiceJob]:
        """List all submitted speech jobs.

        Returns:
            List of VoiceJob items.
        """
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _on_job_completed(self, job: VoiceJob) -> None:
        """Cleanup worker thread reference from active index.

        Args:
            job: The finished VoiceJob context.
        """
        with self._lock:
            self._active_workers.pop(job.job_id, None)
            self._logger.info(f"Active speech worker thread released for job: {job.job_id} [Status: {job.status}]")
