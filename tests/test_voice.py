"""Unit tests for the Voice Engine module (F5-TTS).
"""

from pathlib import Path
import tempfile
import time
import pytest

from core.voice.voice_profile import VoiceProfile
from core.voice.voice_config import VoiceConfig
from core.voice.voice_job import VoiceJob
from core.voice.voice_controller import VoiceController
from core.voice.voice_engine import VoiceEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_voice_profile(temp_workspace):
    """Test VoiceProfile saving, loading, and serialization."""
    audio_src = temp_workspace / "ref.wav"
    audio_src.write_text("dummy audio data")

    profile = VoiceProfile(
        name="Rachel Test",
        ref_text="This is a test transcription.",
        ref_audio_path=audio_src
    )

    assert profile.name == "Rachel Test"
    assert profile.ref_text == "This is a test transcription."
    assert profile.ref_audio_path == audio_src
    assert profile.profile_id is not None

    voices_dir = temp_workspace / "voices"
    profile_dir = profile.save(voices_dir)

    assert profile_dir.exists()
    assert (profile_dir / "profile.json").exists()
    assert (profile_dir / "ref_audio.wav").exists()

    # Load back
    loaded = VoiceProfile.load(profile_dir)
    assert loaded.name == "Rachel Test"
    assert loaded.ref_text == "This is a test transcription."
    assert loaded.profile_id == profile.profile_id
    assert loaded.ref_audio_path.name == "ref_audio.wav"

    # dict conversion
    d = profile.to_dict()
    assert d["name"] == "Rachel Test"
    assert d["ref_text"] == "This is a test transcription."
    assert d["profile_id"] == profile.profile_id


def test_voice_config(temp_workspace):
    """Test VoiceConfig data properties."""
    audio_src = temp_workspace / "ref.wav"
    audio_src.write_text("dummy")
    profile = VoiceProfile(name="Rachel", ref_text="Hello", ref_audio_path=audio_src)
    output_audio = temp_workspace / "output.wav"

    config = VoiceConfig(
        profile=profile,
        script_text="Hello world script",
        output_audio_path=output_audio,
        device="cpu",
        auto_download=False
    )

    assert config.profile == profile
    assert config.script_text == "Hello world script"
    assert config.output_audio_path == output_audio
    assert config.device == "cpu"
    assert config.auto_download is False

    d = config.to_dict()
    assert d["device"] == "cpu"
    assert d["script_text"] == "Hello world script"
    assert d["auto_download"] is False


def test_voice_job(temp_workspace):
    """Test VoiceJob lifecycle and status updates."""
    audio_src = temp_workspace / "ref.wav"
    audio_src.write_text("dummy")
    profile = VoiceProfile(name="Rachel", ref_text="Hello", ref_audio_path=audio_src)
    output_audio = temp_workspace / "output.wav"
    config = VoiceConfig(profile=profile, script_text="Hello", output_audio_path=output_audio)

    job = VoiceJob(config=config)
    assert job.job_id is not None
    assert job.status == "pending"
    assert job.progress == 0.0

    job.update_status("running", 0.5)
    assert job.status == "running"
    assert job.progress == 0.5
    assert job.started_at is not None

    job.update_status("completed", 1.0)
    assert job.status == "completed"
    assert job.progress == 1.0
    assert job.completed_at is not None
    assert job.output_path == output_audio


def test_voice_controller(temp_workspace):
    """Test VoiceController scheduling and cancel operations."""
    controller = VoiceController()
    assert len(controller.list_jobs()) == 0

    audio_src = temp_workspace / "ref.wav"
    audio_src.write_text("dummy")
    profile = VoiceProfile(name="Rachel", ref_text="Hello", ref_audio_path=audio_src)
    output_audio = temp_workspace / "output.wav"

    config = VoiceConfig(
        profile=profile,
        script_text="Hello test script",
        output_audio_path=output_audio,
        auto_download=False
    )

    job = controller.submit_job(config)
    assert job.job_id is not None
    assert len(controller.list_jobs()) == 1

    retrieved = controller.get_job(job.job_id)
    assert retrieved is not None
    assert retrieved.job_id == job.job_id

    # Cancel job
    time.sleep(0.1)
    cancelled = controller.cancel_job(job.job_id)
    assert cancelled is True or job.status in ["completed", "failed"]


def test_voice_engine(temp_workspace):
    """Test VoiceEngine basic registry methods."""
    engine = VoiceEngine(workspace_dir=temp_workspace)
    assert engine.workspace_dir == temp_workspace.resolve()
    assert engine.voices_dir == temp_workspace.resolve() / "assets" / "voices"

    langs = engine.get_supported_languages()
    assert "en" in langs
    assert "fr" in langs
