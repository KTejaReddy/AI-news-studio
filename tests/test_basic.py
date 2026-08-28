"""Unit tests for verification of AI News Studio manager classes and configuration.
"""

import json
from pathlib import Path
import tempfile
import pytest

from core.managers.config_manager import ConfigManager
from core.managers.logger_manager import LoggerManager
from core.managers.settings_manager import SettingsManager
from core.managers.project_manager import ProjectManager, Project
from core.managers.asset_manager import AssetManager
from core.managers.model_manager import ModelManager
from core.managers.output_manager import OutputManager
from core.managers.history_manager import HistoryManager


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary directory for workspace tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_config_manager(temp_workspace):
    """Test loading, saving, and defaults fallback of ConfigManager."""
    # Write a default config mock file in temp workspace config folder
    config_dir = temp_workspace / "config"
    config_dir.mkdir(parents=True)
    
    default_data = {
        "theme": "dark",
        "language": "en",
        "device_mode": "GPU",
        "output_folder": "test_output",
        "model_folder": "test_models",
        "temp_folder": "test_temp",
        "cache_folder": "test_cache",
        "quality": "High",
        "aspect_ratio": "16:9"
    }
    
    with open(config_dir / "default_config.json", "w", encoding="utf-8") as f:
        json.dump(default_data, f)

    mgr = ConfigManager(workspace_dir=temp_workspace)
    assert mgr.get("theme") == "dark"
    assert mgr.get("language") == "en"
    assert mgr.get("device_mode") == "GPU"
    assert mgr.get("output_folder") == "test_output"

    # Set value
    mgr.set("device_mode", "CPU")
    assert mgr.get("device_mode") == "CPU"

    # Verify write
    assert (config_dir / "config.json").exists()


def test_settings_manager(temp_workspace):
    """Test settings manager wraps config correctly."""
    config_mgr = ConfigManager(workspace_dir=temp_workspace)
    settings = SettingsManager(config_manager=config_mgr)

    # Assert getters
    assert settings.theme == "dark"
    assert settings.device_mode == "GPU"

    # Assert setters
    settings.theme = "light"
    assert settings.theme == "light"
    assert config_mgr.get("theme") == "light"


def test_project_manager(temp_workspace):
    """Test Project creation, listing, loading and deletion."""
    config_mgr = ConfigManager(workspace_dir=temp_workspace)
    pm = ProjectManager(workspace_dir=temp_workspace, config_manager=config_mgr)

    # Create project
    proj = pm.create_project(name="Morning Weather Broadcast", aspect_ratio="9:16")
    assert proj.id is not None
    assert proj.name == "Morning Weather Broadcast"
    assert proj.aspect_ratio == "9:16"
    assert proj.status == "Draft"

    # Listing
    projects = pm.list_projects()
    assert len(projects) == 1
    assert projects[0].id == proj.id

    # Load
    loaded = pm.load_project(proj.id)
    assert loaded is not None
    assert loaded.name == proj.name
    assert loaded.aspect_ratio == proj.aspect_ratio

    # Delete
    success = pm.delete_project(proj.id)
    assert success is True
    assert len(pm.list_projects()) == 0


def test_asset_manager(temp_workspace):
    """Test AssetManager metadata retrieval."""
    am = AssetManager(workspace_dir=temp_workspace)
    presenters = am.get_presenters()
    voices = am.get_voices()

    assert len(presenters) > 0
    assert len(voices) > 0
    assert presenters[0]["name"] == "Marcus (News Anchor)"
    assert voices[0]["name"] == "Rachel (Professional, US)"


def test_model_manager(temp_workspace):
    """Test ModelManager installation verification."""
    config_mgr = ConfigManager(workspace_dir=temp_workspace)
    mm = ModelManager(workspace_dir=temp_workspace, config_manager=config_mgr)

    # Initial check (nothing installed)
    status_list = mm.get_model_status()
    for m in status_list:
        assert m["installed"] is False

    # Install simulated model weights
    success = mm.install_mock_model(model_id="model_voice_tts")
    assert success is True

    # Re-check status list
    updated_list = mm.get_model_status()
    tts_model = next(m for m in updated_list if m["id"] == "model_voice_tts")
    assert tts_model["installed"] is True
    assert tts_model["path"] is not None

    # Cleanup remove
    success_remove = mm.remove_model(model_id="model_voice_tts")
    assert success_remove is True
    assert mm.get_model_status()[0]["installed"] is False


def test_history_manager(temp_workspace):
    """Test history recording entries."""
    hm = HistoryManager(workspace_dir=temp_workspace)
    assert len(hm.get_entries()) == 0

    hm.add_entry(project_id="proj_1", project_name="Studio Test", status="Success", details="Render finished.")
    entries = hm.get_entries()
    assert len(entries) == 1
    assert entries[0]["project_id"] == "proj_1"
    assert entries[0]["status"] == "Success"

    hm.clear_history()
    assert len(hm.get_entries()) == 0
