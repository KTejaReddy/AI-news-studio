"""TimelineSerializer for saving and loading tracks, clips, and scene structures to JSON.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene


class TimelineSerializer:
    """Serializes project timeline tracks and scenes to structured JSON files."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)

    def serialize(
        self,
        tracks: List[TimelineTrack],
        scenes: List[TimelineScene],
        total_duration: float = 0.0
    ) -> Dict[str, Any]:
        """Convert track models, clips, and storyboard bounds into a JSON dictionary structure.

        Args:
            tracks: List of TimelineTracks.
            scenes: List of TimelineScenes.
            total_duration: Overall length in seconds.

        Returns:
            JSON-serializable dictionary.
        """
        return {
            "version": "1.0",
            "total_duration": total_duration,
            "scenes": [scene.to_dict() for scene in scenes],
            "tracks": [track.to_dict() for track in tracks]
        }

    def save_to_file(
        self,
        filepath: Path,
        tracks: List[TimelineTrack],
        scenes: List[TimelineScene],
        total_duration: float = 0.0
    ) -> bool:
        """Write serialized timeline dictionary to a JSON file.

        Args:
            filepath: Target file path to write.
            tracks: Tracks list.
            scenes: Scenes list.
            total_duration: Length in seconds.

        Returns:
            True if saved, False otherwise.
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = self.serialize(tracks, scenes, total_duration)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._logger.info(f"Saved project timeline to {filepath.name}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to save timeline to file {filepath}: {e}")
            return False

    def deserialize(self, data: Dict[str, Any]) -> Tuple[List[TimelineTrack], List[TimelineScene], float]:
        """Convert a serialized dictionary back into track objects, clips, and scene structures.

        Args:
            data: Raw dictionary data.

        Returns:
            Tuple of (List[TimelineTrack], List[TimelineScene], total_duration).
        """
        tracks: List[TimelineTrack] = []
        scenes: List[TimelineScene] = []
        total_duration = float(data.get("total_duration", 0.0))

        # 1. Deserialize scenes
        for scene_data in data.get("scenes", []):
            scenes.append(TimelineScene.from_dict(scene_data))

        # 2. Deserialize tracks
        for track_data in data.get("tracks", []):
            tracks.append(TimelineTrack.from_dict(track_data))

        return tracks, scenes, total_duration

    def load_from_file(self, filepath: Path) -> Tuple[List[TimelineTrack], List[TimelineScene], float]:
        """Load timeline details from a JSON file.

        Args:
            filepath: Location of JSON file.

        Returns:
            Tuple of (List[TimelineTrack], List[TimelineScene], total_duration).
        """
        filepath = Path(filepath)
        if not filepath.exists():
            self._logger.warning(f"Timeline file not found: {filepath}")
            return [], [], 0.0

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self.deserialize(data)
        except Exception as e:
            self._logger.error(f"Failed to load timeline from {filepath}: {e}")
            return [], [], 0.0
