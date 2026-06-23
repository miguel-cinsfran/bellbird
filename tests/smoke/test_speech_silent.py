"""Smoke test: Speech degrades gracefully when accessible_output2 is missing."""

import builtins
import sys
from unittest.mock import patch

import pytest


def test_speech_silent_on_import_error():
    """Given accessible_output2 is missing, Speech is silent and doesn't raise."""
    real_import = builtins.__import__

    def _block_a2(name, *args, **kwargs):
        if "accessible_output2" in name:
            raise ImportError(f"blocked: {name}")
        return real_import(name, *args, **kwargs)

    # Remove accessible_output2 and bellbird.core.speech from sys.modules
    # so they re-import fresh.  Removal of a2 also forces Python to call
    # __import__ rather than returning a cached module.
    saved = {}
    for key in list(sys.modules.keys()):
        if "accessible_output2" in key or "bellbird" in key:
            saved[key] = sys.modules.pop(key)

    from bellbird.core.speech import Speech

    try:
        with patch("builtins.__import__", side_effect=_block_a2):
            speech = Speech()
    finally:
        sys.modules.update(saved)

    assert speech.is_silent

    # These should not raise
    speech.speak("test")
    speech.announce_token_chunk("test")
    speech.flush_token_buffer()
    speech.output("test")
    speech.stop()
