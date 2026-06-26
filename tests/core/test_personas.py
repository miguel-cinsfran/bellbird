"""Tests for bellbird.core.personas."""

import json
import pytest
from pathlib import Path

from bellbird.core.config import BellbirdConfig
from bellbird.core.personas import (
    Persona,
    _builtin_defaults,
    apply_persona,
    find_by_id,
    get_active_personas,
    load_personas,
    reset_builtin,
    save_personas,
)

_EXPECTED_IDS = {
    "general", "desarrollador", "traductor", "editor", "redactor_tecnico",
    "profesor", "generador_prompts", "generador_commits", "entrevistador",
    "describe_imagenes",
}


class TestBuiltins:
    def test_ten_builtin_personas(self):
        assert len(_builtin_defaults()) == 10

    def test_all_expected_ids_present(self):
        ids = {p.id for p in _builtin_defaults()}
        assert ids == _EXPECTED_IDS

    def test_all_builtins_have_non_empty_system_prompt(self):
        for p in _builtin_defaults():
            assert p.system_prompt.strip(), f"{p.id} has empty system_prompt"

    def test_all_builtins_are_active_by_default(self):
        for p in _builtin_defaults():
            assert p.activa, f"{p.id} should be active by default"

    def test_all_builtins_have_builtin_flag(self):
        for p in _builtin_defaults():
            assert p.builtin


class TestPersonaSerialisation:
    def test_round_trip(self):
        p = Persona(id="test", nombre="Test", system_prompt="Eres test.")
        assert Persona.from_dict(p.to_dict()) == p

    def test_defaults_preserved(self):
        p = Persona.from_dict({"id": "x", "nombre": "X", "system_prompt": "S"})
        assert p.builtin is False
        assert p.activa is True


class TestLoadSave:
    def test_load_returns_builtins_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("bellbird.core.personas.PERSONAS_PATH", tmp_path / "nope.json")
        personas = load_personas()
        assert len(personas) == 10

    def test_save_and_load_round_trip(self, tmp_path, monkeypatch):
        path = tmp_path / "personas.json"
        monkeypatch.setattr("bellbird.core.personas.PERSONAS_PATH", path)
        original = _builtin_defaults()
        original[0].nombre = "Modificado"
        save_personas(original)
        loaded = load_personas()
        assert loaded[0].nombre == "Modificado"

    def test_new_builtin_added_on_load(self, tmp_path, monkeypatch):
        path = tmp_path / "personas.json"
        monkeypatch.setattr("bellbird.core.personas.PERSONAS_PATH", path)
        # Save only 9 builtins (drop the last one)
        subset = _builtin_defaults()[:-1]
        save_personas(subset)
        loaded = load_personas()
        ids = {p.id for p in loaded}
        assert "describe_imagenes" in ids  # new builtin was re-added


class TestHelpers:
    def test_find_by_id_found(self):
        personas = _builtin_defaults()
        p = find_by_id(personas, "general")
        assert p is not None
        assert p.id == "general"

    def test_find_by_id_not_found_returns_none(self):
        assert find_by_id(_builtin_defaults(), "nonexistent") is None

    def test_get_active_filters_inactive(self):
        personas = _builtin_defaults()
        personas[0].activa = False
        active = get_active_personas(personas)
        assert len(active) == 9
        assert all(p.activa for p in active)

    def test_reset_builtin_restores_prompt(self):
        personas = _builtin_defaults()
        original_prompt = personas[0].system_prompt
        personas[0].system_prompt = "MODIFICADO"
        restored = reset_builtin(personas, "general")
        assert restored[0].system_prompt == original_prompt

    def test_reset_builtin_noop_for_user_persona(self):
        personas = _builtin_defaults()
        user_p = Persona(id="user_xyz", nombre="Mine", system_prompt="X")
        personas.append(user_p)
        result = reset_builtin(personas, "user_xyz")
        assert result[-1].system_prompt == "X"  # unchanged


class TestApplyPersona:
    def test_apply_sets_system_prompt_and_id(self):
        config = BellbirdConfig()
        p = Persona(id="test", nombre="T", system_prompt="Eres test.")
        apply_persona(config, p)
        assert config.system_prompt == "Eres test."
        assert config.persona_activa == "test"

    def test_apply_none_clears_prompt(self):
        config = BellbirdConfig(system_prompt="algo", persona_activa="general")
        apply_persona(config, None)
        assert config.system_prompt == ""
        assert config.persona_activa is None

    def test_apply_builtin_general(self):
        config = BellbirdConfig()
        p = find_by_id(_builtin_defaults(), "general")
        apply_persona(config, p)
        assert "asistente" in config.system_prompt.lower()
        assert config.persona_activa == "general"
