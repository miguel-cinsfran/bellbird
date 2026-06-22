"""Ollama REST API client for OllamaChat.

Provides headless (wx-free) access to a local Ollama daemon:
- Health check via GET /api/tags
- Model listing via GET /api/tags
- Streaming chat via POST /api/chat with NDJSON parsing in a daemon thread
- Clean abort via threading.Event

All streaming callbacks are marshalled to the wx main thread via wx.CallAfter.
"""

import json
import threading
from typing import Any, Callable

import requests


class OllamaClient:
    """Client for a local Ollama daemon.

    Args:
        base_url: Ollama server URL (default http://localhost:11434).
        session: Optional requests.Session for test injection.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self._session = session or requests.Session()
        self._stop_event = threading.Event()
        self._stream_thread: threading.Thread | None = None

    def check_running(self) -> bool:
        """Check if Ollama is running and reachable.

        Returns:
            True if GET /api/tags returns HTTP 200, False otherwise.
        """
        try:
            response = self._session.get(
                f"{self.base_url}/api/tags", timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available model names from Ollama.

        Returns:
            List of model name strings, or [] on any error.
        """
        try:
            response = self._session.get(
                f"{self.base_url}/api/tags", timeout=5
            )
            if response.status_code != 200:
                return []
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Start a streaming chat in a background daemon thread.

        Args:
            model: Model name (e.g. "llama3:latest").
            messages: List of message dicts with role, content, optional images.
            options: Sampling parameters dict.
            on_token: Called per token fragment via wx.CallAfter.
            on_done: Called once on successful completion via wx.CallAfter.
            on_error: Called once on error via wx.CallAfter.
        """
        self._stop_event.clear()
        self._stream_thread = threading.Thread(
            target=self._stream_worker,
            args=(model, messages, options, on_token, on_done, on_error),
            daemon=True,
        )
        self._stream_thread.start()

    def abort(self) -> None:
        """Signal the streaming thread to stop after the current line."""
        self._stop_event.set()

    def _stream_worker(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        """Background thread worker for streaming chat.

        Parses NDJSON lines from the Ollama API response and dispatches
        callbacks via wx.CallAfter.
        """
        import wx  # Import wx only when needed (core/ is wx-free at top level)

        try:
            body = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": options,
            }

            response = self._session.post(
                f"{self.base_url}/api/chat",
                json=body,
                stream=True,
                timeout=60,
            )

            for line in response.iter_lines():
                if self._stop_event.is_set():
                    break
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        wx.CallAfter(on_token, content)
                except json.JSONDecodeError:
                    continue  # skip malformed line

            wx.CallAfter(on_done)

        except Exception as e:
            error_text = f"{type(e).__name__}: {e}"
            try:
                wx.CallAfter(on_error, error_text)
            except Exception:
                pass  # Last resort: don't crash if wx is gone
