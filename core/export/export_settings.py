"""ExportSettings for storing video resolution presets, codec options, watermarks,
and subtitle burn flags.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple


class ExportSettings:
    """Stores project-level transcode encoding options and presets mappings."""

    PRESETS: Dict[str, Tuple[int, int]] = {
        "YouTube Shorts (1080x1920)": (1080, 1920),
        "Instagram Reels (1080x1920)": (1080, 1920),
        "TikTok (1080x1920)": (1080, 1920),
        "Landscape YouTube (1920x1080)": (1920, 1080),
        "Square Instagram (1080x1080)": (1080, 1080),
        "Podcast (1920x1080)": (1920, 1080),
        "Custom Resolution": (1920, 1080)
    }

    def __init__(
        self,
        preset: str = "Landscape YouTube (1920x1080)",
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        codec: str = "H264",
        container: str = "MP4",
        bitrate: str = "Medium",
        gpu_acceleration: str = "Auto-Detect",
        burn_subtitles: bool = True,
        watermark_path: str = "",
        watermark_opacity: float = 0.5,
        intro_path: str = "",
        outro_path: str = ""
    ) -> None:
        """Initialize ExportSettings.

        Args:
            preset: Option preset key.
            width: Custom width pixel size.
            height: Custom height pixel size.
            fps: Playback FPS (24, 30, 60).
            codec: Encoder compression ("H264", "H265", "AV1").
            container: Wrapper file format ("MP4", "MOV", "MKV", "WEBM").
            bitrate: Quality level ("Low", "Medium", "High", "Lossless").
            gpu_acceleration: Hardware routing ("Auto-Detect", "Force CPU").
            burn_subtitles: Burns subtitles directly into video frames.
            watermark_path: Overlay image path.
            watermark_opacity: Transparency alpha overlay.
            intro_path: Intro overlay clip path.
            outro_path: Outro overlay clip path.
        """
        self.preset = preset
        self.fps = fps
        self.codec = codec
        self.container = container
        self.bitrate = bitrate
        self.gpu_acceleration = gpu_acceleration
        self.burn_subtitles = burn_subtitles
        self.watermark_path = watermark_path
        self.watermark_opacity = max(0.0, min(1.0, watermark_opacity))
        self.intro_path = intro_path
        self.outro_path = outro_path

        # Resolve width and height based on presets
        if preset in self.PRESETS and preset != "Custom Resolution":
            self.width, self.height = self.PRESETS[preset]
        else:
            self.width = width
            self.height = height

    def to_dict(self) -> Dict[str, Any]:
        """Serialize settings to a dictionary."""
        return {
            "preset": self.preset,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "codec": self.codec,
            "container": self.container,
            "bitrate": self.bitrate,
            "gpu_acceleration": self.gpu_acceleration,
            "burn_subtitles": self.burn_subtitles,
            "watermark_path": self.watermark_path,
            "watermark_opacity": self.watermark_opacity,
            "intro_path": self.intro_path,
            "outro_path": self.outro_path
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportSettings":
        """Deserialize an ExportSettings instance from a dictionary."""
        return cls(
            preset=data.get("preset", "Landscape YouTube (1920x1080)"),
            width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)),
            fps=int(data.get("fps", 30)),
            codec=data.get("codec", "H264"),
            container=data.get("container", "MP4"),
            bitrate=data.get("bitrate", "Medium"),
            gpu_acceleration=data.get("gpu_acceleration", "Auto-Detect"),
            burn_subtitles=data.get("burn_subtitles", True),
            watermark_path=data.get("watermark_path", ""),
            watermark_opacity=float(data.get("watermark_opacity", 0.5)),
            intro_path=data.get("intro_path", ""),
            outro_path=data.get("outro_path", "")
        )
