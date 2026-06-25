"""Tests for bellbird.core.model_meta — strict TDD, wx-free.

Covers find_mmproj_for_model with temporary directories:
no-sibling, single per pattern, multi → None, alphabetical tie-break,
edge cases (no parent dir, missing model path).
"""

from pathlib import Path

import pytest


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestFindMmprojForModel:
    """Tests for find_mmproj_for_model."""

    def test_no_siblings_returns_none(self, tmp_path: Path) -> None:
        """Given a dir with only the model file, returns None."""
        model = tmp_path / "Llama-3.2-11B.gguf"
        model.write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result is None

    def test_pattern1_single_match(self, tmp_path: Path) -> None:
        """Given a dir with mmproj-Llama*.gguf, returns it."""
        model = tmp_path / "Llama-3.2-11B.gguf"
        model.write_text("")
        proj = tmp_path / "mmproj-Llama-3.2-11B-f16.gguf"
        proj.write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result == proj.resolve()

    def test_pattern1_multi_match_returns_none(self, tmp_path: Path) -> None:
        """Given multiple mmproj-*.gguf, refuses and returns None."""
        model = tmp_path / "model.gguf"
        model.write_text("")
        (tmp_path / "mmproj-A.gguf").write_text("")
        (tmp_path / "mmproj-B.gguf").write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result is None

    def test_pattern2_fallback(self, tmp_path: Path) -> None:
        """Given no mmproj- prefix but *mmproj* match, returns it."""
        model = tmp_path / "model.gguf"
        model.write_text("")
        proj = tmp_path / "llama-vision-mmproj-v1.gguf"
        proj.write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result == proj.resolve()

    def test_pattern3_lowest(self, tmp_path: Path) -> None:
        """Given no pattern 1/2 match but *.mmproj.gguf, returns it."""
        model = tmp_path / "model.gguf"
        model.write_text("")
        proj = tmp_path / "vision.mmproj.gguf"
        proj.write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result == proj.resolve()

    def test_alphabetical_tiebreak(self, tmp_path: Path) -> None:
        """Given multiple mmproj- match IN the same pattern returns None (refuse),
        but for pattern 2 where multi is allowed, returns alphabetical first."""
        model = tmp_path / "model.gguf"
        model.write_text("")
        # Pattern 2 matches: *mmproj* (no mmproj- prefix)
        a_proj = tmp_path / "a-mmproj-v1.gguf"
        a_proj.write_text("")
        b_proj = tmp_path / "b-mmproj-v2.gguf"
        b_proj.write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result == a_proj.resolve()

    def test_non_gguf_siblings_ignored(self, tmp_path: Path) -> None:
        """Given non-GGUF siblings, they are not considered."""
        model = tmp_path / "model.gguf"
        model.write_text("")
        (tmp_path / "readme.txt").write_text("")
        (tmp_path / "mmproj-model.gguf").write_text("")
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(model)

        assert result is not None
        assert result.name == "mmproj-model.gguf"

    def test_model_no_parent_dir_returns_none(self) -> None:
        """Given model_path with no parent (e.g. bare filename), returns None."""
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(Path("bare_model.gguf"))

        assert result is None

    def test_model_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Given model_path that doesn't exist, returns None."""
        from bellbird.core.model_meta import find_mmproj_for_model

        result = find_mmproj_for_model(tmp_path / "nonexistent.gguf")

        assert result is None
