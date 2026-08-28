"""Project and ProjectManager for AI News Studio.

Defines the project structure and manages directory operations, state persistence,
and listings.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from core.managers.config_manager import ConfigManager


class Project:
    """Represents a video creation project containing metadata and script information."""

    def __init__(
        self,
        name: str,
        project_id: Optional[str] = None,
        created_at: Optional[str] = None,
        modified_at: Optional[str] = None,
        script: str = "",
        presenter_id: str = "",
        voice_id: str = "",
        aspect_ratio: str = "16:9",
        status: str = "Draft",
        output_video_path: Optional[str] = None,
    ) -> None:
        """Initialize a Project.

        Args:
            name: Human-readable name of the project.
            project_id: Unique identifier (UUID). Created if None.
            created_at: Creation ISO timestamp. Current time if None.
            modified_at: Modification ISO timestamp. Current time if None.
            script: Text script to convert into video.
            presenter_id: Selected presenter engine/actor ID.
            voice_id: Selected voice clone ID.
            aspect_ratio: Configured aspect ratio (e.g. 16:9, 9:16).
            status: Progress state (Draft, Generating, Completed, Failed).
            output_video_path: Absolute or relative path to final video, if export succeeded.
        """
        self.name = name
        self.id = project_id or str(uuid.uuid4())
        self.created_at = created_at or datetime.now().isoformat()
        self.modified_at = modified_at or datetime.now().isoformat()
        self.script = script
        self.presenter_id = presenter_id
        self.voice_id = voice_id
        self.aspect_ratio = aspect_ratio
        self.status = status
        self.output_video_path = output_video_path

    def update_modification_time(self) -> None:
        """Set the modified_at timestamp to the current time."""
        self.modified_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the project instance to a JSON-serializable dictionary.

        Returns:
            Dictionary representation of the project metadata.
        """
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "script": self.script,
            "presenter_id": self.presenter_id,
            "voice_id": self.voice_id,
            "aspect_ratio": self.aspect_ratio,
            "status": self.status,
            "output_video_path": self.output_video_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Reconstruct a Project instance from a dictionary.

        Args:
            data: Raw dictionary containing project data.

        Returns:
            Reconstructed Project instance.
        """
        return cls(
            name=data.get("name", "Untitled Project"),
            project_id=data.get("id"),
            created_at=data.get("created_at"),
            modified_at=data.get("modified_at"),
            script=data.get("script", ""),
            presenter_id=data.get("presenter_id", ""),
            voice_id=data.get("voice_id", ""),
            aspect_ratio=data.get("aspect_ratio", "16:9"),
            status=data.get("status", "Draft"),
            output_video_path=data.get("output_video_path"),
        )


class ProjectManager:
    """Manages creation, loading, metadata updates, and cleanup of projects."""

    def __init__(self, workspace_dir: Path, config_manager: ConfigManager) -> None:
        """Initialize the ProjectManager.

        Args:
            workspace_dir: App workspace directory.
            config_manager: Injected system ConfigManager.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.config_manager = config_manager
        
        # Read the projects folder from configuration
        projects_folder_name = self.config_manager.get("projects_folder", "projects")
        self.projects_dir = self.workspace_dir / projects_folder_name
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"Projects directory established: {self.projects_dir}")

    def create_project(self, name: str, aspect_ratio: str = "16:9") -> Project:
        """Create a new project directory and metadata file.

        Args:
            name: The display name of the project.
            aspect_ratio: Initial aspect ratio configuration.

        Returns:
            The newly created Project instance.
        """
        project = Project(name=name, aspect_ratio=aspect_ratio)
        self.save_project(project)
        self._logger.info(f"Created new project: '{name}' [{project.id}]")
        return project

    def save_project(self, project: Project) -> None:
        """Save the project's metadata to its corresponding directory.

        Args:
            project: The Project instance to persist.
        """
        project.update_modification_time()
        project_dir = self.projects_dir / project.id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_file = project_dir / "project.json"
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(project.to_dict(), f, indent=2)
        except Exception as e:
            self._logger.error(f"Failed to save project metadata for {project.id}: {e}")

    def load_project(self, project_id: str) -> Optional[Project]:
        """Load a project by its unique ID.

        Args:
            project_id: Unique UUID string matching the folder name.

        Returns:
            The loaded Project instance, or None if not found/corrupted.
        """
        metadata_file = self.projects_dir / project_id / "project.json"
        if not metadata_file.exists():
            self._logger.warning(f"Metadata file not found for project ID: {project_id}")
            return None

        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Project.from_dict(data)
        except Exception as e:
            self._logger.error(f"Failed to parse project metadata for {project_id}: {e}")
            return None

    def delete_project(self, project_id: str) -> bool:
        """Delete a project directory and all of its contents.

        Args:
            project_id: Unique ID of the project.

        Returns:
            True if deletion was successful, False otherwise.
        """
        project_dir = self.projects_dir / project_id
        if not project_dir.exists():
            return False

        try:
            # Clean directory contents recursively
            import shutil
            shutil.rmtree(project_dir)
            self._logger.info(f"Deleted project directory: {project_dir}")
            return True
        except Exception as e:
            self._logger.error(f"Error deleting project {project_id}: {e}")
            return False

    def list_projects(self) -> List[Project]:
        """Scan projects folder and return a list of all loaded Projects.

        Returns:
            List of Project instances sorted by modification date (newest first).
        """
        projects: List[Project] = []
        if not self.projects_dir.exists():
            return projects

        for path in self.projects_dir.iterdir():
            if path.is_dir():
                metadata_file = path / "project.json"
                if metadata_file.exists():
                    proj = self.load_project(path.name)
                    if proj:
                        projects.append(proj)
        
        # Sort by modified time descending
        projects.sort(key=lambda p: p.modified_at, reverse=True)
        return projects

    def get_recent_projects(self, limit: int = 5) -> List[Project]:
        """Get the N most recently modified projects.

        Args:
            limit: Maximum projects to return.

        Returns:
            List of most recently modified Project objects.
        """
        return self.list_projects()[:limit]
