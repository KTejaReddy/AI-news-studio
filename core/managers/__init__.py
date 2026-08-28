"""Managers module for AI News Studio.

Aggregates all core runtime state and lifecycle managers.
"""

from core.managers.config_manager import ConfigManager
from core.managers.logger_manager import LoggerManager
from core.managers.project_manager import Project, ProjectManager
from core.managers.settings_manager import SettingsManager
from core.managers.asset_manager import AssetManager
from core.managers.model_manager import ModelManager
from core.managers.output_manager import OutputManager
from core.managers.history_manager import HistoryManager

__all__ = [
    "ConfigManager",
    "LoggerManager",
    "Project",
    "ProjectManager",
    "SettingsManager",
    "AssetManager",
    "ModelManager",
    "OutputManager",
    "HistoryManager",
]
