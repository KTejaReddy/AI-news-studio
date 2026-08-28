"""Configuration settings for script analysis and planning tasks.
"""

from typing import Any, Dict


class DirectorConfig:
    """Stores parameters for Director AI script analysis execution tasks."""

    def __init__(self, script_text: str, aspect_ratio: str = "16:9") -> None:
        """Initialize DirectorConfig.

        Args:
            script_text: Narration text to analyze.
            aspect_ratio: Configured output aspect ratio.
        """
        self.script_text = script_text
        self.aspect_ratio = aspect_ratio

    def to_dict(self) -> Dict[str, Any]:
        """Convert configurations to a dictionary."""
        return {
            "script_text": self.script_text,
            "aspect_ratio": self.aspect_ratio,
        }
