"""Runtime tests for ChatPanel — wx instantiation required (Windows only).

These tests require a wx application object and real wxPython.
They are skipped automatically on WSL/Linux via ``importorskip("wx")``.
Run via ``run_tests.bat`` on Windows.
"""

import pytest

pytest.importorskip("wx")

import wx


@pytest.fixture
def app():
    """Create a wx.App for the duration of each test."""
    app = wx.App()
    yield app
    # wxPython cleanup is handled by ref-counting


@pytest.fixture
def panel(app):
    """Create a ChatPanel for testing."""
    from bellbird.ui.chat_panel import ChatPanel

    frame = wx.Frame(None)
    speech = None  # Speech mock — we only test visual widgets
    panel = ChatPanel(frame, speech)
    yield panel
    frame.Destroy()


class TestChatPanelRuntime:
    """Runtime tests that verify stream_display absence and streaming state."""

    def test_stream_display_absent(self, panel):
        """ChatPanel no longer has a stream_display attribute."""
        assert not hasattr(panel, "stream_display"), (
            "stream_display attribute must be removed"
        )

    def test_streaming_index_on_start_generation(self, panel):
        """start_generation sets _streaming_index to a valid int."""
        panel.start_generation()
        assert isinstance(panel._streaming_index, int), (
            f"_streaming_index should be int, got {type(panel._streaming_index)}"
        )
        assert panel._streaming_index >= 0

    def test_placeholder_on_start(self, panel):
        """start_generation appends '[IA] (generando…)' placeholder."""
        panel.start_generation()
        idx = panel._streaming_index
        text = panel.message_list.GetString(idx)
        assert text == "[IA] (generando…)", (
            f"Placeholder text mismatch: {text!r}"
        )
