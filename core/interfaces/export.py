"""Abstract Interface for Video Export.

Defines the ExportEngine contract that future encoding and publishing modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class ExportEngine(ABC):
    """Abstract base class for final video encoding and transcoding."""

    @abstractmethod
    def export_video(
        self,
        input_video_path: Path,
        output_video_path: Path,
        quality: str = "High",
        codec: str = "h264"
    ) -> Path:
        """Encode, scale, and compress raw compiled video files into standard release files.

        Args:
            input_video_path: Video file containing edits.
            output_video_path: Target path to write output.
            quality: Quality profile name (Low, Medium, High).
            codec: String video codec encoder (e.g. h264, hevc, av1).

        Returns:
            The Path to the finalized compressed output file.
        """
        pass
