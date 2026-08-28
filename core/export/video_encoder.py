"""VideoEncoder for detecting active GPU encoders and compression transcoding
with hardware acceleration fallback to CPU.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import imageio_ffmpeg
import imageio


class VideoEncoder:
    """Detects GPU encoders and manages video file rendering with imageio/FFmpeg."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._available_encoders: List[str] = []
        self._detect_encoders()

    def _check_encoder_working(self, encoder_name: str) -> bool:
        """Verify if a GPU encoder is actually functional on this hardware/driver."""
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe,
                "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=64x64",
                "-frames:v", "1",
                "-c:v", encoder_name,
                "-f", "null",
                "-"
            ]
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=2.0
            )
            return True
        except Exception:
            return False

    def _detect_encoders(self) -> None:
        """Query FFmpeg binary to check which encoders are compiled and available."""
        try:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            res = subprocess.run(
                [ffmpeg_exe, "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            compiled = []
            # Parse output lines
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and (parts[0].startswith("V") or parts[0].startswith("v")):
                    # It is a video encoder
                    compiled.append(parts[1])
            
            # Filter available encoders by checking GPU ones
            gpu_encoders = [
                "h264_nvenc", "hevc_nvenc", "av1_nvenc",
                "h264_qsv", "hevc_qsv", "av1_qsv",
                "h264_amf", "hevc_amf", "av1_amf"
            ]
            for enc in compiled:
                if enc in gpu_encoders:
                    if self._check_encoder_working(enc):
                        self._available_encoders.append(enc)
                else:
                    self._available_encoders.append(enc)

            self._logger.info(f"Detected available FFmpeg video encoders: {self._available_encoders}")
        except Exception as e:
            self._logger.warning(f"Failed to query FFmpeg encoders: {e}. Defaulting to CPU fallbacks.")
            # Fallbacks
            self._available_encoders = ["libx264", "libx265", "libvpx-vp9"]

    def select_encoder(self, codec: str, gpu_acceleration: str) -> str:
        """Select appropriate FFmpeg encoder name based on codec and GPU acceleration mode.

        Args:
            codec: Codec key ("H264", "H265", "AV1").
            gpu_acceleration: Mode ("Auto-Detect", "Force CPU").

        Returns:
            The selected encoder name string.
        """
        codec = codec.upper()
        
        if gpu_acceleration == "Force CPU":
            if codec == "H265":
                return "libx265"
            elif codec == "AV1":
                # libsvtav1 or libaom-av1
                if "libsvtav1" in self._available_encoders:
                    return "libsvtav1"
                elif "libaom-av1" in self._available_encoders:
                    return "libaom-av1"
                return "libaom-av1"
            return "libx264"

        # Hardware acceleration detection route
        if codec == "H264":
            # NVIDIA, Intel, AMD
            for enc in ["h264_nvenc", "h264_qsv", "h264_amf"]:
                if enc in self._available_encoders:
                    self._logger.info(f"Selected GPU accelerated H.264 encoder: {enc}")
                    return enc
            self._logger.info("No H.264 GPU encoder found, falling back to libx264 (CPU)")
            return "libx264"

        elif codec == "H265":
            for enc in ["hevc_nvenc", "hevc_qsv", "hevc_amf"]:
                if enc in self._available_encoders:
                    self._logger.info(f"Selected GPU accelerated H.265 encoder: {enc}")
                    return enc
            self._logger.info("No H.265 GPU encoder found, falling back to libx265 (CPU)")
            return "libx265"

        elif codec == "AV1":
            for enc in ["av1_nvenc", "av1_qsv", "av1_amf"]:
                if enc in self._available_encoders:
                    self._logger.info(f"Selected GPU accelerated AV1 encoder: {enc}")
                    return enc
            # CPU fallback
            if "libsvtav1" in self._available_encoders:
                return "libsvtav1"
            return "libaom-av1"

        return "libx264"

    def get_bitrate_params(self, bitrate_preset: str, width: int, height: int) -> List[str]:
        """Convert quality bitrate preset to FFmpeg CLI parameters.

        Args:
            bitrate_preset: "Low", "Medium", "High", "Lossless".
            width: Frame width.
            height: Frame height.

        Returns:
            FFmpeg command arguments for target bitrates.
        """
        # Define base target bitrates (in Mbps) for standard 1080p. Scale by resolution area ratio.
        base_area = 1920 * 1080
        curr_area = width * height
        scale_ratio = max(0.2, min(4.0, curr_area / base_area))

        low_val = int(1.5 * scale_ratio * 1000) # kbps
        med_val = int(4.5 * scale_ratio * 1000)
        high_val = int(12.0 * scale_ratio * 1000)

        if bitrate_preset == "Low":
            return ["-b:v", f"{low_val}k", "-maxrate", f"{low_val * 2}k", "-bufsize", f"{low_val * 4}k"]
        elif bitrate_preset == "High":
            return ["-b:v", f"{high_val}k", "-maxrate", f"{high_val * 2}k", "-bufsize", f"{high_val * 4}k"]
        elif bitrate_preset == "Lossless":
            # CRF 0 for lossless (x264)
            return ["-crf", "0"]
        
        # Medium default
        return ["-b:v", f"{med_val}k", "-maxrate", f"{med_val * 2}k", "-bufsize", f"{med_val * 4}k"]

    def create_video_writer(
        self,
        output_path: Path,
        fps: int,
        width: int,
        height: int,
        codec: str,
        bitrate: str,
        gpu_acceleration: str,
        container: str = "MP4"
    ) -> Any:
        """Create a configured imageio writer for encoding video.

        Args:
            output_path: Destination path on disk.
            fps: Video frames per second.
            width: Resolution width.
            height: Resolution height.
            codec: Codec name ("H264", "H265", "AV1").
            bitrate: Quality bitrate level ("Low", "Medium", "High", "Lossless").
            gpu_acceleration: "Auto-Detect" or "Force CPU".
            container: Wrapper file format.

        Returns:
            An imageio video writer.
        """
        encoder_name = self.select_encoder(codec, gpu_acceleration)
        bitrate_params = self.get_bitrate_params(bitrate, width, height)

        # Standard container format overrides or extra flags
        output_params = []
        output_params.extend(bitrate_params)
        
        # Standard pixel format yuv420p is required for compatibility on web/mobile players
        output_params.extend(["-pix_fmt", "yuv420p"])

        # Create writer passing the customized codec and output flags
        self._logger.info(f"Opening video writer for {output_path.name} with encoder {encoder_name}")
        
        try:
            writer = imageio.get_writer(
                str(output_path),
                fps=fps,
                codec=encoder_name,
                macro_block_size=16,
                output_params=output_params,
                ffmpeg_log_level="warning"
            )
            return writer
        except Exception as e:
            if encoder_name not in ["libx264", "libx265", "libaom-av1", "libsvtav1"]:
                self._logger.warning(f"GPU accelerated encoder {encoder_name} failed: {e}. Falling back to CPU encoder.")
                # Force CPU fallback
                fallback_encoder = "libx264"
                if codec.upper() == "H265":
                    fallback_encoder = "libx265"
                elif codec.upper() == "AV1":
                    fallback_encoder = "libsvtav1" if "libsvtav1" in self._available_encoders else "libaom-av1"
                
                writer = imageio.get_writer(
                    str(output_path),
                    fps=fps,
                    codec=fallback_encoder,
                    macro_block_size=16,
                    output_params=output_params,
                    ffmpeg_log_level="warning"
                )
                return writer
            else:
                raise
