"""Concrete implementation of the LipSyncEngine interface using LatentSync.
"""

import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from core.interfaces.lipsync import LipSyncEngine as ILipSyncEngine
from core.lipsync.lipsync_config import LipSyncConfig
from core.lipsync.lipsync_controller import LipSyncController
from core.lipsync.lipsync_job import LipSyncJob


class LipSyncEngine(ILipSyncEngine):
    """Integrates LatentSync lip synchronization engine to align presenter mouth movements to voice tracks."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize LipSyncEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = LipSyncController()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("LipSyncEngine initialized using LatentSync backend.")

    def sync_lips(
        self,
        presenter_video_path: Path,
        audio_path: Path,
        output_path: Path
    ) -> Path:
        """Standard interface implementation. Synchronizes mouth movement to audio track.

        Args:
            presenter_video_path: Video of presenter.
            audio_path: Audio track.
            output_path: Target output path.

        Returns:
            The Path to the synthesized and lip-synchronized video.
        """
        self._logger.info(f"Syncing lips: Video={presenter_video_path.name}, Audio={audio_path.name} -> {output_path.name}")

        config = LipSyncConfig(
            presenter_video_path=presenter_video_path,
            audio_path=audio_path,
            output_video_path=output_path,
            quality="High",
            device="cuda"
        )

        # Submit background job and block until complete (synchronous interface flow)
        job = self.controller.submit_job(config)
        self._logger.info(f"Submitted background lip sync job: {job.job_id}")

        while job.status in ["pending", "downloading_code", "downloading_weights", "running"]:
            time.sleep(0.5)

        if job.status == "completed":
            return output_path
        else:
            raise RuntimeError(f"Failed to synchronize lips: {job.error_message}")

    # --- Async Synthesis Wrapper Method ---
    def generate_lipsync(
        self,
        presenter_video_path: Path,
        audio_path: Path,
        output_video_path: Path,
        quality: str = "High",
        device: str = "cuda",
        auto_download: bool = True
    ) -> LipSyncJob:
        """Submit an asynchronous lip-syncing task to the queue controller.

        Args:
            presenter_video_path: Input speaking video.
            audio_path: Target script audio WAV/MP3.
            output_video_path: Target path for synced MP4 output.
            quality: Quality setting ("Fast" or "High").
            device: Compute device mode ('cuda' or 'cpu').
            auto_download: Auto-download models/code if missing.

        Returns:
            LipSyncJob tracker instance.
        """
        # Quality presets mapping to steps/guidance:
        # Fast: 15 steps, guidance 1.0. High: 30 steps, guidance 1.5.
        inference_steps = 15 if quality == "Fast" else 30
        guidance_scale = 1.0 if quality == "Fast" else 1.5

        config = LipSyncConfig(
            presenter_video_path=presenter_video_path,
            audio_path=audio_path,
            output_video_path=output_video_path,
            quality=quality,
            guidance_scale=guidance_scale,
            inference_steps=inference_steps,
            device=device,
            auto_download=auto_download
        )
        return self.controller.submit_job(config)
