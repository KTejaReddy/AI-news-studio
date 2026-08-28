"""Abstract Interface for Voice Synthesis.

Defines the VoiceEngine contract that future AI TTS and voice cloning modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class VoiceEngine(ABC):
    """Abstract base class for speech synthesis and voice cloning engines."""

    @abstractmethod
    def synthesize_speech(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        quality: str = "High"
    ) -> Path:
        """Synthesize text script into speech audio.

        Args:
            text: Script text to read.
            voice_id: ID of the voice preset or clone model.
            output_path: Path to write the synthesized audio file (e.g. WAV or MP3).
            quality: Quality profile name (e.g. Low, Medium, High).

        Returns:
            The Path where the audio file was written.
        """
        pass

    @abstractmethod
    def clone_voice_model(
        self,
        sample_paths: List[Path],
        voice_name: str,
        output_model_path: Path
    ) -> Dict[str, Any]:
        """Train a cloned voice model from audio sample files.

        Args:
            sample_paths: List of audio sample files containing speaker voice.
            voice_name: Name of the cloned voice profile.
            output_model_path: Target path to write weight/model file.

        Returns:
            Dictionary containing metadata of the cloned voice.
        """
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Get list of ISO language codes supported by this model.

        Returns:
            List of supported language codes (e.g. ['en', 'es', 'fr']).
        """
        pass
