"""Unit tests for the Timeline and Render Engine module.
"""

import json
from pathlib import Path
import tempfile
import time
import pytest
import numpy as np
import soundfile as sf

from core.director.scene_plan import ScenePlan
from core.timeline.timeline_clip import TimelineClip
from core.timeline.timeline_track import TimelineTrack
from core.timeline.timeline_scene import TimelineScene
from core.timeline.timeline_playback import TimelinePlayback
from core.timeline.timeline_history import TimelineHistory
from core.timeline.timeline_serializer import TimelineSerializer
from core.timeline.timeline_builder import TimelineBuilder
from core.timeline.timeline_controller import TimelineController
from core.timeline.timeline_engine import TimelineEngine


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_timeline_clip_trimming_and_moving():
    """Test clip repositioning, duplicate, and trimming limits."""
    clip = TimelineClip(
        name="Test Clip",
        asset_path="assets/mock.mp4",
        start_time=2.0,
        duration=5.0,
        source_start=1.0,
        source_duration=10.0,
        clip_type="Presenter"
    )

    assert clip.start_time == 2.0
    assert clip.duration == 5.0

    # Move clip
    clip.move(4.0)
    assert clip.start_time == 4.0

    # Trim start
    clip.trim_start(1.0)
    assert clip.start_time == 5.0
    assert clip.source_start == 2.0
    assert clip.duration == 4.0

    # Trim end
    clip.trim_end(1.0)
    assert clip.duration == 3.0

    # Duplicate
    dup = clip.duplicate()
    assert dup.clip_id != clip.clip_id
    assert dup.name == "Test Clip (Copy)"
    assert dup.duration == 3.0


def test_timeline_track_collisions():
    """Test track insertion, sorting, and collision validation."""
    track = TimelineTrack(name="Voice Track", track_type="Voice")
    assert track.track_type == "Voice"

    c1 = TimelineClip(name="Clip 1", asset_path="a1.wav", start_time=1.0, duration=3.0, clip_type="Voice")
    c2 = TimelineClip(name="Clip 2", asset_path="a2.wav", start_time=5.0, duration=2.0, clip_type="Voice")

    # Add non-overlapping clips
    assert track.add_clip(c1) is True
    assert track.add_clip(c2) is True
    assert len(track.clips) == 2
    assert track.get_duration() == 7.0

    # Add overlapping clip on non-overlapping track (should be blocked)
    c3 = TimelineClip(name="Clip 3 (Overlapping)", asset_path="a3.wav", start_time=2.0, duration=2.0, clip_type="Voice")
    assert track.add_clip(c3) is False
    assert len(track.clips) == 2

    # Remove clip
    assert track.remove_clip(c1.clip_id) is True
    assert len(track.clips) == 1
    assert track.clips[0].clip_id == c2.clip_id


def test_timeline_history():
    """Test pushing states to history stack and performing undo/redo operations."""
    history = TimelineHistory()
    state_a = {"tracks": [], "scenes": [], "total_duration": 0.0}
    state_b = {"tracks": [{"name": "Track 1"}], "scenes": [], "total_duration": 5.0}

    # Action 1: Timeline starts empty (state_a) -> We push state_a before modifying it.
    history.push_state(state_a)
    assert len(history.undo_stack) == 1
    
    # Current state is now state_b. To Undo:
    prev = history.undo(state_b)
    assert prev == state_a
    assert len(history.undo_stack) == 0
    assert len(history.redo_stack) == 1

    # To Redo:
    nxt = history.redo(state_a)
    assert nxt == state_b
    assert len(history.undo_stack) == 1
    assert len(history.redo_stack) == 0


def test_timeline_serializer_conversions(temp_workspace):
    """Test serializing tracks/clips to json and reloading them back."""
    serializer = TimelineSerializer()
    track = TimelineTrack(name="Music", track_type="Music")
    clip = TimelineClip(name="Song", asset_path="song.wav", start_time=0.0, duration=10.0, clip_type="Music")
    track.clips.append(clip)

    scene = TimelineScene(scene_number=1, start_time=0.0, duration=10.0, transition_type="Crossfade", transition_duration=0.5)

    filepath = temp_workspace / "timeline.json"
    success = serializer.save_to_file(filepath, [track], [scene], total_duration=10.0)
    assert success is True
    assert filepath.exists()

    # Load back
    loaded_tracks, loaded_scenes, duration = serializer.load_from_file(filepath)
    assert duration == 10.0
    assert len(loaded_tracks) == 1
    assert loaded_tracks[0].track_type == "Music"
    assert len(loaded_tracks[0].clips) == 1
    assert loaded_tracks[0].clips[0].name == "Song"
    assert len(loaded_scenes) == 1
    assert loaded_scenes[0].transition_type == "Crossfade"


def test_timeline_builder(temp_workspace):
    """Test auto-building track clips from Director scene plans."""
    builder = TimelineBuilder(temp_workspace)
    s1 = ScenePlan(scene_number=1, scene_type="Hook", duration=4.0, narration="Scene one narration.", presenter_visibility="Presenter")
    s2 = ScenePlan(scene_number=2, scene_type="Statistic", duration=6.0, narration="Scene two narration.", presenter_visibility="B-roll")

    tracks, scenes, duration = builder.build_timeline_from_storyboard([s1, s2])
    assert duration == 10.0
    assert len(scenes) == 2
    assert scenes[0].start_time == 0.0
    assert scenes[1].start_time == 4.0

    # Verify tracks populated
    pres_track = next(t for t in tracks if t.track_type == "Presenter")
    broll_track = next(t for t in tracks if t.track_type == "B-roll")
    
    assert len(pres_track.clips) == 2
    # B-roll only generated for scene 2 (Statistic, visibility: B-roll)
    assert len(broll_track.clips) == 1
    assert broll_track.clips[0].start_time == 4.0


def test_timeline_playback():
    """Test playhead step sizes, loops, wrapping, and states."""
    playback = TimelinePlayback(fps=10) # 0.1s per frame
    playback.loop = True
    assert playback.playing is False
    assert playback.current_time == 0.0

    playback.play()
    assert playback.playing is True

    playback.next_frame(total_duration=5.0)
    assert playback.current_time == 0.1

    playback.prev_frame()
    assert playback.current_time == 0.0

    # Test loop wrap
    playback.set_time(4.95, total_duration=5.0)
    playback.next_frame(total_duration=5.0)
    # 4.95 + 0.1 = 5.05 > 5.0, should wrap to 0.0 since loop is active
    assert playback.current_time == 0.0


def test_timeline_controller_edit_actions(temp_workspace):
    """Test controller editing methods (trim, move, split, delete)."""
    controller = TimelineController(temp_workspace)
    controller.project_id = "test_project"
    controller._load_empty_timeline()

    track = next(t for t in controller.tracks if t.track_type == "Presenter")
    clip = TimelineClip(name="Intro Pres", asset_path="intro.mp4", start_time=1.0, duration=5.0, clip_type="Presenter")
    track.clips.append(clip)
    controller.recalculate_duration()

    assert controller.total_duration == 6.0

    # Move clip
    assert controller.move_clip("Presenter", clip.clip_id, 2.0) is True
    assert clip.start_time == 2.0
    assert controller.total_duration == 7.0

    # Trim clip
    assert controller.trim_clip("Presenter", clip.clip_id, "start", 1.0) is True
    assert clip.start_time == 3.0
    assert clip.duration == 4.0

    # Split clip
    # Clip starts at 3.0, duration is 4.0. Split at 5.0.
    assert controller.split_clip("Presenter", clip.clip_id, 5.0) is True
    assert len(track.clips) == 2
    assert track.clips[0].duration == 2.0
    assert track.clips[1].start_time == 5.0
    assert track.clips[1].duration == 2.0

    # Delete clip
    cid2 = track.clips[1].clip_id
    assert controller.delete_clip("Presenter", cid2) is True
    assert len(track.clips) == 1


def test_timeline_audio_mixing(temp_workspace):
    """Test loading and mixing multiple audio files using soundfile."""
    controller = TimelineController(temp_workspace)
    controller._load_empty_timeline()

    # Generate dummy WAV audio files
    sr = 24000
    t_arr = np.linspace(0, 1, sr)
    # Sine wave
    data_1 = np.sin(2 * np.pi * 440 * t_arr)
    data_2 = np.sin(2 * np.pi * 880 * t_arr)

    wav_1 = temp_workspace / "voice_1.wav"
    wav_2 = temp_workspace / "music_1.wav"
    sf.write(str(wav_1), data_1, sr)
    sf.write(str(wav_2), data_2, sr)

    # Setup clips in tracks
    voice_track = next(t for t in controller.tracks if t.track_type == "Voice")
    music_track = next(t for t in controller.tracks if t.track_type == "Music")

    c_voice = TimelineClip(name="Voice", asset_path=str(wav_1.relative_to(temp_workspace)), start_time=0.0, duration=1.0, clip_type="Voice")
    c_music = TimelineClip(name="Music", asset_path=str(wav_2.relative_to(temp_workspace)), start_time=0.0, duration=1.0, clip_type="Music")

    voice_track.clips.append(c_voice)
    music_track.clips.append(c_music)
    controller.recalculate_duration()

    # Output mixed wave path
    out_wav = temp_workspace / "mixed_soundtrack.wav"
    success = controller.renderer.mix_soundtrack(
        tracks=controller.tracks,
        output_wav_path=out_wav,
        total_duration=1.0,
        samplerate=sr
    )

    assert success is True
    assert out_wav.exists()

    # Load mixed file and verify length
    mix_data, mix_sr = sf.read(str(out_wav))
    assert mix_sr == sr
    assert len(mix_data) == sr
    assert mix_data.shape[1] == 2 # stereo output
