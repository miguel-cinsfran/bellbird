"""Spawn and probe the local llama-server process.

This module is intentionally wx-free so it can be unit-tested
in environments that do not have wxPython installed (e.g. WSL during
development). It returns plain ``(ok, message)`` tuples; the UI layer
in ``MainWindow`` is responsible for announcing the message via
``Speech`` and updating the status bar.

Platform notes
--------------
- On Windows, ``subprocess.Popen`` is called with ``creationflags =
  0x08000000`` (``CREATE_NO_WINDOW``) so a console window does not
  flash when the user clicks the "Iniciar servidor" button.
- On Linux / macOS the same ``llama-server`` command is used; the
  subprocess inherits the terminal's stdio, which is fine during dev.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from ollamachat.core.llama_client import LlamaClient


# Module-level state for tracked server process.
# _lock guards mutation of _server_process across threads.
_server_process: subprocess.Popen | None = None
_lock = threading.Lock()

# Windows subprocess creation flag: prevents a console window from
# flashing when the spawned process is started.
_CREATE_NO_WINDOW = 0x08000000

# Poll interval for server startup checks.
_POLL_INTERVAL_SECONDS = 0.2


def find_llama_server() -> str | None:
    """Locate the llama-server binary on PATH.

    Returns:
        Absolute path to llama-server (or .exe on Windows), or None
        if not found. Does not raise.
    """
    raise NotImplementedError


def find_gguf_models(extra_paths: list[str] | None = None) -> list[str]:
    """Scan standard locations for .gguf model files.

    On Windows (os.name == "nt"), scans:
    - %%USERPROFILE%%\\models\\ (non-recursive)
    - %%USERPROFILE%%\\Downloads\\ (non-recursive)
    - %%USERPROFILE%%\\.cache\\huggingface\\hub\\ (recursive, depth 5)
    - %%USERPROFILE%%\\.lmstudio\\models\\ (non-recursive)
    - %%LOCALAPPDATA%%\\nomic.ai\\GPT4All\\ (non-recursive)
    - extra_paths (if provided, non-recursive)

    On non-Windows, returns [] (extra_paths is also scanned on
    non-Windows for dev/test convenience).

    Returns:
        Sorted list of absolute .gguf paths, deduplicated. Never raises.
    """
    raise NotImplementedError


def start_server(
    model_path: str,
    client: LlamaClient,
    port: int = 8080,
    ctx_size: int = 4096,
    n_gpu_layers: int = 99,
    timeout: float = 60.0,
) -> tuple[bool, str]:
    """Start llama-server with the given model.

    (1) Calls stop_server() unconditionally (idempotent).
    (2) Fast-path: if client.check_running() returns True, returns
        (True, "ya está corriendo") without spawning.
    (3) Spawns subprocess.Popen with the documented argv.
    (4) Polls client.check_running() every 0.2s for up to timeout seconds.
    (5) Returns (True, "Servidor listo") on success or (False, reason)
        on failure.

    Args:
        model_path: Absolute path to the .gguf file.
        client: LlamaClient instance for health polling.
        port: Server port (default 8080).
        ctx_size: Context size in tokens (default 4096).
        n_gpu_layers: GPU layers offload (default 99 = all).
        timeout: Maximum seconds to wait for the server to start.

    Returns:
        (ok, message) tuple.
    """
    raise NotImplementedError


def stop_server() -> None:
    """Stop the tracked llama-server process.

    Sends terminate(), waits up to 5s for graceful exit, falls back to
    kill() if needed. Idempotent — safe to call when no process is tracked.
    """
    raise NotImplementedError


def get_install_command() -> str:
    """Return the winget command to install llama-server.

    Returns:
        The literal string "winget install ggml.llamacpp".
    """
    raise NotImplementedError
