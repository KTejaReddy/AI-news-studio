"""Unit tests for the AI Director Engine module.
"""

import json
from pathlib import Path
import tempfile
import time
import pytest

from core.director.scene_plan import ScenePlan
from core.director.scene_timeline import SceneTimeline
from core.director.timeline_exporter import TimelineExporter
from core.director.scene_analyzer import SceneAnalyzer
from core.director.director_config import DirectorConfig
from core.director.director_job import DirectorJob
from core.director.director_controller import DirectorController
from core.director.director_engine import DirectorEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_scene_plan():
    """Test ScenePlan initialization, dictionary conversion, and loading."""
    scene = ScenePlan(
        scene_number=1,
        scene_type="Hook",
        duration=4.5,
        narration="Hello and welcome!",
        presenter_visibility="Presenter",
        broll_keywords="welcome, intro",
        camera_shot="Medium Shot",
        camera_movement="Static",
        gesture_intensity=1.2,
        transition_type="Cut",
        caption_style="Clean Subtitles",
        background_music_mood="Upbeat",
        voice_emphasis="High",
        emotion="Excited"
    )

    assert scene.scene_number == 1
    assert scene.scene_type == "Hook"
    assert scene.duration == 4.5
    assert scene.narration == "Hello and welcome!"
    assert scene.presenter_visibility == "Presenter"
    assert scene.broll_keywords == "welcome, intro"
    assert scene.camera_shot == "Medium Shot"
    assert scene.camera_movement == "Static"
    assert scene.gesture_intensity == 1.2
    assert scene.transition_type == "Cut"
    assert scene.caption_style == "Clean Subtitles"
    assert scene.background_music_mood == "Upbeat"
    assert scene.voice_emphasis == "High"
    assert scene.emotion == "Excited"

    d = scene.to_dict()
    assert d["scene_type"] == "Hook"
    assert d["duration"] == 4.5
    assert d["narration"] == "Hello and welcome!"

    loaded = ScenePlan.from_dict(d)
    assert loaded.scene_number == 1
    assert loaded.scene_type == "Hook"
    assert loaded.duration == 4.5
    assert loaded.narration == "Hello and welcome!"


def test_scene_timeline():
    """Test SceneTimeline sequential duration sums and JSON conversions."""
    s1 = ScenePlan(scene_number=1, scene_type="Hook", duration=3.0, narration="Scene one.")
    s2 = ScenePlan(scene_number=2, scene_type="Statistic", duration=6.5, narration="Scene two.")
    timeline = SceneTimeline(scenes=[s1, s2])

    assert timeline.total_duration == 9.5
    assert len(timeline.scenes) == 2

    js = timeline.to_json()
    data = json.loads(js)
    assert data["total_duration"] == 9.5
    assert data["scene_count"] == 2
    assert len(data["scenes"]) == 2

    loaded = SceneTimeline.from_json(js)
    assert loaded.total_duration == 9.5
    assert len(loaded.scenes) == 2
    assert loaded.scenes[0].scene_type == "Hook"
    assert loaded.scenes[1].scene_type == "Statistic"


def test_timeline_exporter(temp_workspace):
    """Test TimelineExporter writes files and loads them back."""
    s1 = ScenePlan(scene_number=1, scene_type="Hook", duration=3.0, narration="Scene one.")
    s2 = ScenePlan(scene_number=2, scene_type="Statistic", duration=6.5, narration="Scene two.")
    timeline = SceneTimeline(scenes=[s1, s2])

    filepath = temp_workspace / "storyboard.json"
    TimelineExporter.export_to_file(timeline, filepath)
    assert filepath.exists()

    loaded = TimelineExporter.import_from_file(filepath)
    assert loaded.total_duration == 9.5
    assert len(loaded.scenes) == 2
    assert loaded.scenes[0].narration == "Scene one."
    assert loaded.scenes[1].scene_type == "Statistic"


def test_scene_analyzer():
    """Test SceneAnalyzer splits sentences, categorizes types, and extracts keywords."""
    analyzer = SceneAnalyzer()
    script = (
        "Welcome to AI News! "
        "85% of content creators prefer visual scripts. "
        "Remember: 'Video planning is the key to storytelling.' "
        "Subscribe to our channel and check the link below!"
    )

    timeline = analyzer.analyze_script(script)
    assert len(timeline.scenes) == 4
    
    # Verify sequence numbering
    assert timeline.scenes[0].scene_number == 1
    assert timeline.scenes[1].scene_number == 2
    assert timeline.scenes[2].scene_number == 3
    assert timeline.scenes[3].scene_number == 4

    # Verify type classification heuristic rules
    assert timeline.scenes[0].scene_type == "Hook"
    assert timeline.scenes[1].scene_type == "Statistic"
    assert timeline.scenes[2].scene_type == "Quote"
    assert timeline.scenes[3].scene_type == "Ending"  # Last sentence takes precedence over CTA

    # Verify keyword extraction rules (removes common stopwords)
    keywords = timeline.scenes[0].broll_keywords
    assert "welcome" in keywords
    assert "ai" in keywords
    assert "news" in keywords


def test_director_config():
    """Test DirectorConfig initialization properties."""
    config = DirectorConfig(script_text="Hello world", aspect_ratio="9:16")
    assert config.script_text == "Hello world"
    assert config.aspect_ratio == "9:16"

    d = config.to_dict()
    assert d["script_text"] == "Hello world"
    assert d["aspect_ratio"] == "9:16"


def test_director_job():
    """Test DirectorJob status sequence transitions."""
    config = DirectorConfig(script_text="Hello")
    job = DirectorJob(config=config)

    assert job.job_id is not None
    assert job.status == "pending"
    assert job.progress == 0.0

    job.update_status("running", 0.4)
    assert job.status == "running"
    assert job.progress == 0.4
    assert job.started_at is not None

    timeline = SceneTimeline()
    job.update_status("completed", 1.0, timeline=timeline)
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.completed_at is not None
    assert job.output_timeline == timeline


def test_director_controller():
    """Test DirectorController submitting and canceling queues."""
    controller = DirectorController()
    assert len(controller.list_jobs()) == 0

    config = DirectorConfig(script_text="Hello tests storyboard analyzer.")
    job = controller.submit_job(config)
    
    assert job.job_id is not None
    assert len(controller.list_jobs()) == 1

    retrieved = controller.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id

    time.sleep(0.1)
    cancelled = controller.cancel_job(job.job_id)
    assert cancelled is True or job.status in ["completed", "failed"]


def test_director_engine(temp_workspace):
    """Test DirectorEngine initialization and sync analysis APIs."""
    engine = DirectorEngine(workspace_dir=temp_workspace)
    assert engine.workspace_dir == temp_workspace.resolve()

    script = "Hello world! 85% of people like scripts."
    analysis = engine.analyze_script(script)
    assert analysis["total_scenes"] == 2
    assert analysis["sentiment_profile"] == "Informative / Professional"

    storyboard = engine.generate_storyboard(script)
    assert len(storyboard) == 2
    assert storyboard[0]["scene_index"] == 1
    assert storyboard[0]["visuals_type"] == "presenter"
    assert storyboard[1]["visuals_type"] == "b-roll"  # statistic segment
