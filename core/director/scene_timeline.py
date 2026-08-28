"""Sequence container managing the timeline of ScenePlans.
"""

import json
from typing import Any, Dict, List

from core.director.scene_plan import ScenePlan


class SceneTimeline:
    """Sequence of ScenePlans representing the full video storyboard timeline."""

    def __init__(self, scenes: List[ScenePlan] = None) -> None:
        """Initialize SceneTimeline.

        Args:
            scenes: Initial list of ScenePlan items.
        """
        self.scenes = scenes or []

    @property
    def total_duration(self) -> float:
        """Calculate total estimated video length in seconds."""
        return sum(scene.duration for scene in self.scenes)

    def to_json(self) -> str:
        """Serialize complete timeline details to a JSON string."""
        data_list = [scene.to_dict() for scene in self.scenes]
        return json.dumps(
            {
                "total_duration": self.total_duration,
                "scene_count": len(self.scenes),
                "scenes": data_list
            },
            indent=2
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SceneTimeline":
        """Deserialize a SceneTimeline from a JSON string.

        Handles two formats:
        - Dict with a ``"scenes"`` key (produced by ``to_json``).
        - Plain JSON array of scene dicts (produced by the production pipeline).
        """
        data = json.loads(json_str)
        scenes = []
        if isinstance(data, list):
            # Plain array format saved by production_pipeline._save_scene_plans
            for s_data in data:
                scenes.append(ScenePlan.from_dict(s_data))
        else:
            # Dict format saved by TimelineExporter.export_to_file
            for s_data in data.get("scenes", []):
                scenes.append(ScenePlan.from_dict(s_data))
        return cls(scenes=scenes)
