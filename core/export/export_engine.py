"""Concrete implementation of the ExportEngine interface.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from core.interfaces.export import ExportEngine as IExportEngine
from core.export.export_settings import ExportSettings
from core.export.export_job import ExportJob
from core.export.export_queue import ExportQueue
from core.export.export_history import ExportHistory
from core.export.export_worker import ExportWorker


class ExportEngine(IExportEngine):
    """Unified engine manager for queueing background transcode jobs and encoding final releases."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize ExportEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        
        self.queue = ExportQueue()
        self.history = ExportHistory(self.workspace_dir)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Start background worker thread
        self.worker = ExportWorker(self.queue, self.history, self.workspace_dir)
        self.worker.start()
        self._logger.info("ExportEngine initialized and background worker started.")

    def export_video(
        self,
        input_video_path: Path,
        output_video_path: Path,
        quality: str = "High",
        codec: str = "h264"
    ) -> Path:
        """Stitches overlays and encodes raw video files. Blocks until completion.

        Args:
            input_video_path: Video file containing edits.
            output_video_path: Target path to write output.
            quality: Quality profile name (Low, Medium, High).
            codec: String video codec encoder (e.g. h264, hevc, av1).

        Returns:
            The Path to the finalized compressed output file.
        """
        self._logger.info(f"Sync export_video request: Input={input_video_path.name}, Output={output_video_path.name}")

        # Map codec and quality strings to standard settings
        codec_map = {
            "h264": "H264",
            "h265": "H265",
            "hevc": "H265",
            "av1": "AV1"
        }
        codec_key = codec_map.get(codec.lower(), "H264")
        
        # Determine container from target output extension
        ext = output_video_path.suffix.replace(".", "").upper()
        container = ext if ext in ["MP4", "MOV", "MKV", "WEBM"] else "MP4"

        settings = ExportSettings(
            preset="Custom Resolution",
            width=1920,
            height=1080,
            fps=30,
            codec=codec_key,
            container=container,
            bitrate=quality,
            gpu_acceleration="Auto-Detect",
            burn_subtitles=False
        )

        job = self.submit_export_job(
            output_path=output_video_path,
            settings=settings,
            input_path=input_video_path
        )

        # Block loop until state settles
        while job.status in ["pending", "running", "paused"]:
            time.sleep(0.5)

        if job.status == "completed":
            return output_video_path
        else:
            raise RuntimeError(f"Video export failed: {job.error_message}")

    def submit_export_job(
        self,
        output_path: Path,
        settings: ExportSettings,
        input_path: Optional[Path] = None,
        srt_content: str = ""
    ) -> ExportJob:
        """Create and queue a new background transcode job.

        Args:
            output_path: Target video release destination.
            settings: Configured ExportSettings options.
            input_path: Source temporary/master video file path to transcode.
            srt_content: Optional subtitle string to burn.

        Returns:
            ExportJob tracker instance.
        """
        job = ExportJob(
            output_path=output_path,
            settings=settings,
            input_path=input_path,
            srt_content=srt_content
        )
        self.queue.add_job(job)
        return job

    def shutdown(self) -> None:
        """Stop worker threads and clean resources."""
        self._logger.info("Stopping Export background worker thread...")
        self.worker.stop()
        # Join thread to guarantee completion
        if self.worker.is_alive():
            self.worker.join(timeout=2.0)
        self._logger.info("ExportEngine shutdown finished.")
