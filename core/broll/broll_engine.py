"""Concrete implementation of the BrollEngine interface.
"""

import logging
from pathlib import Path
import time
from typing import List, Optional

from core.interfaces.broll import BrollEngine as IBrollEngine
from core.director.scene_plan import ScenePlan
from core.broll.scene_asset import SceneAsset
from core.broll.broll_config import BrollConfig
from core.broll.broll_job import BrollJob
from core.broll.providers.provider_manager import ProviderManager
from core.broll.asset_library import AssetLibrary
from core.broll.asset_cache import AssetCache
from core.broll.asset_generator import AssetGenerator
from core.broll.asset_controller import AssetController


class BrollEngine(IBrollEngine):
    """Integrates B-roll prompt builders, providers, caching, and library managers."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the BrollEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        
        # Instantiate sub-managers
        self.provider_manager = ProviderManager()
        self.library = AssetLibrary(self.workspace_dir)
        self.cache = AssetCache(self.workspace_dir)
        self.generator = AssetGenerator(self.provider_manager, self.workspace_dir)
        self.controller = AssetController(self.generator, self.library, self.cache)
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("BrollEngine successfully initialized.")

    def generate_broll_clip(
        self,
        prompt: str,
        duration_seconds: float,
        output_path: Path,
        aspect_ratio: str = "16:9",
        fps: int = 30
    ) -> Path:
        """Standard interface implementation. Blocking synchronous call to generate a B-roll clip.

        Args:
            prompt: Text description of the desired visual.
            duration_seconds: Visual clip length.
            output_path: Target video file path to write clip.
            aspect_ratio: Configured aspect ratio.
            fps: Frame rate for the clip.

        Returns:
            The Path to the generated B-roll video clip.
        """
        self._logger.info(f"Synchronous B-roll clip requested: Prompt='{prompt[:40]}...', Duration={duration_seconds}s")
        
        # Build a temporary ScenePlan to feed to our queue controller
        scene_plan = ScenePlan(
            scene_number=999,
            scene_type="B-roll",
            duration=duration_seconds,
            narration=prompt,
            broll_keywords=prompt
        )

        config = BrollConfig(
            provider=self.provider_manager.active_provider_name or "Gemini Flow",
            aspect_ratio=aspect_ratio,
            fps=fps,
            use_cache=True,
            output_path=str(output_path)
        )

        job = self.controller.submit_job(scene_plan, config)
        self._logger.info(f"Submitted sync B-roll job: {job.job_id}")

        # Block until completion
        while job.status in ["pending", "running"]:
            time.sleep(0.1)

        if job.status == "completed" and job.output_path:
            path = Path(job.output_path)
            if not path.is_absolute():
                path = self.workspace_dir / path
            return path
        else:
            raise RuntimeError(f"Failed to generate synchronous B-roll: {job.error_message}")

    def generate_storyboard_broll(
        self,
        scene_plans: List[ScenePlan],
        aspect_ratio: str = "16:9",
        fps: int = 30,
        provider: Optional[str] = None,
        use_cache: bool = True
    ) -> List[BrollJob]:
        """Submit a collection of ScenePlans to the background generation queue.

        Args:
            scene_plans: List of ScenePlans requiring B-roll assets.
            aspect_ratio: Selected project aspect ratio.
            fps: Project frames per second.
            provider: Service provider name overrides.
            use_cache: Cache enable/disable flag.

        Returns:
            List of triggered BrollJob trackers.
        """
        jobs = []
        selected_provider = provider or self.provider_manager.active_provider_name

        for scene in scene_plans:
            # We only generate B-roll if the presenter visibility contains B-roll elements
            # (i.e. "B-roll" or "Mixed Presenter + B-roll")
            # But the caller can filter this or let the engine process all.
            config = BrollConfig(
                provider=selected_provider,
                aspect_ratio=aspect_ratio,
                fps=fps,
                use_cache=use_cache
            )
            job = self.controller.submit_job(scene, config)
            jobs.append(job)

        return jobs
