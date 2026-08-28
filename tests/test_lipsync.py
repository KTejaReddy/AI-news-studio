"""Unit tests for the Lip Sync Engine module (LatentSync).
"""

from pathlib import Path
import tempfile
import time
import pytest

from core.lipsync.lipsync_config import LipSyncConfig
from core.lipsync.lipsync_job import LipSyncJob
from core.lipsync.lipsync_controller import LipSyncController
from core.lipsync.lipsync_engine import LipSyncEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_lipsync_config(temp_workspace):
    """Test LipSyncConfig properties and serialization."""
    vid = temp_workspace / "presenter.mp4"
    aud = temp_workspace / "speech.wav"
    out = temp_workspace / "synced.mp4"

    config = LipSyncConfig(
        presenter_video_path=vid,
        audio_path=aud,
        output_video_path=out,
        quality="Fast",
        guidance_scale=1.2,
        inference_steps=15,
        device="cpu",
        auto_download=False
    )

    assert config.presenter_video_path == vid
    assert config.audio_path == aud
    assert config.output_video_path == out
    assert config.quality == "Fast"
    assert config.guidance_scale == 1.2
    assert config.inference_steps == 15
    assert config.device == "cpu"
    assert config.auto_download is False

    d = config.to_dict()
    assert d["quality"] == "Fast"
    assert d["guidance_scale"] == 1.2
    assert d["inference_steps"] == 15
    assert d["device"] == "cpu"
    assert d["auto_download"] is False


def test_lipsync_job(temp_workspace):
    """Test LipSyncJob status changes and serialization."""
    vid = temp_workspace / "presenter.mp4"
    aud = temp_workspace / "speech.wav"
    out = temp_workspace / "synced.mp4"

    config = LipSyncConfig(presenter_video_path=vid, audio_path=aud, output_video_path=out)
    job = LipSyncJob(config=config)

    assert job.job_id is not None
    assert job.status == "pending"
    assert job.progress == 0.0

    job.update_status("running", 0.3)
    assert job.status == "running"
    assert job.progress == 0.3
    assert job.started_at is not None

    job.update_status("completed", 1.0)
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.completed_at is not None
    assert job.output_path == out


def test_lipsync_controller(temp_workspace):
    """Test LipSyncController scheduling, listing, and cancellation."""
    controller = LipSyncController()
    assert len(controller.list_jobs()) == 0

    vid = temp_workspace / "presenter.mp4"
    aud = temp_workspace / "speech.wav"
    out = temp_workspace / "synced.mp4"

    # Write mock files to allow worker setup check bypass or quick fail
    vid.write_text("mock video")
    aud.write_text("mock audio")

    config = LipSyncConfig(
        presenter_video_path=vid,
        audio_path=aud,
        output_video_path=out,
        auto_download=False  # Stop git cloning in tests
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


def test_lipsync_engine(temp_workspace):
    """Test LipSyncEngine basic instantiation."""
    engine = LipSyncEngine(workspace_dir=temp_workspace)
    assert engine.workspace_dir == temp_workspace.resolve()
