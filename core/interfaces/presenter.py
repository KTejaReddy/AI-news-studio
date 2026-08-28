"""Abstract Interface for Presenter generation.

Defines the PresenterEngine contract that future AI visual presenter modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class PresenterEngine(ABC):
    """Abstract base class for virtual video presenter and anchor generation."""

    @abstractmethod
    def generate_presenter_video(
        self,
        presenter_id: str,
        audio_path: Path,
        output_path: Path,
        aspect_ratio: str = "16:9",
        resolution_width: int = 1920,
        resolution_height: int = 1080
    ) -> Path:
        """Render the talking head anchor video synchronized to the provided audio track.

        Args:
            presenter_id: ID identifier of the selected presenter avatar.
            audio_path: Path to the audio file containing speech.
            output_path: Target video file output path.
            aspect_ratio: Desired frame layout ratio (16:9, 9:16).
            resolution_width: Output horizontal resolution pixels.
            resolution_height: Output vertical resolution pixels.

        Returns:
            The Path to the generated video file.
        """
        pass

    @abstractmethod
    def get_expression_profiles(self, presenter_id: str) -> List[str]:
        """Query emotional expression profiles supported by this presenter (e.g. happy, serious).

        Args:
            presenter_id: ID of the presenter.

        Returns:
            List of supported emotion keys.
        """
        pass
