"""TimelineController for coordinating project timelines, history stacks, track updates,
playheads, and rendering jobs.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading

from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene
from core.timeline.timeline_playback import TimelinePlayback
from core.timeline.timeline_renderer import TimelineRenderer
from core.timeline.timeline_serializer import TimelineSerializer
from core.timeline.timeline_history import TimelineHistory
from core.timeline.timeline_builder import TimelineBuilder
from core.timeline.timeline_job import TimelineRenderJob
from core.director.timeline_exporter import TimelineExporter


class TimelineController:
    """Thread-safe controller managing clips alignment, undo/redo states, and playback updates."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize TimelineController.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        
        self.tracks: List[TimelineTrack] = []
        self.scenes: List[TimelineScene] = []
        self.total_duration = 0.0
        self.project_id: Optional[str] = None

        self.playback = TimelinePlayback()
        self.renderer = TimelineRenderer(self.workspace_dir)
        self.serializer = TimelineSerializer()
        self.history = TimelineHistory()
        self.builder = TimelineBuilder(self.workspace_dir)

        self.active_job: Optional[TimelineRenderJob] = None
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def _push_history(self) -> None:
        """Save a snapshot of the current state to the undo history stack."""
        state = self.serializer.serialize(self.tracks, self.scenes, self.total_duration)
        self.history.push_state(state)

    def load_project_timeline(self, project_id: str) -> None:
        """Load project timeline from disk, or automatically compile a default timeline if missing.

        Args:
            project_id: UUID of project.
        """
        with self._lock:
            self.project_id = project_id
            self.history.clear()
            self.renderer.clear_readers()

            proj_timeline_file = self.workspace_dir / "projects" / project_id / "timeline" / "project_timeline.json"
            if proj_timeline_file.exists():
                self._logger.info(f"Found saved timeline JSON for project {project_id}.")
                tracks, scenes, duration = self.serializer.load_from_file(proj_timeline_file)
                self.tracks = tracks
                self.scenes = scenes
                self.total_duration = duration
            else:
                self._logger.info(f"No saved timeline found. Building timeline from Director storyboard...")
                # Try to load storyboard.json from project directory
                storyboard_file = self.workspace_dir / "projects" / project_id / "storyboard.json"
                if storyboard_file.exists():
                    try:
                        timeline = TimelineExporter.import_from_file(storyboard_file)
                        # We also search for active B-roll library assets
                        # normally loaded via BrollEngine. In controller, we start with empty asset lookup,
                        # and BrollEngine integration will sync it.
                        tracks, scenes, duration = self.builder.build_timeline_from_storyboard(
                            scene_plans=timeline.scenes,
                            project_id=project_id
                        )
                        self.tracks = tracks
                        self.scenes = scenes
                        self.total_duration = duration
                        # Auto save immediately
                        self._save_to_disk_nolock()
                    except Exception as e:
                        self._logger.error(f"Failed to build timeline from storyboard: {e}")
                        self._load_empty_timeline()
                else:
                    self._logger.warning("No storyboard found; loading empty timeline.")
                    self._load_empty_timeline()

            # Push initial state to history
            state = self.serializer.serialize(self.tracks, self.scenes, self.total_duration)
            self.history.undo_stack.append(state)

    def _load_empty_timeline(self) -> None:
        """Create standard empty tracks."""
        self.tracks = [
            TimelineTrack(name="Presenter Track", track_type="Presenter"),
            TimelineTrack(name="Voice Track", track_type="Voice"),
            TimelineTrack(name="B-Roll Track", track_type="B-roll"),
            TimelineTrack(name="Music Track", track_type="Music"),
            TimelineTrack(name="Text Track", track_type="Text"),
            TimelineTrack(name="Camera Track", track_type="Camera")
        ]
        self.scenes = []
        self.total_duration = 0.0

    def save_project_timeline(self) -> bool:
        """Persist current timeline data structure to disk."""
        with self._lock:
            return self._save_to_disk_nolock()

    def _save_to_disk_nolock(self) -> bool:
        """Save to disk without acquiring lock (internal use)."""
        if not self.project_id:
            return False
        proj_timeline_file = self.workspace_dir / "projects" / self.project_id / "timeline" / "project_timeline.json"
        return self.serializer.save_to_file(proj_timeline_file, self.tracks, self.scenes, self.total_duration)

    def recalculate_duration(self) -> float:
        """Recalculate overall timeline duration based on longest track length."""
        with self._lock:
            dur = 0.0
            for track in self.tracks:
                dur = max(dur, track.get_duration())
            self.total_duration = dur
            return dur

    # --- Clip Actions ---

    def move_clip(self, track_type: str, clip_id: str, new_start: float) -> bool:
        """Move a clip on a track to a new starting time.

        Args:
            track_type: Target track classification.
            clip_id: Target clip UUID.
            new_start: Target start time in seconds.

        Returns:
            True if moved, False otherwise.
        """
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if not track or track.locked:
                return False

            clip = track.get_clip(clip_id)
            if not clip:
                return False

            # Collision check for non-overlapping tracks
            if track_type in ["Presenter", "Voice", "Camera"]:
                if track._detect_overlap(new_start, clip.duration, exclude_clip_id=clip_id):
                    return False

            self._push_history()
            clip.move(new_start)
            track.sort_clips()
            self._save_to_disk_nolock()
            
        self.recalculate_duration()
        return True

    def trim_clip(self, track_type: str, clip_id: str, side: str, delta: float) -> bool:
        """Trim the start or end boundary of a clip.

        Args:
            track_type: Target track type.
            clip_id: Target clip UUID.
            side: "start" or "end".
            delta: Float delta trim duration.

        Returns:
            True if trimmed, False otherwise.
        """
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if not track or track.locked:
                return False

            clip = track.get_clip(clip_id)
            if not clip:
                return False

            # Double check collisions if expanding start/end
            # If delta is negative, clip is expanding, so check overlaps
            if delta < 0 and track_type in ["Presenter", "Voice", "Camera"]:
                if side == "start":
                    # start shifts left by abs(delta)
                    if track._detect_overlap(clip.start_time + delta, clip.duration - delta, exclude_clip_id=clip_id):
                        return False
                else:
                    # end shifts right
                    if track._detect_overlap(clip.start_time, clip.duration - delta, exclude_clip_id=clip_id):
                        return False

            self._push_history()
            if side == "start":
                clip.trim_start(delta)
            else:
                clip.trim_end(delta)
            
            track.sort_clips()
            self._save_to_disk_nolock()

        self.recalculate_duration()
        return True

    def split_clip(self, track_type: str, clip_id: str, split_time: float) -> bool:
        """Split a clip into two clips at a specified timeline timestamp.

        Args:
            track_type: Target track type.
            clip_id: Target clip UUID.
            split_time: Timeline time in seconds to cut.

        Returns:
            True if split, False otherwise.
        """
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if not track or track.locked:
                return False

            clip = track.get_clip(clip_id)
            if not clip:
                return False

            # Ensure split_time is inside the clip bounds
            if not (clip.start_time < split_time < (clip.start_time + clip.duration)):
                return False

            self._push_history()

            # First clip gets trimmed end
            first_duration = split_time - clip.start_time
            second_duration = clip.duration - first_duration
            second_source_start = clip.source_start + first_duration

            # Create second clip
            second_clip = TimelineClip(
                name=f"{clip.name} (Part 2)",
                asset_path=clip.asset_path,
                start_time=split_time,
                duration=second_duration,
                source_start=second_source_start,
                source_duration=clip.source_duration,
                clip_type=clip.clip_type,
                muted=clip.muted
            )

            # Trim first clip
            clip.duration = first_duration

            # Add second clip
            track.clips.append(second_clip)
            track.sort_clips()
            self._save_to_disk_nolock()

        self.recalculate_duration()
        return True

    def duplicate_clip(self, track_type: str, clip_id: str) -> bool:
        """Duplicate a clip, placing the copy immediately after the original clip.

        Args:
            track_type: Target track type.
            clip_id: Target clip UUID.

        Returns:
            True if duplicated, False otherwise.
        """
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if not track or track.locked:
                return False

            clip = track.get_clip(clip_id)
            if not clip:
                return False

            dup = clip.duplicate()
            dup.start_time = clip.start_time + clip.duration

            # Find a clear spot if collision exists on non-overlapping tracks
            if track_type in ["Presenter", "Voice", "Camera"]:
                while track._detect_overlap(dup.start_time, dup.duration):
                    dup.start_time += 1.0  # nudge forward

            self._push_history()
            track.clips.append(dup)
            track.sort_clips()
            self._save_to_disk_nolock()

        self.recalculate_duration()
        return True

    def delete_clip(self, track_type: str, clip_id: str) -> bool:
        """Delete a clip from a track.

        Args:
            track_type: Target track type.
            clip_id: Target clip UUID.

        Returns:
            True if deleted, False otherwise.
        """
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if not track or track.locked:
                return False

            self._push_history()
            success = track.remove_clip(clip_id)
            if success:
                self._save_to_disk_nolock()

        self.recalculate_duration()
        return success

    # --- Track Controls ---

    def toggle_track_lock(self, track_type: str) -> None:
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if track:
                track.locked = not track.locked

    def toggle_track_mute(self, track_type: str) -> None:
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if track:
                track.muted = not track.muted

    def toggle_track_solo(self, track_type: str) -> None:
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if track:
                track.soloed = not track.soloed
                # In standard solo rules, soloing a track mutes all other tracks
                is_any_soloed = any(t.soloed for t in self.tracks)
                for t in self.tracks:
                    if is_any_soloed:
                        # Mute if not soloed
                        t.muted = not t.soloed
                    else:
                        t.muted = False

    def toggle_track_visibility(self, track_type: str) -> None:
        with self._lock:
            track = next((t for t in self.tracks if t.track_type == track_type), None)
            if track:
                track.visible = not track.visible

    # --- History Stack Operations ---

    def undo(self) -> bool:
        """Undo the last edit action.

        Returns:
            True if successful, False if no states to undo.
        """
        with self._lock:
            current_state = self.serializer.serialize(self.tracks, self.scenes, self.total_duration)
            prev_state = self.history.undo(current_state)
            if prev_state:
                tracks, scenes, duration = self.serializer.deserialize(prev_state)
                self.tracks = tracks
                self.scenes = scenes
                self.total_duration = duration
                self.renderer.clear_readers()
                self._save_to_disk_nolock()
                return True
            return False

    def redo(self) -> bool:
        """Redo the last undone edit action.

        Returns:
            True if successful, False if no states to redo.
        """
        with self._lock:
            current_state = self.serializer.serialize(self.tracks, self.scenes, self.total_duration)
            next_state = self.history.redo(current_state)
            if next_state:
                tracks, scenes, duration = self.serializer.deserialize(next_state)
                self.tracks = tracks
                self.scenes = scenes
                self.total_duration = duration
                self.renderer.clear_readers()
                self._save_to_disk_nolock()
                return True
            return False

    # --- Render Trigger Queue ---

    def submit_render_job(
        self,
        output_path: Path,
        low_res: bool = False,
        progress_callback: Optional[Any] = None
    ) -> TimelineRenderJob:
        """Start rendering composite project video in a background worker thread.

        Args:
            output_path: Output file destination path (.mp4).
            low_res: Renders low-res dimension size.
            progress_callback: Optional progress listener.

        Returns:
            TimelineRenderJob instance.
        """
        with self._lock:
            if self.active_job and self.active_job.status in ["pending", "running"]:
                raise RuntimeError("A background rendering task is already in progress.")

            job = TimelineRenderJob(output_path=output_path)
            self.active_job = job

            # Spawn rendering background thread
            render_thread = threading.Thread(
                target=self._run_render_worker,
                args=(job, low_res, progress_callback),
                daemon=True
            )
            render_thread.start()
            return job

    def _run_render_worker(
        self,
        job: TimelineRenderJob,
        low_res: bool,
        progress_callback: Optional[Any]
    ) -> None:
        """Worker thread entry point for video render stitching."""
        job.update_status("running", 0.0)
        self._logger.info(f"Render thread started for job {job.job_id} -> {job.output_path}")

        # Local copies of tracks/scenes under lock for thread safety
        with self._lock:
            tracks_copy = [TimelineTrack.from_dict(t.to_dict()) for t in self.tracks]
            scenes_copy = [TimelineScene.from_dict(s.to_dict()) for s in self.scenes]
            duration = self.total_duration

        def local_progress(prog: float) -> None:
            job.update_status("running", prog)
            if progress_callback:
                try:
                    progress_callback(prog)
                except Exception:
                    pass

        try:
            success = self.renderer.render_timeline_video(
                tracks=tracks_copy,
                scenes=scenes_copy,
                output_mp4_path=job.output_path,
                total_duration=duration,
                aspect_ratio="16:9",
                fps=30,
                low_res=low_res,
                progress_callback=local_progress
            )

            if success:
                job.update_status("completed", 1.0)
                self._logger.info("Background rendering finished successfully.")
            else:
                job.update_status("failed", job.progress, error_message="TimelineRenderer failed to composite output video.")
        except Exception as e:
            self._logger.error(f"Error in background rendering: {e}")
            job.update_status("failed", job.progress, error_message=str(e))
