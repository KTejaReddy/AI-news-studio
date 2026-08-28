"""Abstract Interface for Director AI.

Defines the DirectorEngine contract that future AI video planner modules must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DirectorEngine(ABC):
    """Abstract base class for automated video scripting and storyboard generation."""

    @abstractmethod
    def analyze_script(self, script: str) -> Dict[str, Any]:
        """Analyze a plain script to determine pacing, emotional tone, and segments.

        Args:
            script: Full plain text voice-over script.

        Returns:
            Dictionary containing sentiment analysis, pacing, and segments.
        """
        pass

    @abstractmethod
    def generate_storyboard(
        self,
        script: str,
        aspect_ratio: str = "16:9"
    ) -> List[Dict[str, Any]]:
        """Slice the script and plan scene visuals, combining presenter and B-roll.

        Args:
            script: Full script.
            aspect_ratio: Configured aspect ratio.

        Returns:
            List of scene dictionaries. Each scene dict contains:
            - scene_index (int)
            - script_segment (str)
            - visuals_type ("presenter" or "b-roll")
            - broll_prompt (str, if visuals_type is b-roll)
            - duration_est_seconds (float)
        """
        pass
