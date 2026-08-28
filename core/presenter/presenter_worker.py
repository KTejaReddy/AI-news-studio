"""Background worker thread executing LivePortrait model downloading, repository setup,
and portrait animation inference.
"""

import logging
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from typing import Callable, Optional

from core.presenter.presenter_config import PresenterConfig
from core.presenter.presenter_job import PresenterJob


class PresenterWorker(threading.Thread):
    """Executes code cloning, model downloads, and inference pipeline in a background thread."""

    # Hugging Face download base paths
    HF_BASE_URL = "https://huggingface.co/KwaiVGI/LivePortrait/resolve/main"

    WEIGHT_FILES = [
        ("liveportrait/appearance_feature_extractor.pth", HF_BASE_URL + "/liveportrait/appearance_feature_extractor.pth"),
        ("liveportrait/motion_extractor.pth", HF_BASE_URL + "/liveportrait/motion_extractor.pth"),
        ("liveportrait/warping_spade.pth", HF_BASE_URL + "/liveportrait/warping_spade.pth"),
        ("liveportrait/spade_generator.pth", HF_BASE_URL + "/liveportrait/spade_generator.pth"),
        ("liveportrait/stitching_eye.pth", HF_BASE_URL + "/liveportrait/stitching_eye.pth"),
        ("liveportrait/stitching_lip.pth", HF_BASE_URL + "/liveportrait/stitching_lip.pth"),
        ("liveportrait/landmark.pth", HF_BASE_URL + "/liveportrait/landmark.pth"),
        ("insightface/models/buffalo_l/det_10g.onnx", HF_BASE_URL + "/insightface/models/buffalo_l/det_10g.onnx"),
        ("insightface/models/buffalo_l/2d106det.onnx", HF_BASE_URL + "/insightface/models/buffalo_l/2d106det.onnx"),
    ]

    def __init__(self, job: PresenterJob, on_complete_callback: Optional[Callable[[PresenterJob], None]] = None) -> None:
        """Initialize PresenterWorker.

        Args:
            job: PresenterJob instance.
            on_complete_callback: Callback triggered when job completes/fails.
        """
        super().__init__(daemon=True)
        self.job = job
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._process: Optional[subprocess.Popen] = None

    def run(self) -> None:
        """Run the setup and inference pipeline."""
        self._logger.info(f"Starting worker thread for job {self.job.job_id}")
        self.job.update_status("running", 0.0)

        # Resolve paths
        engine_dir = Path(__file__).parent.resolve()
        liveportrait_src_dir = engine_dir / "liveportrait_src"
        pretrained_weights_dir = liveportrait_src_dir / "pretrained_weights"

        try:
            # 1. Setup repository if missing
            if not liveportrait_src_dir.exists() or not any(liveportrait_src_dir.iterdir()):
                if not self.job.config.auto_download:
                    raise FileNotFoundError("LivePortrait repository is missing and auto_download is disabled.")
                
                self.job.update_status("downloading_code", 0.0)
                self._logger.info("Cloning LivePortrait repository from KwaiVGI GitHub...")
                
                # Run git clone
                subprocess.run(
                    ["git", "clone", "https://github.com/KwaiVGI/LivePortrait.git", str(liveportrait_src_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._logger.info("Repository successfully cloned.")

            # 2. Download weights if missing
            missing_weights = []
            for relative_path, url in self.WEIGHT_FILES:
                target_path = pretrained_weights_dir / relative_path
                if not target_path.exists():
                    missing_weights.append((relative_path, url))

            if missing_weights:
                if not self.job.config.auto_download:
                    raise FileNotFoundError("Pretrained weights are missing and auto_download is disabled.")
                
                self.job.update_status("downloading_weights", 0.0)
                self._logger.info(f"Downloading {len(missing_weights)} missing model checkpoints...")
                
                for idx, (relative_path, url) in enumerate(missing_weights):
                    target_path = pretrained_weights_dir / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    self._logger.info(f"Downloading weights file: {relative_path} from {url}")
                    
                    # Perform download with progress callback
                    base_prog = idx / len(missing_weights)
                    weight_step = 1.0 / len(missing_weights)
                    self._download_file_with_progress(url, target_path, base_prog, weight_step)

            # 3. Execute inference using Python subprocess
            self.job.update_status("running", 0.0)
            self._logger.info("Starting LivePortrait video generation...")

            # Build command arguments
            cmd = [
                sys.executable,
                "inference.py",
                "-s", str(self.job.config.source_image_path.resolve()),
                "-d", str(self.job.config.driving_video_path.resolve()),
                "-o", str(self.job.config.output_video_path.parent.resolve()),
            ]

            # Append configs
            if self.job.config.flag_crop:
                cmd.append("--flag_crop_driving_video")
            if not self.job.config.flag_stitching:
                # LivePortrait handles disabling stitch via relative config parameter.
                # In standard inference.py, crop is standard. We can override if needed.
                pass
            
            # Setup environment variables to route cache properly
            import os
            env = os.environ.copy()
            env["PYTHONPATH"] = str(liveportrait_src_dir) + os.pathsep + env.get("PYTHONPATH", "")

            # Start subprocess in liveportrait_src working directory
            self._process = subprocess.Popen(
                cmd,
                cwd=str(liveportrait_src_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )

            # Monitor stderr for tqdm progress bars
            self._monitor_progress()

            # Wait for exit
            stdout_data, stderr_data = self._process.communicate()
            exit_code = self._process.returncode

            if exit_code != 0:
                raise RuntimeError(f"LivePortrait inference process failed with code {exit_code}.\nError details:\n{stderr_data}")

            # Check if output file was created.
            # LivePortrait inference.py saves to output/dir/name_deformed.mp4 by default.
            # Let's locate the generated file and copy it to the user's configured output_video_path.
            self._logger.info("Locating compiled output file...")
            
            # Look in output directory of the repo
            repo_output_dir = liveportrait_src_dir / "animations"
            if not repo_output_dir.exists():
                repo_output_dir = liveportrait_src_dir / "output" # fallback

            # Try locating the newest mp4 file in the repo animations
            generated_file = None
            if repo_output_dir.exists():
                mp4_files = list(repo_output_dir.glob("**/*.mp4"))
                if mp4_files:
                    mp4_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    generated_file = mp4_files[0]

            if generated_file and generated_file.exists():
                self._logger.info(f"Found generated video file at {generated_file}. Copying to {self.job.config.output_video_path}")
                self.job.config.output_video_path.parent.mkdir(parents=True, exist_ok=True)
                
                import shutil
                shutil.copy2(generated_file, self.job.config.output_video_path)
                
                # Delete from repo outputs to keep it clean
                try:
                    generated_file.unlink()
                except Exception:
                    pass
            else:
                # If we can't find it, check if output_video_path was written directly by custom scripts.
                if not self.job.config.output_video_path.exists():
                    raise FileNotFoundError("Could not resolve or locate the exported video file from LivePortrait.")

            self.job.update_status("completed", 1.0)
            self._logger.info("Job successfully completed.")

        except Exception as e:
            self._logger.error(f"Error executing presenter job: {e}")
            tb = traceback.format_exc() if 'traceback' in sys.modules else str(e)
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in on_complete callback: {e}")

    def _download_file_with_progress(self, url: str, dest_path: Path, base_progress: float, weight_step: float) -> None:
        """Download file from HTTP URL, updating job progress.

        Args:
            url: The HTTP direct link.
            dest_path: File path to save target bytes.
            base_progress: Starting progress percentage (0.0 to 1.0).
            weight_step: Progress weight representing this file.
        """
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                bytes_downloaded = 0
                block_size = 1024 * 1024  # 1MB block size
                
                with open(dest_path, "wb") as f:
                    while True:
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
        # LivePortrait writes tqdm output to stderr
        if not self._process or not self._process.stderr:
            return

        # Matches tqdm patterns like: " 15%|█▌        | 18/120"
        tqdm_regex = re.compile(r"(\d+)%\|.*\|?\s+(\d+)/(\d+)")

        for line in self._process.stderr:
            line = line.strip()
            if not line:
                continue

            match = tqdm_regex.search(line)
            if match:
                percentage = int(match.group(1))
                current_frame = int(match.group(2))
                total_frames = int(match.group(3))
                
                # Normalize progress between 0.0 and 1.0
                prog = percentage / 100.0
                self.job.update_status("running", prog)
                self._logger.debug(f"Render progress: {current_frame}/{total_frames} ({percentage}%)")
            else:
                # Capture standard statement logs
                if "loading" in line.lower() or "detecting" in line.lower():
                    self._logger.info(f"LivePortrait: {line}")

    def cancel(self) -> None:
        """Terminate the active subprocess execution."""
        self._logger.info("Cancellation requested.")
        if self._process:
            try:
                self._process.terminate()
                self._logger.info("Process terminated.")
            except Exception as e:
                self._logger.error(f"Error terminating process: {e}")
        self.job.update_status("failed", self.job.progress, error_message="Job was cancelled by the user.")
