"""AssetManager for AI News Studio.

Coordinates indexing, discovery, and path verification for visual, audio, and icon assets.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional


class AssetManager:
    """Manages static and user-uploaded media assets (presenter cards, voice files, UI icons)."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the AssetManager.

        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.assets_dir = self.workspace_dir / "assets"
        self.presenters_dir = self.assets_dir / "presenters"
        self.voices_dir = self.assets_dir / "voices"
        self.icons_dir = self.assets_dir / "icons"

        # Create subfolders if missing
        self.presenters_dir.mkdir(parents=True, exist_ok=True)
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.icons_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"AssetManager setup at {self.assets_dir}")

        # Default system presets
        self._default_presenters = [
            {"id": "pres_news_male_1", "name": "Marcus (News Anchor)", "gender": "Male", "avatar": "marcus.png", "type": "Studio 3D"},
            {"id": "pres_tech_female_1", "name": "Evelyn (Tech Reporter)", "gender": "Female", "avatar": "evelyn.png", "type": "Photorealistic"},
            {"id": "pres_finance_male_2", "name": "David (Finance Host)", "gender": "Male", "avatar": "david.png", "type": "Cartoon Animated"},
            {"id": "pres_casual_female_2", "name": "Clara (Vlogger style)", "gender": "Female", "avatar": "clara.png", "type": "Photorealistic"}
        ]

        self._default_voices = [
            {"id": "voice_cloned_rachel", "name": "Rachel (Professional, US)", "gender": "Female", "sample": "rachel_sample.wav", "mood": "Professional"},
            {"id": "voice_cloned_antoni", "name": "Antoni (Deep Baritone, UK)", "gender": "Male", "sample": "antoni_sample.wav", "mood": "Narrative"},
            {"id": "voice_cloned_dom", "name": "Dominic (Energetic, US)", "gender": "Male", "sample": "dom_sample.wav", "mood": "Excited"},
            {"id": "voice_cloned_bella", "name": "Bella (Warm, AU)", "gender": "Female", "sample": "bella_sample.wav", "mood": "Conversational"}
        ]

    def get_presenters(self) -> List[Dict[str, Any]]:
        """Retrieve list of all available presenters (default presets + custom scans).

        Returns:
            List of dictionaries containing presenter attributes.
        """
        # Read from folder could happen in production
        presenters = self._default_presenters.copy()
        
        # Scan presenters directory for custom presenter profiles
        # Format assumed: folder/json file or subdirectories
        for p_path in self.presenters_dir.glob("*.json"):
            try:
                import json
                with open(p_path, "r", encoding="utf-8") as f:
                    custom_pres = json.load(f)
                    # Verify required keys
                    if "id" in custom_pres and "name" in custom_pres:
                        presenters.append(custom_pres)
            except Exception as e:
                self._logger.error(f"Failed to load custom presenter from {p_path}: {e}")
                
        return presenters

    def get_voices(self) -> List[Dict[str, Any]]:
        """Retrieve list of available voices.

        Returns:
            List of dictionaries representing voice styles.
        """
        voices = self._default_voices.copy()

        # Scan for custom voice models
        for v_path in self.voices_dir.glob("*.json"):
            try:
                import json
                with open(v_path, "r", encoding="utf-8") as f:
                    custom_voice = json.load(f)
                    if "id" in custom_voice and "name" in custom_voice:
                        voices.append(custom_voice)
            except Exception as e:
                self._logger.error(f"Failed to load custom voice profile from {v_path}: {e}")

        return voices

    def get_icon_path(self, icon_name: str) -> Optional[Path]:
        """Resolve path to an icon image. If not found in custom asset folder, returns None.

        Args:
            icon_name: Name of the icon (e.g. dashboard.png).

        Returns:
            Path object or None.
        """
        target = self.icons_dir / icon_name
        if target.exists():
            return target
        return None
