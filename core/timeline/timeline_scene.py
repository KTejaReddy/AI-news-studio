"""TimelineScene mapping storyboard scenes boundaries and transition effects.
"""

from typing import Any, Dict, Optional


class TimelineScene:
    """Groups scene index metadata, durations, and transition styles."""

    def __init__(
        self,
        scene_number: int,
        start_time: float,
        duration: float,
        transition_type: str = "Cut",
        transition_duration: float = 0.5,
        narration: str = "",
        broll_keywords: str = ""
    ) -> None:
        """Initialize TimelineScene.

        Args:
            scene_number: Sequence scene index.
            start_time: Absolute timeline start boundary in seconds.
            duration: Scene runtime in seconds.
            transition_type: Style ("Cut", "Fade", "Crossfade", "Slide", "Zoom", "Whip", "Dip to Black").
            transition_duration: Transition blend duration in seconds.
            narration: Exact narration voice-over script details.
            broll_keywords: Related visual keywords search strings.
        """
        self.scene_number = scene_number
        self.start_time = max(0.0, start_time)
        self.duration = max(0.1, duration)
        self.transition_type = transition_type
        self.transition_duration = max(0.0, transition_duration)
        self.narration = narration
        self.broll_keywords = broll_keywords

    def to_dict(self) -> Dict[str, Any]:
        """Serialize scene attributes to a dictionary."""
        return {
            "scene_number": self.scene_number,
            "start_time": self.start_time,
            "duration": self.duration,
            "transition_type": self.transition_type,
            "transition_duration": self.transition_duration,
            "narration": self.narration,
            "broll_keywords": self.broll_keywords
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineScene":
        """Deserialize a TimelineScene instance from a dictionary."""
        return cls(
            scene_number=int(data["scene_number"]),
            start_time=float(data["start_time"]),
            duration=float(data["duration"]),
            transition_type=data.get("transition_type", "Cut"),
            transition_duration=float(data.get("transition_duration", 0.5)),
            narration=data.get("narration", ""),
            broll_keywords=data.get("broll_keywords", "")
        )
