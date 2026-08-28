"""Unit tests for the Motion Engine module (MimicMotion).
"""

from pathlib import Path
import tempfile
import time
import pytest

from core.motion.motion_config import MotionConfig
from core.motion.motion_job import MotionJob
from core.motion.motion_controller import MotionController
from core.motion.motion_engine import MotionEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_motion_config(temp_workspace):
    """Test MotionConfig data properties."""
    img = temp_workspace / "source.jpg"
    out = temp_workspace / "output.mp4"

    config = MotionConfig(
        source_image_path=img,
        output_video_path=out,
        motion_style="Casual",
        gesture_strength=1.5,
        enable_idle_motion=False,
        motion_smoothing=0.8,
        device="cpu"
    )

    assert config.source_image_path == img
    assert config.output_video_path == out
    assert config.motion_style == "Casual"
    assert config.gesture_strength == 1.5
    assert config.enable_idle_motion is False
    assert config.motion_smoothing == 0.8
    assert config.device == "cpu"

    d = config.to_dict()
    assert d["motion_style"] == "Casual"
    assert d["gesture_strength"] == 1.5
    assert d["enable_idle_motion"] is False


def test_motion_job(temp_workspace):
    """Test MotionJob lifecycle and status updates."""
    img = temp_workspace / "source.jpg"
    out = temp_workspace / "output.mp4"

    config = MotionConfig(source_image_path=img, output_video_path=out)
    job = MotionJob(config=config)

    assert job.job_id is not None
    assert job.status == "pending"
    assert job.progress == 0.0

    # Start
    job.update_status("running", 0.2)
    assert job.status == "running"
    assert job.progress == 0.2
    assert job.started_at is not None

    # Complete
    job.update_status("completed", 1.0)
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.completed_at is not None
    assert job.output_path == out


def test_motion_controller(temp_workspace):
    """Test MotionController submission, list, and cancel queue actions."""
    controller = MotionController()
    assert len(controller.list_jobs()) == 0

    img = temp_workspace / "source.jpg"
    out = temp_workspace / "output.mp4"
    img.write_text("dummy")

    config = MotionConfig(
        source_image_path=img,
        output_video_path=out,
        auto_download=False  # Avoid clone during test
    )

    job = controller.submit_job(config)
    assert job.job_id is not None
    assert len(controller.list_jobs()) == 1

    retrieved = controller.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id

    # Cancel
    time.sleep(0.1)
    cancelled = controller.cancel_job(job.job_id)
    assert cancelled is True or job.status in ["completed", "failed"]


def test_motion_engine(temp_workspace):
    """Test MotionEngine initialization."""
    engine = MotionEngine(workspace_dir=temp_workspace)
    assert engine.workspace_dir == temp_workspace.resolve()
