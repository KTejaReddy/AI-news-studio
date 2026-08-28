"""AssetGenerator that orchestrates prompt creation and routes generation to active B-roll providers.
"""

import logging
from pathlib import Path
from typing import Tuple

from core.director.scene_plan import ScenePlan
from core.broll.prompt_builder import PromptBuilder
from core.broll.providers.provider_manager import ProviderManager


class AssetGenerator:
    """Combines ScenePlans, builds custom visual prompts, and executes active provider drivers."""

    def __init__(self, provider_manager: ProviderManager, workspace_dir: Path) -> None:
        """Initialize the AssetGenerator.

        Args:
            provider_manager: Registry for visual provider drivers.
            workspace_dir: Path to the workspace directory.
        """
        self.provider_manager = provider_manager
        self.workspace_dir = Path(workspace_dir).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)

    def generate_for_scene(
        self,
        scene: ScenePlan,
        output_path: Path,
        aspect_ratio: str = "16:9",
        fps: int = 30
    ) -> Tuple[Path, str, str]:
        """Synthesize B-roll visuals for a ScenePlan and run the active generation provider.

        Args:
            scene: ScenePlan configurations from the AI Director.
            output_path: Path to save the generated media file.
            aspect_ratio: Configured aspect ratio.
            fps: Video frames per second.

        Returns:
            Tuple of (Path, prompt, asset_type) where Path is the generated visual media file path.
        """
        # 1. Build prompt and asset type recommendation
        prompt, asset_type = PromptBuilder.build_prompt_and_type(scene)
        self._logger.info(f"Synthesized prompt for scene {scene.scene_number}: type={asset_type}, prompt='{prompt[:60]}...'")

        # 2. Query selected provider driver
        provider = self.provider_manager.get_active_provider()
        if not provider:
            raise RuntimeError("No active B-roll provider configured in ProviderManager.")

        # Determine file suffix (e.g. .mp4 for Video/Graphic/Animation, .png for Image)
        # Note: If the user provides a path with a suffix, respect it, otherwise append.
        actual_suffix = ".png" if asset_type == "Image" else ".mp4"
        if not output_path.suffix:
            output_path = output_path.with_suffix(actual_suffix)

        # 3. Execute generation
        self._logger.info(f"Routing B-roll generation to provider '{provider.get_name()}'")
        generated_path = provider.generate(
            prompt=prompt,
            duration=scene.duration,
            aspect_ratio=aspect_ratio,
            fps=fps,
            output_path=output_path
        )

        return generated_path, prompt, asset_type
