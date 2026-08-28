"""DependencyResolver for the AI Production Orchestrator.

Determines which pipeline stages can be skipped based on previously cached
outputs already present on disk. Enables intelligent resumption and incremental
regeneration.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set

from core.production.production_state import PipelineStage


class DependencyResolver:
    """Analyzes per-project workspace directories to resolve which pipeline stages
    have already been completed and can safely be skipped.

    Caching policy:
    - A stage is considered ``cached`` if all expected output files exist on disk.
    - The caller (orchestrator) must still verify file validity before relying on caches.
    """

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize DependencyResolver.

        Args:
            workspace_dir: Root application workspace path.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)

    def resolve_cached_stages(
        self,
        project_id: str,
        num_scenes: int,
        skip_stages: List[PipelineStage],
    ) -> Set[PipelineStage]:
        """Determine which stages can be skipped due to cached outputs.

        Args:
            project_id: Active project UUID.
            num_scenes: Total number of scenes in the storyboard.
            skip_stages: Explicit stages the user has requested to skip.

        Returns:
            Set of PipelineStage values that can be skipped.
        """
        cached: Set[PipelineStage] = set(skip_stages)

        proj_dir = self.workspace_dir / "projects" / project_id

        # Check voice track cache
        if self._all_scene_files_exist(proj_dir / "voice", num_scenes, ".wav"):
            cached.add(PipelineStage.GENERATE_VOICE)
            self._logger.info(f"[DependencyResolver] Voice cache hit ({num_scenes} scenes).")

        # Check motion video cache
        if self._all_scene_files_exist(proj_dir / "motion", num_scenes, ".mp4"):
            cached.add(PipelineStage.GENERATE_MOTION)
            self._logger.info(f"[DependencyResolver] Motion cache hit ({num_scenes} scenes).")

        # Check lipsync video cache
        if self._all_scene_files_exist(proj_dir / "lipsync", num_scenes, ".mp4"):
            cached.add(PipelineStage.GENERATE_LIPSYNC)
            self._logger.info(f"[DependencyResolver] LipSync cache hit ({num_scenes} scenes).")

        # Check broll cache — only scenes with b-roll/mixed visibility need files
        if self._broll_cache_hit(proj_dir):
            cached.add(PipelineStage.GENERATE_BROLL)
            self._logger.info("[DependencyResolver] B-Roll cache hit.")

        # Check storyboard.json cache for director plan
        storyboard_file = proj_dir / "storyboard.json"
        if storyboard_file.exists() and storyboard_file.stat().st_size > 10:
            cached.add(PipelineStage.DIRECTOR_PLAN)
            self._logger.info("[DependencyResolver] Director storyboard cache hit.")

        # Check preview cache
        preview_path = proj_dir / "preview" / "preview.mp4"
        if preview_path.exists() and preview_path.stat().st_size > 0:
            cached.add(PipelineStage.RENDER_PREVIEW)
            self._logger.info("[DependencyResolver] Preview cache hit.")

        return cached

    def get_project_paths(self, project_id: str) -> Dict[str, Path]:
        """Return a dictionary of standard subdirectory paths for a project.

        Args:
            project_id: Active project UUID.

        Returns:
            Dictionary mapping stage name to the corresponding directory path.
        """
        proj_dir = self.workspace_dir / "projects" / project_id
        return {
            "voice": proj_dir / "voice",
            "motion": proj_dir / "motion",
            "lipsync": proj_dir / "lipsync",
            "broll": proj_dir / "broll",
            "preview": proj_dir / "preview",
            "timeline": proj_dir / "timeline",
            "export": proj_dir / "export",
            "logs": proj_dir / "logs",
        }

    def ensure_project_dirs(self, project_id: str) -> None:
        """Create all required per-project subdirectories if missing.

        Args:
            project_id: Active project UUID.
        """
        for path in self.get_project_paths(project_id).values():
            path.mkdir(parents=True, exist_ok=True)

    # --- Internal Helpers ---

    def _all_scene_files_exist(
        self,
        directory: Path,
        num_scenes: int,
        extension: str,
    ) -> bool:
        """Check whether all expected per-scene output files are present.

        Args:
            directory: Target directory to scan.
            num_scenes: Number of expected files (scene_1 .. scene_N).
            extension: File extension to check (e.g. '.wav', '.mp4').

        Returns:
            True if all scene files from scene_1 to scene_N exist with content.
        """
        if not directory.exists():
            return False
        if num_scenes == 0:
            return False

        for i in range(1, num_scenes + 1):
            expected = directory / f"scene_{i}{extension}"
            if not expected.exists() or expected.stat().st_size == 0:
                return False
        return True

    def _broll_cache_hit(self, proj_dir: Path) -> bool:
        """Check B-roll cache by reading the storyboard to determine which scenes
        actually require B-roll clips (visibility 'B-roll' or 'Mixed').

        If the storyboard cannot be read, falls back to scanning the broll directory
        for any .mp4 file, which is a safe approximation.

        Args:
            proj_dir: Project directory containing storyboard.json and broll/.

        Returns:
            True if all required B-roll scene files exist with content.
        """
        broll_dir = proj_dir / "broll"
        storyboard_file = proj_dir / "storyboard.json"

        if not broll_dir.exists():
            return False

        # Read storyboard to determine which scenes need B-roll
        if storyboard_file.exists():
            try:
                with open(storyboard_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                required_scenes = [
                    d["scene_number"]
                    for d in data
                    if "b-roll" in str(d.get("presenter_visibility", "")).lower()
                    or "mixed" in str(d.get("presenter_visibility", "")).lower()
                ]
                if not required_scenes:
                    # No scenes need B-roll; stage is trivially cached
                    return True
                for sn in required_scenes:
                    expected = broll_dir / f"scene_{sn}.mp4"
                    if not expected.exists() or expected.stat().st_size == 0:
                        return False
                return True
            except Exception:
                pass

        # Fallback: any .mp4 in broll dir means partial cache — treat as not cached
        # to avoid skipping generation incorrectly
        return False
