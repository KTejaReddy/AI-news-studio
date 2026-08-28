"""AudioEncoder for transcoding audio tracks and merging audio/video streams using FFmpeg.
"""

import logging
import subprocess
from pathlib import Path
import imageio_ffmpeg


class AudioEncoder:
    """Manages audio file compression, transcoding, and merging onto silent video streams."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    def merge_audio_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        audio_codec: str = "aac",
        audio_bitrate: str = "192k"
    ) -> bool:
        """Combine a silent video stream and an audio stream into a single output file.

        Args:
            video_path: Silent input video.
            audio_path: Audio track (WAV, MP3, etc.).
            output_path: Target video file path.
            audio_codec: FFmpeg audio codec name (e.g. "aac", "libmp3lame", "copy").
            audio_bitrate: Audio quality bitrate (e.g. "128k", "192k", "320k").

        Returns:
            True if merge succeeded, False otherwise.
        """
        video_path = Path(video_path).resolve()
        audio_path = Path(audio_path).resolve()
        output_path = Path(output_path).resolve()

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",  # Copy video stream directly without re-encoding
            "-c:a", audio_codec,
            "-b:a", audio_bitrate,
            "-strict", "experimental",
            str(output_path)
        ]

        self._logger.info(f"Merging audio ({audio_path.name}) and video ({video_path.name}) into {output_path.name}")
        
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            self._logger.info("Successfully merged audio and video streams.")
            return True
        except subprocess.CalledProcessError as e:
            self._logger.error(f"FFmpeg audio/video merge failed: {e.stderr}")
            return False
        except Exception as e:
            self._logger.error(f"Failed to run merge command: {e}")
            return False

    def transcode_audio(
        self,
        input_audio_path: Path,
        output_audio_path: Path,
        codec: str = "aac",
        bitrate: str = "192k"
    ) -> Path:
        """Convert an audio track into another format (e.g., WAV to AAC/MP3).

        Args:
            input_audio_path: Source audio file.
            output_audio_path: Target audio file destination.
            codec: Audio compression codec.
            bitrate: Speed bitrate level.

        Returns:
            The Path to the transcoded output.
        """
        input_audio_path = Path(input_audio_path).resolve()
        output_audio_path = Path(output_audio_path).resolve()

        if not input_audio_path.exists():
            raise FileNotFoundError(f"Source audio not found: {input_audio_path}")

        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-i", str(input_audio_path),
            "-c:a", codec,
            "-b:a", bitrate,
            str(output_audio_path)
        ]

        self._logger.info(f"Transcoding audio {input_audio_path.name} -> {output_audio_path.name}")

        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_audio_path
        except subprocess.CalledProcessError as e:
            self._logger.error(f"FFmpeg audio transcode failed: {e.stderr}")
            raise RuntimeError(f"Audio transcoding failed: {e.stderr}")
        except Exception as e:
            self._logger.error(f"Failed to run transcode command: {e}")
            raise
Account = "AudioEncoder"
