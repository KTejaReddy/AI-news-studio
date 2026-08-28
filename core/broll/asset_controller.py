"""AssetController for orchestrating and managing the background generation queues for B-roll visuals.
"""

import logging
from typing import Dict, List, Optional
import threading

from core.director.scene_plan import ScenePlan
from core.broll.broll_config import BrollConfig
from core.broll.broll_job import BrollJob
from core.broll.asset_generator import AssetGenerator
from core.broll.asset_library import AssetLibrary
from core.broll.asset_cache import AssetCache
from core.broll.asset_worker import AssetWorker


class AssetController:
    """Manages thread-safe job queues and processes B-roll requests concurrently in background threads."""

    def __init__(
        self,
        generator: AssetGenerator,
        library: AssetLibrary,
        cache: AssetCache
    ) -> None:
        """Initialize AssetController.

        Args:
            generator: AssetGenerator orchestration instance.
            library: AssetLibrary instance.
            cache: AssetCache instance.
        """
        self.generator = generator
        self.library = library
        self.cache = cache
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()
        self.jobs: Dict[str, BrollJob] = {}
        self.workers: Dict[str, AssetWorker] = {}

    def submit_job(self, scene_plan: ScenePlan, config: BrollConfig) -> BrollJob:
        """Submit a new storyboard scene visual generation task to run in the background.

        Args:
            scene_plan: ScenePlan parameters.
            config: BrollConfig parameters.

        Returns:
            The created BrollJob instance.
        """
        with self._lock:
            # Check if there is already an active job for this scene_id/scene_number in completed state or running?
            # Normally we just submit it under a new unique job UUID.
            job = BrollJob(scene_plan=scene_plan, config=config)
            self.jobs[job.job_id] = job

            # Instantiate and start the worker thread
            worker = AssetWorker(
                job=job,
                generator=self.generator,
                library=self.library,
                cache=self.cache,
                on_complete_callback=self._handle_job_completion
            )
            self.workers[job.job_id] = worker
            worker.start()

            self._logger.info(f"Submitted B-roll job {job.job_id} for scene {scene_plan.scene_number}.")
            return job

    def get_job(self, job_id: str) -> Optional[BrollJob]:
        """Retrieve a BrollJob status by its unique ID.

        Args:
            job_id: Unique job UUID.

        Returns:
            BrollJob or None.
        """
        with self._lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> List[BrollJob]:
        """List all active or completed jobs.

        Returns:
            List of BrollJob instances.
        """
        with self._lock:
            return list(self.jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        """Request termination of a running job.

        Args:
            job_id: Unique job UUID.

        Returns:
            True if cancelled, False otherwise.
        """
        with self._lock:
            worker = self.workers.get(job_id)
            job = self.jobs.get(job_id)
            
            if not worker or not job:
                return False

            if job.status in ["completed", "failed"]:
                return False

            try:
                worker.cancel()
                self._logger.info(f"Requested cancellation for job {job_id}.")
                return True
            except Exception as e:
                self._logger.error(f"Error cancelling B-roll worker thread {job_id}: {e}")
                return False

    def clear_completed_jobs(self) -> None:
        """Clear all completed or failed jobs from the history manager cache."""
        with self._lock:
            to_remove = [jid for jid, job in self.jobs.items() if job.status in ["completed", "failed"]]
            for jid in to_remove:
                del self.jobs[jid]
                if jid in self.workers:
                    del self.workers[jid]
            self._logger.debug(f"Cleared {len(to_remove)} completed B-roll jobs from queue history.")

    def _handle_job_completion(self, job: BrollJob) -> None:
        """Internal callback triggered when a background worker thread exits."""
        self._logger.info(f"B-roll job {job.job_id} exited with status: {job.status}")
        # Retain job info but allow thread resource to clean up
        with self._lock:
            if job.job_id in self.workers:
                # Keep job info, but worker thread can be dereferenced
                pass
