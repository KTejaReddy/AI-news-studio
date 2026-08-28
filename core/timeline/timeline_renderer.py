"""TimelineRenderer for asynchronous multi-track frame compositing, audio mixing,
subtitle overlaying, transitions blending, and caching.
"""

import logging
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw
import imageio
import soundfile as sf

from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene


class TimelineRenderer:
    """Orchestrates compositing video tracks and mixing audio paths in background threads."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize TimelineRenderer.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.cache_dir = self.workspace_dir / "core" / "timeline" / "cache"
        self.render_dir = self.workspace_dir / "core" / "timeline" / "render"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Readers cache to keep file handles open for efficiency
        self._readers: Dict[str, Any] = {}
        self._render_lock = threading.Lock()

        # In-memory frame cache to accelerate GUI playhead scrubbing
        self._frame_cache: Dict[int, np.ndarray] = {}

    def clear_readers(self) -> None:
        """Close and clear all cached video readers."""
        with self._render_lock:
            for clip_id, reader in self._readers.items():
                try:
                    reader.close()
                except Exception:
                    pass
            self._readers.clear()
            self._frame_cache.clear()

    def get_frame_at_time(
        self,
        t: float,
        tracks: List[TimelineTrack],
        scenes: List[TimelineScene],
        aspect_ratio: str = "16:9",
        fps: int = 30,
        low_res: bool = True
    ) -> np.ndarray:
        """Composite all visible tracks at timeline timestamp t.

        Args:
            t: Timeline time in seconds.
            tracks: Active TimelineTracks.
            scenes: TimelineScenes.
            aspect_ratio: Configured aspect ratio.
            fps: Playback frame rate.
            low_res: If True, renders half-size image for preview speed.

        Returns:
            Numpy array of RGB frame pixels.
        """
        frame_idx = int(t * fps)
        
        # Check cache first for GUI scrubbing acceleration
        if frame_idx in self._frame_cache:
            return self._frame_cache[frame_idx]

        # Resolution boundaries
        width, height = (640, 360) if low_res else (1280, 720)
        if aspect_ratio == "9:16":
            width, height = (360, 640) if low_res else (720, 1280)
        elif aspect_ratio == "1:1":
            width, height = (480, 480) if low_res else (720, 720)

        # Base background canvas (Slate Dark theme)
        base_img = Image.new("RGB", (width, height), color=(20, 20, 24))

        # Check visible tracks
        presenter_track = next((tk for tk in tracks if tk.track_type == "Presenter"), None)
        broll_track = next((tk for tk in tracks if tk.track_type == "B-roll"), None)
        text_track = next((tk for tk in tracks if tk.track_type == "Text"), None)

        presenter_frame = None
        broll_frame = None

        with self._render_lock:
            # 1. Fetch Presenter frame
            if presenter_track and presenter_track.visible:
                clip = self._find_active_clip(presenter_track, t)
                if clip:
                    presenter_frame = self._read_video_frame(clip, t, fps, width, height)

            # 2. Fetch B-roll frame
            if broll_track and broll_track.visible:
                clip = self._find_active_clip(broll_track, t)
                if clip:
                    broll_frame = self._read_video_frame(clip, t, fps, width, height)

        # 3. Layer and Blend
        # Transitions handling near scene boundaries
        active_scene = self._find_active_scene(scenes, t)
        next_scene = self._find_next_scene(scenes, t)
        
        # We blend transition frames if near boundary
        in_transition = False
        alpha = 0.0
        if next_scene and active_scene:
            trans_start = next_scene.start_time
            trans_dur = next_scene.transition_duration
            if trans_start - trans_dur <= t <= trans_start:
                in_transition = True
                alpha = (t - (trans_start - trans_dur)) / trans_dur
                alpha = max(0.0, min(1.0, alpha))

        if in_transition and active_scene and next_scene:
            # Render Scene A frame
            img_a = self._layer_scene_frames(base_img, presenter_frame, broll_frame, width, height)
            
            # Fetch Scene B frames
            with self._render_lock:
                pres_b = None
                broll_b = None
                if presenter_track and presenter_track.visible:
                    clip_b = self._find_active_clip(presenter_track, next_scene.start_time)
                    if clip_b:
                        pres_b = self._read_video_frame(clip_b, next_scene.start_time, fps, width, height)
                if broll_track and broll_track.visible:
                    clip_b = self._find_active_clip(broll_track, next_scene.start_time)
                    if clip_b:
                        broll_b = self._read_video_frame(clip_b, next_scene.start_time, fps, width, height)
            
            img_b = self._layer_scene_frames(base_img, pres_b, broll_b, width, height)
            
            # Apply transition blend
            blended = self._apply_transition(img_a, img_b, next_scene.transition_type, alpha)
            final_img = Image.fromarray(blended)
        else:
            final_img = self._layer_scene_frames(base_img, presenter_frame, broll_frame, width, height)

        # 4. Overlay Narration Subtitles
        if text_track and text_track.visible:
            clip = self._find_active_clip(text_track, t)
            if clip and clip.name:
                self._draw_subtitles(final_img, clip.name, width, height)

        # Convert back to Numpy
        ret_np = np.array(final_img)

        # Cache in memory
        if len(self._frame_cache) < 200:  # limit cache size
            self._frame_cache[frame_idx] = ret_np

        return ret_np

    def _layer_scene_frames(
        self,
        base_canvas: Image.Image,
        presenter: Optional[np.ndarray],
        broll: Optional[np.ndarray],
        w: int,
        h: int
    ) -> Image.Image:
        """Combine presenter and B-roll layers on base canvas."""
        img = base_canvas.copy()
        
        # Presenter as first layer
        if presenter is not None:
            pres_img = Image.fromarray(presenter).resize((w, h))
            img.paste(pres_img, (0, 0))

        # B-roll as overlay layer (takes precedence/covers presenter)
        if broll is not None:
            broll_img = Image.fromarray(broll).resize((w, h))
            img.paste(broll_img, (0, 0))

        return img

    def _apply_transition(
        self,
        img_a: Image.Image,
        img_b: Image.Image,
        transition: str,
        alpha: float
    ) -> np.ndarray:
        """Blend Scene A and Scene B frames based on transition effect type."""
        arr_a = np.array(img_a, dtype=np.float32)
        arr_b = np.array(img_b, dtype=np.float32)

        if transition == "Crossfade" or transition == "Fade":
            blended = arr_a * (1.0 - alpha) + arr_b * alpha
            return np.clip(blended, 0, 255).astype(np.uint8)
        
        elif transition == "Dip to Black":
            # Fade out to black, then fade in to B
            if alpha < 0.5:
                # Scene A to Black
                a_local = alpha * 2.0
                blended = arr_a * (1.0 - a_local)
            else:
                # Black to Scene B
                a_local = (alpha - 0.5) * 2.0
                blended = arr_b * a_local
            return np.clip(blended, 0, 255).astype(np.uint8)

        elif transition == "Slide":
            # Slide horizontal wipe
            w = img_a.width
            offset = int(w * alpha)
            out_arr = np.zeros_like(arr_a, dtype=np.uint8)
            # Paste left side B, right side A
            np_a = np.array(img_a)
            np_b = np.array(img_b)
            out_arr[:, :offset] = np_b[:, :offset]
            out_arr[:, offset:] = np_a[:, offset:]
            return out_arr

        # Default fallback "Cut" (hard transition half way)
        return np.array(img_b) if alpha >= 0.5 else np.array(img_a)

    def _draw_subtitles(self, img: Image.Image, text: str, w: int, h: int) -> None:
        """Render subtitle caption text overlays near the bottom center."""
        draw = ImageDraw.Draw(img)
        # Use default PIL font (or basic standard fonts)
        font_size = max(11, int(h * 0.04))
        # Draw background shadow rectangle for text readability
        char_w = font_size * 0.6
        max_chars = int(w * 0.8 / char_w)
        
        # Word wrap text
        words = text.split()
        lines = []
        cur_line = []
        for word in words:
            if len(" ".join(cur_line + [word])) <= max_chars:
                cur_line.append(word)
            else:
                lines.append(" ".join(cur_line))
                cur_line = [word]
        if cur_line:
            lines.append(" ".join(cur_line))

        text_y = int(h * 0.82) - (len(lines) - 1) * font_size
        
        for line in lines:
            line_w = len(line) * char_w
            text_x = int((w - line_w) / 2)
            
            # Shadow
            draw.rectangle(
                [text_x - 5, text_y - 2, text_x + line_w + 5, text_y + font_size + 2],
                fill=(0, 0, 0, 160)
            )
            # Text (Yellow Karaoke standard highlights)
            draw.text((text_x, text_y), line, fill=(250, 204, 21))
            text_y += font_size + 4

    def _find_active_clip(self, track: TimelineTrack, t: float) -> Optional[TimelineClip]:
        """Find the clip on a track covering timestamp t."""
        for clip in track.clips:
            if clip.start_time <= t <= (clip.start_time + clip.duration):
                return clip
        return None

    def _find_active_scene(self, scenes: List[TimelineScene], t: float) -> Optional[TimelineScene]:
        """Locate scene index boundary covering t."""
        for scene in scenes:
            if scene.start_time <= t <= (scene.start_time + scene.duration):
                return scene
        return None

    def _find_next_scene(self, scenes: List[TimelineScene], t: float) -> Optional[TimelineScene]:
        """Fetch the immediate succeeding scene near t."""
        for scene in scenes:
            if scene.start_time > t:
                return scene
        return None

    def _read_video_frame(self, clip: TimelineClip, t: float, fps: int, w: int, h: int) -> Optional[np.ndarray]:
        """Fetch video frame from cache or open file handle."""
        abs_path = self.workspace_dir / clip.asset_path
        if not abs_path.exists():
            return None

        # Determine frame index within clip file
        local_time = t - clip.start_time + clip.source_start
        frame_idx = int(local_time * fps)

        try:
            # Set up reader
            if clip.clip_id not in self._readers:
                self._readers[clip.clip_id] = imageio.get_reader(str(abs_path))
            
            reader = self._readers[clip.clip_id]
            meta = reader.get_meta_data()
            duration_meta = meta.get("duration", clip.duration)
            
            # Loop check or end check
            if local_time > duration_meta:
                # Clamp to last frame
                frame_idx = int(duration_meta * fps) - 1

            frame_idx = max(0, frame_idx)
            return reader.get_data(frame_idx)
        except Exception:
            # Fallback if frame index out of bounds or read failure
            return None

    def mix_soundtrack(
        self,
        tracks: List[TimelineTrack],
        output_wav_path: Path,
        total_duration: float,
        samplerate: int = 24000
    ) -> bool:
        """Combine voice narration tracks and music layers into single stereo WAV.

        Args:
            tracks: TimelineTracks catalog.
            output_wav_path: Target soundtrack WAV file destination.
            total_duration: Overall length in seconds.
            samplerate: Target sample rate.

        Returns:
            True if mixed, False otherwise.
        """
        output_wav_path = Path(output_wav_path)
        output_wav_path.parent.mkdir(parents=True, exist_ok=True)

        total_samples = int(total_duration * samplerate)
        if total_samples <= 0:
            return False

        # Accumulator array for stereo mixed audio (2 channels)
        mixed_audio = np.zeros((total_samples, 2), dtype=np.float32)

        voice_track = next((tk for tk in tracks if tk.track_type == "Voice"), None)
        music_track = next((tk for tk in tracks if tk.track_type == "Music"), None)

        try:
            # 1. Blend Voice Narration Clips
            if voice_track and not voice_track.muted:
                for clip in voice_track.clips:
                    if clip.muted or not clip.asset_path:
                        continue
                    abs_path = self.workspace_dir / clip.asset_path
                    if not abs_path.exists():
                        continue

                    # Read sound
                    data, sr = sf.read(str(abs_path))
                    # Ensure stereo representation
                    if len(data.shape) == 1:
                        data = np.stack([data, data], axis=-1)

                    # Resample if mismatch
                    if sr != samplerate:
                        # Basic linear interpolation resample
                        num_samples = int(len(data) * samplerate / sr)
                        xp = np.linspace(0, len(data) - 1, len(data))
                        x = np.linspace(0, len(data) - 1, num_samples)
                        resampled = np.zeros((num_samples, 2), dtype=np.float32)
                        resampled[:, 0] = np.interp(x, xp, data[:, 0])
                        resampled[:, 1] = np.interp(x, xp, data[:, 1])
                        data = resampled

                    # Copy aligned segments to accumulator
                    start_sample = int(clip.start_time * samplerate)
                    clip_samples = int(clip.duration * samplerate)
                    
                    data_to_copy = data[int(clip.source_start * samplerate):, :]
                    slice_len = min(clip_samples, len(data_to_copy), total_samples - start_sample)
                    
                    if slice_len > 0:
                        mixed_audio[start_sample:start_sample + slice_len, :] += data_to_copy[:slice_len, :]

            # 2. Blend Background Music Clips
            if music_track and not music_track.muted:
                for clip in music_track.clips:
                    if clip.muted or not clip.asset_path:
                        continue
                    abs_path = self.workspace_dir / clip.asset_path
                    if not abs_path.exists():
                        continue

                    data, sr = sf.read(str(abs_path))
                    if len(data.shape) == 1:
                        data = np.stack([data, data], axis=-1)

                    # Resample
                    if sr != samplerate:
                        num_samples = int(len(data) * samplerate / sr)
                        xp = np.linspace(0, len(data) - 1, len(data))
                        x = np.linspace(0, len(data) - 1, num_samples)
                        resampled = np.zeros((num_samples, 2), dtype=np.float32)
                        resampled[:, 0] = np.interp(x, xp, data[:, 0])
                        resampled[:, 1] = np.interp(x, xp, data[:, 1])
                        data = resampled

                    start_sample = int(clip.start_time * samplerate)
                    clip_samples = int(clip.duration * samplerate)
                    data_to_copy = data[int(clip.source_start * samplerate):, :]
                    slice_len = min(clip_samples, len(data_to_copy), total_samples - start_sample)

                    if slice_len > 0:
                        # Apply default music bed dampening reduction (e.g. 0.15 volume level)
                        mixed_audio[start_sample:start_sample + slice_len, :] += data_to_copy[:slice_len, :] * 0.15

            # 3. Normalize peaks to avoid clipping distortion
            max_peak = np.max(np.abs(mixed_audio))
            if max_peak > 1.0:
                mixed_audio /= max_peak

            # Write mixed audio
            sf.write(str(output_wav_path), mixed_audio, samplerate)
            self._logger.info(f"Assembled stereo soundtrack written to {output_wav_path.name}")
            return True
        except Exception as e:
            self._logger.error(f"Error mixing audio tracks: {e}")
            return False

    def render_timeline_video(
        self,
        tracks: List[TimelineTrack],
        scenes: List[TimelineScene],
        output_mp4_path: Path,
        total_duration: float,
        aspect_ratio: str = "16:9",
        fps: int = 30,
        low_res: bool = False,
        progress_callback: Optional[Any] = None
    ) -> bool:
        """Asynchronously stitch all visual layers and mix audio tracks into target MP4.

        Args:
            tracks: Tracks list.
            scenes: Scenes list.
            output_mp4_path: Target path to write final MP4.
            total_duration: Overall length.
            aspect_ratio: Aspect layout shape.
            fps: Video frame rate.
            low_res: Renders low-res dimensions.
            progress_callback: Callbacks receiving float progress (0.0 to 1.0).

        Returns:
            True if render succeeded, False otherwise.
        """
        output_mp4_path = Path(output_mp4_path)
        output_mp4_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Temp WAV for audio mixing
        temp_wav = output_mp4_path.with_suffix(".temp.wav")

        writer = None
        try:
            # 1. Mix soundtrack WAV
            self.mix_soundtrack(tracks, temp_wav, total_duration)

            # 2. Setup video writer
            num_frames = int(total_duration * fps)
            if num_frames <= 0:
                num_frames = 1

            self._logger.info(f"Starting timeline video render: {num_frames} frames ({total_duration}s)...")
            
            # Temporary silent video render path
            temp_silent_video = output_mp4_path.with_suffix(".temp.mp4")
            
            writer = imageio.get_writer(str(temp_silent_video), fps=fps)

            # Render frames sequentially
            for f in range(num_frames):
                t = f / fps
                frame_pixels = self.get_frame_at_time(
                    t=t,
                    tracks=tracks,
                    scenes=scenes,
                    aspect_ratio=aspect_ratio,
                    fps=fps,
                    low_res=low_res
                )
                writer.append_data(frame_pixels)

                if progress_callback:
                    # Map progress to 0.90 to reserve 10% for ffmpeg merge
                    progress_callback(min(0.90, (f / num_frames) * 0.90))

            writer.close()
            writer = None
            self.clear_readers()

            # 3. Merge audio and video using imageio-ffmpeg subprocess
            import imageio_ffmpeg
            import subprocess
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            merge_cmd = [
                ffmpeg_exe,
                "-y",
                "-i", str(temp_silent_video),
                "-i", str(temp_wav),
                "-c:v", "copy",
                "-c:a", "aac",
                "-strict", "experimental",
                str(output_mp4_path)
            ]
            result = subprocess.run(
                merge_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg merge failed: {result.stderr[-500:]}")

            # Clean up temp files
            if temp_silent_video.exists():
                temp_silent_video.unlink()
            if temp_wav.exists():
                temp_wav.unlink()

            if progress_callback:
                progress_callback(1.0)

            self._logger.info(f"Render completed successfully -> {output_mp4_path}")
            return True

        except Exception as e:
            self._logger.error(f"Render timeline failed: {e}\n{traceback.format_exc()}")
            # Clean up partial renders
            if output_mp4_path.exists():
                try:
                    output_mp4_path.unlink()
                except Exception:
                    pass
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            self.clear_readers()
            # Clean up temp files
            try:
                temp_silent_video = output_mp4_path.with_suffix(".temp.mp4")
                if temp_silent_video.exists():
                    temp_silent_video.unlink()
            except Exception:
                pass
            try:
                if temp_wav.exists():
                    temp_wav.unlink()
            except Exception:
                pass
