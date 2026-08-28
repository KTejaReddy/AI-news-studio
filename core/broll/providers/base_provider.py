"""Base provider interface for B-roll generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BrollProvider(ABC):
    """Abstract base class interface that all B-roll visual generation drivers must implement."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        duration: float,
        aspect_ratio: str,
        fps: int,
        output_path: Path
    ) -> Path:
        """Generate a visual media file (video or image) under target path.

        Args:
            prompt: Synthesized text prompt.
            duration: Desired video duration in seconds (if video).
            aspect_ratio: Configured aspect ratio ("16:9", "9:16", "1:1").
            fps: Video frames per second.
            output_path: The target path to write the media.

        Returns:
            The Path to the generated asset file.
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the provider name."""
        pass
