"""Configuration Manager for AI News Studio.

Handles reading, writing, and validating system configuration parameters.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Manages application configuration, loading defaults and user-specific profiles."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the ConfigManager with a workspace directory.

        Args:
            workspace_dir: The root directory of the workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.default_config_path = self.workspace_dir / "config" / "default_config.json"
        self.user_config_path = self.workspace_dir / "config" / "config.json"
        self._config: Dict[str, Any] = {}
        self._logger = logging.getLogger(self.__class__.__name__)
        
        self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from the user config file or fall back to defaults.

        Returns:
            The loaded configuration dictionary.
        """
        # First load default configuration
        defaults: Dict[str, Any] = {}
        if self.default_config_path.exists():
            try:
                with open(self.default_config_path, "r", encoding="utf-8") as f:
                    defaults = json.load(f)
            except Exception as e:
                self._logger.error(f"Failed to read default config at {self.default_config_path}: {e}")
        else:
            self._logger.warning(f"Default config not found at {self.default_config_path}. Using hardcoded fallback.")
            defaults = {
                "theme": "dark",
                "language": "en",
                "device_mode": "GPU",
                "output_folder": "output",
                "model_folder": "models",
                "temp_folder": "temp",
                "cache_folder": "cache",
                "quality": "High",
                "aspect_ratio": "16:9"
            }

        # Merge with user configuration if it exists
        self._config = defaults.copy()
        if self.user_config_path.exists():
            try:
                with open(self.user_config_path, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
                    self._config.update(user_settings)
            except Exception as e:
                self._logger.error(f"Failed to read user config at {self.user_config_path}: {e}. Reverting to defaults.")

        # Ensure directories exist according to configuration
        self._ensure_config_directories()
        return self._config

    def _ensure_config_directories(self) -> None:
        """Ensure that the folders defined in config exist relative to the workspace."""
        for folder_key in ["output_folder", "model_folder", "temp_folder", "cache_folder"]:
            folder_name = self._config.get(folder_key)
            if folder_name:
                folder_path = self.workspace_dir / folder_name
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self._logger.error(f"Failed to create config directory {folder_path}: {e}")

    def save_config(self) -> None:
        """Save the current configuration to the user config file."""
        try:
            self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.user_config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            self._logger.info(f"Configuration saved successfully to {self.user_config_path}")
        except Exception as e:
            self._logger.error(f"Failed to write user config to {self.user_config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Config key.
            default: Default value if not found.

        Returns:
            The config value.
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Config key.
            value: Value to set.
        """
        self._config[key] = value
        self._ensure_config_directories()
        self.save_config()

    @property
    def config_dict(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config.copy()
