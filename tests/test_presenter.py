"""Unit tests for the Presenter Engine module (LivePortrait).
"""

from pathlib import Path
import tempfile
import time
import pytest

from core.presenter.presenter_config import PresenterConfig
from core.presenter.presenter_job import PresenterJob
from core.presenter.presenter_controller import PresenterController
from core.presenter.presenter_engine import PresenterEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_presenter_config(temp_workspace):
    """Test PresenterConfig data properties."""
    img = temp_workspace / "source.jpg"
    vid = temp_workspace / "driving.mp4"
    out = temp_workspace / "output.mp4"

    config = PresenterConfig(
        source_image_path=img,
        driving_video_path=vid,
        output_video_path=out,
        device="cpu",
        flag_crop=True,
        flag_stitching=False
    )

    assert config.source_image_path == img
    assert config.driving_video_path == vid
    assert config.output_video_path == out
    assert config.device == "cpu"
    assert config.flag_crop is True
    assert config.flag_stitching is False

    d = config.to_dict()
    assert d["device"] == "cpu"
    assert d["flag_crop"] is True
    assert d["flag_stitching"] is False


def test_presenter_job(temp_workspace):
    """Test PresenterJob lifecycle and state updates."""
    img = temp_workspace / "source.jpg"
    vid = temp_workspace / "driving.mp4"
    out = temp_workspace / "output.mp4"

    config = PresenterConfig(source_image_path=img, driving_video_path=vid, output_video_path=out)
    job = PresenterJob(config=config)

    assert job.job_id is not None
    assert job.status == "pending"
    assert job.progress == 0.0

    # Start job
    job.update_status("running", 0.1)
    assert job.status == "running"
    assert job.progress == 0.1
    assert job.started_at is not None

    # Fail job
    job.update_status("failed", 0.5, error_message="Runtime Error description")
    assert job.status == "failed"
    assert job.progress == 0.5
    assert job.completed_at is not None
    assert job.error_message == "Runtime Error description"


def test_presenter_controller(temp_workspace):
    """Test PresenterController scheduling and job registry."""
    controller = PresenterController()
    assert len(controller.list_jobs()) == 0

    img = temp_workspace / "source.jpg"
    vid = temp_workspace / "driving.mp4"
    out = temp_workspace / "output.mp4"

    # Write dummy inputs to avoid immediate worker crash before thread checks
    img.write_text("dummy")
    vid.write_text("dummy")

    config = PresenterConfig(
        source_image_path=img,
        driving_video_path=vid,
        output_video_path=out,
        auto_download=False  # Disable download to fail quickly/safely
    )

    job = controller.submit_job(config)
    assert job.job_id is not None
    assert len(controller.list_jobs()) == 1

    # Retrieve
    retrieved = controller.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id

    # Wait briefly and cancel (since worker is running)
    time.sleep(0.1)
    cancelled = controller.cancel_job(job.job_id)
    assert cancelled is True or job.status in ["completed", "failed"]


def test_presenter_engine(temp_workspace):
    """Test PresenterEngine instantiation."""
    engine = PresenterEngine(workspace_dir=temp_workspace)
    assert engine.workspace_dir == temp_workspace.resolve()
    
    profiles = engine.get_expression_profiles("marcus")
    assert "smiling" in profiles
    assert "serious" in profiles
