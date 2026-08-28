"""Concrete implementation of the MotionEngine interface using MimicMotion.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from core.interfaces.motion import MotionEngine as IMotionEngine
from core.motion.motion_config import MotionConfig
from core.motion.motion_controller import MotionController
from core.motion.motion_job import MotionJob


class MotionEngine(IMotionEngine):
    """Integrates MimicMotion pose diffusion to animate static human pictures."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the MotionEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = MotionController()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("MotionEngine initialized using MimicMotion backend.")

    def animate_still_presenter(
        self,
        image_path: Path,
        motion_template: Dict[str, Any],
        output_path: Path,
        duration_seconds: float
    ) -> Path:
        """Standard interface implementation. Animates body using template dictionary.

        Args:
            image_path: Static presenter image.
            motion_template: Dictionary detailing landmarks or keyframe settings.
            output_path: Target path for output video.
            duration_seconds: Video duration in seconds.

        Returns:
            The generated video Path.
        """
        self._logger.info(f"Animating still presenter image {image_path.name} to {output_path.name}")
        
        # Configure motion config based on template dict keys
        style = motion_template.get("style", "Professional")
        strength = motion_template.get("strength", 1.0)
        enable_idle = motion_template.get("enable_idle", True)
        smoothing = motion_template.get("smoothing", 0.5)

        config = MotionConfig(
            source_image_path=image_path,
            output_video_path=output_path,
            motion_style=style,
            gesture_strength=strength,
            enable_idle_motion=enable_idle,
            motion_smoothing=smoothing,
            device="cuda"
        )

        # Submit background job and block until complete (synchronous interface flow)
        job = self.controller.submit_job(config)
        self._logger.info(f"Submitted background motion job: {job.job_id}")

        import time
        while job.status in ["pending", "downloading_code", "downloading_weights", "running"]:
            time.sleep(0.5)

        if job.status == "completed":
            return output_path
        else:
            raise RuntimeError(f"Failed to animate body movement: {job.error_message}")

    def generate_body_motion(
        self,
        source_image_path: Path,
        output_video_path: Path,
        motion_style: str = "Professional",
        gesture_strength: float = 1.0,
        enable_idle_motion: bool = True,
        motion_smoothing: float = 0.5,
        device: str = "cuda",
        auto_download: bool = True
    ) -> MotionJob:
        """Submit custom body generation job to the queue controller.

        Args:
            source_image_path: Static face portrait image.
            output_video_path: Video file output path.
            motion_style: Movement preset name.
            gesture_strength: Gesture amplitude multiplier.
            enable_idle_motion: Toggle breathing/sway animations.
            motion_smoothing: Motion low-pass filter.
            device: Compute device.
            auto_download: Auto clone/download models.

        Returns:
            MotionJob tracker instance.
        """
        config = MotionConfig(
            source_image_path=source_image_path,
            output_video_path=output_video_path,
            motion_style=motion_style,
            gesture_strength=gesture_strength,
            enable_idle_motion=enable_idle_motion,
            motion_smoothing=motion_smoothing,
            device=device,
            auto_download=auto_download
        )
        return self.controller.submit_job(config)
