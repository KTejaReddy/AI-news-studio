"""TimelineBuilder for automatically assembling storyboard scenes into aligned track clips.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from core.director.scene_plan import ScenePlan
from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene
from core.broll.scene_asset import SceneAsset


class TimelineBuilder:
    """Orchestrates automatic track allocation and timing alignments from Director ScenePlans."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize TimelineBuilder.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self._logger = logging.getLogger(self.__class__.__name__)

    def build_timeline_from_storyboard(
        self,
        scene_plans: List[ScenePlan],
        broll_assets: List[SceneAsset] = None,
        project_id: Optional[str] = None
    ) -> tuple[List[TimelineTrack], List[TimelineScene], float]:
        """Convert a list of Director ScenePlans into populated track tracks and clip grids.

        Args:
            scene_plans: Storyboard timeline scenes from AI Director.
            broll_assets: Optional list of cataloged B-roll assets.
            project_id: Active project UUID.

        Returns:
            Tuple of (tracks_list, scenes_list, total_duration).
        """
        self._logger.info(f"Building timeline for {len(scene_plans)} storyboard scenes.")
        
        # 1. Initialize empty tracks
        track_types = [
            ("Presenter Track", "Presenter"),
            ("Voice Track", "Voice"),
            ("B-Roll Track", "B-roll"),
            ("Music Track", "Music"),
            ("Text Track", "Text"),
            ("Camera Track", "Camera")
        ]
        
        tracks: List[TimelineTrack] = []
        tracks_by_type: Dict[str, TimelineTrack] = {}
        for name, t_type in track_types:
            track = TimelineTrack(name=name, track_type=t_type)
            tracks.append(track)
            tracks_by_type[t_type] = track

        scenes: List[TimelineScene] = []
        current_time = 0.0

        # Index B-roll assets by scene ID for quick lookup
        broll_by_scene: Dict[str, SceneAsset] = {}
        if broll_assets:
            for asset in broll_assets:
                broll_by_scene[str(asset.scene_id)] = asset

        # 2. Iterate storyboard scenes and build aligned clips
        for idx, plan in enumerate(scene_plans):
            scene_num = plan.scene_number
            duration = plan.duration
            scene_start = current_time

            # Create TimelineScene details
            scene_obj = TimelineScene(
                scene_number=scene_num,
                start_time=scene_start,
                duration=duration,
                transition_type=plan.transition_type,
                transition_duration=0.5,
                narration=plan.narration,
                broll_keywords=plan.broll_keywords
            )
            scenes.append(scene_obj)

            # Define folder paths for project resources
            proj_str = project_id or "default"
            voice_dir = self.workspace_dir / "projects" / proj_str / "voice"
            presenter_dir = self.workspace_dir / "projects" / proj_str / "lipsync"

            # Create path names (simulated or real based on structure)
            voice_file = voice_dir / f"scene_{scene_num}.wav"
            presenter_file = presenter_dir / f"scene_{scene_num}.mp4"

            # a. Add Voice clip (Starts at scene start)
            voice_clip = TimelineClip(
                name=f"Voice S{scene_num}",
                asset_path=str(voice_file.relative_to(self.workspace_dir)) if voice_file.is_relative_to(self.workspace_dir) else str(voice_file),
                start_time=scene_start,
                duration=duration,
                clip_type="Voice"
            )
            tracks_by_type["Voice"].add_clip(voice_clip)

            # b. Add Presenter clip (Presenter starts at narration start)
            # For simplicity, narration starts exactly at scene start in this version
            pres_clip = TimelineClip(
                name=f"Presenter S{scene_num}",
                asset_path=str(presenter_file.relative_to(self.workspace_dir)) if presenter_file.is_relative_to(self.workspace_dir) else str(presenter_file),
                start_time=scene_start,
                duration=duration,
                clip_type="Presenter"
            )
            tracks_by_type["Presenter"].add_clip(pres_clip)

            # c. Add B-Roll clip if visibilities settings require it
            # Visible settings: "B-roll" or "Mixed" (Presenter + B-roll)
            vis = plan.presenter_visibility.lower()
            if "b-roll" in vis or "mixed" in vis:
                broll_asset = broll_by_scene.get(str(scene_num))
                broll_path = ""
                if broll_asset:
                    broll_path = broll_asset.file_path
                else:
                    # Check if the real generated B-roll file exists
                    real_broll_file = self.workspace_dir / "projects" / proj_str / "broll" / f"scene_{scene_num}.mp4"
                    if real_broll_file.exists():
                        broll_path = str(real_broll_file.relative_to(self.workspace_dir)) if real_broll_file.is_relative_to(self.workspace_dir) else str(real_broll_file)
                    else:
                        # Mock placeholder B-roll clip path
                        broll_path = f"assets/broll/generated/scene_{scene_num}_mock.mp4"

                broll_clip = TimelineClip(
                    name=f"B-Roll S{scene_num} ({plan.broll_keywords[:20]})",
                    asset_path=broll_path,
                    start_time=scene_start,
                    duration=duration,
                    clip_type="B-roll"
                )
                tracks_by_type["B-roll"].add_clip(broll_clip)

            # d. Add Text clip representing subtitles
            text_clip = TimelineClip(
                name=f"Subtitles S{scene_num}",
                asset_path="",  # Text clip doesn't need file path, name is the text
                start_time=scene_start,
                duration=duration,
                clip_type="Text"
            )
            # Stash the subtitle narration inside name or custom property
            text_clip.name = plan.narration
            tracks_by_type["Text"].add_clip(text_clip)

            # e. Add Camera motion keyframe/clip
            cam_clip = TimelineClip(
                name=f"Cam: {plan.camera_shot} ({plan.camera_movement})",
                asset_path="",
                start_time=scene_start,
                duration=duration,
                clip_type="Camera"
            )
            tracks_by_type["Camera"].add_clip(cam_clip)

            # Progress time tracker
            current_time += duration

        self._logger.info(f"Timeline successfully assembled. Total duration: {current_time:.2f}s")
        return tracks, scenes, current_time
