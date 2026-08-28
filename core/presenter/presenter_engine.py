"""Concrete implementation of the PresenterEngine interface using LivePortrait.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interfaces.presenter import PresenterEngine as IPresenterEngine
from core.presenter.presenter_config import PresenterConfig
from core.presenter.presenter_controller import PresenterController
from core.presenter.presenter_job import PresenterJob


class PresenterEngine(IPresenterEngine):
    """Integrates KwaiVGI LivePortrait model engine to render virtual news anchors."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize PresenterEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = PresenterController()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("PresenterEngine initialized using LivePortrait backend.")

    def generate_presenter_video(
        self,
        presenter_id: str,
        audio_path: Path,
        output_path: Path,
        aspect_ratio: str = "16:9",
        resolution_width: int = 1920,
        resolution_height: int = 1080
    ) -> Path:
        """Standard interface implementation. Animates default presenter preset.

        Args:
            presenter_id: ID of the preset presenter.
            audio_path: Path to the audio file.
            output_path: Output target path.
            aspect_ratio: Desired aspect ratio.
            resolution_width: Target width.
            resolution_height: Target height.

        Returns:
            Path of generated output file.
        """
        self._logger.info(f"Generating video for preset anchor: {presenter_id}")
        
        # Resolve preset avatar image path (e.g. from assets)
        # For default execution, we'll map preset IDs to static image files
        avatar_img = self.workspace_dir / "assets" / "presenters" / f"{presenter_id}.png"
        if not avatar_img.exists():
            # Create a fallback/default image path
            avatar_img = self.workspace_dir / "assets" / "presenters" / "default.png"
            avatar_img.parent.mkdir(parents=True, exist_ok=True)
            if not avatar_img.exists():
                with open(avatar_img, "w", encoding="utf-8") as f:
                    f.write("FALLBACK IMAGE BYTES")

        # Resolve standard driving video path (e.g., standard speech template)
        driving_video = self.workspace_dir / "assets" / "driving" / "default_driving.mp4"
        driving_video.parent.mkdir(parents=True, exist_ok=True)
        if not driving_video.exists():
            with open(driving_video, "w", encoding="utf-8") as f:
                f.write("FALLBACK DRIVING VIDEO BYTES")

        # Setup config
        config = PresenterConfig(
            source_image_path=avatar_img,
            driving_video_path=driving_video,
            output_video_path=output_path,
            device="cuda",
            flag_crop=True,
            flag_stitching=True
        )

        # Submit background job and block until complete
        job = self.controller.submit_job(config)
        self._logger.info(f"Submitted background presenter job: {job.job_id}")

        # Block waiting for execution (standard synchronous interface behavior)
        import time
        while job.status in ["pending", "downloading_code", "downloading_weights", "running"]:
            time.sleep(0.5)

        if job.status == "completed":
            return output_path
        else:
            raise RuntimeError(f"Failed to generate presenter video: {job.error_message}")

    def get_expression_profiles(self, presenter_id: str) -> List[str]:
        """Get expression profiles available.

        Args:
            presenter_id: ID of the presenter.

        Returns:
            List of emotion strings.
        """
        return ["neutral", "smiling", "serious", "surprised"]

    def animate_portrait(
        self,
        source_image_path: Path,
        driving_video_path: Path,
        output_video_path: Path,
        device: str = "cuda",
        flag_crop: bool = True,
        flag_stitching: bool = True,
        flag_eye_retargeting: bool = False,
        flag_lip_retargeting: bool = False,
        flag_relative_motion: bool = True,
        flag_do_blinking: bool = True,
        flag_do_head_motion: bool = True,
        flag_do_shoulder_motion: bool = True,
        flag_do_upper_body: bool = True,
        flag_do_eye_smooth: bool = True,
        flag_facial_stability: bool = True,
        auto_download: bool = True,
    ) -> PresenterJob:
        """Animate a custom image using a custom driving video.

        Args:
            source_image_path: Path of source face.
            driving_video_path: Path of driving motion.
            output_video_path: Target path for output.
            device: Compute device.
            flag_crop: Toggle facial auto-crop.
            flag_stitching: Toggle border stitching.
            flag_eye_retargeting: Toggle eye size tuning.
            flag_lip_retargeting: Toggle mouth size tuning.
            flag_relative_motion: Toggle relative keypoints.
            flag_do_blinking: Toggle blinking.
            flag_do_head_motion: Toggle head movement.
            flag_do_shoulder_motion: Toggle shoulder movement.
            flag_do_upper_body: Toggle upper-body drift.
            flag_do_eye_smooth: Toggle eye smoothing.
            flag_facial_stability: Toggle border noise stability.
            auto_download: Toggle auto setup.

        Returns:
            PresenterJob tracking instance.
        """
        config = PresenterConfig(
            source_image_path=source_image_path,
            driving_video_path=driving_video_path,
            output_video_path=output_video_path,
            device=device,
            flag_crop=flag_crop,
            flag_stitching=flag_stitching,
            flag_eye_retargeting=flag_eye_retargeting,
            flag_lip_retargeting=flag_lip_retargeting,
            flag_relative_motion=flag_relative_motion,
            flag_do_blinking=flag_do_blinking,
            flag_do_head_motion=flag_do_head_motion,
            flag_do_shoulder_motion=flag_do_shoulder_motion,
            flag_do_upper_body=flag_do_upper_body,
            flag_do_eye_smooth=flag_do_eye_smooth,
            flag_facial_stability=flag_facial_stability,
            auto_download=auto_download,
        )
        return self.controller.submit_job(config)
