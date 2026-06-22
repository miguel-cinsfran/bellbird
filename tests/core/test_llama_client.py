"""Tests for LlamaClient module — strict TDD, RED first, then GREEN."""

import json
import sys
import threading
import time
import types
from unittest.mock import Mock, patch

import pytest
import requests


# ─── Wx module stub ──────────────────────────────────────────────────────────


def _ensure_wx_module():
    """Ensure wx module exists in sys.modules for patching wx.CallAfter."""
    if "wx" not in sys.modules:
        wx_mod = types.ModuleType("wx")

        def call_after(fn, *args):
            fn(*args)

        wx_mod.CallAfter = call_after
        sys.modules["wx"] = wx_mod


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def ensure_wx():
    """Ensure wx module is available for all tests."""
    _ensure_wx_module()
    yield


@pytest.fixture
def mock_session():
    """Inject a fake requests.Session."""
    return Mock(spec=requests.Session)


@pytest.fixture
def mock_call_after():
    """Capture wx.CallAfter calls for assertion."""
    calls = []

    def fake_call_after(fn, *args):
        calls.append((fn, args))
        # Invoke immediately so tests can assert on effects
        fn(*args)

    with patch("wx.CallAfter", side_effect=fake_call_after):
        yield calls


# ─── Test class ───────────────────────────────────────────────────────────────


class TestLlamaClient:
    """Tests for LlamaClient."""
    pass
