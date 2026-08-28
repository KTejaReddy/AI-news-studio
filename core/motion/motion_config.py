"""Configuration settings for the Motion Engine.
"""

from pathlib import Path
from typing import Any, Dict


class MotionConfig:
    """Stores configuration and hyperparameters for pose-driven body motion generation."""

    def __init__(
        self,
        source_image_path: Path,
        output_video_path: Path,
        motion_style: str = "Professional",
        gesture_strength: float = 1.0,
        enable_idle_motion: bool = True,
        motion_smoothing: float = 0.5,
        device: str = "cuda",
        auto_download: bool = True,
    ) -> None:
        """Initialize MotionConfig.

        Args:
            source_image_path: Path to the static presenter image.
            output_video_path: Target path to write the generated body animation video.
            motion_style: Preset motion template name (Professional, Casual, Energetic, News Anchor, Podcast).
            gesture_strength: Multiplier for hand/arm movement range (0.0 to 2.0).
            enable_idle_motion: Toggles automatic breathing/torso sway when hand gestures are inactive.
            motion_smoothing: Low-pass filter smoothing coefficient (0.0 to 1.0).
            device: Compute device ('cuda' or 'cpu').
            auto_download: Automatically download models if missing.
        """
        self.source_image_path = Path(source_image_path)
        self.output_video_path = Path(output_video_path)
        self.motion_style = motion_style
        self.gesture_strength = gesture_strength
        self.enable_idle_motion = enable_idle_motion
        self.motion_smoothing = motion_smoothing
        self.device = device
        self.auto_download = auto_download

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "source_image_path": str(self.source_image_path),
            "output_video_path": str(self.output_video_path),
            "motion_style": self.motion_style,
            "gesture_strength": self.gesture_strength,
            "enable_idle_motion": self.enable_idle_motion,
            "motion_smoothing": self.motion_smoothing,
            "device": self.device,
            "auto_download": self.auto_download,
        }
