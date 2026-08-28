"""VoiceProfile class for storing and loading voice profiles.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import uuid


class VoiceProfile:
    """Represents a voice clone profile containing reference audio metadata and transcriptions."""

    def __init__(
        self,
        name: str,
        ref_text: str,
        ref_audio_path: Path,
        profile_id: Optional[str] = None
    ) -> None:
        """Initialize VoiceProfile.

        Args:
            name: Display name for the voice profile.
            ref_text: The spoken transcription of the reference audio clip.
            ref_audio_path: Path to the reference audio WAV/MP3 file.
            profile_id: Unique UUID string, created if None.
        """
        self.profile_id = profile_id or str(uuid.uuid4())
        self.name = name
        self.ref_text = ref_text
        self.ref_audio_path = Path(ref_audio_path)

    def save(self, voices_dir: Path) -> Path:
        """Save voice profile metadata and copy reference audio to assets folder.

        Args:
            voices_dir: Subdirectory assets/voices.

        Returns:
            The Path to the saved profile directory.
        """
        profile_dir = Path(voices_dir) / self.profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Copy audio file to profile directory if it's not already there
        target_audio_path = profile_dir / "ref_audio.wav"
        if self.ref_audio_path.resolve() != target_audio_path.resolve() and self.ref_audio_path.exists():
            import shutil
            shutil.copy2(self.ref_audio_path, target_audio_path)
            self.ref_audio_path = target_audio_path

        # Write metadata JSON
        metadata_file = profile_dir / "profile.json"
        metadata = {
            "profile_id": self.profile_id,
            "name": self.name,
            "ref_text": self.ref_text,
            "ref_audio_path": str(self.ref_audio_path.name)  # store filename relative to folder
        }
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return profile_dir

    @classmethod
    def load(cls, profile_dir: Path) -> "VoiceProfile":
        """Load a VoiceProfile from its directory.

        Args:
            profile_dir: Profile directory containing profile.json.

        Returns:
            Reconstructed VoiceProfile instance.
        """
        profile_dir = Path(profile_dir)
        metadata_file = profile_dir / "profile.json"
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"VoiceProfile metadata not found at: {metadata_file}")

        with open(metadata_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        audio_filename = data.get("ref_audio_path", "ref_audio.wav")
        audio_path = profile_dir / audio_filename

        return cls(
            name=data["name"],
            ref_text=data["ref_text"],
            ref_audio_path=audio_path,
            profile_id=data["profile_id"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert voice profile attributes to a dictionary."""
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "ref_text": self.ref_text,
            "ref_audio_path": str(self.ref_audio_path),
        }
