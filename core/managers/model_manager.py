"""ModelManager for AI News Studio.

Checks download status, path mappings, and sizes of local AI neural net model files.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.managers.config_manager import ConfigManager


class ModelManager:
    """Manages check status, directory sizing, and metadata for required AI model files."""

    def __init__(self, workspace_dir: Path, config_manager: ConfigManager) -> None:
        """Initialize the ModelManager.

        Args:
            workspace_dir: Workspace root directory.
            config_manager: System configuration manager.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.config_manager = config_manager
        
        # Read models directory from settings
        models_folder_name = self.config_manager.get("model_folder", "models")
        self.models_dir = self.workspace_dir / models_folder_name
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"ModelManager scanning directory: {self.models_dir}")

        # List of required model definitions for AI news video generation
        self._required_models = [
            {
                "id": "model_voice_tts",
                "name": "Voice Synthesis & TTS Engine",
                "filename": "tts_v2.ckpt",
                "size_gb": 1.2,
                "description": "Multi-speaker voice cloner and text-to-speech converter."
            },
            {
                "id": "model_talking_head",
                "name": "Presenter Talking Head Generator",
                "filename": "talking_head_v3.bin",
                "size_gb": 2.4,
                "description": "Generates lifelike presenter expressions and head motions."
            },
            {
                "id": "model_lipsync",
                "name": "LipSync Audio-Video Sync",
                "filename": "lipsync_wav2lip.pth",
                "size_gb": 0.85,
                "description": "Synchronizes presenter lip movements with voice waveforms."
            },
            {
                "id": "model_broll_gen",
                "name": "B-roll Visual Composer",
                "filename": "cinematic_diff_v1.safetensors",
                "size_gb": 4.1,
                "description": "Text-to-video diffuser for cinematic filler footage."
            }
        ]

    def get_model_status(self) -> List[Dict[str, Any]]:
        """Check local files and return state information for all defined models.

        Returns:
            List of dictionaries listing status, paths, sizes, and installation status.
        """
        status_list: List[Dict[str, Any]] = []

        for model in self._required_models:
            expected_path = self.models_dir / model["id"] / model["filename"]
            is_downloaded = expected_path.exists()
            
            # Read size if downloaded, else use standard definition
            actual_size = expected_path.stat().st_size / (1024 * 1024 * 1024) if is_downloaded else 0.0

            status_list.append({
                "id": model["id"],
                "name": model["name"],
                "filename": model["filename"],
                "expected_size_gb": model["size_gb"],
                "actual_size_gb": round(actual_size, 2) if is_downloaded else 0.0,
                "description": model["description"],
                "installed": is_downloaded,
                "path": str(expected_path) if is_downloaded else None
            })

        return status_list

    def install_mock_model(self, model_id: str, progress_callback: Optional[Callable[[float], None]] = None) -> bool:
        """Create a mock model file on disk to simulate download/install completion.

        Args:
            model_id: The ID of the model to install.
            progress_callback: Optional callback for simulation progress percentage (0.0 to 1.0).

        Returns:
            True if installation succeeded, False if ID not recognized.
        """
        # Find model metadata
        meta = next((m for m in self._required_models if m["id"] == model_id), None)
        if not meta:
            self._logger.error(f"Cannot install unknown model: {model_id}")
            return False

        import time
        model_subfolder = self.models_dir / model_id
        model_subfolder.mkdir(parents=True, exist_ok=True)
        model_filepath = model_subfolder / meta["filename"]

        self._logger.info(f"Simulating installation of model: {meta['name']}")

        # Simulate progressive download if callback is provided
        if progress_callback:
            for step in range(1, 11):
                time.sleep(0.1)  # Brief simulated download delay
                progress_callback(step / 10.0)

        # Create dummy file with small mock payload to simulate download completion
        try:
            with open(model_filepath, "w", encoding="utf-8") as f:
                f.write(f"MOCK WEIGHTS FOR {meta['name']}\nVersion: 1.0\nCreated: Mock Setup\n")
            self._logger.info(f"Model installed successfully at: {model_filepath}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to create model weights: {e}")
            return False

    def remove_model(self, model_id: str) -> bool:
        """Delete a local model file if it exists.

        Args:
            model_id: ID of the model.

        Returns:
            True if deleted, False if not found/error.
        """
        meta = next((m for m in self._required_models if m["id"] == model_id), None)
        if not meta:
            return False

        model_filepath = self.models_dir / model_id / meta["filename"]
        if model_filepath.exists():
            try:
                model_filepath.unlink()
                # Clean parent dir if empty
                parent_dir = model_filepath.parent
                if not any(parent_dir.iterdir()):
                    parent_dir.rmdir()
                self._logger.info(f"Removed model file: {model_filepath}")
                return True
            except Exception as e:
                self._logger.error(f"Error removing model file: {e}")
                return False
        return False
