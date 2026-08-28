"""Abstract Interface for Subtitle/Caption Generation.

Defines the CaptionEngine contract that future transcription/ASR modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class CaptionEngine(ABC):
    """Abstract base class for transcribing voice audio into subtitle files (SRT)."""

    @abstractmethod
    def generate_subtitles(
        self,
        audio_path: Path,
        output_srt_path: Path,
        max_chars_per_line: int = 40
    ) -> Path:
        """Transcribe speech in an audio file and format it as SRT.

        Args:
            audio_path: Input audio file containing spoken words.
            output_srt_path: Target SRT subtitle file path to write.
            max_chars_per_line: Limit characters per caption line.

        Returns:
            The Path to the generated SRT file.
        """
        pass
