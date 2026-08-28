"""TimelineEngine representing the unified public API wrapper for editing, playback,
and composition rendering.
"""

import logging
from pathlib import Path
from typing import List, Optional

from core.timeline.timeline_controller import TimelineController
from core.timeline.timeline_job import TimelineRenderJob
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene


class TimelineEngine:
    """Unified engine manager exposing public APIs for multi-track playback, editing, and rendering."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize TimelineEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = TimelineController(self.workspace_dir)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("TimelineEngine successfully initialized.")

    def load_project_timeline(self, project_id: str) -> None:
        """Load project timeline from disk, or automatically compile a default timeline if missing.

        Args:
            project_id: UUID of project.
        """
        self._logger.info(f"Loading project timeline for project: {project_id}")
        self.controller.load_project_timeline(project_id)

    def save_project_timeline(self) -> bool:
        """Persist current timeline data structure to disk.

        Returns:
            True if saved successfully, False otherwise.
        """
        return self.controller.save_project_timeline()

    def get_tracks(self) -> List[TimelineTrack]:
        """Fetch all tracks in the active timeline project.

        Returns:
            List of TimelineTracks.
        """
        return self.controller.tracks

    def get_scenes(self) -> List[TimelineScene]:
        """Fetch all scenes in the active timeline project.

        Returns:
            List of TimelineScenes.
        """
        return self.controller.scenes

    def get_total_duration(self) -> float:
        """Get the current length of the project timeline.

        Returns:
            Length in seconds.
        """
        return self.controller.total_duration

    def get_playback_time(self) -> float:
        """Get current playhead position time.

        Returns:
            Position in seconds.
        """
        return self.controller.playback.current_time

    def render_video(
        self,
        output_path: Path,
        low_res: bool = False,
        progress_callback: Optional[any] = None
    ) -> TimelineRenderJob:
        """Asynchronously trigger the compositor renderer to compile project MP4.

        Args:
            output_path: Output file destination path (.mp4).
            low_res: If True, renders smaller width/height for fast preview.
            progress_callback: Optional callback to track progress (0.0 to 1.0).

        Returns:
            TimelineRenderJob instance.
        """
        self._logger.info(f"Submitting render job: path={output_path.name}, low_res={low_res}")
        return self.controller.submit_render_job(
            output_path=output_path,
            low_res=low_res,
            progress_callback=progress_callback
        )
