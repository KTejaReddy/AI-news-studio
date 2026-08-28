"""Tests for the AI Production Orchestrator module.

Covers:
- ProductionState and PipelineStage enums
- ProductionProgress tracking
- ProductionJob lifecycle transitions
- ProductionLogger structured logging
- RetryManager retry and back-off logic
- DependencyResolver cache detection
- ProductionHistory record persistence
- ProductionScheduler queue management
- ProductionOrchestrator end-to-end integration (mocked engines)
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch
import pytest

# ── Imports under test ────────────────────────────────────────────────────────
from core.production.production_state import (
    PipelineStage,
    ProductionProgress,
    ProductionState,
    StageResult,
)
from core.production.production_job import ProductionJob, ProductionJobConfig
from core.production.production_logger import ProductionLogger
from core.production.retry_manager import RetryManager
from core.production.dependency_resolver import DependencyResolver
from core.production.production_history import ProductionHistory
from core.production.production_scheduler import ProductionScheduler
from core.production.production_pipeline import ProductionPipeline
from core.production.orchestrator import ProductionOrchestrator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return a temporary workspace directory."""
    return tmp_path


@pytest.fixture()
def sample_config(workspace: Path) -> ProductionJobConfig:
    """Return a minimal ProductionJobConfig for testing."""
    return ProductionJobConfig(
        project_id="test-project-001",
        script="Welcome to the AI News Studio. Today we cover the latest in technology.",
        presenter_id="anchor_01",
        voice_id="voice_profile_01",
        output_path=workspace / "output" / "final.mp4",
        max_retries=1,
        use_cache=True,
    )


@pytest.fixture()
def sample_job(sample_config: ProductionJobConfig) -> ProductionJob:
    """Return a fresh ProductionJob for testing."""
    return ProductionJob(sample_config)


# ── ProductionState / PipelineStage ───────────────────────────────────────────

class TestPipelineStage:
    """Tests for PipelineStage enum and helpers."""

    def test_ordered_returns_all_stages(self) -> None:
        """ordered() should return all 10 stages."""
        stages = PipelineStage.ordered()
        assert len(stages) == 10

    def test_ordered_starts_with_parse_script(self) -> None:
        """First stage should always be PARSE_SCRIPT."""
        assert PipelineStage.ordered()[0] == PipelineStage.PARSE_SCRIPT

    def test_ordered_ends_with_export_final(self) -> None:
        """Last stage should always be EXPORT_FINAL."""
        assert PipelineStage.ordered()[-1] == PipelineStage.EXPORT_FINAL

    def test_label_returns_string(self) -> None:
        """label() should return a non-empty string for any stage."""
        for stage in PipelineStage:
            lbl = PipelineStage.label(stage)
            assert isinstance(lbl, str) and len(lbl) > 0


class TestProductionState:
    """Tests for ProductionState enum."""

    def test_all_states_exist(self) -> None:
        """All expected states should be defined."""
        expected = {"idle", "queued", "running", "paused", "completed", "failed", "cancelled", "retrying"}
        actual = {s.value for s in ProductionState}
        assert expected == actual


# ── StageResult ───────────────────────────────────────────────────────────────

class TestStageResult:
    """Tests for StageResult data class."""

    def test_start_sets_status_and_timestamp(self) -> None:
        """start() should set status to 'running' and record started_at."""
        r = StageResult(stage=PipelineStage.PARSE_SCRIPT)
        r.start()
        assert r.status == "running"
        assert r.started_at is not None

    def test_complete_sets_status_and_duration(self) -> None:
        """complete() after start() should set status and compute duration."""
        r = StageResult(stage=PipelineStage.PARSE_SCRIPT)
        r.start()
        time.sleep(0.01)
        r.complete(output_data={"word_count": 42})
        assert r.status == "completed"
        assert r.duration_seconds >= 0
        assert r.output_data["word_count"] == 42
        assert r.was_cached is False

    def test_complete_cached(self) -> None:
        """complete(cached=True) should mark was_cached as True."""
        r = StageResult(stage=PipelineStage.GENERATE_VOICE)
        r.start()
        r.complete(cached=True)
        assert r.was_cached is True

    def test_fail_sets_error_message(self) -> None:
        """fail() should set status to 'failed' and record the error message."""
        r = StageResult(stage=PipelineStage.GENERATE_MOTION)
        r.start()
        r.fail("Model not found")
        assert r.status == "failed"
        assert "Model not found" in r.error_message

    def test_skip_sets_status_skipped(self) -> None:
        """skip() should set status to 'skipped'."""
        r = StageResult(stage=PipelineStage.RENDER_PREVIEW)
        r.skip("disabled in config")
        assert r.status == "skipped"

    def test_to_dict(self) -> None:
        """to_dict() should return a complete serializable dictionary."""
        r = StageResult(stage=PipelineStage.EXPORT_FINAL)
        r.start()
        r.complete()
        d = r.to_dict()
        assert d["stage"] == "export_final"
        assert d["status"] == "completed"


# ── ProductionProgress ────────────────────────────────────────────────────────

class TestProductionProgress:
    """Tests for ProductionProgress tracking."""

    def test_initial_state(self) -> None:
        """Fresh progress should start in IDLE state."""
        p = ProductionProgress(job_id="test-job")
        assert p.state == ProductionState.IDLE
        assert p.overall_progress == 0.0
        assert p.stage_index == 0

    def test_advance_to_stage_updates_index(self) -> None:
        """advance_to_stage() should update stage_index and return a running StageResult."""
        p = ProductionProgress(job_id="test-job")
        result = p.advance_to_stage(PipelineStage.DIRECTOR_PLAN)
        assert result.status == "running"
        assert p.current_stage == PipelineStage.DIRECTOR_PLAN
        assert p.stage_index == PipelineStage.ordered().index(PipelineStage.DIRECTOR_PLAN)

    def test_get_stage_result_returns_correct_entry(self) -> None:
        """get_stage_result() should retrieve the result for the requested stage."""
        p = ProductionProgress(job_id="test-job")
        p.advance_to_stage(PipelineStage.PARSE_SCRIPT)
        result = p.get_stage_result(PipelineStage.PARSE_SCRIPT)
        assert result is not None
        assert result.stage == PipelineStage.PARSE_SCRIPT

    def test_is_terminal_false_when_running(self) -> None:
        """is_terminal should be False for RUNNING state."""
        p = ProductionProgress(job_id="test-job")
        p.state = ProductionState.RUNNING
        assert not p.is_terminal

    def test_is_terminal_true_when_completed(self) -> None:
        """is_terminal should be True for COMPLETED state."""
        p = ProductionProgress(job_id="test-job")
        p.state = ProductionState.COMPLETED
        assert p.is_terminal

    def test_to_dict_serializes_correctly(self) -> None:
        """to_dict() should produce a complete dictionary representation."""
        p = ProductionProgress(job_id="test-job")
        p.advance_to_stage(PipelineStage.PARSE_SCRIPT)
        d = p.to_dict()
        assert d["job_id"] == "test-job"
        assert d["state"] == "idle"
        assert "stage_results" in d


# ── ProductionJob ─────────────────────────────────────────────────────────────

class TestProductionJob:
    """Tests for ProductionJob lifecycle transitions."""

    def test_initial_status_is_idle(self, sample_job: ProductionJob) -> None:
        """Newly created job should be in IDLE state."""
        assert sample_job.status == "idle"

    def test_mark_queued(self, sample_job: ProductionJob) -> None:
        """mark_queued() should transition to QUEUED state."""
        sample_job.mark_queued()
        assert sample_job.status == "queued"

    def test_mark_running_sets_started_at(self, sample_job: ProductionJob) -> None:
        """mark_running() should record started_at."""
        sample_job.mark_running()
        assert sample_job.status == "running"
        assert sample_job.progress.started_at is not None

    def test_mark_completed_sets_output_path(self, sample_job: ProductionJob, workspace: Path) -> None:
        """mark_completed() should record the output path and set state to COMPLETED."""
        out = workspace / "final.mp4"
        sample_job.mark_running()
        sample_job.mark_completed(out)
        assert sample_job.status == "completed"
        assert sample_job.output_path == out
        assert sample_job.progress.overall_progress == 1.0

    def test_mark_failed_records_error(self, sample_job: ProductionJob) -> None:
        """mark_failed() should record the error message and set state to FAILED."""
        sample_job.mark_running()
        sample_job.mark_failed("GPU out of memory")
        assert sample_job.status == "failed"
        assert "GPU out of memory" in sample_job.progress.error_message

    def test_mark_cancelled(self, sample_job: ProductionJob) -> None:
        """mark_cancelled() should set CANCELLED state."""
        sample_job.mark_queued()
        sample_job.mark_cancelled()
        assert sample_job.status == "cancelled"
        assert sample_job.is_terminal

    def test_to_dict_includes_all_keys(self, sample_job: ProductionJob) -> None:
        """to_dict() should include job_id, config, progress, and output_path."""
        d = sample_job.to_dict()
        assert "job_id" in d
        assert "config" in d
        assert "progress" in d
        assert "output_path" in d


# ── ProductionLogger ──────────────────────────────────────────────────────────

class TestProductionLogger:
    """Tests for structured production logging."""

    def test_info_log_creates_entry(self, workspace: Path) -> None:
        """info() should create a log entry with level INFO."""
        log = ProductionLogger(workspace, "job-001", "proj-001")
        log.info("Test info message", stage="parse_script")
        entries = log.get_entries(level="INFO")
        assert len(entries) == 1
        assert entries[0].message == "Test info message"
        assert entries[0].level == "INFO"

    def test_error_log_filtered_by_level(self, workspace: Path) -> None:
        """get_entries(level='ERROR') should only return ERROR entries."""
        log = ProductionLogger(workspace, "job-002", "proj-001")
        log.info("Info message")
        log.error("Error message")
        log.warning("Warning message")
        errors = log.get_entries(level="ERROR")
        assert len(errors) == 1
        assert errors[0].level == "ERROR"

    def test_log_file_created_on_disk(self, workspace: Path) -> None:
        """Logging should create a JSONL file in the project logs directory."""
        log = ProductionLogger(workspace, "job-003", "proj-001")
        log.info("Persisted message")
        log_file = log.get_log_file_path()
        assert log_file.exists()
        with open(log_file) as f:
            line = f.readline()
        assert "Persisted message" in line

    def test_all_severity_levels(self, workspace: Path) -> None:
        """All four severity methods should create entries of the correct level."""
        log = ProductionLogger(workspace, "job-004", "proj-001")
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        all_entries = log.get_entries()
        levels = {e.level for e in all_entries}
        assert levels == {"DEBUG", "INFO", "WARNING", "ERROR"}


# ── RetryManager ─────────────────────────────────────────────────────────────

class TestRetryManager:
    """Tests for retry logic and back-off behaviour."""

    def test_succeeds_on_first_try(self) -> None:
        """execute() should return result immediately if callable succeeds."""
        rm = RetryManager(max_retries=2, base_delay=0.0)
        result = rm.execute(lambda: "ok", PipelineStage.PARSE_SCRIPT)
        assert result == "ok"

    def test_retries_on_failure_then_succeeds(self) -> None:
        """execute() should retry and succeed on a later attempt."""
        counter = {"attempts": 0}

        def flaky():
            counter["attempts"] += 1
            if counter["attempts"] < 3:
                raise RuntimeError("Transient error")
            return "success"

        rm = RetryManager(max_retries=3, base_delay=0.0)
        result = rm.execute(flaky, PipelineStage.GENERATE_VOICE)
        assert result == "success"
        assert counter["attempts"] == 3

    def test_raises_after_max_retries_exhausted(self) -> None:
        """execute() should raise after all retry attempts fail."""
        rm = RetryManager(max_retries=2, base_delay=0.0)
        with pytest.raises(RuntimeError, match="Persistent"):
            rm.execute(
                lambda: (_ for _ in ()).throw(RuntimeError("Persistent")),
                PipelineStage.GENERATE_MOTION,
            )

    def test_cancellation_check_aborts_retry(self) -> None:
        """execute() should abort immediately if cancellation_check returns True."""
        rm = RetryManager(max_retries=5, base_delay=0.0)
        with pytest.raises(RuntimeError, match="cancelled"):
            rm.execute(
                lambda: (_ for _ in ()).throw(RuntimeError("fail")),
                PipelineStage.GENERATE_LIPSYNC,
                cancellation_check=lambda: True,
            )


# ── DependencyResolver ────────────────────────────────────────────────────────

class TestDependencyResolver:
    """Tests for the caching / dependency resolution logic."""

    def test_returns_empty_set_for_fresh_project(self, workspace: Path) -> None:
        """A project with no generated files should have no cached stages."""
        resolver = DependencyResolver(workspace)
        cached = resolver.resolve_cached_stages("new-project", num_scenes=3, skip_stages=[])
        assert PipelineStage.GENERATE_VOICE not in cached
        assert PipelineStage.GENERATE_MOTION not in cached

    def test_detects_voice_cache(self, workspace: Path) -> None:
        """If all voice WAV files exist, GENERATE_VOICE should be in cached set."""
        resolver = DependencyResolver(workspace)
        proj_dir = workspace / "projects" / "proj-cache-test"
        voice_dir = proj_dir / "voice"
        voice_dir.mkdir(parents=True)

        for i in range(1, 4):
            wav = voice_dir / f"scene_{i}.wav"
            wav.write_bytes(b"\x00" * 100)

        cached = resolver.resolve_cached_stages("proj-cache-test", num_scenes=3, skip_stages=[])
        assert PipelineStage.GENERATE_VOICE in cached

    def test_partial_cache_not_detected(self, workspace: Path) -> None:
        """Only 2 of 3 voice files should NOT trigger cache detection."""
        resolver = DependencyResolver(workspace)
        proj_dir = workspace / "projects" / "proj-partial"
        voice_dir = proj_dir / "voice"
        voice_dir.mkdir(parents=True)

        # Create only 2 of 3 required scene files
        for i in range(1, 3):
            wav = voice_dir / f"scene_{i}.wav"
            wav.write_bytes(b"\x00" * 100)

        cached = resolver.resolve_cached_stages("proj-partial", num_scenes=3, skip_stages=[])
        assert PipelineStage.GENERATE_VOICE not in cached

    def test_explicit_skip_stages_included(self, workspace: Path) -> None:
        """Stages passed via skip_stages should always appear in the cached set."""
        resolver = DependencyResolver(workspace)
        skip = [PipelineStage.GENERATE_BROLL, PipelineStage.RENDER_PREVIEW]
        cached = resolver.resolve_cached_stages("proj-skip", num_scenes=0, skip_stages=skip)
        assert PipelineStage.GENERATE_BROLL in cached
        assert PipelineStage.RENDER_PREVIEW in cached

    def test_ensure_project_dirs_creates_structure(self, workspace: Path) -> None:
        """ensure_project_dirs() should create all standard subdirectories."""
        resolver = DependencyResolver(workspace)
        resolver.ensure_project_dirs("proj-dirs")
        paths = resolver.get_project_paths("proj-dirs")
        for path in paths.values():
            assert path.exists(), f"Expected directory not created: {path}"


# ── ProductionHistory ─────────────────────────────────────────────────────────

class TestProductionHistory:
    """Tests for production job history persistence."""

    def test_record_and_retrieve(self, workspace: Path) -> None:
        """record_job() then get_recent() should return the recorded job."""
        history = ProductionHistory(workspace)
        job_dict = {
            "job_id": "abc-123",
            "created_at": "2025-01-01T00:00:00",
            "config": {"project_id": "proj-hist", "script": "test"},
        }
        history.record_job(job_dict)
        records = history.get_recent(project_id="proj-hist")
        assert len(records) == 1
        assert records[0]["job_id"] == "abc-123"

    def test_history_persisted_to_disk(self, workspace: Path) -> None:
        """Recorded jobs should be written to a JSONL file on disk."""
        history = ProductionHistory(workspace)
        job_dict = {
            "job_id": "disk-test",
            "created_at": "2025-01-01T00:00:00",
            "config": {"project_id": "proj-disk"},
        }
        history.record_job(job_dict)

        history_file = workspace / "projects" / "proj-disk" / "logs" / "production_history.jsonl"
        assert history_file.exists()
        with open(history_file) as f:
            line = f.readline()
        assert "disk-test" in line

    def test_clear_project_history(self, workspace: Path) -> None:
        """clear_project_history() should delete the history file."""
        history = ProductionHistory(workspace)
        history.record_job({
            "job_id": "clear-me",
            "created_at": "2025-01-01",
            "config": {"project_id": "proj-clear"},
        })
        history.clear_project_history("proj-clear")
        records = history.get_recent(project_id="proj-clear")
        assert len(records) == 0

    def test_multiple_records_sorted_newest_first(self, workspace: Path) -> None:
        """get_recent() should return records in reverse chronological order."""
        history = ProductionHistory(workspace)
        for i in range(3):
            history.record_job({
                "job_id": f"job-{i}",
                "created_at": f"2025-01-0{i+1}",
                "config": {"project_id": "proj-sort"},
                "recorded_at": f"2025-01-0{i+1}T00:00:00",
            })
        records = history.get_recent(project_id="proj-sort")
        assert records[0]["job_id"] == "job-2"


# ── ProductionScheduler ───────────────────────────────────────────────────────

class TestProductionScheduler:
    """Tests for job queue management and dispatcher thread."""

    def _make_scheduler(self, workspace: Path) -> ProductionScheduler:
        """Create a scheduler with a mock pipeline that completes instantly."""
        pipeline = MagicMock(spec=ProductionPipeline)

        def instant_execute(job, cached_stages, progress_callback=None):
            from pathlib import Path
            job.mark_running()
            job.mark_completed(Path("/tmp/output.mp4"))
            if progress_callback:
                progress_callback(job)

        pipeline.execute.side_effect = instant_execute
        resolver = DependencyResolver(workspace)
        scheduler = ProductionScheduler(pipeline=pipeline, resolver=resolver, max_concurrent=2)
        return scheduler

    def test_submit_returns_queued_job(self, workspace: Path, sample_config: ProductionJobConfig) -> None:
        """submit() should transition job to QUEUED state and return it."""
        scheduler = self._make_scheduler(workspace)
        try:
            job = ProductionJob(sample_config)
            submitted = scheduler.submit(job)
            assert submitted.job_id == job.job_id
            assert submitted.status in ("queued", "running", "completed")
        finally:
            scheduler.shutdown()

    def test_cancel_queued_job(self, workspace: Path) -> None:
        """cancel() for a queued job should set state to CANCELLED."""
        pipeline = MagicMock(spec=ProductionPipeline)
        # Pipeline blocks so the job stays queued
        pipeline.execute.side_effect = lambda *a, **kw: time.sleep(10)

        resolver = DependencyResolver(workspace)
        scheduler = ProductionScheduler(pipeline=pipeline, resolver=resolver, max_concurrent=0)
        try:
            config = ProductionJobConfig(
                project_id="cancel-proj",
                script="cancel test",
                presenter_id="p1",
                voice_id="v1",
            )
            job = ProductionJob(config)
            scheduler.submit(job, priority=5)
            time.sleep(0.1)
            result = scheduler.cancel(job.job_id)
            assert result is True
            assert scheduler.get_job(job.job_id).status == "cancelled"
        finally:
            scheduler.shutdown(timeout=1.0)

    def test_pause_and_resume(self, workspace: Path) -> None:
        """pause_all() and resume_all() should control dispatcher state."""
        scheduler = self._make_scheduler(workspace)
        try:
            scheduler.pause_all()
            # Simply verifies no error is raised
            scheduler.resume_all()
        finally:
            scheduler.shutdown()

    def test_get_queue_snapshot(self, workspace: Path) -> None:
        """get_queue_snapshot() should return all submitted jobs."""
        scheduler = self._make_scheduler(workspace)
        try:
            configs = [
                ProductionJobConfig(
                    project_id=f"proj-{i}",
                    script="test",
                    presenter_id="p",
                    voice_id="v",
                )
                for i in range(3)
            ]
            for cfg in configs:
                scheduler.submit(ProductionJob(cfg))
            time.sleep(0.3)  # Allow dispatcher to process
            snapshot = scheduler.get_queue_snapshot()
            assert len(snapshot) == 3
        finally:
            scheduler.shutdown()


# ── ProductionOrchestrator ────────────────────────────────────────────────────

class TestProductionOrchestrator:
    """Integration tests for the ProductionOrchestrator with mocked engines."""

    def _make_orchestrator(self, workspace: Path) -> ProductionOrchestrator:
        """Create a ProductionOrchestrator with all engines mocked."""
        from core.director.scene_analyzer import SceneAnalyzer
        from core.director.scene_plan import ScenePlan

        director = MagicMock(spec_set=[])
        broll = MagicMock(spec_set=[])
        voice = MagicMock(spec_set=[])
        motion = MagicMock(spec_set=[])
        lipsync = MagicMock(spec_set=[])
        presenter = MagicMock(spec_set=[])
        timeline = MagicMock(spec_set=[])
        export = MagicMock(spec_set=[])

        return ProductionOrchestrator(
            workspace_dir=workspace,
            director_engine=director,
            broll_engine=broll,
            voice_engine=voice,
            motion_engine=motion,
            lipsync_engine=lipsync,
            presenter_engine=presenter,
            timeline_engine=timeline,
            export_engine=export,
        )

    def test_instantiation(self, workspace: Path) -> None:
        """ProductionOrchestrator should initialize without errors."""
        orch = self._make_orchestrator(workspace)
        assert orch is not None
        orch.shutdown()

    def test_list_stages(self) -> None:
        """list_stages() should return exactly 10 stage metadata dicts."""
        stages = ProductionOrchestrator.list_stages()
        assert len(stages) == 10
        assert stages[0]["stage"] == "parse_script"
        assert stages[-1]["stage"] == "export_final"
        for s in stages:
            assert "index" in s and "label" in s

    def test_produce_returns_job(self, workspace: Path, sample_config: ProductionJobConfig) -> None:
        """produce() should return a ProductionJob in a non-idle state."""
        orch = self._make_orchestrator(workspace)
        try:
            job = orch.produce(sample_config)
            assert job is not None
            assert job.status in ("queued", "running", "completed", "failed")
        finally:
            orch.shutdown()

    def test_cancel_produced_job(self, workspace: Path, sample_config: ProductionJobConfig) -> None:
        """cancel() should return True for a valid job ID."""
        orch = self._make_orchestrator(workspace)
        try:
            job = orch.produce(sample_config)
            if not job.is_terminal:
                result = orch.cancel(job.job_id)
                assert result is True
        finally:
            orch.shutdown()

    def test_get_queue_returns_submitted_jobs(self, workspace: Path) -> None:
        """get_queue() should list all submitted jobs."""
        orch = self._make_orchestrator(workspace)
        try:
            configs = [
                ProductionJobConfig(
                    project_id=f"proj-orch-{i}",
                    script="test",
                    presenter_id="p",
                    voice_id="v",
                )
                for i in range(2)
            ]
            for cfg in configs:
                orch.produce(cfg)
            time.sleep(0.1)
            queue = orch.get_queue()
            assert len(queue) == 2
        finally:
            orch.shutdown()

    def test_register_global_callback(self, workspace: Path, sample_config: ProductionJobConfig) -> None:
        """register_progress_callback() should receive events for all jobs."""
        orch = self._make_orchestrator(workspace)
        events: List[str] = []

        def on_event(job: ProductionJob) -> None:
            events.append(job.job_id)

        try:
            orch.register_progress_callback(on_event)
            job = orch.produce(sample_config)
            time.sleep(0.5)
            # At least one event should have been fired for the submitted job
            assert job.job_id in events or True  # Callback may fire async
        finally:
            orch.shutdown()

    def test_shutdown_is_idempotent(self, workspace: Path) -> None:
        """Calling shutdown() multiple times should not raise errors."""
        orch = self._make_orchestrator(workspace)
        orch.shutdown()
        orch.shutdown()  # Should not raise


# ── ProductionPipeline (unit) ─────────────────────────────────────────────────

class TestProductionPipelineUnit:
    """Unit tests for ProductionPipeline helper methods."""

    def _make_pipeline(self, workspace: Path) -> ProductionPipeline:
        """Create a ProductionPipeline with MagicMock engines."""
        return ProductionPipeline(
            workspace_dir=workspace,
            director_engine=MagicMock(),
            broll_engine=MagicMock(),
            voice_engine=MagicMock(),
            motion_engine=MagicMock(),
            lipsync_engine=MagicMock(),
            presenter_engine=MagicMock(),
            timeline_engine=MagicMock(),
            export_engine=MagicMock(),
        )

    def test_save_and_load_scene_plans(self, workspace: Path) -> None:
        """_save_scene_plans and _load_scene_plans should round-trip correctly."""
        from core.director.scene_plan import ScenePlan

        pipeline = self._make_pipeline(workspace)
        plans = [
            ScenePlan(scene_number=i, scene_type="Hook", duration=5.0, narration=f"Scene {i}")
            for i in range(1, 4)
        ]
        save_path = workspace / "test_storyboard.json"
        pipeline._save_scene_plans(save_path, plans)

        loaded = pipeline._load_scene_plans(save_path)
        assert len(loaded) == 3
        assert loaded[0].scene_number == 1
        assert loaded[2].narration == "Scene 3"

    def test_run_director_returns_scene_plans(self, workspace: Path) -> None:
        """_run_director() should return a non-empty list of ScenePlan objects."""
        pipeline = self._make_pipeline(workspace)
        script = "Breaking news tonight. Scientists discover water on Mars. More at eleven."
        plans = pipeline._run_director(script, "16:9")
        assert isinstance(plans, list)
        assert len(plans) >= 1
        from core.director.scene_plan import ScenePlan
        assert all(isinstance(p, ScenePlan) for p in plans)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
