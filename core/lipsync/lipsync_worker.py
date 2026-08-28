"""Background worker thread executing LatentSync repository cloning, weights downloading,
and lip synchronization inference.
"""

import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import traceback
import urllib.request
from typing import Callable, Optional

import torch

from core.lipsync.lipsync_config import LipSyncConfig
from core.lipsync.lipsync_job import LipSyncJob


class LipSyncWorker(threading.Thread):
    """Executes code cloning, model downloads, and inference pipeline in a background thread."""

    HF_BASE_URL = "https://huggingface.co/ByteDance/LatentSync/resolve/main"

    WEIGHT_FILES = [
        ("latentsync_unet.pt", HF_BASE_URL + "/latentsync_unet.pt"),
        ("whisper/tiny.pt", HF_BASE_URL + "/whisper/tiny.pt"),
    ]

    def __init__(self, job: LipSyncJob, on_complete_callback: Optional[Callable[[LipSyncJob], None]] = None) -> None:
        """Initialize LipSyncWorker.

        Args:
            job: LipSyncJob instance.
            on_complete_callback: Callback triggered when job completes/fails.
        """
        super().__init__(daemon=True)
        self.job = job
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def run(self) -> None:
        """Run the setup and inference pipeline."""
        self._logger.info(f"Starting worker thread for job {self.job.job_id}")
        self.job.update_status("running", 0.0)

        # Resolve paths
        engine_dir = Path(__file__).parent.resolve()
        latentsync_src_dir = engine_dir / "latentsync_src"
        checkpoints_dir = latentsync_src_dir / "checkpoints"

        try:
            # 1. Setup repository if missing
            if not latentsync_src_dir.exists() or not any(latentsync_src_dir.iterdir()):
                if not self.job.config.auto_download:
                    raise FileNotFoundError("LatentSync repository is missing and auto_download is disabled.")

                self.job.update_status("downloading_code", 0.0)
                self._logger.info("Cloning LatentSync repository from ByteDance GitHub...")

                subprocess.run(
                    ["git", "clone", "https://github.com/bytedance/LatentSync.git", str(latentsync_src_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._logger.info("Repository successfully cloned.")

            # 2. Download weights if missing
            missing_weights = []
            for relative_path, url in self.WEIGHT_FILES:
                target_path = checkpoints_dir / relative_path
                if not target_path.exists():
                    missing_weights.append((relative_path, url))

            if missing_weights:
                if not self.job.config.auto_download:
                    raise FileNotFoundError("Pretrained weights are missing and auto_download is disabled.")

                self.job.update_status("downloading_weights", 0.0)
                self._logger.info(f"Downloading {len(missing_weights)} missing model checkpoints...")

                for idx, (relative_path, url) in enumerate(missing_weights):
                    if self._cancelled:
                        raise RuntimeError("Job cancelled by user.")

                    target_path = checkpoints_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    self._logger.info(f"Downloading weights file: {relative_path} from {url}")

                    base_prog = idx / len(missing_weights)
                    weight_step = 1.0 / len(missing_weights)
                    self._download_file_with_progress(url, target_path, base_prog, weight_step)

            if self._cancelled:
                raise RuntimeError("Job cancelled by user.")

            # 3. Execute inference using Python subprocess
            self.job.update_status("running", 0.0)
            self._logger.info("Starting LatentSync lip sync generation...")

            # Resolve compute device (CUDA fallback to CPU)
            device = "cuda" if self.job.config.device == "cuda" and torch.cuda.is_available() else "cpu"
            self._logger.info(f"Selected compute device: {device}")

            # Build command arguments
            cmd = [
                sys.executable,
                "-m",
                "scripts.inference",
                "--unet_config_path", "configs/unet/stage2.yaml",
                "--inference_ckpt_path", str((checkpoints_dir / "latentsync_unet.pt").resolve()),
                "--video_path", str(self.job.config.presenter_video_path.resolve()),
                "--audio_path", str(self.job.config.audio_path.resolve()),
                "--video_out_path", str(self.job.config.output_video_path.resolve()),
                "--inference_steps", str(self.job.config.inference_steps),
                "--guidance_scale", str(self.job.config.guidance_scale)
            ]

            # Setup environment variables to route cache/python path
            env = os.environ.copy()
            env["PYTHONPATH"] = str(latentsync_src_dir) + os.pathsep + env.get("PYTHONPATH", "")
            
            # Force CPU if requested and selected
            if device == "cpu":
                env["CUDA_VISIBLE_DEVICES"] = ""

            # Start subprocess in latentsync_src working directory
            self._process = subprocess.Popen(
                cmd,
                cwd=str(latentsync_src_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )

            # Monitor progress
            self._monitor_progress()

            # Wait for exit
            stdout_data, stderr_data = self._process.communicate()
            exit_code = self._process.returncode

            if exit_code != 0:
                raise RuntimeError(
                    f"LatentSync inference process failed with code {exit_code}.\n"
                    f"Stdout:\n{stdout_data}\n"
                    f"Stderr:\n{stderr_data}"
                )

            if not self.job.config.output_video_path.exists():
                raise FileNotFoundError("Could not resolve or locate the exported video file from LatentSync.")

            self.job.update_status("completed", 1.0)
            self._logger.info("Job successfully completed.")

        except Exception as e:
            self._logger.error(f"Error executing lipsync job: {e}")
            tb = traceback.format_exc()
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in on_complete callback: {e}")

    def _download_file_with_progress(self, url: str, dest_path: Path, base_progress: float, weight_step: float) -> None:
        """Download file from HTTP URL, updating job progress."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                bytes_downloaded = 0
                block_size = 1024 * 1024  # 1MB block size

                with open(dest_path, "wb") as f:
                    while True:
                        if self._cancelled:
                            raise RuntimeError("Job cancelled by user.")

                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        bytes_downloaded += len(buffer)

                        if total_size > 0:
                            pct = bytes_downloaded / total_size
                            current_prog = base_progress + (pct * weight_step)
                            self.job.update_status("downloading_weights", current_prog)
        except Exception as e:
            raise RuntimeError(f"Failed downloading weights checkpoint from {url}: {e}")

    def _monitor_progress(self) -> None:
        """Parse stderr output of the inference process to resolve progress bar updates."""
        if not self._process or not self._process.stderr:
            return

        # Matches tqdm patterns like: " 15%|█▌        | 18/120"
        tqdm_regex = re.compile(r"(\d+)%\|.*\|?\s+(\d+)/(\d+)")

        # Read line by line
        for line in self._process.stderr:
            line = line.strip()
            if not line:
                continue

            match = tqdm_regex.search(line)
            if match:
                percentage = int(match.group(1))
                current_frame = int(match.group(2))
                total_frames = int(match.group(3))

                prog = percentage / 100.0
                self.job.update_status("running", prog)
                self._logger.debug(f"LipSync progress: {current_frame}/{total_frames} ({percentage}%)")
            else:
                if "loading" in line.lower() or "synchronizing" in line.lower() or "processing" in line.lower():
                    self._logger.info(f"LatentSync: {line}")

    def cancel(self) -> None:
        """Terminate the active subprocess execution."""
        self._cancelled = True
        self._logger.info("Cancellation requested.")
        if self._process:
            try:
                self._process.terminate()
                self._logger.info("Subprocess terminated.")
            except Exception as e:
                self._logger.error(f"Error terminating subprocess: {e}")
        self.job.update_status("failed", self.job.progress, error_message="Job was cancelled by the user.")
