"""Tests for bellbird.core.config — strict TDD, wx-free.

Covers: missing file defaults, save+load round-trip, unknown key filtering,
per-instance list default, path location, legacy migration. All use
monkeypatch for CONFIG_PATH isolation.
"""

import importlib
import json

import pytest

from bellbird.core.config import BellbirdConfig, load_config, save_config


def test_load_config_returns_defaults_on_missing_file(monkeypatch, tmp_path):
    """GIVEN CONFIG_PATH is a non-existent path
    WHEN load_config() is called
    THEN return BellbirdConfig() with no exception."""
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", tmp_path / "nope.json")
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
    # Legacy file must NOT be deleted
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
    # Must still have the original new value, NOT overwritten
    assert content["temperature"] == 0.99


def test_migrate_legacy_legacy_missing_noop(monkeypatch, tmp_path):
    """GIVEN legacy config does NOT exist
    WHEN migrate_legacy_config() runs
    THEN no exception is raised and no new file is created."""
    from bellbird.core import config as config_module

    new_dir = tmp_path / "Bellbird"
    new_config = new_dir / "config.json"
    assert not new_config.exists()

    # LEGACY_CONFIG_PATH points to non-existent file
    monkeypatch.setattr(config_module, "LEGACY_CONFIG_PATH", tmp_path / "nope.json")
    monkeypatch.setattr(config_module, "CONFIG_PATH", new_config)

    # Must not raise
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

    # Make shutil.copy2 raise PermissionError
    import shutil

    original_copy2 = shutil.copy2

    def failing_copy2(src, dst, **kwargs):
        raise PermissionError("access denied")

    monkeypatch.setattr(shutil, "copy2", failing_copy2)

    # Must not raise
    config_module.migrate_legacy_config()


def test_extra_model_folders_default_is_empty_list():
    """GIVEN two fresh BellbirdConfig() instances
    WHEN one gets an appended folder
    THEN the other instance still has an empty list."""
    a = BellbirdConfig()
    b = BellbirdConfig()
    a.extra_model_folders.append("/x")
    assert b.extra_model_folders == []


def test_last_model_default_is_empty_string():
    """GIVEN a fresh BellbirdConfig()
    THEN .last_model == ""."""
    cfg = BellbirdConfig()
    assert cfg.last_model == ""


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
    import json

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
    # Direct dict access uses basename
    assert cfg.model_mmproj.get("vl.gguf") == "C:\\m\\p.gguf"
    # Same basename regardless of parent path
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
    # File does not exist
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


# ── mmproj_offload ────────────────────────────────────────────────────────


def test_request_timeout_default_is_120():
    """GIVEN a fresh BellbirdConfig()
    THEN request_timeout == 120."""
    cfg = BellbirdConfig()
    assert cfg.request_timeout == 120


def test_request_timeout_missing_in_json_uses_default(monkeypatch, tmp_path):
    """GIVEN a config.json without request_timeout
    WHEN load_config() is called
    THEN request_timeout is 120 (field default)."""
    import json
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"port": 8080}), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.request_timeout == 120


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


def test_mmproj_offload_default_is_true():
    """GIVEN a fresh BellbirdConfig()
    THEN mmproj_offload is True."""
    cfg = BellbirdConfig()
    assert cfg.mmproj_offload is True


def test_min_p_default():
    """GIVEN a fresh BellbirdConfig()
    THEN min_p == 0.05 (2026 consensus)."""
    cfg = BellbirdConfig()
    assert cfg.min_p == 0.05


def test_seed_default():
    """GIVEN a fresh BellbirdConfig()
    THEN seed == -1 (aleatorio sentinel)."""
    cfg = BellbirdConfig()
    assert cfg.seed == -1


def test_stop_default():
    """GIVEN a fresh BellbirdConfig()
    THEN stop == [] (no stop strings sentinel)."""
    cfg = BellbirdConfig()
    assert cfg.stop == []


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
    import json
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
    AND no entry references min_p, seed, or stop."""
    from bellbird.core.config import _MIGRATIONS
    assert len(_MIGRATIONS) == 1
    assert "max_tokens" in _MIGRATIONS
    assert _MIGRATIONS["max_tokens"] == (512, 4096)
    assert "min_p" not in _MIGRATIONS
    assert "seed" not in _MIGRATIONS
    assert "stop" not in _MIGRATIONS


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


def test_max_tool_iterations_default():
    """GIVEN a fresh BellbirdConfig()
    THEN max_tool_iterations == 5."""
    cfg = BellbirdConfig()
    assert cfg.max_tool_iterations == 5


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
    import json

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
    # The load must normalise list to tuple
    val = loaded.keymap_overrides["copy_last"]
    assert val == (3, 67), f"Expected (3, 67), got {val!r}"


def test_keymap_overrides_unknown_id_does_not_crash(monkeypatch, tmp_path):
    """GIVEN config.json with unknown action id in keymap_overrides
    WHEN load_config() runs
    THEN no KeyError is raised (the drop is Keymap's job)."""
    import json

    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"ghost_action": [0, 81]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    # The config layer does not validate action ids; Keymap.from_overrides_dict does
    result = load_config()
    assert "ghost_action" in result.keymap_overrides


def test_keymap_overrides_non_int_falls_back(monkeypatch, tmp_path):
    """GIVEN config.json with string value instead of (int, int) pair
    WHEN load_config() runs
    THEN falls back to defaults (BellbirdConfig(), corrupt-config policy)."""
    import json

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
    import json

    path = tmp_path / "config.json"
    data = {"keymap_overrides": {"copy_last": [1.5, "C"]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module

    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.keymap_overrides == {}


# ── _MIGRATIONS regression guard ──────────────────────────────────────────


def test_migrations_dict_unchanged_no_new_entries():
    """GIVEN the _MIGRATIONS dict
    THEN it has exactly one entry (max_tokens 512->4096)
    AND no entry references keymap_overrides."""
    from bellbird.core.config import _MIGRATIONS
    assert len(_MIGRATIONS) == 1
    assert "max_tokens" in _MIGRATIONS
    assert _MIGRATIONS["max_tokens"] == (512, 4096)
    assert "keymap_overrides" not in _MIGRATIONS


def test_keymap_overrides_list_to_tuple_normalisation(monkeypatch, tmp_path):
    """GIVEN config.json with list-of-two-ints for keymap_overrides
    WHEN load_config() runs
    THEN the value is normalised to a tuple of ints."""
    import json

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


def test_max_tool_iterations_overridable(monkeypatch, tmp_path):
    """GIVEN config JSON with max_tool_iterations: 10
    WHEN load_config()
    THEN max_tool_iterations == 10."""
    import json
    path = tmp_path / "config.json"
    data = {"max_tool_iterations": 10}
    path.write_text(json.dumps(data), encoding="utf-8")
    from bellbird.core import config as config_module
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    result = load_config()
    assert result.max_tool_iterations == 10
