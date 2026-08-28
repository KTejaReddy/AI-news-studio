"""OutputManager for AI News Studio.

Tracks, validates, and manages final exported video files in the output directory.
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List

from core.managers.config_manager import ConfigManager


class OutputManager:
    """Coordinates video exports, validates files, and scans outputs for gallery viewing."""

    def __init__(self, workspace_dir: Path, config_manager: ConfigManager) -> None:
        """Initialize the OutputManager.

        Args:
            workspace_dir: Path to the workspace directory.
            config_manager: ConfigManager to query default export directory.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.config_manager = config_manager
        
        output_folder_name = self.config_manager.get("output_folder", "output")
        self.output_dir = self.workspace_dir / output_folder_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"OutputManager directory: {self.output_dir}")

    def get_outputs(self) -> List[Dict[str, Any]]:
        """Index all video file exports in the output folder.

        Returns:
            List of dictionaries containing output file details.
        """
        exports: List[Dict[str, Any]] = []
        if not self.output_dir.exists():
            return exports

        # Supported video file extensions
        extensions = [".mp4", ".mkv", ".avi", ".mov"]
        for path in self.output_dir.iterdir():
            if path.is_file() and path.suffix.lower() in extensions:
                try:
                    stat = path.stat()
                    created_time = datetime.fromtimestamp(stat.st_ctime).isoformat()
                    size_mb = stat.st_size / (1024 * 1024)

                    exports.append({
                        "name": path.name,
                        "path": str(path),
                        "size_mb": round(size_mb, 2),
                        "created_at": created_time,
                        "extension": path.suffix
                    })
                except Exception as e:
                    self._logger.error(f"Failed to read output details for {path.name}: {e}")

        # Sort outputs newest first
        exports.sort(key=lambda x: x["created_at"], reverse=True)
        return exports

    def delete_output(self, filename: str) -> bool:
        """Remove a video file from the output directory.

        Args:
            filename: The name of the file (e.g. output_project_1.mp4).

        Returns:
            True if deleted successfully, False otherwise.
        """
        file_path = self.output_dir / filename
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
                self._logger.info(f"Deleted video export from disk: {file_path}")
                return True
            except Exception as e:
                self._logger.error(f"Failed to delete video export {filename}: {e}")
                return False
        return False
