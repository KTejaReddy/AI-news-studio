"""Background worker thread executing visual prompt generation, provider routing,
thumbnail extraction, and library/cache registration.
"""

import logging
import time
import traceback
from pathlib import Path
from typing import Callable, Optional
import threading

from core.broll.broll_job import BrollJob
from core.broll.scene_asset import SceneAsset
from core.broll.asset_generator import AssetGenerator
from core.broll.asset_library import AssetLibrary
from core.broll.asset_cache import AssetCache
from core.broll.prompt_builder import PromptBuilder


class AssetWorker(threading.Thread):
    """Executes B-roll visual generation, caching, and library integration in a background thread."""

    def __init__(
        self,
        job: BrollJob,
        generator: AssetGenerator,
        library: AssetLibrary,
        cache: AssetCache,
        on_complete_callback: Optional[Callable[[BrollJob], None]] = None
    ) -> None:
        """Initialize AssetWorker.

        Args:
            job: BrollJob instance tracking parameters.
            generator: AssetGenerator orchestration instance.
            library: AssetLibrary manager for index storage.
            cache: AssetCache manager.
            on_complete_callback: Callback triggered on completion or failure.
        """
        super().__init__(daemon=True)
        self.job = job
        self.generator = generator
        self.library = library
        self.cache = cache
        self.on_complete = on_complete_callback
        self._logger = logging.getLogger(f"{self.__class__.__name__}_{job.job_id[:8]}")
        self._cancelled = False

    def run(self) -> None:
        """Run the visual generation worker thread."""
        self._logger.info(f"Starting B-roll worker thread for job {self.job.job_id}")
        self.job.update_status("running", 0.05)

        # Set up output path
        generated_dir = self.library.library_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        try:
            scene = self.job.scene_plan
            config = self.job.config

            # 1. Synthesize visual parameters to check cache first
            prompt, asset_type = PromptBuilder.build_prompt_and_type(scene)
            actual_suffix = ".png" if asset_type == "Image" else ".mp4"
            if config.output_path:
                output_path = Path(config.output_path)
            else:
                output_filename = f"scene_{scene.scene_number}_{self.job.job_id}{actual_suffix}"
                output_path = generated_dir / output_filename

            # Check cache
            cached_path = None
            if config.use_cache:
                self.job.update_status("running", 0.1)
                cached_path = self.cache.get_cached_asset_path(
                    prompt=prompt,
                    provider=config.provider,
                    aspect_ratio=config.aspect_ratio,
                    duration=scene.duration
                )

            if cached_path and cached_path.exists():
                self._logger.info(f"Cache HIT. Copying cached asset from {cached_path}")
                self.job.update_status("running", 0.3)
                import shutil
                shutil.copy2(cached_path, output_path)
                
                # Check cancellation
                if self._cancelled:
                    raise RuntimeError("Job cancelled by user.")

                # Generate thumbnail
                self.job.update_status("running", 0.6)
                try:
                    rel_media_path = output_path.relative_to(self.library.workspace_dir)
                except ValueError:
                    rel_media_path = output_path
                thumb_rel_path = self.library.generate_thumbnail(output_path, self.job.job_id, asset_type)
            else:
                # Cache miss: Run generation provider
                self._logger.info("Cache miss. Running provider generation...")
                self.job.update_status("running", 0.2)
                
                # Paced progress steps for mockup feedback
                time.sleep(0.5)
                if self._cancelled:
                    raise RuntimeError("Job cancelled by user.")
                self.job.update_status("running", 0.4)
                
                time.sleep(0.5)
                if self._cancelled:
                    raise RuntimeError("Job cancelled by user.")
                self.job.update_status("running", 0.7)

                # Execute generator call
                generated_media_path, prompt, asset_type = self.generator.generate_for_scene(
                    scene=scene,
                    output_path=output_path,
                    aspect_ratio=config.aspect_ratio,
                    fps=config.fps
                )

                if self._cancelled:
                    # Clean up generated file if cancelled
                    if generated_media_path.exists():
                        generated_media_path.unlink()
                    raise RuntimeError("Job cancelled by user.")

                # Write to Cache if enabled
                if config.use_cache:
                    self._logger.info("Writing generated asset to Cache.")
                    self.cache.add_to_cache(
                        prompt=prompt,
                        provider=config.provider,
                        aspect_ratio=config.aspect_ratio,
                        duration=scene.duration,
                        source_file=generated_media_path
                    )

                self.job.update_status("running", 0.9)
                try:
                    rel_media_path = generated_media_path.relative_to(self.library.workspace_dir)
                except ValueError:
                    rel_media_path = generated_media_path
                thumb_rel_path = self.library.generate_thumbnail(generated_media_path, self.job.job_id, asset_type)

            # Check cancellation before final catalog indexing
            if self._cancelled:
                raise RuntimeError("Job cancelled by user.")

            # Create asset and register in library
            asset = SceneAsset(
                asset_id=self.job.job_id,
                scene_id=str(scene.scene_number),
                prompt=prompt,
                provider=config.provider,
                file_path=str(rel_media_path),
                asset_type=asset_type,
                duration=scene.duration,
                aspect_ratio=config.aspect_ratio,
                thumbnail_path=thumb_rel_path,
                tags=[config.provider.lower(), asset_type.lower()],
                status="completed"
            )
            self.library.add_asset(asset)

            self.job.update_status("completed", 1.0, output_asset=asset)
            self._logger.info(f"B-roll generation completed for scene {scene.scene_number}.")

        except Exception as e:
            self._logger.error(f"Error in B-roll worker generation: {e}")
            tb = traceback.format_exc()
            self.job.update_status("failed", self.job.progress, error_message=tb)

        finally:
            if self.on_complete:
                try:
                    self.on_complete(self.job)
                except Exception as e:
                    self._logger.error(f"Error in B-roll worker on_complete callback: {e}")

    def cancel(self) -> None:
        """Cancel the background generation job."""
        self._cancelled = True
        self._logger.info("Cancellation requested.")
        self.job.update_status("failed", self.job.progress, error_message="Job was cancelled by the user.")
