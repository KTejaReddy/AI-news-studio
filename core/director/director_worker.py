"""Background worker thread executing script analysis.
"""

import logging
import threading
import time
import traceback
from typing import Callable, Optional

from core.director.director_config import DirectorConfig
from core.director.director_job import DirectorJob
from core.director.scene_analyzer import SceneAnalyzer


class DirectorWorker(threading.Thread):
    """Parses scripts and structures timelines in a separate background execution thread."""

    def __init__(self, job: DirectorJob, on_complete_callback: Optional[Callable[[DirectorJob], None]] = None) -> None:
        """Initialize DirectorWorker.

        Args:
            job: DirectorJob context tracker.
            on_complete_callback: Triggered when job completes/fails.
        """
        super().__init__(daemon=True)
        self.job = job
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._cancelled = False

    def run(self) -> None:
        """Run the script analysis thread pipeline."""
        self._logger.info(f"Starting script analysis worker for job {self.job.job_id}")
        self.job.update_status("running", 0.0)

        try:
            # 1. Parsing initialization
            time.sleep(0.2)
            if self._cancelled:
                raise RuntimeError("Job cancelled by user.")
            self.job.update_status("running", 0.3)

            # 2. Heuristics analysis
            analyzer = SceneAnalyzer()
            self._logger.info("Executing rules-based NLP scene segments planning...")
            timeline = analyzer.analyze_script(self.job.config.script_text)

            time.sleep(0.3)
            if self._cancelled:
                raise RuntimeError("Job cancelled by user.")
            self.job.update_status("running", 0.7)

            # 3. Validation and completion
            time.sleep(0.2)
            if self._cancelled:
                raise RuntimeError("Job cancelled by user.")

            self.job.update_status("completed", 1.0, timeline=timeline)
            self._logger.info("Script timeline generation finished successfully.")

        except Exception as e:
            self._logger.error(f"Error compiling script plan: {e}")
            tb = traceback.format_exc()
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in on_complete callback: {e}")

    def cancel(self) -> None:
        """Abort execution."""
        self._cancelled = True
