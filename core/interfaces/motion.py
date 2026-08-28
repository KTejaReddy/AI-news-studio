"""Abstract Interface for Motion Engine.

Defines the MotionEngine contract that future AI character animating modules must implement.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class MotionEngine(ABC):
    """Abstract base class for driving facial gestures and body movement from templates."""

    @abstractmethod
    def animate_still_presenter(
        self,
        image_path: Path,
        motion_template: Dict[str, Any],
        output_path: Path,
        duration_seconds: float
    ) -> Path:
        """Animate a static image using facial keypoints or motion templates.

        Args:
            image_path: Input path to the static image.
            motion_template: Dict detailing landmarks or animation keyframe parameters.
            output_path: Target path to write output video.
            duration_seconds: Visual animation duration.

        Returns:
            The Path to the generated animation video.
        """
        pass
