"""Tests for bellbird.core.config — strict TDD, wx-free.

Covers: missing file defaults, save+load round-trip, unknown key filtering,
per-instance list default, path location, legacy migration. All use
monkeypatch for CONFIG_PATH isolation.
"""

import importlib
import json
import os

import pytest

from bellbird.core.config import BellbirdConfig, load_config, save_config


def test_load_config_returns_defaults_on_missing_file(monkeypatch, tmp_path):
    """GIVEN CONFIG_PATH is a non-existent path
    WHEN load_config() is called
    THEN return BellbirdConfig() with no exception."""
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "nope.json")
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", tmp_path / "no_legacy.json")
    result = load_config()
    assert result == BellbirdConfig()


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    """GIVEN a BellbirdConfig with non-default values
    WHEN save_config then load_config
    THEN the loaded config equals the original."""
    cfg = BellbirdConfig(
        port=9090,
        ctx_size=8192,
        extra_model_folders=["D:\\llms"],
    )
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded == cfg


def test_load_config_ignores_unknown_keys(monkeypatch, tmp_path):
    """GIVEN a JSON file with extra unknown keys
    WHEN load_config() is called
    THEN known fields are loaded and unknown keys are silently dropped."""
    path = tmp_path / "config.json"
    data = {
        "port": 9090,
        "future_field": "x",
        "temperature": 0.5,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.port == 9090
    assert result.temperature == 0.5
    assert result.max_tokens == 4096


def test_config_path_is_under_user_data_dir(monkeypatch, tmp_path):
    """GIVEN platformdirs.user_data_dir is monkeypatched to <tmp_path>/Bellbird
    WHEN bellbird.core.config is reloaded
    THEN CONFIG_PATH equals <tmp_path>/Bellbird/config.json
    AND does not contain bellbird/data."""
    import platformdirs

    monkeypatch.setattr(
        platformdirs,
        "user_data_dir",
        lambda app, appauthor: str(tmp_path / app),
    )
    from bellbird.core import config as config_module

    importlib.reload(config_module)

    expected = tmp_path / "Bellbird" / "config.json"
    assert config_module.CONFIG_PATH == expected
    assert "bellbird/data" not in str(config_module.CONFIG_PATH)
    assert "config.json" in str(config_module.CONFIG_PATH)


def test_migrate_legacy_legacy_exists_copies(monkeypatch, tmp_path):
    """GIVEN legacy config exists and new config does NOT
    WHEN migrate_legacy_config() runs
    THEN the new file is created with the legacy content
    AND the legacy file is NOT deleted."""
    import json

    from bellbird.core import config as config_module

    legacy = tmp_path / "data" / "config.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"temperature": 0.42}), encoding="utf-8")

    new_dir = tmp_path / "Bellbird"
    new_config = new_dir / "config.json"
    assert not new_config.exists()

    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy)
    monkeypatch.setattr(config_module, "CONFIG_PATH", new_config)

    config_module.migrate_legacy_config()

    assert new_config.exists()
    content = json.loads(new_config.read_text(encoding="utf-8"))
    assert content["temperature"] == 0.42
    assert legacy.exists()


def test_migrate_legacy_new_exists_no_overwrite(monkeypatch, tmp_path):
    """GIVEN both legacy and new config exist
    WHEN migrate_legacy_config() runs
    THEN new file is NOT overwritten."""
    import json

    from bellbird.core import config as config_module

    legacy = tmp_path / "data" / "config.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"temperature": 0.42}), encoding="utf-8")

    new_dir = tmp_path / "Bellbird"
    new_dir.mkdir(parents=True, exist_ok=True)
    new_config = new_dir / "config.json"
    new_config.write_text(json.dumps({"temperature": 0.99}), encoding="utf-8")

    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy)
    monkeypatch.setattr(config_module, "CONFIG_PATH", new_config)

    config_module.migrate_legacy_config()

    content = json.loads(new_config.read_text(encoding="utf-8"))
    assert content["temperature"] == 0.99


def test_migrate_legacy_legacy_missing_noop(monkeypatch, tmp_path):
    """GIVEN legacy config does NOT exist
    WHEN migrate_legacy_config() runs
    THEN no exception is raised and no new file is created."""
    from bellbird.core import config as config_module

    new_dir = tmp_path / "Bellbird"
    new_config = new_dir / "config.json"
    assert not new_config.exists()

    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", tmp_path / "nope.json")
    monkeypatch.setattr(config_module, "CONFIG_PATH", new_config)

    config_module.migrate_legacy_config()

    assert not new_config.exists()


def test_migrate_legacy_copy_raises_swallowed(monkeypatch, tmp_path):
    """GIVEN legacy exists but shutil.copy2 raises
    WHEN migrate_legacy_config() runs
    THEN no exception propagates (best-effort)."""
    from bellbird.core import config as config_module

    legacy = tmp_path / "data" / "config.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("{}", encoding="utf-8")

    new_dir = tmp_path / "Bellbird"
    new_config = new_dir / "config.json"

    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", legacy)
    monkeypatch.setattr(config_module, "CONFIG_PATH", new_config)

    import shutil

    def failing_copy2(src, dst, **kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr(shutil, "copy2", failing_copy2)

    config_module.migrate_legacy_config()


def test_scalar_field_defaults():
    """All scalar fields have the documented default values."""
    cfg = BellbirdConfig()
    assert cfg.last_model == ""
    assert cfg.request_timeout == 120
    assert cfg.mmproj_offload is True
    assert cfg.min_p == 0.05
    assert cfg.seed == -1
    assert cfg.stop == []
    assert cfg.max_tool_iterations == 5
    assert cfg.url_max_chars == 50000
    assert cfg.restore_last_session is True
    assert cfg.last_session_path == ""
    assert cfg.recent_files == []


def test_extra_model_folders_default_is_empty_list():
    """GIVEN two fresh BellbirdConfig() instances
    WHEN one gets an appended folder
    THEN the other instance still has an empty list."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.extra_model_folders.append("/x")
    assert b.extra_model_folders == []


def test_last_model_persists_on_save_load(monkeypatch, tmp_path):
    """GIVEN last_model='llama-3.gguf'
    WHEN save_config then load_config
    THEN the loaded config has last_model='llama-3.gguf'."""
    cfg = BellbirdConfig(last_model="llama-3.gguf")
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.last_model == "llama-3.gguf"


def test_load_config_applies_max_tokens_migration(monkeypatch, tmp_path):
    """GIVEN a config.json persisted with the legacy max_tokens default (512)
    WHEN load_config() reads it
    THEN _MIGRATIONS bumps max_tokens to 4096 so reasoning models can finish
    their thinking phase before producing output (v0.5.1+ default)."""
    from bellbird.core import config as config_module

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{"max_tokens": 512}', encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", cfg_file)

    result = load_config()

    assert result.max_tokens == 4096


# ── model_mmproj ──────────────────────────────────────────────────────────


def test_model_mmproj_default_is_empty_dict():
    """GIVEN a fresh BellbirdConfig()
    THEN model_mmproj == {} (not shared across instances)."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.model_mmproj["k.gguf"] = "C:\\p.gguf"
    assert b.model_mmproj == {}


def test_model_mmproj_round_trip(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig(model_mmproj={"a.gguf": "C:\\m\\p.gguf"})
    WHEN save_config then load_config
    THEN model_mmproj equals the input dict."""
    cfg = BellbirdConfig(model_mmproj={"a.gguf": "C:\\m\\p.gguf"})
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.model_mmproj == {"a.gguf": "C:\\m\\p.gguf"}


def test_model_mmproj_unknown_key_dropped(monkeypatch, tmp_path):
    """GIVEN JSON with model_mmproj AND a future_field key
    WHEN load_config() reads it
    THEN model_mmproj is loaded and future_field is silently dropped."""
    path = tmp_path / "config.json"
    data = {
        "model_mmproj": {"a.gguf": "C:\\m\\p.gguf"},
        "future_field": "x",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.model_mmproj == {"a.gguf": "C:\\m\\p.gguf"}
    assert not hasattr(result, "future_field")


def test_model_mmproj_basename_lookup():
    """GIVEN model_mmproj key by basename
    WHEN accessing via Path().name
    THEN returns the stored value regardless of parent dir."""
    cfg = BellbirdConfig(model_mmproj={"vl.gguf": "C:\\m\\p.gguf"})
    assert cfg.model_mmproj.get("vl.gguf") == "C:\\m\\p.gguf"
    from pathlib import Path

    key = Path("/other/path/vl.gguf").name
    assert key == "vl.gguf"


def test_get_mmproj_for_missing_key_returns_none(tmp_path):
    """GIVEN model_mmproj has no entry for the given model
    WHEN get_mmproj_for is called
    THEN returns None."""
    cfg = BellbirdConfig(model_mmproj={"other.gguf": str(tmp_path / "p.gguf")})
    result = cfg.get_mmproj_for(tmp_path / "model.gguf")
    assert result is None


def test_get_mmproj_for_missing_file_returns_none(tmp_path):
    """GIVEN model_mmproj has an entry whose file no longer exists
    WHEN get_mmproj_for is called
    THEN returns None."""
    proj = tmp_path / "p.gguf"
    cfg = BellbirdConfig(model_mmproj={"model.gguf": str(proj)})
    result = cfg.get_mmproj_for(tmp_path / "model.gguf")
    assert result is None


def test_get_mmproj_for_valid_entry_returns_resolved_path(tmp_path):
    """GIVEN model_mmproj has a valid entry
    WHEN get_mmproj_for is called
    THEN returns the resolved absolute path."""
    proj = tmp_path / "p.gguf"
    proj.write_text("")
    cfg = BellbirdConfig(model_mmproj={"model.gguf": str(proj)})
    result = cfg.get_mmproj_for(tmp_path / "model.gguf")
    assert result == str(proj.resolve())


# ── request_timeout / mmproj_offload ──────────────────────────────────────


def test_request_timeout_custom_persists(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig(request_timeout=300)
    WHEN save_config then load_config
    THEN request_timeout == 300."""
    cfg = BellbirdConfig(request_timeout=300)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.request_timeout == 300


# ── sampler fields (min_p / seed / stop) ──────────────────────────────────


def test_stop_default_is_per_instance():
    """GIVEN two fresh BellbirdConfig() instances
    WHEN one appends a stop string
    THEN the other instance still has an empty list."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.stop.append("</s>")
    assert b.stop == []


def test_round_trip_with_new_fields(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig with non-default min_p/seed/stop
    WHEN save_config then load_config
    THEN the loaded config preserves all three new fields."""
    cfg = BellbirdConfig(min_p=0.10, seed=42, stop=["</s>", "[/INST]"])
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.min_p == 0.10
    assert loaded.seed == 42
    assert loaded.stop == ["</s>", "[/INST]"]


def test_missing_new_keys_use_defaults(monkeypatch, tmp_path):
    """GIVEN a config.json from v0.7.1 without min_p/seed/stop
    WHEN load_config() runs
    THEN the loaded config has the documented defaults for the new fields."""
    path = tmp_path / "config.json"
    data = {"port": 8080, "temperature": 0.7}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.min_p == 0.05
    assert result.seed == -1
    assert result.stop == []


def test_migrations_dict_unchanged():
    """GIVEN the _MIGRATIONS dict
    THEN it has exactly one entry (max_tokens 512->4096)
    AND no entry references min_p, seed, stop, audio fields, or recent-session fields."""
    from bellbird.core.config import _MIGRATIONS
    assert len(_MIGRATIONS) == 1
    assert "max_tokens" in _MIGRATIONS
    assert _MIGRATIONS["max_tokens"] == (512, 4096)
    assert "min_p" not in _MIGRATIONS
    assert "seed" not in _MIGRATIONS
    assert "stop" not in _MIGRATIONS
    assert "keymap_overrides" not in _MIGRATIONS
    assert "system_voice_name" not in _MIGRATIONS
    assert "restore_last_session" not in _MIGRATIONS
    assert "param_presets" not in _MIGRATIONS
    assert "filter_strip_markdown" not in _MIGRATIONS


def test_mmproj_offload_round_trip_false(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig(mmproj_offload=False)
    WHEN save_config then load_config
    THEN mmproj_offload is False."""
    cfg = BellbirdConfig(mmproj_offload=False)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.mmproj_offload is False


# ── max_tool_iterations (v0.7.5) ──────────────────────────────────────────


# ── keymap_overrides (v0.8.0) ──────────────────────────────────────────


def test_keymap_overrides_default_is_empty_dict():
    """GIVEN a fresh BellbirdConfig()
    THEN keymap_overrides == {} (not shared across instances)."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.keymap_overrides["copy_last"] = (3, 67)
    assert b.keymap_overrides == {}


def test_keymap_overrides_default_on_missing_key(monkeypatch, tmp_path):
    """GIVEN a v0.7.x config.json without keymap_overrides key
    WHEN load_config() runs
    THEN the loaded cfg.keymap_overrides == {}."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 8080}), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.keymap_overrides == {}


def test_keymap_overrides_round_trip(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig with keymap_overrides
    WHEN save_config then load_config
    THEN the loaded cfg.keymap_overrides round-trips to the same shape."""
    cfg = BellbirdConfig(keymap_overrides={"copy_last": (3, 67)})
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    val = loaded.keymap_overrides["copy_last"]
    assert val == (3, 67), f"Expected (3, 67), got {val!r}"


def test_keymap_overrides_unknown_id_does_not_crash(monkeypatch, tmp_path):
    """GIVEN config.json with unknown action id in keymap_overrides
    WHEN load_config() runs
    THEN no KeyError is raised (the drop is Keymap's job)."""
    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"ghost_action": [0, 81]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert "ghost_action" in result.keymap_overrides


def test_keymap_overrides_non_int_falls_back(monkeypatch, tmp_path):
    """GIVEN config.json with string value instead of (int, int) pair
    WHEN load_config() runs
    THEN falls back to defaults (BellbirdConfig(), corrupt-config policy)."""
    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"copy_last": "Ctrl+Shift+C"}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.keymap_overrides == {}


def test_keymap_overrides_non_int_tuple_falls_back(monkeypatch, tmp_path):
    """GIVEN config.json with non-int values inside the list pair
    WHEN load_config() runs
    THEN falls back to defaults."""
    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"copy_last": [1.5, "C"]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.keymap_overrides == {}


def test_keymap_overrides_list_to_tuple_normalisation(monkeypatch, tmp_path):
    """GIVEN config.json with list-of-two-ints for keymap_overrides
    WHEN load_config() runs
    THEN the value is normalised to a tuple of ints."""
    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"copy_last": [1 | 2, 67]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    val = result.keymap_overrides["copy_last"]
    assert isinstance(val, tuple), f"Expected tuple, got {type(val).__name__}"
    assert len(val) == 2
    assert all(isinstance(v, int) for v in val)


# ── url_max_chars (v0.8.3) ────────────────────────────────────────────────


def test_load_config_with_url_max_chars_present(monkeypatch, tmp_path):
    """GIVEN a JSON file containing url_max_chars
    WHEN load_config() is called
    THEN url_max_chars is loaded with the custom value."""
    path = tmp_path / "config.json"
    data = {"url_max_chars": 80000, "port": 8080}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.url_max_chars == 80000


def test_save_config_roundtrip_url_max_chars(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig(url_max_chars=80000)
    WHEN save_config then load_config
    THEN url_max_chars == 80000."""
    cfg = BellbirdConfig(url_max_chars=80000)
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.url_max_chars == 80000


def test_max_tool_iterations_overridable(monkeypatch, tmp_path):
    """GIVEN config JSON with max_tool_iterations: 10
    WHEN load_config()
    THEN max_tool_iterations == 10."""
    path = tmp_path / "config.json"
    data = {"max_tool_iterations": 10}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.max_tool_iterations == 10


# ── restore_last_session / last_session_path / recent_files (v0.8.2) ──────


def test_recent_files_default_is_per_instance():
    """GIVEN two fresh BellbirdConfig() instances
    WHEN one gets an appended file path
    THEN the other instance still has an empty list."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.recent_files.append("/path/a.json")
    assert b.recent_files == []


def test_load_config_with_new_fields_present(monkeypatch, tmp_path):
    """GIVEN a JSON file containing the 3 new fields
    WHEN load_config() is called
    THEN the fields are loaded with the correct values."""
    path = tmp_path / "config.json"
    data = {
        "restore_last_session": False,
        "last_session_path": "/home/user/bellbird/last.json",
        "recent_files": ["/home/user/a.json", "/home/user/b.json"],
        "port": 8080,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.restore_last_session is False
    assert result.last_session_path == "/home/user/bellbird/last.json"
    assert result.recent_files == ["/home/user/a.json", "/home/user/b.json"]


def test_load_config_with_new_fields_missing(monkeypatch, tmp_path):
    """GIVEN a JSON file from v0.8.1 without the 3 new fields
    WHEN load_config() is called on v0.8.2
    THEN the defaults for the new fields are applied."""
    path = tmp_path / "config.json"
    data = {"port": 8080, "temperature": 0.7}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.restore_last_session is True
    assert result.last_session_path == ""
    assert result.recent_files == []


def test_save_config_roundtrip_new_fields(monkeypatch, tmp_path):
    """GIVEN BellbirdConfig with non-default values for the 3 new fields
    WHEN save_config then load_config
    THEN the loaded config preserves all 3 new fields."""
    cfg = BellbirdConfig(
        restore_last_session=False,
        last_session_path="/tmp/session.json",
        recent_files=["/tmp/a.json", "/tmp/b.json"],
    )
    path = tmp_path / "config.json"
    save_config(cfg, path)
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    loaded = load_config()
    assert loaded.restore_last_session is False
    assert loaded.last_session_path == "/tmp/session.json"
    assert loaded.recent_files == ["/tmp/a.json", "/tmp/b.json"]


# ── update_recents / remove_from_recents / should_auto_restore (v0.8.2) ───


def test_update_recents_basic():
    """GIVEN an empty recent_files list
    WHEN update_recents('/p/a.json', [])
    THEN the path is added at the front."""
    from bellbird.core.config import update_recents

    result = update_recents("/p/a.json", [])
    assert result[0] == os.path.abspath("/p/a.json")
    assert len(result) == 1


def test_update_recents_dedup():
    """GIVEN a list with an existing path
    WHEN update_recents with the same path
    THEN the path moves to front, no duplicate."""
    from bellbird.core.config import update_recents

    pa = os.path.abspath("/p/a.json")
    pb = os.path.abspath("/p/b.json")
    pc = os.path.abspath("/p/c.json")
    result = update_recents("/p/a.json", [pb, pa, pc])
    assert result[0] == pa
    assert result.count(pa) == 1
    assert len(result) == 3


def test_update_recents_cap_10():
    """GIVEN 12 paths added in order
    WHEN update_recents for each
    THEN recent_files has at most 10 entries (most recent first)."""
    from bellbird.core.config import update_recents

    recent: list[str] = []
    for i in range(12):
        recent = update_recents(f"/p/file{i}.json", recent)
    assert len(recent) == 10
    assert recent[0] == os.path.abspath("/p/file11.json")
    assert recent[-1] == os.path.abspath("/p/file2.json")


def test_update_recents_mru_order():
    """GIVEN multiple paths added
    WHEN update_recents
    THEN entries are in MRU order (most recent first)."""
    from bellbird.core.config import update_recents

    recent = update_recents("/p/a.json", [])
    recent = update_recents("/p/b.json", recent)
    recent = update_recents("/p/c.json", recent)
    assert recent == [
        os.path.abspath("/p/c.json"),
        os.path.abspath("/p/b.json"),
        os.path.abspath("/p/a.json"),
    ]


def test_update_recents_uses_absolute_paths():
    """GIVEN a relative path
    WHEN update_recents
    THEN the path is stored as absolute."""
    from bellbird.core.config import update_recents

    result = update_recents("relative/path/chat.json", [])
    assert result[0] != "relative/path/chat.json"
    assert os.path.isabs(result[0])


def test_remove_from_recents_present():
    """GIVEN a list with a path
    WHEN remove_from_recents
    THEN the path is removed."""
    from bellbird.core.config import remove_from_recents

    pa = os.path.abspath("/p/a.json")
    pb = os.path.abspath("/p/b.json")
    result = remove_from_recents("/p/a.json", [pa, pb])
    assert pa not in result
    assert result == [pb]


def test_remove_from_recents_absent():
    """GIVEN a list without a path
    WHEN remove_from_recents
    THEN no error, list unchanged."""
    from bellbird.core.config import remove_from_recents

    pa = os.path.abspath("/p/a.json")
    result = remove_from_recents("/p/zzz.json", [pa])
    assert result == [pa]


def test_should_auto_restore_toggle_off(tmp_path):
    """GIVEN restore_last_session=False
    WHEN should_auto_restore
    THEN returns False even if path exists."""
    from bellbird.core.config import should_auto_restore

    file = tmp_path / "session.json"
    file.write_text("{}", encoding="utf-8")
    cfg = BellbirdConfig(restore_last_session=False, last_session_path=str(file))
    assert should_auto_restore(cfg) is False


def test_should_auto_restore_path_empty(tmp_path):
    """GIVEN last_session_path=''
    WHEN should_auto_restore
    THEN returns False."""
    from bellbird.core.config import should_auto_restore

    cfg = BellbirdConfig(restore_last_session=True, last_session_path="")
    assert should_auto_restore(cfg) is False


def test_should_auto_restore_path_missing():
    """GIVEN last_session_path points to non-existent file
    WHEN should_auto_restore
    THEN returns False."""
    from bellbird.core.config import should_auto_restore

    cfg = BellbirdConfig(
        restore_last_session=True, last_session_path="/nonexistent/path.json"
    )
    assert should_auto_restore(cfg) is False


def test_should_auto_restore_ok(tmp_path):
    """GIVEN toggle on AND path exists AND non-empty
    WHEN should_auto_restore
    THEN returns True."""
    from bellbird.core.config import should_auto_restore

    file = tmp_path / "session.json"
    file.write_text("{}", encoding="utf-8")
    cfg = BellbirdConfig(restore_last_session=True, last_session_path=str(file))
    assert should_auto_restore(cfg) is True


# ─── v0.9.0: 4 new fields (T-WU1-12) ────────────────────────────────────────


class TestV090Config:
    """Tests for the 4 new BellbirdConfig fields."""

    def test_safe_vram_mode_default_false(self):
        """GIVEN a fresh BellbirdConfig()
        THEN safe_vram_mode is False."""
        from bellbird.core.config import BellbirdConfig
        cfg = BellbirdConfig()
        assert cfg.safe_vram_mode is False

    def test_status_toggles_default_all_true(self):
        """GIVEN a fresh BellbirdConfig()
        THEN status_toggles has all DEFAULT_STATUS_TOGGLES keys set to True."""
        from bellbird.core.config import BellbirdConfig
        from bellbird.core.status_formatter import DEFAULT_STATUS_TOGGLES

        cfg = BellbirdConfig()
        for name in DEFAULT_STATUS_TOGGLES:
            assert cfg.status_toggles[name] is True, f"toggle {name!r} should be True"

    def test_status_toggles_per_instance(self):
        """GIVEN two fresh BellbirdConfig() instances
        WHEN one instance modifies status_toggles
        THEN the other instance is unchanged."""
        from bellbird.core.config import BellbirdConfig

        a = BellbirdConfig()
        b = BellbirdConfig()
        a.status_toggles["model_name"] = False
        assert b.status_toggles["model_name"] is True

    def test_model_tunings_default_empty_dict(self):
        """GIVEN a fresh BellbirdConfig()
        THEN model_tunings == {}."""
        from bellbird.core.config import BellbirdConfig

        cfg = BellbirdConfig()
        assert cfg.model_tunings == {}

    def test_model_tunings_per_instance(self):
        """GIVEN two fresh BellbirdConfig() instances
        WHEN one sets model_tunings
        THEN the other is empty."""
        from bellbird.core.config import BellbirdConfig

        a = BellbirdConfig()
        b = BellbirdConfig()
        a.model_tunings["phi-3.gguf"] = {"ctx_size": 8192}
        assert b.model_tunings == {}

    def test_pre_send_warn_default_true(self):
        """GIVEN a fresh BellbirdConfig()
        THEN pre_send_warn is True."""
        from bellbird.core.config import BellbirdConfig

        cfg = BellbirdConfig()
        assert cfg.pre_send_warn is True

    def test_4_new_fields_roundtrip(self, monkeypatch, tmp_path):
        """GIVEN BellbirdConfig with all 4 new fields set
        WHEN save then load
        THEN all 4 fields round-trip."""
        from bellbird.core.config import BellbirdConfig, save_config, load_config
        from bellbird.core import config as config_module

        cfg = BellbirdConfig(
            safe_vram_mode=True,
            status_toggles={"model_name": False, "context_pct": True},
            model_tunings={"a.gguf": {"ctx_size": 4096, "n_gpu_layers": 35, "threads": 4}},
            pre_send_warn=False,
        )
        path = tmp_path / "config.json"
        save_config(cfg, path)
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()

        assert loaded.safe_vram_mode is True
        assert loaded.status_toggles["model_name"] is False
        assert loaded.status_toggles["context_pct"] is True
        assert loaded.model_tunings["a.gguf"]["ctx_size"] == 4096
        assert loaded.pre_send_warn is False

    def test_missing_new_keys_from_v083_fallback_to_defaults(self, monkeypatch, tmp_path):
        """GIVEN a v0.8.3 config.json WITHOUT the 4 new fields
        WHEN load_config() runs
        THEN the new fields have their defaults."""
        from bellbird.core import config as config_module
        from bellbird.core.config import load_config

        path = tmp_path / "config.json"
        data = {"port": 8080, "temperature": 0.7}
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()

        assert loaded.safe_vram_mode is False
        assert len(loaded.status_toggles) == 13
        assert loaded.model_tunings == {}
        assert loaded.pre_send_warn is True
        assert loaded.llama_server_path == ""

    def test_status_toggles_as_set_returns_true_keys(self):
        """GIVEN BellbirdConfig with partial toggles
        WHEN status_toggles_as_set() is called
        THEN returns set of True-valued keys."""
        from bellbird.core.config import BellbirdConfig

        cfg = BellbirdConfig(status_toggles={
            "model_name": True, "context_pct": False, "temperature": True,
        })
        result = cfg.status_toggles_as_set()
        assert result == {"model_name", "temperature"}

    def test_status_toggles_as_set_empty_returns_empty_set(self):
        """GIVEN BellbirdConfig with empty status_toggles
        WHEN status_toggles_as_set() is called
        THEN returns empty set (no error)."""
        from bellbird.core.config import BellbirdConfig

        cfg = BellbirdConfig(status_toggles={})
        result = cfg.status_toggles_as_set()
        assert result == set()


# ─── v0.10.0: 6 new audio output fields (T-WU1 T1A) ────────────────────────


class TestV0100AudioConfig:
    """Tests for the 6 new BellbirdConfig audio output fields."""

    def test_audio_field_defaults(self):
        """GIVEN a fresh BellbirdConfig()
        THEN all 6 audio fields have their documented defaults."""
        cfg = BellbirdConfig()
        assert cfg.system_voice_name == ""
        assert cfg.system_voice_rate == 0
        assert cfg.auto_speak_responses is False
        assert cfg.notifications_enabled is True
        assert cfg.sounds_enabled is True
        assert cfg.sound_theme == "default"

    def test_6_new_fields_roundtrip(self, monkeypatch, tmp_path):
        """GIVEN BellbirdConfig with all 6 new fields set to non-default values
        WHEN save then load
        THEN all 6 fields round-trip."""
        from bellbird.core import config as config_module

        cfg = BellbirdConfig(
            system_voice_name="Microsoft Helena",
            system_voice_rate=3,
            auto_speak_responses=True,
            notifications_enabled=False,
            sounds_enabled=False,
            sound_theme="custom",
        )
        path = tmp_path / "config.json"
        save_config(cfg, path)
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()

        assert loaded.system_voice_name == "Microsoft Helena"
        assert loaded.system_voice_rate == 3
        assert loaded.auto_speak_responses is True
        assert loaded.notifications_enabled is False
        assert loaded.sounds_enabled is False
        assert loaded.sound_theme == "custom"

    def test_missing_new_keys_from_v090_fallback_to_defaults(self, monkeypatch, tmp_path):
        """GIVEN a v0.9.0 config.json WITHOUT the 6 new fields
        WHEN load_config() runs
        THEN the new fields have their documented defaults."""
        from bellbird.core import config as config_module

        path = tmp_path / "config.json"
        data = {"port": 8080, "temperature": 0.7}
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()

        assert loaded.system_voice_name == ""
        assert loaded.system_voice_rate == 0
        assert loaded.auto_speak_responses is False
        assert loaded.notifications_enabled is True
        assert loaded.sounds_enabled is True
        assert loaded.sound_theme == "default"


# ─── v0.11.0: 5 new fields (param_presets + 4 filter_strip_*) ───────────────


class TestV0110Config:
    """Tests for the 5 new BellbirdConfig fields (v0.11.0)."""

    def test_filter_strip_defaults(self):
        """GIVEN a fresh BellbirdConfig()
        THEN all 4 filter_strip fields default to True."""
        cfg = BellbirdConfig()
        assert cfg.filter_strip_markdown is True
        assert cfg.filter_strip_urls is True
        assert cfg.filter_strip_emojis is True
        assert cfg.filter_strip_code_blocks is True

    def test_param_presets_default_empty(self):
        """GIVEN a fresh BellbirdConfig()
        THEN param_presets == [] (per-instance default)."""
        cfg = BellbirdConfig()
        assert cfg.param_presets == []

    def test_param_presets_per_instance(self):
        """GIVEN two fresh BellbirdConfig() instances
        WHEN one gets a preset appended
        THEN the other's param_presets is still empty."""
        a = BellbirdConfig()
        b = BellbirdConfig()
        from bellbird.core.preset import ParamPreset
        a.param_presets.append(ParamPreset(name="x", temperature=0.7))
        assert b.param_presets == []

    def test_v0110_filter_toggles_round_trip(self, monkeypatch, tmp_path):
        """GIVEN BellbirdConfig with all 4 filter toggles set
        WHEN save then load
        THEN all 4 toggles round-trip."""
        from bellbird.core import config as config_module

        cfg = BellbirdConfig(
            filter_strip_markdown=False,
            filter_strip_urls=True,
            filter_strip_emojis=False,
            filter_strip_code_blocks=True,
        )
        path = tmp_path / "config.json"
        save_config(cfg, path)
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()
        assert loaded.filter_strip_markdown is False
        assert loaded.filter_strip_urls is True
        assert loaded.filter_strip_emojis is False
        assert loaded.filter_strip_code_blocks is True

    def test_v0110_param_presets_round_trip(self, monkeypatch, tmp_path):
        """GIVEN BellbirdConfig with a ParamPreset list
        WHEN save then load
        THEN the param_presets list round-trips as a list of ParamPreset."""
        from bellbird.core import config as config_module
        from bellbird.core.preset import ParamPreset

        cfg = BellbirdConfig(
            param_presets=[
                ParamPreset(
                    name="creativo",
                    temperature=1.10,
                    min_p=0.08,
                    max_tokens=2048,
                    top_p=0.95,
                    top_k=50,
                    repeat_penalty=1.05,
                    seed=42,
                ),
            ],
        )
        path = tmp_path / "config.json"
        save_config(cfg, path)
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()
        assert len(loaded.param_presets) == 1
        p = loaded.param_presets[0]
        assert p.name == "creativo"
        assert p.temperature == 1.10
        assert p.min_p == 0.08
        assert p.max_tokens == 2048
        assert p.top_p == 0.95
        assert p.top_k == 50
        assert p.repeat_penalty == 1.05
        assert p.seed == 42

    def test_v0110_forward_compat_no_new_fields(self, monkeypatch, tmp_path):
        """GIVEN a config.json WITHOUT the 5 new fields (v0.10.0 style)
        WHEN load_config() runs on v0.11.0
        THEN defaults are applied (no error)."""
        from bellbird.core import config as config_module

        path = tmp_path / "config.json"
        data = {"port": 8080, "temperature": 0.7}
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(config_module, "CONFIG_PATH", path)
        loaded = load_config()
        assert loaded.param_presets == []
        assert loaded.filter_strip_markdown is True
        assert loaded.filter_strip_urls is True
        assert loaded.filter_strip_emojis is True
        assert loaded.filter_strip_code_blocks is True


# ─── migration invariants ─────────────────────────────────────────────────────


def test_migrations_bump_max_tokens_512_to_4096(monkeypatch, tmp_path):
    """GIVEN a JSON config with ``max_tokens: 512`` (v0.5.0 default)
    WHEN load_config() runs
    THEN the resulting ``BellbirdConfig.max_tokens`` equals 4096.

    Per REQ-CONFIG-3 in openspec/changes/config-log-user-data-dir/specs.
    The migration in ``_MIGRATIONS`` MUST rewrite the legacy 512 value
    to the post-v0.5.1 default of 4096 so reasoning models can complete
    their thinking phase.
    """
    from bellbird.core import config as config_module

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"max_tokens": 512}), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)

    loaded = load_config()
    assert loaded.max_tokens == 4096


def test_migrations_does_not_touch_max_tokens_when_not_512(monkeypatch, tmp_path):
    """GIVEN a JSON config with a non-default ``max_tokens`` (not 512)
    WHEN load_config() runs
    THEN ``max_tokens`` is preserved as-is (no false-positive migration)."""
    from bellbird.core import config as config_module

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"max_tokens": 2048}), encoding="utf-8")
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)

    loaded = load_config()
    assert loaded.max_tokens == 2048
