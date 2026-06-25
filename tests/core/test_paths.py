"""Tests for bellbird.core.paths — strict TDD, wx-free.

Covers: user_data_dir() returns a Path, matches platformdirs,
idempotent on repeated calls, directory created on disk.
"""

from pathlib import Path

import pytest

# Import will fail with ImportError — paths.py doesn't exist yet (RED phase)
from bellbird.core.paths import user_data_dir


def test_user_data_dir_returns_path(monkeypatch):
    """GIVEN a monkey-patched platformdirs returning a tmp path
    WHEN user_data_dir() is called
    THEN the returned path equals the expected path
    AND the directory is created on disk."""
    import platformdirs

    tmp = Path("/tmp/test-bellbird-data")
    monkeypatch.setattr(
        platformdirs,
        "user_data_dir",
        lambda app, appauthor: str(tmp / app),
    )
    result = user_data_dir()
    expected = tmp / "Bellbird"
    assert result == expected
    assert expected.is_dir()


def test_user_data_dir_passes_appauthor_false(monkeypatch):
    """GIVEN platformdirs.user_data_dir
    WHEN user_data_dir() is called
    THEN appauthor=False is passed to platformdirs."""
    import platformdirs

    captured = {}

    def tracking_user_data_dir(app, appauthor):
        captured["app"] = app
        captured["appauthor"] = appauthor
        return f"/tmp/{app}"

    monkeypatch.setattr(platformdirs, "user_data_dir", tracking_user_data_dir)
    user_data_dir()
    assert captured["app"] == "Bellbird"
    assert captured["appauthor"] is False


def test_user_data_dir_idempotent(monkeypatch):
    """GIVEN the user-data dir already exists
    WHEN user_data_dir() is called again
    THEN no exception is raised."""
    import platformdirs

    tmp = Path("/tmp/test-bellbird-idempotent")
    monkeypatch.setattr(
        platformdirs,
        "user_data_dir",
        lambda app, appauthor: str(tmp / app),
    )
    # First call creates
    first = user_data_dir()
    assert first.is_dir()
    # Second call must not raise
    second = user_data_dir()
    assert second == first
    assert second.is_dir()
