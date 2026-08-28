"""TimelineClip representing a single media segment placed on a track.
"""

import uuid
from typing import Any, Dict, Optional


class TimelineClip:
    """Represents a clip of visual or audio media placed at a specific time in a track."""

    def __init__(
        self,
        name: str,
        asset_path: str,
        start_time: float,
        duration: float,
        source_start: float = 0.0,
        source_duration: Optional[float] = None,
        clip_type: str = "Presenter",
        muted: bool = False,
        clip_id: Optional[str] = None
    ) -> None:
        """Initialize TimelineClip.

        Args:
            name: Display name.
            asset_path: Relative or absolute path to target file.
            start_time: Seconds from timeline start.
            duration: Active timeline duration length in seconds.
            source_start: Seconds from source file start.
            source_duration: Total duration of the underlying media file.
            clip_type: Classification track type.
            muted: Active mute indicator.
            clip_id: Unique UUID identifier.
        """
        self.clip_id = clip_id or str(uuid.uuid4())
        self.name = name
        self.asset_path = asset_path
        self.start_time = max(0.0, start_time)
        self.duration = max(0.05, duration)
        self.source_start = max(0.0, source_start)
        self.source_duration = source_duration if source_duration is not None else duration
        self.clip_type = clip_type
        self.muted = muted

    def trim_start(self, delta: float) -> None:
        """Trim the beginning of the clip, adjusting start_time and source_start.

        Args:
            delta: Float difference (positive trims, negative expands if possible).
        """
        # Ensure we don't trim past current duration
        actual_delta = min(delta, self.duration - 0.05)
        # Ensure we don't trim source start past 0
        actual_delta = max(actual_delta, -self.source_start)

        self.start_time += actual_delta
        self.source_start += actual_delta
        self.duration -= actual_delta

    def trim_end(self, delta: float) -> None:
        """Trim the end of the clip, adjusting duration.

        Args:
            delta: Float difference (positive trims end, negative expands).
        """
        self.duration = max(0.05, self.duration - delta)

    def move(self, new_start: float) -> None:
        """Reposition the clip on the timeline grid.

        Args:
            new_start: Target start time in seconds.
        """
        self.start_time = max(0.0, new_start)

    def duplicate(self) -> "TimelineClip":
        """Create a carbon copy of this clip with a fresh UUID.

        Returns:
            New TimelineClip instance.
        """
        return TimelineClip(
            name=f"{self.name} (Copy)",
            asset_path=self.asset_path,
            start_time=self.start_time + 1.0,  # Offset slightly
            duration=self.duration,
            source_start=self.source_start,
            source_duration=self.source_duration,
            clip_type=self.clip_type,
            muted=self.muted
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize clip attributes to a dictionary."""
        return {
            "clip_id": self.clip_id,
            "name": self.name,
            "asset_path": self.asset_path,
            "start_time": self.start_time,
            "duration": self.duration,
            "source_start": self.source_start,
            "source_duration": self.source_duration,
            "clip_type": self.clip_type,
            "muted": self.muted
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineClip":
        """Deserialize a TimelineClip instance from a dictionary."""
        return cls(
            name=data["name"],
            asset_path=data["asset_path"],
            start_time=float(data["start_time"]),
            duration=float(data["duration"]),
            source_start=float(data["source_start"]),
            source_duration=float(data["source_duration"]),
            clip_type=data["clip_type"],
            muted=data.get("muted", False),
            clip_id=data["clip_id"]
        )
