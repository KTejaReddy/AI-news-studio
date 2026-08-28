"""ExportQueue for managing, ordering, and pausing/resuming batch export jobs.
"""

import logging
from typing import Any, Dict, List, Optional
import threading

from core.export.export_job import ExportJob


class ExportQueue:
    """Manages thread-safe queues operations for background worker threads."""

    def __init__(self) -> None:
        self.jobs: Dict[str, ExportJob] = {}
        self.order: List[str] = []
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.is_paused = False

    def add_job(self, job: ExportJob) -> None:
        """Enqueue a new job to the end of the list.

        Args:
            job: ExportJob instance.
        """
        with self._lock:
            self.jobs[job.job_id] = job
            self.order.append(job.job_id)
            self._logger.info(f"Enqueued export job {job.job_id} -> {job.output_path.name}")

    def get_job(self, job_id: str) -> Optional[ExportJob]:
        """Fetch job details by ID.

        Args:
            job_id: Unique UUID.

        Returns:
            ExportJob or None.
        """
        with self._lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> List[ExportJob]:
        """Get list of all enqueued jobs in scheduled sequence order.

        Returns:
            List of ExportJobs.
        """
        with self._lock:
            return [self.jobs[jid] for jid in self.order if jid in self.jobs]

    def pop_next_pending_job(self) -> Optional[ExportJob]:
        """Retrieve the next pending task from the front of the queue, if not paused.

        Returns:
            ExportJob or None.
        """
        with self._lock:
            if self.is_paused:
                return None

            for jid in self.order:
                job = self.jobs.get(jid)
                if job and job.status == "pending":
                    job.update_status("running")
                    return job
            return None

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job, removing it or marking it failed.

        Args:
            job_id: Unique UUID.

        Returns:
            True if cancelled successfully, False otherwise.
        """
        with self._lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            if job.status in ["completed", "failed"]:
                return False

            job.update_status("failed", error_message="Job was cancelled by the user.")
            self._logger.info(f"Cancelled export job {job_id}.")
            return True

    def pause_queue(self) -> None:
        """Halt processing of new items in the queue."""
        with self._lock:
            self.is_paused = True
            self._logger.info("Export queue paused.")

    def resume_queue(self) -> None:
        """Allow processing of pending tasks."""
        with self._lock:
            self.is_paused = False
            self._logger.info("Export queue resumed.")

    def clear_queue(self) -> None:
        """Remove all completed/failed/cancelled tasks from index."""
        with self._lock:
            to_remove = [jid for jid, j in self.jobs.items() if j.status in ["completed", "failed"]]
            for jid in to_remove:
                del self.jobs[jid]
                self.order.remove(jid)
            self._logger.debug(f"Cleared {len(to_remove)} completed/failed tasks from export queue index.")
class ExportProfile:
    """Helper representing a saved template profile for export settings."""

    def __init__(self, name: str, settings: Any) -> None:
        self.name = name
        self.settings = settings
