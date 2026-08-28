"""Concrete implementation of the DirectorEngine interface.
"""

import logging
from pathlib import Path
import time
from typing import Any, Dict, List

from core.interfaces.director import DirectorEngine as IDirectorEngine
from core.director.director_config import DirectorConfig
from core.director.director_controller import DirectorController
from core.director.director_job import DirectorJob
from core.director.scene_analyzer import SceneAnalyzer
from core.director.scene_timeline import SceneTimeline


class DirectorEngine(IDirectorEngine):
    """Orchestrates voice script analysis and scene timeline layout planning."""

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize DirectorEngine.

        Args:
            workspace_dir: Absolute path of workspace.
        """
        self.workspace_dir = Path(workspace_dir).resolve()
        self.controller = DirectorController()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("DirectorEngine initialized.")

    def analyze_script(self, script: str) -> Dict[str, Any]:
        """Analyze narration text to determine pacing, sentiment, and scene breakdown blocks.

        Args:
            script: Voice-over narration text.

        Returns:
            Dictionary containing sentiment, pacing, and segments checklist.
        """
        self._logger.info("Running synchronous script segmentation analysis...")
        analyzer = SceneAnalyzer()
        timeline = analyzer.analyze_script(script)

        # Estimate reading pace metric:
        word_count = len(script.split())
        pacing = "Moderate"
        if word_count > 0:
            duration = timeline.total_duration
            wps = word_count / duration
            if wps > 3.0:
                pacing = "Fast"
            elif wps < 2.0:
                pacing = "Slow"

        # Categorize overall segment statistics
        scene_types = [scene.scene_type for scene in timeline.scenes]
        types_summary = {}
        for t in scene_types:
            types_summary[t] = types_summary.get(t, 0) + 1

        return {
            "pacing": pacing,
            "sentiment_profile": "Informative / Professional",
            "total_scenes": len(timeline.scenes),
            "estimated_duration_seconds": timeline.total_duration,
            "scene_types_breakdown": types_summary,
            "raw_timeline_json": timeline.to_json()
        }

    def generate_storyboard(
        self,
        script: str,
        aspect_ratio: str = "16:9"
    ) -> List[Dict[str, Any]]:
        """Slice the script and plan scene visuals, combining presenter and B-roll.

        Args:
            script: Full plain text script.
            aspect_ratio: Video layout aspect ratio.

        Returns:
            List of scene dictionaries.
        """
        self._logger.info(f"Generating synchronous storyboard storyboard layout (Aspect: {aspect_ratio})...")
        analyzer = SceneAnalyzer()
        timeline = analyzer.analyze_script(script)

        storyboard = []
        for scene in timeline.scenes:
            storyboard.append({
                "scene_index": scene.scene_number,
                "script_segment": scene.narration,
                "visuals_type": "b-roll" if scene.presenter_visibility == "B-roll" else "presenter",
                "broll_prompt": scene.broll_keywords,
                "duration_est_seconds": scene.duration
            })

        return storyboard

    # --- Async Storyboard Generation Wrapper Method ---
    def generate_timeline(self, script_text: str, aspect_ratio: str = "16:9") -> DirectorJob:
        """Submit a script planning task to the queue controller.

        Args:
            script_text: Narration text script.
            aspect_ratio: Configured aspect ratio.

        Returns:
            DirectorJob context tracker.
        """
        config = DirectorConfig(script_text=script_text, aspect_ratio=aspect_ratio)
        return self.controller.submit_job(config)
