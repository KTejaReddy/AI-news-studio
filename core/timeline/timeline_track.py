"""TimelineTrack representing a sequential or layered track layer on the project timeline.
"""

import uuid
from typing import Any, Dict, List, Optional

from core.timeline.timeline_clip import TimelineClip


class TimelineTrack:
    """Manages a collections of non-overlapping (or layered) clips of a specific type."""

    def __init__(
        self,
        name: str,
        track_type: str,
        track_id: Optional[str] = None
    ) -> None:
        """Initialize TimelineTrack.

        Args:
            name: Display name.
            track_type: Type of clips stored ("Presenter", "Voice", "Music", "Sound Effects", etc.).
            track_id: Unique UUID identifier.
        """
        self.track_id = track_id or str(uuid.uuid4())
        self.name = name
        self.track_type = track_type
        self.clips: List[TimelineClip] = []
        self.locked = False
        self.muted = False
        self.soloed = False
        self.visible = True

    def add_clip(self, clip: TimelineClip) -> bool:
        """Add a clip to the track, maintaining sorted order and checking collision rules.

        Args:
            clip: TimelineClip to add.

        Returns:
            True if clip was added successfully, False if blocked by track lock or overlap collisions.
        """
        if self.locked:
            return False

        # Collision check for non-overlapping tracks (Voice, Presenter, Camera)
        if self.track_type in ["Presenter", "Voice", "Camera"]:
            if self._detect_overlap(clip.start_time, clip.duration):
                return False

        self.clips.append(clip)
        self.sort_clips()
        return True

    def remove_clip(self, clip_id: str) -> bool:
        """Remove a clip from the track.

        Args:
            clip_id: UUID of clip to remove.

        Returns:
            True if removed, False otherwise.
        """
        if self.locked:
            return False

        for idx, clip in enumerate(self.clips):
            if clip.clip_id == clip_id:
                self.clips.pop(idx)
                return True
        return False

    def get_clip(self, clip_id: str) -> Optional[TimelineClip]:
        """Fetch a clip by its unique ID.

        Args:
            clip_id: UUID of clip.

        Returns:
            TimelineClip or None.
        """
        for clip in self.clips:
            if clip.clip_id == clip_id:
                return clip
        return None

    def sort_clips(self) -> None:
        """Sort clips in place by start time."""
        self.clips.sort(key=lambda c: c.start_time)

    def _detect_overlap(self, start: float, duration: float, exclude_clip_id: Optional[str] = None) -> bool:
        """Check if a time window overlaps with existing clips in this track.

        Args:
            start: Seconds timeline start boundary.
            duration: Timeline duration length.
            exclude_clip_id: Optional clip ID to skip (useful for self-moving checks).

        Returns:
            True if overlap exists, False otherwise.
        """
        end = start + duration
        for clip in self.clips:
            if exclude_clip_id and clip.clip_id == exclude_clip_id:
                continue
            clip_end = clip.start_time + clip.duration
            # Overlap check
            if max(start, clip.start_time) < min(end, clip_end):
                return True
        return False

    def get_duration(self) -> float:
        """Compute the total duration (last clip end time) of this track.

        Returns:
            Total duration in seconds.
        """
        if not self.clips:
            return 0.0
        return max(c.start_time + c.duration for c in self.clips)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize track attributes to a dictionary."""
        return {
            "track_id": self.track_id,
            "name": self.name,
            "track_type": self.track_type,
            "clips": [clip.to_dict() for clip in self.clips],
            "locked": self.locked,
            "muted": self.muted,
            "soloed": self.soloed,
            "visible": self.visible
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineTrack":
        """Deserialize a TimelineTrack instance from a dictionary."""
        track = cls(
            name=data["name"],
            track_type=data["track_type"],
            track_id=data["track_id"]
        )
        track.locked = data.get("locked", False)
        track.muted = data.get("muted", False)
        track.soloed = data.get("soloed", False)
        track.visible = data.get("visible", True)
        
        # Load clips
        for clip_data in data.get("clips", []):
            clip = TimelineClip.from_dict(clip_data)
            track.clips.append(clip)
        
        track.sort_clips()
        return track
