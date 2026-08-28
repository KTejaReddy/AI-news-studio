"""Configuration settings for the B-Roll Generation Engine.
"""

from typing import Any, Dict, Optional


class BrollConfig:
    """Stores default parameters for B-roll generation tasks."""

    def __init__(
        self,
        provider: str = "Gemini Flow",
        aspect_ratio: str = "16:9",
        fps: int = 30,
        quality: str = "High",
        use_cache: bool = True,
        output_path: Optional[str] = None,
    ) -> None:
        """Initialize BrollConfig.

        Args:
            provider: Service provider name (e.g. Gemini Flow, Veo).
            aspect_ratio: Media aspect ratio layout ("16:9", "9:16", "1:1").
            fps: Frame rate for video assets.
            quality: Render quality level ("High", "Standard", "Fast").
            use_cache: If True, cache generated files and read from cache if prompt matches.
            output_path: Optional custom path to save the final media file.
        """
        self.provider = provider
        self.aspect_ratio = aspect_ratio
        self.fps = fps
        self.quality = quality
        self.use_cache = use_cache
        self.output_path = output_path

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "provider": self.provider,
            "aspect_ratio": self.aspect_ratio,
            "fps": self.fps,
            "quality": self.quality,
            "use_cache": self.use_cache,
            "output_path": self.output_path,
        }
