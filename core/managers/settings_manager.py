"""SettingsManager class for AI News Studio.

Acts as a clean, structured interface over ConfigManager, with support for
observer notifications when preferences update.
"""

import logging
from typing import Callable, Dict, List

from core.managers.config_manager import ConfigManager


class SettingsManager:
    """Provides type-safe property accessors and observer hooks for configuration settings."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize SettingsManager.

        Args:
            config_manager: The ConfigManager instance to wrap.
        """
        self.config = config_manager
        self._logger = logging.getLogger(self.__class__.__name__)
        self._listeners: Dict[str, List[Callable[[str, any], None]]] = {}

    def register_listener(self, key: str, callback: Callable[[str, any], None]) -> None:
        """Register a callback to invoke when a specific setting key is modified.

        Args:
            key: Config key to watch.
            callback: Function matching signature `(key, value)`.
        """
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def unregister_listener(self, key: str, callback: Callable[[str, any], None]) -> None:
        """Unregister a setting listener.

        Args:
            key: Config key.
            callback: Function to remove.
        """
        if key in self._listeners and callback in self._listeners[key]:
            self._listeners[key].remove(callback)

    def _notify(self, key: str, value: any) -> None:
        """Notify all listeners registered to a specific config key.

        Args:
            key: Config key modified.
            value: The new value.
        """
        if key in self._listeners:
            for callback in self._listeners[key]:
                try:
                    callback(key, value)
                except Exception as e:
                    self._logger.error(f"Error in settings listener callback for {key}: {e}")

    # Properties
    @property
    def theme(self) -> str:
        """Get the current UI theme (light / dark)."""
        return self.config.get("theme", "dark")

    @theme.setter
    def theme(self, val: str) -> None:
        """Set the current UI theme (light / dark)."""
        if val in ["light", "dark", "system"]:
            self.config.set("theme", val)
            self._notify("theme", val)

    @property
    def language(self) -> str:
        """Get the current UI language."""
        return self.config.get("language", "en")

    @language.setter
    def language(self, val: str) -> None:
        """Set the current UI language."""
        self.config.set("language", val)
        self._notify("language", val)

    @property
    def device_mode(self) -> str:
        """Get current compute device setting (GPU or CPU)."""
        return self.config.get("device_mode", "GPU")

    @device_mode.setter
    def device_mode(self, val: str) -> None:
        """Set compute device setting (GPU or CPU)."""
        if val in ["GPU", "CPU"]:
            self.config.set("device_mode", val)
            self._notify("device_mode", val)

    @property
    def output_folder(self) -> str:
        """Get the output folder location configuration."""
        return self.config.get("output_folder", "output")

    @output_folder.setter
    def output_folder(self, val: str) -> None:
        """Set the output folder location configuration."""
        self.config.set("output_folder", val)
        self._notify("output_folder", val)

    @property
    def model_folder(self) -> str:
        """Get the models folder location configuration."""
        return self.config.get("model_folder", "models")

    @model_folder.setter
    def model_folder(self, val: str) -> None:
        """Set the models folder location configuration."""
        self.config.set("model_folder", val)
        self._notify("model_folder", val)

    @property
    def temp_folder(self) -> str:
        """Get the temporary folder location configuration."""
        return self.config.get("temp_folder", "temp")

    @temp_folder.setter
    def temp_folder(self, val: str) -> None:
        """Set the temporary folder location configuration."""
        self.config.set("temp_folder", val)
        self._notify("temp_folder", val)

    @property
    def cache_folder(self) -> str:
        """Get the cache folder location configuration."""
        return self.config.get("cache_folder", "cache")

    @cache_folder.setter
    def cache_folder(self, val: str) -> None:
        """Set the cache folder location configuration."""
        self.config.set("cache_folder", val)
        self._notify("cache_folder", val)

    @property
    def quality(self) -> str:
        """Get the default quality settings (Low, Medium, High)."""
        return self.config.get("quality", "High")

    @quality.setter
    def quality(self, val: str) -> None:
        """Set default quality settings (Low, Medium, High)."""
        self.config.set("quality", val)
        self._notify("quality", val)

    @property
    def aspect_ratio(self) -> str:
        """Get the default aspect ratio setting."""
        return self.config.get("aspect_ratio", "16:9")

    @aspect_ratio.setter
    def aspect_ratio(self, val: str) -> None:
        """Set default aspect ratio setting."""
        self.config.set("aspect_ratio", val)
        self._notify("aspect_ratio", val)
