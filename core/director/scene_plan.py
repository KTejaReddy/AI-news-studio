"""Data model representing a single scene's visual and audio production plan.
"""

from typing import Any, Dict


class ScenePlan:
    """Detailed storyboard settings and parameters for a single script scene."""

    def __init__(
        self,
        scene_number: int,
        scene_type: str,
        duration: float,
        narration: str,
        presenter_visibility: str = "Presenter",
        broll_keywords: str = "",
        camera_shot: str = "Medium Shot",
        camera_movement: str = "Static",
        gesture_intensity: float = 1.0,
        transition_type: str = "Cut",
        caption_style: str = "Standard Subtitles",
        background_music_mood: str = "Neutral",
        voice_emphasis: str = "Normal",
        emotion: str = "Neutral"
    ) -> None:
        """Initialize ScenePlan.

        Args:
            scene_number: Sequence index number.
            scene_type: Sentiment/layout classification (e.g. Hook, Statistics, CTA).
            duration: Estimated scene runtime in seconds.
            narration: Narration script text segment for this scene.
            presenter_visibility: Visible subject layout ("Presenter", "B-roll", "Mixed").
            broll_keywords: Search prompts for B-roll generators.
            camera_shot: Framings ("Close-up", "Medium Shot", "Wide Shot").
            camera_movement: Camera motion ("Static", "Pan Left", "Tilt Up", "Zoom In").
            gesture_intensity: Hand/arm gesture velocity scale slider.
            transition_type: Video transitions ("Cut", "Fade", "Dissolve").
            caption_style: Text overlay font layouts.
            background_music_mood: Soundtrack theme ambiance.
            voice_emphasis: Cloned speech pitch/tone weight.
            emotion: Emotion tone profile.
        """
        self.scene_number = scene_number
        self.scene_type = scene_type
        self.duration = duration
        self.narration = narration
        self.presenter_visibility = presenter_visibility
        self.broll_keywords = broll_keywords
        self.camera_shot = camera_shot
        self.camera_movement = camera_movement
        self.gesture_intensity = gesture_intensity
        self.transition_type = transition_type
        self.caption_style = caption_style
        self.background_music_mood = background_music_mood
        self.voice_emphasis = voice_emphasis
        self.emotion = emotion

    def to_dict(self) -> Dict[str, Any]:
        """Serialize scene attributes to a dictionary."""
        return {
            "scene_number": self.scene_number,
            "scene_type": self.scene_type,
            "duration": self.duration,
            "narration": self.narration,
            "presenter_visibility": self.presenter_visibility,
            "broll_keywords": self.broll_keywords,
            "camera_shot": self.camera_shot,
            "camera_movement": self.camera_movement,
            "gesture_intensity": self.gesture_intensity,
            "transition_type": self.transition_type,
            "caption_style": self.caption_style,
            "background_music_mood": self.background_music_mood,
            "voice_emphasis": self.voice_emphasis,
            "emotion": self.emotion
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScenePlan":
        """Deserialize a ScenePlan instance from a dictionary."""
        return cls(
            scene_number=int(data["scene_number"]),
            scene_type=str(data["scene_type"]),
            duration=float(data["duration"]),
            narration=str(data["narration"]),
            presenter_visibility=str(data.get("presenter_visibility", "Presenter")),
            broll_keywords=str(data.get("broll_keywords", "")),
            camera_shot=str(data.get("camera_shot", "Medium Shot")),
            camera_movement=str(data.get("camera_movement", "Static")),
            gesture_intensity=float(data.get("gesture_intensity", 1.0)),
            transition_type=str(data.get("transition_type", "Cut")),
            caption_style=str(data.get("caption_style", "Standard Subtitles")),
            background_music_mood=str(data.get("background_music_mood", "Neutral")),
            voice_emphasis=str(data.get("voice_emphasis", "Normal")),
            emotion=str(data.get("emotion", "Neutral"))
        )
