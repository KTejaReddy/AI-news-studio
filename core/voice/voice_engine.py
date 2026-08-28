"""Concrete implementation of the VoiceEngine interface using F5-TTS.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.interfaces.voice import VoiceEngine as IVoiceEngine
from core.voice.voice_config import VoiceConfig
from core.voice.voice_controller import VoiceController
from core.voice.voice_job import VoiceJob
from core.voice.voice_profile import VoiceProfile


class VoiceEngine(IVoiceEngine):
    """Integrates F5-TTS voice cloning to synthesize spoken tracks from text scripts."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize VoiceEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = VoiceController()
        
        # Resolve voice profiles assets directory
        self.voices_dir = self.workspace_dir / "assets" / "voices"
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("VoiceEngine initialized using F5-TTS backend.")

    def synthesize_speech(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        quality: str = "High"
    ) -> Path:
        """Standard interface implementation. Synthesizes script into audio.

        Args:
            text: Script text to read.
            voice_id: Unique voice profile ID.
            output_path: Target path to write WAV.
            quality: Quality setting.

        Returns:
            The output WAV file path.
        """
        self._logger.info(f"Synthesizing speech: Profile={voice_id} -> {output_path.name}")

        # Load voice profile
        profile = self.load_profile(voice_id)
        if not profile:
            raise ValueError(f"Voice profile not found with ID: {voice_id}")

        config = VoiceConfig(
            profile=profile,
            script_text=text,
            output_audio_path=output_path,
            device="cuda"
        )

        # Submit background job and block until complete (synchronous interface flow)
        job = self.controller.submit_job(config)
        self._logger.info(f"Submitted background voice job: {job.job_id}")

        import time
        while job.status in ["pending", "downloading_weights", "running"]:
            time.sleep(0.5)

        if job.status == "completed":
            return output_path
        else:
            raise RuntimeError(f"Failed to synthesize speech: {job.error_message}")

    def clone_voice_model(
        self,
        sample_paths: List[Path],
        voice_name: str,
        output_model_path: Path
    ) -> Dict[str, Any]:
        """Clone voice from samples (standard interface stub, maps to profile creation).

        Args:
            sample_paths: Audio sample files.
            voice_name: Voice clone label.
            output_model_path: Output metadata target.

        Returns:
            Profile metadata dictionary.
        """
        if not sample_paths:
            raise ValueError("Reference audio samples list cannot be empty.")

        # Create voice profile using the first sample
        profile = self.create_profile(
            name=voice_name,
            ref_text="Reference transcription placeholder.",
            ref_audio_path=sample_paths[0]
        )
        
        # Save output path metadata
        output_model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_model_path, "w", encoding="utf-8") as f:
            import json
            json.dump(profile.to_dict(), f, indent=2)

        return profile.to_dict()

    def get_supported_languages(self) -> List[str]:
        """Get languages supported by F5-TTS.

        Returns:
            List of supported language codes.
        """
        return ["en", "zh", "ja", "ko", "de", "fr"]

    # --- Profile Manager Methods ---
    def create_profile(self, name: str, ref_text: str, ref_audio_path: Path) -> VoiceProfile:
        """Create, preprocess, and save a new VoiceProfile.

        Args:
            name: Display name.
            ref_text: Reference transcription.
            ref_audio_path: Reference audio WAV/MP3 path.

        Returns:
            The created VoiceProfile instance.
        """
        profile = VoiceProfile(name=name, ref_text=ref_text, ref_audio_path=ref_audio_path)
        profile.save(self.voices_dir)
        self._logger.info(f"Created reusable voice profile '{name}' [{profile.profile_id}]")
        return profile

    def load_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        """Load a single voice profile by ID.

        Args:
            profile_id: Profile UUID string.

        Returns:
            VoiceProfile instance or None if not found/corrupted.
        """
        profile_dir = self.voices_dir / profile_id
        if not profile_dir.exists():
            return None
        try:
            return VoiceProfile.load(profile_dir)
        except Exception as e:
            self._logger.error(f"Error loading voice profile {profile_id}: {e}")
            return None

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a voice profile and its files from disk.

        Args:
            profile_id: Profile UUID.

        Returns:
            True if deletion was successful, False otherwise.
        """
        profile_dir = self.voices_dir / profile_id
        if not profile_dir.exists():
            return False
        try:
            import shutil
            shutil.rmtree(profile_dir)
            self._logger.info(f"Deleted voice profile folder: {profile_dir}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to delete voice profile {profile_id}: {e}")
            return False

    def list_profiles(self) -> List[VoiceProfile]:
        """Scan directory and list all loadable VoiceProfiles.

        Returns:
            List of VoiceProfile instances.
        """
        profiles = []
        if not self.voices_dir.exists():
            return profiles

        for path in self.voices_dir.iterdir():
            if path.is_dir():
                metadata_file = path / "profile.json"
                if metadata_file.exists():
                    try:
                        p = VoiceProfile.load(path)
                        profiles.append(p)
                    except Exception as e:
                        self._logger.error(f"Failed loading profile at {path.name}: {e}")
                        
        # Sort by name
        profiles.sort(key=lambda x: x.name.lower())
        return profiles

    # --- Synthesis Wrapper Method ---
    def generate_cloned_speech(
        self,
        profile: VoiceProfile,
        script_text: str,
        output_audio_path: Path,
        device: str = "cuda",
        auto_download: bool = True
    ) -> VoiceJob:
        """Submit a voice cloning task to the queue controller.

        Args:
            profile: VoiceProfile clone speaker.
            script_text: Script text to read.
            output_audio_path: Target path for output WAV.
            device: Compute device.
            auto_download: Auto clone/download models.

        Returns:
            VoiceJob tracker instance.
        """
        config = VoiceConfig(
            profile=profile,
            script_text=script_text,
            output_audio_path=output_audio_path,
            device=device,
            auto_download=auto_download
        )
        return self.controller.submit_job(config)
