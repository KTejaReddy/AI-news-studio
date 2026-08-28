"""Unit tests for the B-Roll Engine module.
"""

import json
from pathlib import Path
import tempfile
import time
import pytest

from core.director.scene_plan import ScenePlan
from core.broll.scene_asset import SceneAsset
from core.broll.prompt_builder import PromptBuilder
from core.broll.broll_config import BrollConfig
from core.broll.broll_job import BrollJob
from core.broll.asset_library import AssetLibrary
from core.broll.asset_cache import AssetCache
from core.broll.asset_downloader import AssetDownloader
from core.broll.asset_generator import AssetGenerator
from core.broll.asset_worker import AssetWorker
from core.broll.asset_controller import AssetController
from core.broll.broll_engine import BrollEngine
from core.broll.providers.provider_manager import ProviderManager
from core.broll.providers.mock_providers import GeminiFlowProvider


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_scene_asset_serialization():
    """Test SceneAsset to/from dictionary conversion."""
    asset = SceneAsset(
        scene_id="scene_1",
        prompt="Cinematic view of futuristic city",
        provider="Gemini Flow",
        file_path="assets/broll/generated/scene_1.mp4",
        asset_type="Video",
        duration=4.5,
        resolution="1920x1080",
        fps=30,
        aspect_ratio="16:9",
        thumbnail_path="assets/broll/thumbnails/scene_1.png",
        tags=["futuristic", "city"],
        status="completed"
    )

    d = asset.to_dict()
    assert d["scene_id"] == "scene_1"
    assert d["provider"] == "Gemini Flow"
    assert d["duration"] == 4.5
    assert d["tags"] == ["futuristic", "city"]

    loaded = SceneAsset.from_dict(d)
    assert loaded.asset_id == asset.asset_id
    assert loaded.scene_id == "scene_1"
    assert loaded.provider == "Gemini Flow"
    assert loaded.duration == 4.5
    assert loaded.tags == ["futuristic", "city"]


def test_prompt_builder():
    """Test PromptBuilder generates custom descriptions and asset type classification."""
    s1 = ScenePlan(
        scene_number=1,
        scene_type="Statistic",
        duration=5.0,
        narration="Here is a chart displaying 75% increase in user retention.",
        broll_keywords="user retention chart",
        emotion="Neutral"
    )
    prompt1, asset_type1 = PromptBuilder.build_prompt_and_type(s1)
    assert asset_type1 == "Motion Graphic"
    assert "infographic animation" in prompt1

    s2 = ScenePlan(
        scene_number=2,
        scene_type="Quote",
        duration=4.0,
        narration="To be or not to be.",
        broll_keywords="shakespeare writing quill",
        emotion="Dramatic"
    )
    prompt2, asset_type2 = PromptBuilder.build_prompt_and_type(s2)
    assert asset_type2 == "Image"
    assert "Fine-art photography" in prompt2

    s3 = ScenePlan(
        scene_number=3,
        scene_type="Intro",
        duration=6.0,
        narration="Hello everyone!",
        broll_keywords="waving hand hello",
        emotion="Friendly"
    )
    prompt3, asset_type3 = PromptBuilder.build_prompt_and_type(s3)
    assert asset_type3 == "Video"
    assert "Cinematic footage" in prompt3


def test_provider_manager():
    """Test ProviderManager registering and selection."""
    pm = ProviderManager()
    providers = pm.list_providers()
    assert "Gemini Flow" in providers
    assert "Veo" in providers
    assert "Local ComfyUI" in providers

    assert pm.active_provider_name == "Gemini Flow"
    assert pm.get_active_provider() is not None
    assert pm.get_active_provider().get_name() == "Gemini Flow"

    pm.set_active_provider("Veo")
    assert pm.active_provider_name == "Veo"
    assert pm.get_active_provider().get_name() == "Veo"


def test_asset_cache(temp_workspace):
    """Test AssetCache writes indexing files and resolves query hits."""
    cache = AssetCache(temp_workspace)
    assert cache.cache_index_file.exists() or not cache.cache_registry

    # Create dummy file to cache
    dummy_file = temp_workspace / "dummy_asset.mp4"
    dummy_file.write_text("dummy visual data")

    # Add to cache
    cached_path = cache.add_to_cache(
        prompt="A cute cat playing yarn",
        provider="Veo",
        aspect_ratio="16:9",
        duration=3.0,
        source_file=dummy_file
    )
    assert cached_path.exists()
    assert cached_path.parent == cache.cache_dir

    # Retrieve from cache
    retrieved = cache.get_cached_asset_path(
        prompt="A cute cat playing yarn",
        provider="Veo",
        aspect_ratio="16:9",
        duration=3.0
    )
    assert retrieved is not None
    assert retrieved.resolve() == cached_path.resolve()

    # Clear cache
    cache.clear_cache()
    assert len(cache.cache_registry) == 0
    assert not cached_path.exists()


def test_asset_library_imports(temp_workspace):
    """Test AssetLibrary saves database and copies local media files."""
    library = AssetLibrary(temp_workspace)
    assert library.library_file.parent.exists()

    # Create local file to import
    local_img = temp_workspace / "local_screenshot.png"
    # Create simple PIL image
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    img.save(local_img)

    asset = library.import_local_asset(
        source_path=local_img,
        scene_id="12",
        prompt="User UI screenshot",
        provider="Local Import",
        asset_type="Image",
        duration=0.0
    )

    assert asset.asset_id is not None
    assert asset.scene_id == "12"
    assert asset.asset_type == "Image"
    assert Path(temp_workspace / asset.file_path).exists()
    assert Path(temp_workspace / asset.thumbnail_path).exists()

    # Verify database reload
    library2 = AssetLibrary(temp_workspace)
    assert asset.asset_id in library2.assets
    assert library2.assets[asset.asset_id].prompt == "User UI screenshot"

    # Remove asset
    success = library.remove_asset(asset.asset_id)
    assert success is True
    assert not Path(temp_workspace / asset.file_path).exists()
    assert not Path(temp_workspace / asset.thumbnail_path).exists()
    assert asset.asset_id not in library.assets


def test_broll_engine_sync(temp_workspace):
    """Test BrollEngine synchronous blocking visual generation."""
    engine = BrollEngine(temp_workspace)
    
    output_path = temp_workspace / "scene_output.mp4"
    generated_path = engine.generate_broll_clip(
        prompt="A professional office backdrop",
        duration_seconds=2.0,
        output_path=output_path,
        aspect_ratio="16:9",
        fps=10
    )

    assert generated_path.exists()
    assert generated_path.resolve() == output_path.resolve()
    # Confirm thumbnail generated under assets
    assets = engine.library.list_assets()
    assert len(assets) > 0


def test_broll_engine_async_storyboard(temp_workspace):
    """Test BrollEngine async storyboard submissions and monitoring."""
    engine = BrollEngine(temp_workspace)
    
    s1 = ScenePlan(scene_number=1, scene_type="Hook", duration=1.0, narration="Narrating intro.")
    s2 = ScenePlan(scene_number=2, scene_type="Statistic", duration=1.0, narration="Narrating stats.")
    
    jobs = engine.generate_storyboard_broll(
        scene_plans=[s1, s2],
        aspect_ratio="16:9",
        fps=10,
        provider="Gemini Flow"
    )

    assert len(jobs) == 2
    job1, job2 = jobs[0], jobs[1]

    # Wait for completion of both jobs
    timeout = 10.0
    start_time = time.time()
    while True:
        if job1.status in ["completed", "failed"] and job2.status in ["completed", "failed"]:
            break
        if time.time() - start_time > timeout:
            pytest.fail("Jobs timed out.")
        time.sleep(0.1)

    assert job1.status == "completed"
    assert job2.status == "completed"
    assert job1.output_path is not None
    assert job2.output_path is not None
    assert Path(temp_workspace / job1.output_path).exists()
