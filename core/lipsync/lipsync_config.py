"""Configuration settings for the Lip Sync Engine.
"""

from pathlib import Path
from typing import Any, Dict


class LipSyncConfig:
    """Stores parameters for LatentSync lip synchronization execution tasks."""

    def __init__(
        self,
        presenter_video_path: Path,
        audio_path: Path,
        output_video_path: Path,
        quality: str = "High",
        guidance_scale: float = 1.5,
        inference_steps: int = 20,
        device: str = "cuda",
        auto_download: bool = True,
    ) -> None:
        """Initialize LipSyncConfig.

        Args:
            presenter_video_path: Input video of the speaking presenter.
            audio_path: Audio script track to sync lips with.
            output_video_path: Path to write the output synchronized MP4 file.
            quality: Quality preset ("Fast" or "High").
            guidance_scale: Classifier-free guidance scale.
            inference_steps: Number of DDIM steps.
            device: Compute device mode ('cuda' or 'cpu').
            auto_download: Automatically download repo and checkpoints if missing.
        """
        self.presenter_video_path = Path(presenter_video_path)
        self.audio_path = Path(audio_path)
        self.output_video_path = Path(output_video_path)
        self.quality = quality
        self.guidance_scale = guidance_scale
        self.inference_steps = inference_steps
        self.device = device
        self.auto_download = auto_download

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "presenter_video_path": str(self.presenter_video_path),
            "audio_path": str(self.audio_path),
            "output_video_path": str(self.output_video_path),
            "quality": self.quality,
            "guidance_scale": self.guidance_scale,
            "inference_steps": self.inference_steps,
            "device": self.device,
            "auto_download": self.auto_download,
        }
