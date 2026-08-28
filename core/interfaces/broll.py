"""Abstract Interface for B-roll Generation.

Defines the BrollEngine contract that future AI video diffusers or footage selectors must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BrollEngine(ABC):
    """Abstract base class for generating or selecting B-roll cinematic clips."""

    @abstractmethod
    def generate_broll_clip(
        self,
        prompt: str,
        duration_seconds: float,
        output_path: Path,
        aspect_ratio: str = "16:9",
        fps: int = 30
    ) -> Path:
        """Generate a short video clip based on a prompt.

        Args:
            prompt: Text description of the desired visual.
            duration_seconds: Visual clip length.
            output_path: Target video file path to write clip.
            aspect_ratio: Configured aspect ratio.
            fps: Frame rate for the clip.

        Returns:
            The Path to the generated B-roll video clip.
        """
        pass
