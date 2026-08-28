"""ExportWorker for background batch transcoding and rendering.
"""

import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional
import imageio

from core.export.export_job import ExportJob
from core.export.export_queue import ExportQueue
from core.export.export_history import ExportHistory
from core.export.video_encoder import VideoEncoder
from core.export.audio_encoder import AudioEncoder
from core.export.render_pipeline import RenderPipeline
from core.export.thumbnail_generator import ThumbnailGenerator


class ExportWorker(threading.Thread):
    """Processes jobs from the ExportQueue in a background thread."""

    def __init__(
        self,
        queue: ExportQueue,
        history: ExportHistory,
        workspace_dir: Path
    ) -> None:
        """Initialize ExportWorker.

        Args:
            queue: Thread-safe ExportQueue.
            history: ExportHistory manager.
            workspace_dir: Absolute path of workspace.
        """
        super().__init__()
        self.queue = queue
        self.history = history
        self.workspace_dir = Path(workspace_dir).resolve()
        
        self.video_encoder = VideoEncoder()
        self.audio_encoder = AudioEncoder()
        self.render_pipeline = RenderPipeline(self.workspace_dir)
        self.thumbnail_generator = ThumbnailGenerator(self.workspace_dir)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._stop_event = threading.Event()
        self.daemon = True

        self.active_job: Optional[ExportJob] = None

    def stop(self) -> None:
        """Request the worker thread to stop."""
        self._stop_event.set()

    def run(self) -> None:
        """Continuous polling loop for jobs."""
        self._logger.info("Export background worker thread started.")
        while not self._stop_event.is_set():
            try:
                # Pop next pending job if not paused
                job = self.queue.pop_next_pending_job()
                if job is None:
                    time.sleep(0.5)
                    continue

                self.active_job = job
                self._logger.info(f"Worker picked up job {job.job_id} -> target: {job.output_path.name}")
                
                # Run the actual export process
                self._execute_job(job)

                self.active_job = None
            except Exception as e:
                self._logger.error(f"Error in export worker loop: {e}")
                time.sleep(1.0)
        self._logger.info("Export background worker thread stopped.")

    def _execute_job(self, job: ExportJob) -> None:
        """Transcode and render the specified job.

        Args:
            job: ExportJob to process.
        """
        # Resolve target paths
        output_path = self.workspace_dir / job.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Temporary file paths
        temp_dir = self.workspace_dir / "core" / "export" / "render_cache" / job.job_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_wav = temp_dir / "extracted_audio.wav"
        temp_silent_video = temp_dir / "silent_render.mp4"

        reader = None
        writer = None
        try:
            # If no input_path was provided, we cannot transcode!
            if not job.input_path:
                raise ValueError("No input video path provided in export job settings.")

            input_path = self.workspace_dir / job.input_path
            if not input_path.exists():
                # Check if it is an absolute path
                if Path(job.input_path).exists():
                    input_path = Path(job.input_path)
                else:
                    raise FileNotFoundError(f"Input master video file not found: {job.input_path}")

            self._logger.info(f"Starting transcode for {input_path.name} to {output_path.name}")

            # 1. Extract audio from original video using FFmpeg if it exists
            has_audio = self._extract_audio(input_path, temp_wav)

            # 2. Get reader for input video
            reader = imageio.get_reader(str(input_path))
            meta = reader.get_meta_data()
            input_fps = meta.get("fps", 30)
            duration = meta.get("duration", 0.0)

            # Retrieve total frame count safely
            try:
                total_frames = reader.count_frames()
            except Exception:
                if duration > 0:
                    total_frames = int(duration * input_fps)
                else:
                    total_frames = 300  # Fallback

            # Calculate total frames including intro/outro if specified
            intro_frames = 0
            if job.settings.intro_path:
                intro_p = Path(job.settings.intro_path)
                if intro_p.exists():
                    try:
                        with imageio.get_reader(str(intro_p)) as r:
                            intro_frames = r.count_frames()
                    except Exception:
                        pass

            outro_frames = 0
            if job.settings.outro_path:
                outro_p = Path(job.settings.outro_path)
                if outro_p.exists():
                    try:
                        with imageio.get_reader(str(outro_p)) as r:
                            outro_frames = r.count_frames()
                    except Exception:
                        pass

            overall_total_frames = total_frames + intro_frames + outro_frames
            job.total_frames = overall_total_frames

            # 3. Create video writer for silent render
            writer = self.video_encoder.create_video_writer(
                output_path=temp_silent_video,
                fps=job.settings.fps,
                width=job.settings.width,
                height=job.settings.height,
                codec=job.settings.codec,
                bitrate=job.settings.bitrate,
                gpu_acceleration=job.settings.gpu_acceleration,
                container=job.settings.container
            )

            # 4. Generate visual frames sequentially
            frame_gen = self.render_pipeline.process_frames(
                video_reader=reader,
                width=job.settings.width,
                height=job.settings.height,
                fps=job.settings.fps,
                watermark_path=job.settings.watermark_path,
                watermark_opacity=job.settings.watermark_opacity,
                burn_subtitles=job.settings.burn_subtitles,
                srt_content=job.srt_content,
                intro_path=job.settings.intro_path,
                outro_path=job.settings.outro_path
            )

            start_time = time.time()
            frames_written = 0

            for frame in frame_gen:
                # Check for cancellation/pause in queue
                # If job was cancelled by user
                refreshed_job = self.queue.get_job(job.job_id)
                if refreshed_job and refreshed_job.status == "failed" and "cancelled" in (refreshed_job.error_message or "").lower():
                    self._logger.info(f"Cancellation detected for job {job.job_id}.")
                    return

                # Pause handling: wait in loop if queue is paused or job status is paused
                while self.queue.is_paused or (refreshed_job and refreshed_job.status == "paused"):
                    time.sleep(0.5)
                    refreshed_job = self.queue.get_job(job.job_id)
                    if refreshed_job and refreshed_job.status == "failed" and "cancelled" in (refreshed_job.error_message or "").lower():
                        return

                writer.append_data(frame)
                frames_written += 1

                # Update progress periodic stats
                elapsed = time.time() - start_time
                speed = frames_written / max(0.1, elapsed) # fps
                remaining_frames = overall_total_frames - frames_written
                remaining_sec = remaining_frames / max(0.1, speed)

                job.update_progress(
                    frames_rendered=frames_written,
                    total_frames=overall_total_frames,
                    render_speed=speed,
                    time_remaining=remaining_sec
                )

            # Close reader and writer
            writer.close()
            writer = None
            reader.close()
            reader = None

            # 5. Merge silent video and extracted audio WAV
            if has_audio and temp_wav.exists():
                success = self.audio_encoder.merge_audio_video(
                    video_path=temp_silent_video,
                    audio_path=temp_wav,
                    output_path=output_path
                )
                if not success:
                    raise RuntimeError("Failed to merge audio and video tracks.")
            else:
                # No audio, just copy silent video to output
                shutil.copy(str(temp_silent_video), str(output_path))

            # 6. Extract final thumbnail from output video
            try:
                self.thumbnail_generator.generate_thumbnail(
                    video_path=output_path,
                    position="best"
                )
            except Exception as te:
                self._logger.warning(f"Failed to generate output thumbnail: {te}")

            # 7. Complete job details
            job.update_status("completed")
            self.history.add_entry(job)
            self._logger.info(f"Export Job {job.job_id} completed successfully!")

        except Exception as e:
            self._logger.error(f"Export job {job.job_id} failed: {e}")
            job.update_status("failed", error_message=str(e))

        finally:
            if writer is not None:
                try:
                    writer.close()
                except Exception as we:
                    self._logger.warning(f"Failed to close writer in finally: {we}")
            if reader is not None:
                try:
                    reader.close()
                except Exception as re:
                    self._logger.warning(f"Failed to close reader in finally: {re}")
            # Clean up temp directory and files
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as ce:
                    self._logger.warning(f"Failed to clean up temp render directory: {ce}")

    def _extract_audio(self, video_path: Path, output_wav: Path) -> bool:
        """Extract audio stream from video to WAV.

        Args:
            video_path: Source video.
            output_wav: Target WAV destination.

        Returns:
            True if audio exists and was extracted, False otherwise.
        """
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", str(video_path),
            "-vn",                  # Disable video recording stream
            "-acodec", "pcm_s16le",  # Uncompressed 16-bit audio PCM
            "-ar", "24000",          # Match narration samplerate
            "-ac", "2",              # Stereo
            str(output_wav)
        ]

        try:
            # Run silently
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            # If size of output_wav is greater than 0, then we successfully extracted audio
            if output_wav.exists() and output_wav.stat().st_size > 1000:
                self._logger.info(f"Extracted audio track from {video_path.name}")
                return True
            return False
        except Exception as e:
            self._logger.warning(f"Audio extraction from video failed: {e}")
            return False
