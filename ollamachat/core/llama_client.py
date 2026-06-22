"""LlamaClient — HTTP client for llama.cpp's OpenAI-compatible server.

Provides headless (wx-free) access to a local llama-server:
- Health check via GET /health
- Loaded model query via GET /v1/models
- Streaming chat via POST /v1/chat/completions with SSE parsing in a daemon thread
- Clean abort via threading.Event

All streaming callbacks are marshalled to the wx main thread via wx.CallAfter.
"""

import json
import threading
from typing import Any, Callable

import requests


class LlamaClient:
    """Client for a local llama-server (llama.cpp's HTTP server).

    Args:
        base_url: Server URL (default http://localhost:8080).
        session: Optional requests.Session for test injection.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self._session = session or requests.Session()
        self._stop_event = threading.Event()
        self._stream_thread: threading.Thread | None = None

    def check_running(self) -> bool:
        """Check if llama-server is running and healthy.

        Returns:
            True if GET /health returns 200 with {"status": "ok"},
            False otherwise (no raise).
        """
        raise NotImplementedError

    def get_loaded_model(self) -> str:
        """Get the id of the currently loaded model.

        Returns:
            Model id string from GET /v1/models data[0]["id"],
            or "" on any error (no raise).
        """
        raise NotImplementedError

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Start a streaming chat in a background daemon thread.

        POST /v1/chat/completions with SSE parsing. The request body
        contains sampling parameters at the root (not nested in options).

        Args:
            messages: List of message dicts with role and content.
            options: Sampling parameters dict (temperature, top_p, etc.).
            on_token: Called per token fragment via wx.CallAfter.
            on_done: Called once on successful completion via wx.CallAfter.
            on_error: Called once on error via wx.CallAfter.
        """
        raise NotImplementedError

    def abort(self) -> None:
        """Signal the streaming thread to stop after the current SSE line."""
        raise NotImplementedError

    def _stream_worker(
        self,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Background thread worker for streaming chat.

        Imports wx locally to keep core/ wx-free at module level.
        Parses SSE lines from the llama-server response and dispatches
        callbacks via wx.CallAfter.
        """
        raise NotImplementedError
