"""Configuration settings for the Presenter Engine and LivePortrait processor.
"""

from pathlib import Path
from typing import Any, Dict, Optional


class PresenterConfig:
    """Stores setup and hyper-parameters for portrait animation processing."""

    def __init__(
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
    ) -> None:
        """Initialize PresenterConfig.

        Args:
            source_image_path: Path to the static presenter portrait image.
            driving_video_path: Path to the driving motion video (.mp4).
            output_video_path: Target path to write the compiled animated video.
            device: Computing device ('cuda' or 'cpu').
            flag_crop: Crop source image to standard face frame dimensions.
            flag_stitching: Apply stitching module to merge face back into background.
            flag_eye_retargeting: Enable specific eye size retargeting adjustments.
            flag_lip_retargeting: Enable specific lip size retargeting adjustments.
            flag_relative_motion: Apply relative keypoint motions instead of absolute coordinates.
            flag_do_blinking: Enable natural eye blinking motion synthesis.
            flag_do_head_motion: Enable head pitch/yaw/roll motion mapping.
            flag_do_shoulder_motion: Enable subtle shoulder motion mapping.
            flag_do_upper_body: Enable upper-body secondary motion mapping.
            flag_do_eye_smooth: Enable Kalman-like smoothing for eye gaze vectors.
            flag_facial_stability: Restrict jittering noise in background borders.
            auto_download: Automatically clone repository and download weights if missing.
        """
        self.source_image_path = Path(source_image_path)
        self.driving_video_path = Path(driving_video_path)
        self.output_video_path = Path(output_video_path)
        self.device = device
        self.flag_crop = flag_crop
        self.flag_stitching = flag_stitching
        self.flag_eye_retargeting = flag_eye_retargeting
        self.flag_lip_retargeting = flag_lip_retargeting
        self.flag_relative_motion = flag_relative_motion
        self.flag_do_blinking = flag_do_blinking
        self.flag_do_head_motion = flag_do_head_motion
        self.flag_do_shoulder_motion = flag_do_shoulder_motion
        self.flag_do_upper_body = flag_do_upper_body
        self.flag_do_eye_smooth = flag_do_eye_smooth
        self.flag_facial_stability = flag_facial_stability
        self.auto_download = auto_download

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "source_image_path": str(self.source_image_path),
            "driving_video_path": str(self.driving_video_path),
            "output_video_path": str(self.output_video_path),
            "device": self.device,
            "flag_crop": self.flag_crop,
            "flag_stitching": self.flag_stitching,
            "flag_eye_retargeting": self.flag_eye_retargeting,
            "flag_lip_retargeting": self.flag_lip_retargeting,
            "flag_relative_motion": self.flag_relative_motion,
            "flag_do_blinking": self.flag_do_blinking,
            "flag_do_head_motion": self.flag_do_head_motion,
            "flag_do_shoulder_motion": self.flag_do_shoulder_motion,
            "flag_do_upper_body": self.flag_do_upper_body,
            "flag_do_eye_smooth": self.flag_do_eye_smooth,
            "flag_facial_stability": self.flag_facial_stability,
            "auto_download": self.auto_download,
        }
