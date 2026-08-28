"""Abstract Interface for Editor Engine.

Defines the EditorEngine contract that future automated timeline editors must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class EditorEngine(ABC):
    """Abstract base class for combining media elements, B-rolls, and audio tracks."""

    @abstractmethod
    def assemble_edit_timeline(
        self,
        presenter_video_path: Path,
        broll_clips: List[Dict[str, Any]],
        voice_audio_path: Path,
        background_music_path: Optional[Path],
        subtitles_path: Optional[Path],
        output_path: Path,
        music_volume_reduction: float = 0.8
    ) -> Path:
        """Combine video tracks, sound overlays, and templates into a finished draft.

        Args:
            presenter_video_path: Video track showing the speaking presenter.
            broll_clips: List of B-roll overlays with timing details:
                         e.g. {'path': Path, 'start_time': float, 'duration': float}
            voice_audio_path: Primary spoken voice audio file.
            background_music_path: Secondary background music file.
            subtitles_path: Path to transcription file (SRT).
            output_path: Target video file path to write compiled edits.
            music_volume_reduction: Gain multiplier to apply to background track (0.0 to 1.0).

        Returns:
            The Path to the final assembled video clip.
        """
        pass
