"""Abstract Interface for Lip Synchronization.

Defines the LipSyncEngine contract that future AI lip-matching modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class LipSyncEngine(ABC):
    """Abstract base class for audio-to-video lip-matching sync modules."""

    @abstractmethod
    def sync_lips(
        self,
        presenter_video_path: Path,
        audio_path: Path,
        output_path: Path
    ) -> Path:
        """Apply lip synchronization overlay onto a presenter video clip matching a voice track.

        Args:
            presenter_video_path: Video showing presenter speaking (possibly with wrong lips).
            audio_path: The target voice track audio.
            output_path: Target video file path to write.

        Returns:
            The Path to the synthesized and lip-synchronized video.
        """
        pass
