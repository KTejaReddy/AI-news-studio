"""Unit and integration tests for the Export Engine module.
"""

from pathlib import Path
import shutil
import tempfile
import time
import pytest
import numpy as np
from PIL import Image
import imageio

from core.export.export_settings import ExportSettings
from core.export.export_job import ExportJob
from core.export.export_queue import ExportQueue
from core.export.export_history import ExportHistory
from core.export.export_engine import ExportEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_export_settings():
    """Test ExportSettings default configuration, custom presets, and serialization."""
    settings = ExportSettings()
    assert settings.preset == "Landscape YouTube (1920x1080)"
    assert settings.width == 1920
    assert settings.height == 1080
    assert settings.fps == 30
    assert settings.codec == "H264"
    assert settings.container == "MP4"
    assert settings.bitrate == "Medium"
    assert settings.gpu_acceleration == "Auto-Detect"
    assert settings.burn_subtitles is True
    assert settings.watermark_path == ""
    assert settings.watermark_opacity == 0.5
    assert settings.intro_path == ""
    assert settings.outro_path == ""

    # Custom Preset
    settings_custom = ExportSettings(preset="Custom Resolution", width=1280, height=720)
    assert settings_custom.width == 1280
    assert settings_custom.height == 720

    # Specific Preset
    settings_shorts = ExportSettings(preset="YouTube Shorts (1080x1920)")
    assert settings_shorts.width == 1080
    assert settings_shorts.height == 1920

    # Dict Serialization
    d = settings.to_dict()
    assert d["preset"] == "Landscape YouTube (1920x1080)"
    assert d["width"] == 1920
    assert d["height"] == 1080

    # Dict Deserialization
    settings_loaded = ExportSettings.from_dict(d)
    assert settings_loaded.preset == settings.preset
    assert settings_loaded.width == settings.width
    assert settings_loaded.height == settings.height


def test_export_job(temp_workspace):
    """Test ExportJob status progression, progress updates, and serialization."""
    settings = ExportSettings()
    output_path = temp_workspace / "output.mp4"
    input_path = temp_workspace / "input.mp4"
    job = ExportJob(
        output_path=output_path,
        settings=settings,
        input_path=input_path,
        srt_content="1\n00:00:01,000 --> 00:00:03,000\nHello caption!"
    )

    assert job.status == "pending"
    assert job.progress == 0.0
    assert job.srt_content == "1\n00:00:01,000 --> 00:00:03,000\nHello caption!"

    # Progress Update
    job.update_progress(
        frames_rendered=45,
        total_frames=90,
        render_speed=15.0,
        time_remaining=3.0
    )
    assert job.progress == 0.5
    assert job.frames_rendered == 45
    assert job.total_frames == 90
    assert job.render_speed == 15.0
    assert job.time_remaining == 3.0

    # Status Updates
    job.update_status("running")
    assert job.status == "running"
    assert job.started_at is not None

    job.update_status("completed")
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.completed_at is not None

    # Dict Serialization
    d = job.to_dict()
    assert d["status"] == "completed"
    assert d["progress"] == 1.0
    
    # Dict Deserialization
    job_loaded = ExportJob.from_dict(d)
    assert job_loaded.job_id == job.job_id
    assert job_loaded.status == "completed"
    assert job_loaded.progress == 1.0


def test_export_queue(temp_workspace):
    """Test ExportQueue job additions, status polling, pauses, and cancellations."""
    queue = ExportQueue()
    settings = ExportSettings()
    job1 = ExportJob(output_path=temp_workspace / "out1.mp4", settings=settings)
    job2 = ExportJob(output_path=temp_workspace / "out2.mp4", settings=settings)

    queue.add_job(job1)
    queue.add_job(job2)

    assert len(queue.list_jobs()) == 2
    assert queue.get_job(job1.job_id) == job1

    # Pop next pending job
    next_job = queue.pop_next_pending_job()
    assert next_job == job1
    assert job1.status == "running"

    # Queue Pausing
    queue.pause_queue()
    assert queue.is_paused is True
    assert queue.pop_next_pending_job() is None

    # Queue Resuming
    queue.resume_queue()
    assert queue.is_paused is False
    next_job2 = queue.pop_next_pending_job()
    assert next_job2 == job2
    assert job2.status == "running"

    # Cancellation
    job3 = ExportJob(output_path=temp_workspace / "out3.mp4", settings=settings)
    queue.add_job(job3)
    assert queue.cancel_job(job3.job_id) is True
    assert job3.status == "failed"
    assert "cancelled" in (job3.error_message or "").lower()

    # Clear Completed/Failed Queue
    queue.clear_queue()
    # job1 and job2 are running. job3 is failed. job3 should be cleared.
    remaining_jobs = queue.list_jobs()
    assert len(remaining_jobs) == 2
    assert job3.job_id not in queue.jobs


def test_export_history(temp_workspace):
    """Test ExportHistory load, save, listing, and cleaning routines."""
    history = ExportHistory(temp_workspace)
    settings = ExportSettings()
    job = ExportJob(output_path=temp_workspace / "out.mp4", settings=settings)
    job.update_status("completed")

    history.add_entry(job)
    assert len(history.list_entries()) == 1
    assert history.list_entries()[0]["job_id"] == job.job_id

    # Persistence verification
    history2 = ExportHistory(temp_workspace)
    assert len(history2.list_entries()) == 1
    assert history2.list_entries()[0]["job_id"] == job.job_id

    # Clear history
    history.clear_history()
    assert len(history.list_entries()) == 0
    assert history.history_file.exists()
    import json
    with open(history.history_file, "r") as f:
        assert json.load(f) == []


def test_export_engine_integration(temp_workspace):
    """Test ExportEngine full end-to-end transcode workflow with dummy files."""
    # 1. Create dummy input video file (10 frames)
    input_video = temp_workspace / "dummy_input.mp4"
    fps = 10
    width, height = 320, 240
    writer = imageio.get_writer(str(input_video), fps=fps, codec="libx264")
    for _ in range(10):
        writer.append_data(np.zeros((height, width, 3), dtype=np.uint8))
    writer.close()

    output_video = temp_workspace / "dummy_output.mp4"

    # 2. Instantiate ExportEngine
    engine = ExportEngine(temp_workspace)
    try:
        # Run synchronous export_video
        result_path = engine.export_video(
            input_video_path=input_video,
            output_video_path=output_video,
            quality="Low",
            codec="h264"
        )
        
        # Verify output exists
        assert result_path.exists()
        assert result_path.resolve() == output_video.resolve()
        
        # Verify history entry created
        assert len(engine.history.list_entries()) == 1
        assert Path(engine.history.list_entries()[0]["output_path"]).name == output_video.name
    finally:
        engine.shutdown()
