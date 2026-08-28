"""Background worker thread executing Motion Engine repository setup, weights downloading,
and pose-driven body motion generation.
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

from core.motion.motion_config import MotionConfig
from core.motion.motion_job import MotionJob


class MotionWorker(threading.Thread):
    """Executes pose templates generation, model downloading, and subprocess video animation."""

    # Hugging Face weights direct paths
    HF_SVD_URL = "https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt/resolve/main/svd_xt.safetensors"
    HF_MIMIC_URL = "https://huggingface.co/TencentARC/MimicMotion/resolve/main/MimicMotion_1.ckpt"

    def __init__(self, job: MotionJob, on_complete_callback: Optional[Callable[[MotionJob], None]] = None) -> None:
        """Initialize MotionWorker.

        Args:
            job: MotionJob instance.
            on_complete_callback: Callback triggered when job finishes.
        """
        super().__init__(daemon=True)
        self.job = job
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._process: Optional[subprocess.Popen] = None

    def run(self) -> None:
        """Execute setup and body motion rendering pipeline."""
        self._logger.info(f"Starting worker thread for motion job: {self.job.job_id}")
        self.job.update_status("running", 0.0)

        engine_dir = Path(__file__).parent.resolve()
        mimicmotion_src_dir = engine_dir / "mimicmotion_src"
        weights_dir = mimicmotion_src_dir / "pretrained_weights"

        try:
            # 1. Setup repository if missing
            if not mimicmotion_src_dir.exists() or not any(mimicmotion_src_dir.iterdir()):
                if not self.job.config.auto_download:
                    raise FileNotFoundError("MimicMotion repository is missing and auto_download is disabled.")
                
                self.job.update_status("downloading_code", 0.0)
                self._logger.info("Cloning MimicMotion repository from Tencent GitHub...")
                subprocess.run(
                    ["git", "clone", "https://github.com/tencent/MimicMotion.git", str(mimicmotion_src_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._logger.info("MimicMotion repository successfully cloned.")

            # 2. Check and download checkpoints
            svd_path = weights_dir / "svd_xt.safetensors"
            mimic_path = weights_dir / "MimicMotion_1.ckpt"

            missing_downloads = []
            if not svd_path.exists():
                missing_downloads.append((svd_path, self.HF_SVD_URL))
            if not mimic_path.exists():
                missing_downloads.append((mimic_path, self.HF_MIMIC_URL))

            if missing_downloads:
                if not self.job.config.auto_download:
                    raise FileNotFoundError("Pretrained weights (SVD/MimicMotion) are missing and auto_download is disabled.")
                
                self.job.update_status("downloading_weights", 0.0)
                self._logger.info(f"Downloading {len(missing_downloads)} missing model weights files...")
                
                for idx, (target_path, url) in enumerate(missing_downloads):
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    self._logger.info(f"Downloading {target_path.name} from {url}...")
                    
                    base_prog = idx / len(missing_downloads)
                    weight_step = 1.0 / len(missing_downloads)
                    self._download_file(url, target_path, base_prog, weight_step)

            # 3. Generate skeletal pose sequence template programmatically
            # Different presets (Professional, Casual, Energetic, News Anchor, Podcast) map to distinct movements.
            self.job.update_status("running", 0.1)
            self._logger.info(f"Preprocessing motion preset style: {self.job.config.motion_style}")
            
            # Resolve pose template target path
            templates_dir = engine_dir / "pose_templates"
            templates_dir.mkdir(parents=True, exist_ok=True)
            custom_pose_file = templates_dir / f"pose_{self.job.job_id}.json"

            # Create pose timeline
            self._generate_skeletal_pose_timeline(
                style=self.job.config.motion_style,
                strength=self.job.config.gesture_strength,
                smoothing=self.job.config.motion_smoothing,
                enable_idle=self.job.config.enable_idle_motion,
                out_path=custom_pose_file
            )

            # 4. Run MimicMotion inference via Python subprocess
            self.job.update_status("running", 0.3)
            self._logger.info("Executing MimicMotion video compilation loop...")

            # Assemble CLI command
            # MimicMotion standard inference uses inference.py with image, pose, and model path configurations
            cmd = [
                sys.executable,
                "inference.py",
                "--ref_image", str(self.job.config.source_image_path.resolve()),
                "--pose_sequence", str(custom_pose_file.resolve()),
                "--output_video", str(self.job.config.output_video_path.resolve()),
                "--device", self.job.config.device,
            ]

            import os
            env = os.environ.copy()
            env["PYTHONPATH"] = str(mimicmotion_src_dir) + os.pathsep + env.get("PYTHONPATH", "")

            # Start subprocess in mimicmotion_src working directory
            self._process = subprocess.Popen(
                cmd,
                cwd=str(mimicmotion_src_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env
            )

            # Monitor progress
            self._monitor_inference_logs()

            # Wait for exit
            stdout_data, stderr_data = self._process.communicate()
            exit_code = self._process.returncode

            # Delete custom pose files to clean up
            try:
                custom_pose_file.unlink()
            except Exception:
                pass

            if exit_code != 0:
                raise RuntimeError(f"MimicMotion process crashed with code {exit_code}.\nDetails:\n{stderr_data}")

            # Check if output file was created
            if not self.job.config.output_video_path.exists():
                # Fallback search in mimicmotion_src output folders
                out_folder = mimicmotion_src_dir / "outputs"
                generated_file = None
                if out_folder.exists():
                    mp4s = list(out_folder.glob("*.mp4"))
                    if mp4s:
                        mp4s.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        generated_file = mp4s[0]
                
                if generated_file and generated_file.exists():
                    self.job.config.output_video_path.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(generated_file, self.job.config.output_video_path)
                    try:
                        generated_file.unlink()
                    except Exception:
                        pass
                else:
                    raise FileNotFoundError("Target body animation video was not found on output folders.")

            self.job.update_status("completed", 1.0)
            self._logger.info("Job successfully completed.")

        except Exception as e:
            self._logger.error(f"Error executing motion job: {e}")
            tb = traceback.format_exc()
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in on_complete callback: {e}")

    def _download_file(self, url: str, target_path: Path, base_progress: float, weight_step: float) -> None:
        """Download file with progress metrics.

        Args:
            url: direct HTTP link.
            target_path: File location to save target bytes.
            base_progress: Starting progress percentage.
            weight_step: Progress weight representing this file.
        """
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                bytes_downloaded = 0
                block_size = 1024 * 1024
                
                with open(target_path, "wb") as f:
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
            raise RuntimeError(f"Failed downloading checkpoint: {e}")

    def _generate_skeletal_pose_timeline(
        self,
        style: str,
        strength: float,
        smoothing: float,
        enable_idle: bool,
        out_path: Path
    ) -> None:
        """Programmatically generate a skeletal pose coordinate sequence mapping to chosen preset.

        Args:
            style: The style preset (Professional, Casual, Energetic, News Anchor, Podcast).
            strength: Multiplier coefficient for limb motions.
            smoothing: Low-pass smoothing filter.
            enable_idle: Toggle breathing and torso sway.
            out_path: JSON file target path.
        """
        import json
        import math

        num_frames = 120  # ~4 seconds of motion at 30fps
        fps = 30
        pose_data = []

        # Define default skeletal joints base coordinates (normalized 0.0 to 1.0)
        # 0: nose, 1: neck, 2: R-shoulder, 3: R-elbow, 4: R-wrist, 5: L-shoulder, 6: L-elbow, 7: L-wrist, etc.
        base_joints = {
            "neck": [0.5, 0.25],
            "r_shoulder": [0.38, 0.3],
            "l_shoulder": [0.62, 0.3],
            "r_elbow": [0.32, 0.45],
            "l_elbow": [0.68, 0.45],
            "r_wrist": [0.35, 0.6],
            "l_wrist": [0.65, 0.6],
        }

        # Apply specific parameters based on style
        for frame in range(num_frames):
            t = frame / fps
            joints = {}

            # 1. Idle breathing (subtle shoulder vertical bounce)
            breath_offset = 0.0 if not enable_idle else math.sin(2 * math.pi * 0.25 * t) * 0.003
            
            # 2. Torso sway (subtle horizontal drift)
            sway_period = 10.0 if style == "News Anchor" else (6.0 if style == "Professional" else 4.0)
            sway_amp = 0.001 if style == "News Anchor" else (0.004 if style == "Professional" else 0.01)
            sway_offset = 0.0 if not enable_idle else math.sin(2 * math.pi * (1 / sway_period) * t) * sway_amp

            # Calculate neck and shoulders
            joints["neck"] = [base_joints["neck"][0] + sway_offset, base_joints["neck"][1]]
            joints["r_shoulder"] = [base_joints["r_shoulder"][0] + sway_offset, base_joints["r_shoulder"][1] + breath_offset]
            joints["l_shoulder"] = [base_joints["l_shoulder"][0] + sway_offset, base_joints["l_shoulder"][1] + breath_offset]

            # 3. Gesture Arm/Wrist animations
            # Generate different arm movements based on style
            r_arm_offset = [0.0, 0.0]
            l_arm_offset = [0.0, 0.0]

            if style == "Energetic":
                # Large, circular gesturing
                r_arm_offset[0] = math.cos(2 * math.pi * 0.8 * t) * 0.08 * strength
                r_arm_offset[1] = math.sin(2 * math.pi * 0.8 * t) * 0.06 * strength
                l_arm_offset[0] = math.cos(2 * math.pi * 0.6 * t + math.pi) * 0.07 * strength
                l_arm_offset[1] = math.sin(2 * math.pi * 0.6 * t) * 0.05 * strength
            elif style == "Casual":
                # Modest, alternating gesturing
                r_arm_offset[0] = math.sin(2 * math.pi * 0.5 * t) * 0.03 * strength
                r_arm_offset[1] = math.cos(2 * math.pi * 0.4 * t) * 0.02 * strength
                l_arm_offset[0] = math.sin(2 * math.pi * 0.3 * t) * 0.02 * strength
            elif style == "Podcast":
                # Leaning forward, subtle gesturing close to center
                r_arm_offset[0] = math.sin(2 * math.pi * 0.4 * t) * 0.01 * strength
                r_arm_offset[1] = math.sin(2 * math.pi * 0.8 * t) * 0.01 * strength
            elif style == "News Anchor":
                # Rested hands, zero hand gestures, pure breathing/sway
                pass
            else:  # Professional
                # Smooth explanatory gestures
                r_arm_offset[0] = math.sin(2 * math.pi * 0.3 * t) * 0.02 * strength
                r_arm_offset[1] = math.sin(2 * math.pi * 0.6 * t) * 0.01 * strength

            # Apply low pass filter smoothing
            # Emulated by merging coordinates with neighboring values
            if frame > 0:
                prev_joints = pose_data[-1]["joints"]
                # Apply smoothing coefficient
                alpha = 1.0 - smoothing  # higher smoothing yields smaller movements
                r_arm_offset[0] = r_arm_offset[0] * alpha
                r_arm_offset[1] = r_arm_offset[1] * alpha
                l_arm_offset[0] = l_arm_offset[0] * alpha
                l_arm_offset[1] = l_arm_offset[1] * alpha

            joints["r_elbow"] = [base_joints["r_elbow"][0] + sway_offset + r_arm_offset[0] * 0.5, base_joints["r_elbow"][1] + r_arm_offset[1] * 0.4]
            joints["l_elbow"] = [base_joints["l_elbow"][0] + sway_offset + l_arm_offset[0] * 0.5, base_joints["l_elbow"][1] + l_arm_offset[1] * 0.4]
            
            joints["r_wrist"] = [base_joints["r_wrist"][0] + sway_offset + r_arm_offset[0], base_joints["r_wrist"][1] + r_arm_offset[1]]
            joints["l_wrist"] = [base_joints["l_wrist"][0] + sway_offset + l_arm_offset[0], base_joints["l_wrist"][1] + l_arm_offset[1]]

            pose_data.append({
                "frame_index": frame,
                "timestamp": t,
                "joints": joints
            })

        # Save to file
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"pose_sequence": pose_data}, f, indent=2)

    def _monitor_inference_logs(self) -> None:
        """Parse stdout/stderr logs of MimicMotion process to resolve progress bar updates."""
        if not self._process or not self._process.stderr:
            return

        # Matches output patterns like "Step: 15/25" or "Progress: 60%"
        progress_regex = re.compile(r"(?:step|progress|frame):\s*(\d+)/?(\d+)?")

        for line in self._process.stderr:
            line = line.strip().lower()
            if not line:
                continue

            match = progress_regex.search(line)
            if match:
                current = int(match.group(1))
                total = int(match.group(2)) if match.group(2) else 100
                
                # SVD rendering is row 3 (0.3) to 1.0
                prog = 0.3 + (current / total) * 0.7
                self.job.update_status("running", prog)
                self._logger.debug(f"Motion step: {current}/{total}")
            else:
                if "loading" in line or "pose" in line:
                    self._logger.info(f"MimicMotion: {line}")

    def cancel(self) -> None:
        """Terminate active subprocess."""
        self._logger.info("Cancellation requested.")
        if self._process:
            try:
                self._process.terminate()
                self._logger.info("Process terminated.")
            except Exception as e:
                self._logger.error(f"Error terminating process: {e}")
        self.job.update_status("failed", self.job.progress, error_message="Job was cancelled by the user.")
