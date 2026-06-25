"""wx-runtime test for MainWindow construction without network calls.

This test requires wxPython to run. It is skipped in WSL/CI environments
that do not have wxPython installed (via ``pytest.importorskip("wx")``).

On Windows, it verifies that:
- The window is shown before any I/O (startup checks are async).
- The status bar shows "Iniciando..." on construction.
"""

import pytest

pytest.importorskip("wx")

import wx


@pytest.fixture(scope="module")
def app():
    """Create a wx.App for the test module."""
    return wx.App()


def test_window_shown_before_probe(app):
    """MainWindow is visible immediately after __init__, before any I/O.

    The startup probe runs on a background thread, so the window should
    be shown synchronously after the constructor returns.
    """
    from bellbird.ui.main_window import MainWindow

    frame = MainWindow(None, title="Bellbird")
    try:
        assert frame.IsShown(), (
            "MainWindow must be shown (visible) immediately after __init__ "
            "— the startup probe must run on a background thread."
        )
        # Status bar field 0 should say "Iniciando..." until the probe completes
        status_text = frame.status_bar.GetStatusText(0)
        assert "Iniciando" in status_text, (
            f"Status bar field 0 should contain 'Iniciando...', "
            f"got: {status_text!r}"
        )
    finally:
        frame.Destroy()
