"""Data model representing a generated or imported B-roll media asset.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


class SceneAsset:
    """Holds metadata information for a single B-roll visual asset."""

    def __init__(
        self,
        scene_id: str,
        prompt: str,
        provider: str,
        file_path: str,
        asset_type: str = "Video",
        duration: float = 5.0,
        resolution: str = "1920x1080",
        fps: int = 30,
        aspect_ratio: str = "16:9",
        thumbnail_path: str = "",
        tags: Optional[List[str]] = None,
        status: str = "completed",
        asset_id: Optional[str] = None,
        generation_time: Optional[str] = None
    ) -> None:
        """Initialize SceneAsset.

        Args:
            scene_id: ID of the scene this asset is mapped to.
            prompt: Text prompt used to generate the visual.
            provider: Service name provider (e.g. Gemini Flow, Runway).
            file_path: Relative or absolute path to the media file on disk.
            asset_type: Visual media format ("Image", "Video", "Animation", etc.).
            duration: Media length in seconds.
            resolution: Pixel size string (e.g., "1920x1080").
            fps: Video frames per second.
            aspect_ratio: Media aspect shape ratio.
            thumbnail_path: Path to local PNG/JPG preview thumbnail.
            tags: Descriptive tag strings.
            status: Active render status ("pending", "completed", "failed").
            asset_id: Unique UUID identifier.
            generation_time: ISO creation timestamp string.
        """
        self.asset_id = asset_id or str(uuid.uuid4())
        self.scene_id = scene_id
        self.prompt = prompt
        self.provider = provider
        self.generation_time = generation_time or datetime.now().isoformat()
        self.duration = duration
        self.resolution = resolution
        self.fps = fps
        self.aspect_ratio = aspect_ratio
        self.thumbnail_path = thumbnail_path
        self.file_path = file_path
        self.tags = tags or []
        self.status = status
        self.asset_type = asset_type

    def to_dict(self) -> Dict[str, Any]:
        """Serialize asset attributes to a dictionary."""
        return {
            "asset_id": self.asset_id,
            "scene_id": self.scene_id,
            "prompt": self.prompt,
            "provider": self.provider,
            "generation_time": self.generation_time,
            "duration": self.duration,
            "resolution": self.resolution,
            "fps": self.fps,
            "aspect_ratio": self.aspect_ratio,
            "thumbnail_path": self.thumbnail_path,
            "file_path": self.file_path,
            "tags": self.tags,
            "status": self.status,
            "asset_type": self.asset_type
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneAsset":
        """Deserialize a SceneAsset instance from a dictionary."""
        return cls(
            asset_id=data["asset_id"],
            scene_id=data["scene_id"],
            prompt=data["prompt"],
            provider=data["provider"],
            generation_time=data["generation_time"],
            duration=float(data["duration"]),
            resolution=data["resolution"],
            fps=int(data["fps"]),
            aspect_ratio=data["aspect_ratio"],
            thumbnail_path=data.get("thumbnail_path", ""),
            file_path=data["file_path"],
            tags=data.get("tags", []),
            status=data.get("status", "completed"),
            asset_type=data.get("asset_type", "Video")
        )
