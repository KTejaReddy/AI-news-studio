"""Exporter utility to save and load SceneTimeline storyboards.
"""

from pathlib import Path

from core.director.scene_timeline import SceneTimeline


class TimelineExporter:
    """Helper to export/import SceneTimeline to/from JSON files."""

    @staticmethod
    def export_to_file(timeline: SceneTimeline, filepath: Path) -> Path:
        """Save a SceneTimeline instance to a JSON file.

        Args:
            timeline: The SceneTimeline to write.
            filepath: Destination file path.

        Returns:
            The Path where the file was saved.
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(timeline.to_json())
            
        return filepath

    @staticmethod
    def import_from_file(filepath: Path) -> SceneTimeline:
        """Load a SceneTimeline instance from a JSON file.

        Args:
            filepath: File path containing the JSON.

        Returns:
            The loaded SceneTimeline instance.
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Storyboard JSON file not found at: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            json_str = f.read()

        return SceneTimeline.from_json(json_str)
