"""Configuration settings for the Voice Engine.
"""

from pathlib import Path
from typing import Any, Dict

from core.voice.voice_profile import VoiceProfile


class VoiceConfig:
    """Stores parameters for F5-TTS voice synthesis speech generation tasks."""

    def __init__(
        self,
        profile: VoiceProfile,
        script_text: str,
        output_audio_path: Path,
        device: str = "cuda",
        auto_download: bool = True,
    ) -> None:
        """Initialize VoiceConfig.

        Args:
            profile: VoiceProfile clone speaker.
            script_text: Text script to generate speech for.
            output_audio_path: Target path to write output WAV file.
            device: Compute device ('cuda' or 'cpu').
            auto_download: Automatically download models if missing.
        """
        self.profile = profile
        self.script_text = script_text
        self.output_audio_path = Path(output_audio_path)
        self.device = device
        self.auto_download = auto_download

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "profile": self.profile.to_dict(),
            "script_text": self.script_text,
            "output_audio_path": str(self.output_audio_path),
            "device": self.device,
            "auto_download": self.auto_download,
        }
