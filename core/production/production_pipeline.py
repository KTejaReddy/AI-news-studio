"""ProductionPipeline for the AI Production Orchestrator.

Executes all 10 pipeline stages in sequence for a single ProductionJob,
coordinating between engines, tracking progress, and enforcing caching logic.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Callable, List, Optional, Set

from core.director.director_engine import DirectorEngine
from core.broll.broll_engine import BrollEngine
from core.voice.voice_engine import VoiceEngine
from core.motion.motion_engine import MotionEngine
from core.lipsync.lipsync_engine import LipSyncEngine
from core.presenter.presenter_engine import PresenterEngine
from core.timeline.timeline_engine import TimelineEngine
from core.export.export_engine import ExportEngine
from core.export.export_settings import ExportSettings
from core.director.scene_analyzer import SceneAnalyzer
from core.director.scene_plan import ScenePlan

from core.production.production_job import ProductionJob
from core.production.production_state import PipelineStage, ProductionState
from core.production.production_logger import ProductionLogger
from core.production.retry_manager import RetryManager
from core.production.dependency_resolver import DependencyResolver


# Type alias for progress callback signature
ProgressCallback = Optional[Callable[[ProductionJob], None]]


class ProductionPipeline:
    """Executes the full production pipeline for a single ProductionJob.

    Runs in a dedicated background thread. Progress updates are emitted through
    an optional callback for GUI / scheduler integration.

    Pipeline stages (in order):
        1. Parse Script
        2. Director Plan
        3. Assign Presenter
        4. Generate Voice
        5. Generate Motion
        6. Generate LipSync
        7. Generate B-Roll
        8. Assemble Timeline
        9. Render Preview
        10. Export Final
    """

    def __init__(
        self,
        workspace_dir: Path,
        director_engine: DirectorEngine,
        broll_engine: BrollEngine,
        voice_engine: VoiceEngine,
        motion_engine: MotionEngine,
        lipsync_engine: LipSyncEngine,
        presenter_engine: PresenterEngine,
        timeline_engine: TimelineEngine,
        export_engine: ExportEngine,
    ) -> None:
        """Initialize ProductionPipeline.

        Args:
            workspace_dir: Application workspace root path.
            director_engine: DirectorEngine instance.
            broll_engine: BrollEngine instance.
            voice_engine: VoiceEngine instance.
            motion_engine: MotionEngine instance.
            lipsync_engine: LipSyncEngine instance.
            presenter_engine: PresenterEngine instance.
            timeline_engine: TimelineEngine instance.
            export_engine: ExportEngine instance.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.director_engine = director_engine
        self.broll_engine = broll_engine
        self.voice_engine = voice_engine
        self.motion_engine = motion_engine
        self.lipsync_engine = lipsync_engine
        self.presenter_engine = presenter_engine
        self.timeline_engine = timeline_engine
        self.export_engine = export_engine
        self._logger = logging.getLogger(self.__class__.__name__)

    def execute(
        self,
        job: ProductionJob,
        cached_stages: Set[PipelineStage],
        progress_callback: ProgressCallback = None,
    ) -> None:
        """Run the entire pipeline for the given job.

        This method is designed to be called from a background thread.
        Progress is emitted after each stage completes.

        Args:
            job: The ProductionJob to execute.
            cached_stages: Set of stages that can be skipped (already cached).
            progress_callback: Optional callable receiving the updated job after each stage.
        """
        cfg = job.config
        log = ProductionLogger(self.workspace_dir, job.job_id, cfg.project_id)
        retry = RetryManager(max_retries=cfg.max_retries)
        resolver = DependencyResolver(self.workspace_dir)

        # Ensure all project subdirectories exist
        resolver.ensure_project_dirs(cfg.project_id)
        paths = resolver.get_project_paths(cfg.project_id)

        def cancelled() -> bool:
            return job.progress.state == ProductionState.CANCELLED

        def emit() -> None:
            if progress_callback:
                try:
                    progress_callback(job)
                except Exception:
                    pass

        # ── STAGE 1: Parse Script ──────────────────────────────────────────
        stage = PipelineStage.PARSE_SCRIPT
        result = job.progress.advance_to_stage(stage)
        log.info("Parsing script and extracting structure...", stage.value)
        try:
            words = len(cfg.script.split())
            result.complete(output_data={"word_count": words, "char_count": len(cfg.script)})
            log.info(f"Script parsed: {words} words.", stage.value)
        except Exception as e:
            result.fail(str(e))
            job.mark_failed(f"Script parsing failed: {e}")
            emit()
            return
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 2: Director Plan ─────────────────────────────────────────
        stage = PipelineStage.DIRECTOR_PLAN
        result = job.progress.advance_to_stage(stage)
        storyboard_file = paths["voice"].parent / "storyboard.json"
        if stage in cached_stages and storyboard_file.exists():
            log.info("Loading cached Director storyboard...", stage.value)
            scene_plans = self._load_scene_plans(storyboard_file)
            result.complete(
                output_data={"num_scenes": len(scene_plans)}, cached=True
            )
        else:
            log.info("Running Director scene analysis...", stage.value)
            try:
                scene_plans = retry.execute(
                    lambda: self._run_director(cfg.script, cfg.aspect_ratio),
                    stage,
                    cancellation_check=cancelled,
                )
                self._save_scene_plans(storyboard_file, scene_plans)
                result.complete(output_data={"num_scenes": len(scene_plans)})
                log.info(f"Director planned {len(scene_plans)} scenes.", stage.value)
            except Exception as e:
                result.fail(str(e))
                job.mark_failed(f"Director planning failed: {e}")
                emit()
                return

        job.scene_plans = scene_plans
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        num_scenes = len(scene_plans)

        # ── STAGE 3: Assign Presenter ──────────────────────────────────────
        stage = PipelineStage.ASSIGN_PRESENTER
        result = job.progress.advance_to_stage(stage)
        log.info(f"Assigning presenter '{cfg.presenter_id}' to {num_scenes} scenes.", stage.value)
        result.complete(output_data={"presenter_id": cfg.presenter_id})
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 4: Generate Voice ────────────────────────────────────────
        stage = PipelineStage.GENERATE_VOICE
        result = job.progress.advance_to_stage(stage)
        voice_dir = paths["voice"]
        voice_paths: List[Path] = []

        if stage in cached_stages:
            log.info("Loading cached voice tracks...", stage.value)
            for i, plan in enumerate(scene_plans, start=1):
                voice_paths.append(voice_dir / f"scene_{i}.wav")
            result.complete(output_data={"num_tracks": len(voice_paths)}, cached=True)
        else:
            log.info(f"Generating voice tracks for {num_scenes} scenes...", stage.value)
            try:
                voice_profile = self.voice_engine.load_profile(cfg.voice_id)
                if not voice_profile:
                    raise ValueError(f"Voice profile not found: {cfg.voice_id}")

                for i, plan in enumerate(scene_plans, start=1):
                    if cancelled():
                        job.mark_cancelled()
                        return
                    out_path = voice_dir / f"scene_{i}.wav"
                    if not out_path.exists() or out_path.stat().st_size == 0:
                        log.info(f"  Synthesizing voice for scene {i}/{num_scenes}...", stage.value)
                        retry.execute(
                            lambda p=plan, op=out_path: self.voice_engine.synthesize_speech(
                                text=p.narration,
                                voice_id=cfg.voice_id,
                                output_path=op,
                                quality=cfg.quality,
                            ),
                            stage,
                            cancellation_check=cancelled,
                        )
                    voice_paths.append(out_path)
                    job.progress.stage_progress = i / num_scenes
                    emit()

                result.complete(output_data={"num_tracks": len(voice_paths)})
                log.info(f"Voice generation complete: {len(voice_paths)} tracks.", stage.value)
            except Exception as e:
                result.fail(str(e))
                job.mark_failed(f"Voice generation failed: {e}")
                emit()
                return

        job.voice_audio_paths = voice_paths
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 5: Generate Motion ───────────────────────────────────────
        stage = PipelineStage.GENERATE_MOTION
        result = job.progress.advance_to_stage(stage)
        motion_dir = paths["motion"]
        motion_paths: List[Path] = []

        if stage in cached_stages:
            log.info("Loading cached motion videos...", stage.value)
            for i in range(1, num_scenes + 1):
                motion_paths.append(motion_dir / f"scene_{i}.mp4")
            result.complete(output_data={"num_videos": len(motion_paths)}, cached=True)
        else:
            log.info(f"Generating body motion for {num_scenes} scenes...", stage.value)
            try:
                presenter_image = (
                    self.workspace_dir / "assets" / "presenters" / f"{cfg.presenter_id}.png"
                )
                for i, plan in enumerate(scene_plans, start=1):
                    if cancelled():
                        job.mark_cancelled()
                        return
                    out_path = motion_dir / f"scene_{i}.mp4"
                    if not out_path.exists() or out_path.stat().st_size == 0:
                        log.info(f"  Generating motion for scene {i}/{num_scenes}...", stage.value)
                        motion_template = {
                            "style": "Professional",
                            "strength": plan.gesture_intensity,
                            "enable_idle": True,
                            "smoothing": 0.5,
                        }
                        retry.execute(
                            lambda ip=presenter_image, op=out_path, d=plan.duration, mt=motion_template:
                                self.motion_engine.animate_still_presenter(
                                    image_path=ip,
                                    motion_template=mt,
                                    output_path=op,
                                    duration_seconds=d,
                                ),
                            stage,
                            cancellation_check=cancelled,
                        )
                    motion_paths.append(out_path)
                    job.progress.stage_progress = i / num_scenes
                    emit()

                result.complete(output_data={"num_videos": len(motion_paths)})
                log.info(f"Motion generation complete: {len(motion_paths)} videos.", stage.value)
            except Exception as e:
                result.fail(str(e))
                job.mark_failed(f"Motion generation failed: {e}")
                emit()
                return

        job.motion_video_paths = motion_paths
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 6: Generate LipSync ──────────────────────────────────────
        stage = PipelineStage.GENERATE_LIPSYNC
        result = job.progress.advance_to_stage(stage)
        lipsync_dir = paths["lipsync"]
        lipsync_paths: List[Path] = []

        if stage in cached_stages:
            log.info("Loading cached lipsync videos...", stage.value)
            for i in range(1, num_scenes + 1):
                lipsync_paths.append(lipsync_dir / f"scene_{i}.mp4")
            result.complete(output_data={"num_videos": len(lipsync_paths)}, cached=True)
        else:
            log.info(f"Applying lip sync for {num_scenes} scenes...", stage.value)
            try:
                for i, (motion_path, voice_path) in enumerate(
                    zip(job.motion_video_paths, job.voice_audio_paths), start=1
                ):
                    if cancelled():
                        job.mark_cancelled()
                        return
                    out_path = lipsync_dir / f"scene_{i}.mp4"
                    if not out_path.exists() or out_path.stat().st_size == 0:
                        log.info(f"  Syncing lips for scene {i}/{num_scenes}...", stage.value)
                        retry.execute(
                            lambda vp=motion_path, ap=voice_path, op=out_path:
                                self.lipsync_engine.sync_lips(
                                    presenter_video_path=vp,
                                    audio_path=ap,
                                    output_path=op,
                                ),
                            stage,
                            cancellation_check=cancelled,
                        )
                    lipsync_paths.append(out_path)
                    job.progress.stage_progress = i / num_scenes
                    emit()

                result.complete(output_data={"num_videos": len(lipsync_paths)})
                log.info(f"LipSync complete: {len(lipsync_paths)} videos.", stage.value)
            except Exception as e:
                result.fail(str(e))
                job.mark_failed(f"LipSync failed: {e}")
                emit()
                return

        job.lipsync_video_paths = lipsync_paths
        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 7: Generate B-Roll ───────────────────────────────────────
        stage = PipelineStage.GENERATE_BROLL
        result = job.progress.advance_to_stage(stage)
        broll_dir = paths["broll"]
        broll_needs_scenes = [p for p in scene_plans if "b-roll" in p.presenter_visibility.lower() or "mixed" in p.presenter_visibility.lower()]

        if stage in cached_stages:
            log.info("Loading cached B-Roll assets...", stage.value)
            for i, plan in enumerate(broll_needs_scenes, start=1):
                broll_path = broll_dir / f"scene_{plan.scene_number}.mp4"
                job.broll_asset_paths.append(broll_path)
            result.complete(output_data={"num_broll_clips": len(broll_needs_scenes)}, cached=True)
        else:
            log.info(f"Generating B-Roll for {len(broll_needs_scenes)} scenes...", stage.value)
            try:
                for idx, plan in enumerate(broll_needs_scenes, start=1):
                    if cancelled():
                        job.mark_cancelled()
                        return
                    out_path = broll_dir / f"scene_{plan.scene_number}.mp4"
                    if not out_path.exists() or out_path.stat().st_size == 0:
                        log.info(
                            f"  Generating B-Roll for scene {plan.scene_number} "
                            f"'{plan.broll_keywords[:30]}'...",
                            stage.value,
                        )
                        retry.execute(
                            lambda p=plan, op=out_path:
                                self.broll_engine.generate_broll_clip(
                                    prompt=p.broll_keywords,
                                    duration_seconds=p.duration,
                                    output_path=op,
                                    aspect_ratio=cfg.aspect_ratio,
                                    fps=cfg.fps,
                                ),
                            stage,
                            cancellation_check=cancelled,
                        )
                    job.broll_asset_paths.append(out_path)
                    job.progress.stage_progress = idx / max(len(broll_needs_scenes), 1)
                    emit()

                result.complete(output_data={"num_broll_clips": len(job.broll_asset_paths)})
                log.info(f"B-Roll complete: {len(job.broll_asset_paths)} clips.", stage.value)
            except Exception as e:
                result.fail(str(e))
                job.mark_failed(f"B-Roll generation failed: {e}")
                emit()
                return

        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 8: Assemble Timeline ─────────────────────────────────────
        stage = PipelineStage.ASSEMBLE_TIMELINE
        result = job.progress.advance_to_stage(stage)
        log.info("Assembling timeline from scene plans and generated assets...", stage.value)
        try:
            # Force rebuild timeline from storyboard to include newly generated assets
            proj_timeline_file = self.workspace_dir / "projects" / cfg.project_id / "timeline" / "project_timeline.json"
            if proj_timeline_file.exists():
                try:
                    proj_timeline_file.unlink()
                except Exception as e:
                    log.warning(f"Could not delete existing timeline file: {e}", stage.value)
            self.timeline_engine.load_project_timeline(cfg.project_id)
            self.timeline_engine.save_project_timeline()
            total_dur = self.timeline_engine.get_total_duration()
            result.complete(output_data={"total_duration": total_dur})
            log.info(f"Timeline assembled: {total_dur:.2f}s total duration.", stage.value)
        except Exception as e:
            result.fail(str(e))
            job.mark_failed(f"Timeline assembly failed: {e}")
            emit()
            return

        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 9: Render Preview ────────────────────────────────────────
        stage = PipelineStage.RENDER_PREVIEW
        result = job.progress.advance_to_stage(stage)
        preview_dir = paths["preview"]
        preview_path = preview_dir / "preview.mp4"

        if stage in cached_stages and preview_path.exists():
            log.info("Loading cached preview video...", stage.value)
            job.preview_path = preview_path
            result.complete(output_data={"preview_path": str(preview_path)}, cached=True)
        elif cfg.generate_preview:
            log.info("Rendering preview video (low-res)...", stage.value)
            try:
                render_job = self.timeline_engine.render_video(
                    output_path=preview_path,
                    low_res=True,
                    progress_callback=lambda p: setattr(job.progress, "stage_progress", p) or emit(),
                )
                import time
                while render_job.status in ["pending", "running"]:
                    if cancelled():
                        job.mark_cancelled()
                        return
                    time.sleep(0.5)

                if render_job.status == "completed":
                    job.preview_path = preview_path
                    result.complete(output_data={"preview_path": str(preview_path)})
                    log.info("Preview render complete.", stage.value)
                else:
                    result.fail(render_job.error_message or "Render failed.")
                    log.warning(f"Preview render failed: {render_job.error_message}", stage.value)
            except Exception as e:
                # Preview failure is non-fatal
                result.fail(str(e))
                log.warning(f"Preview render skipped due to error: {e}", stage.value)
        else:
            result.skip("generate_preview=False")
            log.info("Preview generation skipped (disabled in config).", stage.value)

        emit()
        if cancelled():
            job.mark_cancelled()
            return

        # ── STAGE 10: Export Final ─────────────────────────────────────────
        stage = PipelineStage.EXPORT_FINAL
        result = job.progress.advance_to_stage(stage)

        # Determine output path
        export_dir = paths["export"]
        if cfg.output_path:
            final_output = Path(cfg.output_path)
        else:
            final_output = export_dir / f"{cfg.project_id}_final.mp4"

        log.info(f"Exporting final video to: {final_output.name}", stage.value)
        try:
            # Map quality string to ExportSettings bitrate
            settings = ExportSettings(
                preset="Custom Resolution",
                width=1920 if cfg.aspect_ratio == "16:9" else 1080,
                height=1080 if cfg.aspect_ratio == "16:9" else 1920,
                fps=cfg.fps,
                codec=cfg.codec,
                container="MP4",
                bitrate=cfg.quality,
                gpu_acceleration="Auto-Detect",
                burn_subtitles=False,
            )

            # Use the composed preview/render as input if available, else let
            # the export engine render from the timeline directly.
            input_source = job.preview_path if (
                job.preview_path and job.preview_path.exists()
            ) else None

            def _do_export():
                if input_source:
                    return self.export_engine.export_video(
                        input_video_path=input_source,
                        output_video_path=final_output,
                        quality=cfg.quality,
                        codec=cfg.codec.lower(),
                    )
                # No preview available; request a render then export
                render_output = export_dir / "render_raw.mp4"
                render_job = self.timeline_engine.render_video(
                    output_path=render_output,
                    low_res=False,
                )
                import time
                while render_job.status in ["pending", "running"]:
                    time.sleep(0.5)
                if render_job.status != "completed":
                    raise RuntimeError(f"Timeline render failed: {render_job.error_message}")
                return self.export_engine.export_video(
                    input_video_path=render_output,
                    output_video_path=final_output,
                    quality=cfg.quality,
                    codec=cfg.codec.lower(),
                )

            retry.execute(_do_export, stage, cancellation_check=cancelled)
            job.mark_completed(final_output)
            result.complete(output_data={"output_path": str(final_output)})
            log.info(f"Export complete: {final_output}", stage.value)

        except Exception as e:
            result.fail(str(e))
            job.mark_failed(f"Export failed: {e}")
            log.error(f"Export failed: {e}", stage.value)
            emit()
            return

        emit()

    # ── Private helpers ────────────────────────────────────────────────────

    def _run_director(self, script: str, aspect_ratio: str) -> List[ScenePlan]:
        """Run director scene analysis and return a list of ScenePlans.

        Args:
            script: Raw text script.
            aspect_ratio: Desired video aspect ratio.

        Returns:
            List of ScenePlan objects for the script.
        """
        analyzer = SceneAnalyzer()
        scene_timeline = analyzer.analyze_script(script)
        return scene_timeline.scenes

    def _save_scene_plans(self, path: Path, plans: List[ScenePlan]) -> None:
        """Serialize scene plans to a JSON file.

        Args:
            path: Destination file path.
            plans: List of ScenePlan instances to save.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [p.to_dict() for p in plans]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_scene_plans(self, path: Path) -> List[ScenePlan]:
        """Load scene plans from a JSON file.

        Args:
            path: Source JSON file path.

        Returns:
            List of reconstructed ScenePlan objects.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ScenePlan.from_dict(d) for d in data]
