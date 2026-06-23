# Design: migrate-llama-cpp

## 1. Architecture overview

### Module map

```
ollamachat/
  main.py                       # entry point — UNCHANGED
  core/                         # wx-free, testable
    speech.py                   # UNCHANGED
    conversation.py             # UNCHANGED
    logger.py                   # UNCHANGED
    llama_client.py             # NEW (replaces ollama_client.py)
    llama_runner.py             # NEW (replaces ollama_runner.py)
  ui/
    main_window.py              # MODIFIED (new toolbar, 3-state startup)
    chat_panel.py               # TOUCHED (image attachments → OpenAI content-array)
    params_panel.py             # MODIFIED (wx.Choice → wx.ComboBox + scan/explore)
  data/                         # UNCHANGED (gitignored runtime)
tests/
  core/
    test_llama_client.py        # NEW (replaces test_ollama_client.py)
    test_llama_runner.py        # NEW (replaces test_ollama_runner.py)
    test_speech.py              # UNCHANGED
    test_conversation.py        # UNCHANGED
    test_logger.py              # UNCHANGED
  ui/
    test_*_static.py            # UNCHANGED (AST checks)
  smoke/
    test_speech_silent.py       # UNCHANGED
openspec/                       # change artifacts
scripts/
  build_windows.sh              # UNCHANGED
```

### Layer boundaries

- `core/llama_client.py` imports `wx` **only inside** the streaming worker function (mirrors the existing `OllamaClient` pattern). Top-level imports are stdlib + `requests` only.
- `core/llama_runner.py` is **fully wx-free** (no wx import anywhere). It is platform-aware via `os.name` and `sys.platform`.
- `ui/` depends on `core/` and `wx`. Never the other way.
- `data/` is the only persistent side-effect; gitignored.

### What each module owns

- `LlamaClient` — HTTP I/O, SSE parsing, thread orchestration. Does NOT spawn the server, does NOT know where `.gguf` files live.
- `LlamaRunner` — process lifecycle (find, start, stop), `.gguf` filesystem discovery, install command. Does NOT do HTTP.
- `MainWindow` — orchestrates both, manages the three startup states, voice announcements.
- `ParamsPanel` — UI for model selection + sampling parameters.
- `ChatPanel` — UI for the conversation; builds message dicts in the OpenAI content-array format when images are attached.

## 2. Sequence diagrams

### 2.1 Startup detection (three states)

```
MainWindow.__init__
  └─> _startup_check
        ├─> LlamaRunner.find_llama_server()
        │     └─> returns path | None
        ├─ if None:
        │     ├─> speech("llama-server no instalado...")
        │     └─> wx.MessageDialog(install command)
        ├─ elif LlamaClient.check_running() == False:
        │     ├─> status_bar "Servidor detenido"
        │     └─> speech("Servidor detenido. Selecciona un modelo y pulsa Iniciar servidor.")
        └─ else:
              ├─> loaded = LlamaClient.get_loaded_model()
              ├─> status_bar "Conectado: <basename>"
              └─> speech("Conectado. Modelo cargado: <basename>.")
```

### 2.2 First chat flow

```
User picks .gguf in ComboBox  (params_panel.get_model() → "/path/to/x.gguf")
User clicks "Iniciar servidor"  (start_server_button)
  └─> MainWindow._on_start_server
        ├─> speech("Iniciando servidor...")
        ├─> LlamaRunner.start_server("/path/to/x.gguf", self._client)
        │     ├─> stop_server()            # idempotent, no-op if nothing tracked
        │     ├─> if client.check_running(): return (True, "ya está corriendo")
        │     ├─> Popen(["llama-server", "--model", path, "--port", "8080",
        │     │            "--host", "127.0.0.1", "--ctx-size", "4096",
        │     │            "--n-gpu-layers", "99", "--jinja"],
        │     │            stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL,
        │     │            creationflags=CREATE_NO_WINDOW on Windows)
        │     └─> poll check_running() every 0.2s, up to 60s
        │           └─> return (True, "Servidor listo") | (False, "timeout msg")
        └─> if ok: speech("Servidor listo")
                enable stop_server_button
                params_panel._scan_models_button.Enable()

User types message + clicks "Enviar"  (chat_panel.send_button)
  └─> MainWindow.send_message
        ├─> build api_messages (system + history + new user)
        │     # if images: content-array with image_url blocks
        ├─> options = params_panel.get_params()  # dict with max_tokens already
        ├─> self._client.chat_stream(messages, options, on_token, on_done, on_error)
        │     └─> spawn daemon thread → POST /v1/chat/completions
        │           body = {model: "local", messages, stream: true,
        │                    temperature, top_p, top_k, repeat_penalty, max_tokens}
        │           parse SSE line-by-line:
        │             data: {...}  → on_token(choices[0].delta.content)
        │             data: [DONE] → on_done, break
        │             blank / malformed → skip
        └─> all callbacks via wx.CallAfter
```

### 2.3 Model switch

```
User picks different .gguf in ComboBox
User clicks "Iniciar servidor" again
  └─> MainWindow._on_start_server
        └─> LlamaRunner.start_server(new_path, self._client)
              ├─> stop_server()              # terminate old process, wait 5s, kill if needed
              ├─> if client.check_running(): return
              ├─> Popen(new argv)
              └─> poll until ready or timeout
```

### 2.4 Stream abort

```
User clicks "Detener" (chat_panel.stop_button)
  └─> MainWindow.abort_generation
        └─> self._client.abort()
              └─> self._stop_event.set()

Inside _stream_worker (background thread):
  next iter_lines() iteration:
    if self._stop_event.is_set():
        break
  wx.CallAfter(on_done)   # not on_error
```

## 3. `LlamaClient` internal structure

### Class sketch

```python
import json
import threading
from typing import Any, Callable
import requests


class LlamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self._session = session or requests.Session()
        self._stop_event = threading.Event()
        self._stream_thread: threading.Thread | None = None

    def check_running(self) -> bool: ...
    def get_loaded_model(self) -> str: ...
    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        on_token: Callable[[str], None],
        on_done: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None: ...
    def abort(self) -> None: ...

    def _stream_worker(self, messages, options, on_token, on_done, on_error) -> None: ...
```

### Public methods — error handling

| Method | Endpoint | Error → return |
|---|---|---|
| `check_running` | `GET /health` | Any exception or non-200 → `False`. No raise. |
| `get_loaded_model` | `GET /v1/models` | Any exception or non-200 → `""`. No raise. |
| `chat_stream` | `POST /v1/chat/completions` (SSE) | Spawns thread; errors surface via `on_error` callback (already wrapped in `wx.CallAfter`). |
| `abort` | — | Sets `self._stop_event`. No-op if no stream. |

### Threading model

- `_stop_event = threading.Event()` — created in `__init__`.
- `_stream_thread` — references the active worker; `None` when idle.
- `chat_stream` clears the event, then spawns a new daemon thread.
- The worker imports `wx` **locally** (line 1 of `_stream_worker`) so `core/llama_client.py` stays importable without wx installed.
- All public callbacks (`on_token`, `on_done`, `on_error`) are dispatched via `wx.CallAfter` from inside the worker.
- The abort event is checked **between SSE lines** (after `iter_lines()` yields a line), never between bytes.

## 4. SSE parser design

### Buffering strategy

Use `response.iter_lines()` to get one logical line at a time. The underlying transport may deliver bytes in arbitrary chunks, but `iter_lines` reassembles complete lines (`\n`, `\r\n`, `\r` boundaries) before yielding. This is sufficient for `llama-server` which emits standard SSE.

### Line classification

For each yielded `line` (bytes, decode with `utf-8`):

1. **Empty line** → SSE event separator, skip.
2. **Starts with `data: `** → strip the prefix, then:
   - If the remaining text is `[DONE]` → stream terminator, set a local flag, break the loop.
   - Else → `json.loads(...)`, extract `choices[0].delta.content`, call `on_token` (if non-empty).
   - If `json.loads` raises → skip silently (malformed event).
3. **Anything else** (heartbeat lines like `event:`, `id:`, `retry:`) → skip.

### When the abort event is checked

The check sits between `iter_lines()` iterations, NOT inside the parse:

```python
for line in response.iter_lines():
    if self._stop_event.is_set():
        break
    if not line:
        continue
    decoded = line.decode("utf-8") if isinstance(line, bytes) else line
    if not decoded.startswith("data: "):
        continue
    payload = decoded[len("data: "):]
    if payload == "[DONE]":
        break
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        continue
    content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
    if content:
        wx.CallAfter(on_token, content)

wx.CallAfter(on_done)
```

### Partial-chunk handling

`requests` with `stream=True` plus `iter_lines()` already handles partial chunks at the TCP level: `iter_lines` internally buffers bytes until a newline arrives. We do not need an extra application-level buffer.

If we ever migrate to a transport that does not give us `iter_lines` (e.g. raw socket), we would add a `_buffer: str` accumulator and split on `"\n"`. The test suite will lock the iter_lines-based behavior; if needed we add an explicit "partial chunk across two reads" test using a fake `iter_lines` that yields split lines.

## 5. `LlamaRunner` internal structure

### Module-level state

```python
_server_process: subprocess.Popen | None = None
_lock = threading.Lock()  # guards mutation of _server_process
```

A lock is required because `start_server` and `stop_server` may be called from any thread (the UI calls them on the main thread, but tests may interleave).

### `find_llama_server() -> str | None`

1. Use `shutil.which("llama-server")` — on Windows this respects `PATHEXT` and finds `llama-server.exe` automatically.
2. If found, return the absolute path (`Path(...).resolve()`).
3. If not, return `None`. Do not raise.

No fallback to a hard-coded `C:\Program Files\...` path; we trust `shutil.which` and let the install dialog point the user at the install command.

### `find_gguf_models(extra_paths: list[str] | None = None) -> list[str]`

On Windows (`os.name == "nt"`), scan these standard locations:

- `%USERPROFILE%\models\` — non-recursive, `*.gguf` only at root
- `%USERPROFILE%\Downloads\` — non-recursive, `*.gguf` only at root
- `%USERPROFILE%\.cache\huggingface\hub\` — **recursive**, depth limit 5, `*.gguf` only
- `%USERPROFILE%\.lmstudio\models\` — non-recursive, `*.gguf` only at root
- `%LOCALAPPDATA%\nomic.ai\GPT4All\` — non-recursive, `*.gguf` only at root
- `extra_paths` (if provided) — non-recursive, `*.gguf` only at root

`Path.home()` is used for `%USERPROFILE%`. `%LOCALAPPDATA%` is read from `os.environ`.

For each location:
- If the directory does not exist, skip silently.
- If it exists, collect absolute paths to all `*.gguf` files (recursive scan in the HF cache case, non-recursive otherwise).
- For the recursive HF cache, use `Path.rglob("*.gguf")` with a manual depth counter so we cap at depth 5 relative to the cache root.

On non-Windows (`os.name != "nt"`), return `[]` immediately. The 5 standard paths do not apply, but `extra_paths` is still scanned (in case the user pointed the dev box at a `.gguf` for manual testing).

Return the union, sorted by `Path.name` (basename) ascending, deduplicated.

### `start_server(model_path, client, port=8080, ctx_size=4096, n_gpu_layers=99, timeout=60.0) -> tuple[bool, str]`

1. Acquire `_lock`.
2. Call `stop_server()` unconditionally (idempotent no-op if nothing is tracked).
3. Fast-path: if `client.check_running()` returns `True`, return `(True, "El servidor ya está corriendo")` without spawning.
4. Build argv: `["llama-server", "--model", model_path, "--port", str(port), "--host", "127.0.0.1", "--ctx-size", str(ctx_size), "--n-gpu-layers", str(n_gpu_layers), "--jinja"]`.
5. Build Popen kwargs: `stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL`. On Windows add `creationflags=0x08000000` (CREATE_NO_WINDOW).
6. `Popen(argv, **kwargs)` inside a `try/except (FileNotFoundError, OSError)`:
   - On `FileNotFoundError` (the binary is gone between `find_llama_server` and now), release lock, return `(False, "No se encontró llama-server")`.
   - On `OSError`, return `(False, "No se pudo iniciar el servidor: <e>")`.
7. Store the Popen handle in `_server_process` before starting the poll.
8. Release the lock (don't hold it during polling — that would block `stop_server` from the same thread).
9. Poll: `attempts = int(timeout / 0.2)`; for each attempt, `time.sleep(0.2)`, then `client.check_running()`. If `True`, return `(True, "Servidor listo")`.
10. If all attempts exhausted, return `(False, "El servidor no responde dentro de {timeout}s")`. The process is **left running** (the user may want to investigate; `stop_server` will clean it up).

### `stop_server() -> None`

1. Acquire `_lock`.
2. If `_server_process is None` or `.poll() is not None` (already exited), set `_server_process = None` and return (idempotent no-op).
3. Call `_server_process.terminate()`.
4. Wait up to 5 seconds (`for _ in range(50): time.sleep(0.1); if proc.poll() is not None: break`).
5. If still alive, call `_server_process.kill()`, then `.wait()`.
6. Set `_server_process = None`.
7. Release the lock.

### `get_install_command() -> str`

Returns the literal string `"winget install ggml.llamacpp"`. Stable, platform-independent. The dialog in `MainWindow` uses this verbatim.

## 6. `params_panel` changes

### Widget swaps

| Before | After | Reason |
|---|---|---|
| `wx.Choice` named `model_selector` | `wx.ComboBox` named `model_selector` | Allows user to type a `.gguf` path directly (accessibility: blind users can use type-ahead instead of stepping through a dropdown) |
| `wx.Button` named `refresh_models_button` (label "Actualizar modelos") | `wx.Button` named `scan_models_button` (label "Buscar modelos") | Renamed to match the new semantics (filesystem scan, not server query) |
| (none) | `wx.Button` named `browse_model_button` (label "Explorar...") | Opens a `wx.FileDialog` with wildcard `*.gguf` for manual path selection |

### Internal state

```python
self._basename_to_path: dict[str, str] = {}  # populated by set_models
self.model_selector: wx.ComboBox             # shows basenames only
```

### `set_models(paths: list[str])` — new contract

```python
def set_models(self, paths: list[str]) -> None:
    self.model_selector.Clear()
    self._basename_to_path.clear()
    for path_str in paths:
        path = Path(path_str)
        self._basename_to_path[path.name] = str(path)
        self.model_selector.Append(path.name)
    if paths:
        self.model_selector.SetSelection(0)
```

The ComboBox **displays basenames only** — NVDA cannot read full Windows paths usefully, and basenames are what the user types/scans for.

### `get_model() -> str` — new contract

Resolution order:

1. If the ComboBox value exactly matches a key in `_basename_to_path`, return the mapped absolute path.
2. Else, treat the ComboBox value as a user-typed path:
   - If it looks like a path (contains `\` or `/` or `:`) and `Path(value).is_file()`, return it verbatim.
   - Else, return `""` (logically "no model selected").

The caller (`MainWindow._on_start_server`) MUST check for empty string and announce "Selecciona primero un modelo .gguf" via speech.

### Layout

- `wx.StaticText(self, label="Modelo (.gguf):")` (new label text).
- `wx.BoxSizer(wx.HORIZONTAL)` containing the ComboBox (proportion=1, EXPAND) + `scan_models_button` + `browse_model_button`.
- All in `BoxSizer`, no grid sizers.

## 7. `main_window` changes

### Toolbar layout (new)

```
wx.StaticText("Servidor:")  +  start_server_button  +  stop_server_button
                              (label "Iniciar servidor",
                               name "start_server_button")
                              (label "Detener servidor",
                               name "stop_server_button",
                               initially disabled)
```

### Imports

- `from ollamachat.core.llama_client import LlamaClient`
- `from ollamachat.core.llama_runner import start_server, stop_server, find_gguf_models, find_llama_server, get_install_command`

### Renamed methods

- `_on_start_ollama` → `_on_start_server` (calls `start_server(model_path, self._client)` instead of `start_ollama(self._client)`).
- `_refresh_models` → `_scan_models` (calls `find_gguf_models()` and announces count).

### Three-state startup check (`_startup_check`)

Replaces the current two-state (running / not running) check:

```python
def _startup_check(self) -> None:
    log = get_logger()
    install_cmd = get_install_command()
    if find_llama_server() is None:
        log.warning("Startup: llama-server not installed")
        msg = f"llama-server no instalado. Instalalo con: {install_cmd}."
        self.status_bar.SetStatusText("llama-server no instalado", 0)
        self._speech.speak(msg, interrupt=True)
        wx.MessageDialog(self, message=msg, caption="llama-server no instalado",
                         style=wx.OK | wx.ICON_WARNING).ShowModal()
        return
    if not self._client.check_running():
        log.info("Startup: llama-server installed but not running")
        self.status_bar.SetStatusText("Servidor detenido", 0)
        self._speech.speak(
            "Servidor detenido. Selecciona un modelo y pulsa Iniciar servidor.",
            interrupt=True,
        )
        return
    loaded = self._client.get_loaded_model()
    log.info(f"Startup: connected, model={loaded!r}")
    self.status_bar.SetStatusText(f"Conectado: {loaded}", 0)
    self._speech.speak(f"Conectado. Modelo cargado: {loaded}.", interrupt=True)
    self._scan_models()
```

### `send_message` change

Drop the `model=` kwarg from the `chat_stream` call:

```python
self._client.chat_stream(
    messages=api_messages,    # NOTE: no model=
    options=options,
    on_token=self._on_token,
    on_done=self._on_done,
    on_error=self._on_error,
)
```

The model path was already used by `start_server` to pick the model; the running server has exactly one model loaded at a time.

### `_scan_models` (replaces `_refresh_models`)

```python
def _scan_models(self) -> None:
    log = get_logger()
    paths = find_gguf_models()
    self.params_panel.set_models(paths)
    if paths:
        log.info(f"Scan: {len(paths)} .gguf file(s) found")
        self._speech.speak(f"{len(paths)} modelos encontrados", interrupt=True)
    else:
        log.warning("Scan: no .gguf files found")
        self._speech.speak("Ningún modelo .gguf encontrado", interrupt=True)
```

Wired up to `params_panel.scan_models_button`.

## 8. `chat_panel` touch

The `main_window.send_message` builds the user message. When `get_attached_images()` returns a non-empty list, the construction changes:

### Before (Ollama)

```python
user_msg = {"role": "user", "content": user_text}
if attached_images:
    user_msg["images"] = attached_images   # list of base64 strings
```

### After (OpenAI content-array)

```python
user_msg = {"role": "user", "content": user_text}
if attached_images:
    # First attached image carries the user text; subsequent images are appended.
    parts: list[dict] = [{"type": "text", "text": user_text}]
    for i, b64 in enumerate(attached_images):
        mime = "image/jpeg"  # see note below
        url = f"data:{mime};base64,{b64}"
        parts.append({"type": "image_url", "image_url": {"url": url}})
    user_msg["content"] = parts
```

### MIME inference

The current `chat_panel.attach_file` stores the raw base64 bytes but **does not** record the MIME type. For the migration, the safest mapping is to extend `_attached_images` to store `(b64, mime)` tuples OR to keep the existing list and default to `image/jpeg`. The proposal accepts `jpeg` or `png` explicitly (REQ-LLAMA-013). Decision: change the storage shape in `chat_panel._attached_images` from `list[str]` to `list[tuple[str, str]]` where the second element is the MIME. This is a small, contained change inside `chat_panel.py` and `main_window.send_message`.

### No `images=` key

`grep -n 'images=' ollamachat/` after the migration must return zero matches in production code. The data flows entirely through `content` (string for no images, list for with images).

## 9. Decision log (NEW decisions, beyond proposal)

1. **`max_tokens` is computed in `params_panel.get_params()`, not in the client.** The spec said "derived from options[num_predict]"; we choose to do the rename at the UI layer (returns `"max_tokens"` already) so the client never has to know the Ollama name existed. This is a one-line change to the return dict and keeps the client surface clean.
2. **MIME tracking in `chat_panel`.** We extend `_attached_images` to `list[tuple[str, str]]` (b64, mime). This is the minimum change that lets the content-array carry the right MIME without guessing.
3. **`start_server` does NOT kill the process on timeout.** It returns `(False, msg)` and leaves the process running. Rationale: the model may be still loading (60s was tuned for normal cases; outliers happen); killing the process would lose the partially-loaded model. The user can call `stop_server` manually.
4. **Lock around `_server_process` mutations.** Tests may call `start_server` and `stop_server` from different threads; a `threading.Lock` makes the state transitions atomic without adding complexity.
5. **Shutdown hook.** `MainWindow.__del__` (or a `wx.EVT_CLOSE` handler) should call `stop_server()` so we don't leak a `llama-server.exe` if the user closes the window. The current Ollama code didn't need this because the daemon was independent; the new design requires it. This goes into `MainWindow._on_close` (NEW).

## 10. Testing strategy

### Test files

| File | Status | Mocking pattern |
|---|---|---|
| `tests/core/test_llama_client.py` | NEW (replaces `test_ollama_client.py`) | `Mock(spec=requests.Session)` + fake `wx.CallAfter` (autouse `ensure_wx` fixture) |
| `tests/core/test_llama_runner.py` | NEW (replaces `test_ollama_runner.py`) | `MagicMock()` client + `patch("ollamachat.core.llama_runner.subprocess.Popen")` |
| `tests/core/test_conversation.py` | UNCHANGED | — |
| `tests/core/test_speech.py` | UNCHANGED | — |
| `tests/core/test_logger.py` | UNCHANGED | — |
| `tests/smoke/test_speech_silent.py` | UNCHANGED | — |
| `tests/ui/test_*_static.py` | UNCHANGED | AST checks; need to update for new `params_panel` widget names (`model_selector` stays; `refresh_models_button` → `scan_models_button`; new `browse_model_button`) |

### Fixtures to introduce

- `mock_session: Mock(spec=requests.Session)` — reuse the pattern from the archived `test_ollama_client.py`. Add a `_stub_stream(lines: list[str])` helper that builds a fake response whose `iter_lines()` yields the given lines.
- `mock_call_after: MagicMock` — patches `wx.CallAfter` to record and invoke synchronously.
- `ensure_wx` (autouse) — materialises a fake `wx` module with `CallAfter` if real wx is not installed.

### Per-method minimum test counts (from REQ-LLAMA-016)

- `LlamaClient.check_running` — 3 tests (200/ok, ConnectionError, 503).
- `LlamaClient.get_loaded_model` — 2 tests (success, ConnectionError).
- `LlamaClient.chat_stream` — 5 tests (2 events + DONE; ConnectionError on POST; full-options forwarded; malformed JSON skipped; partial-chunk reassembly).
- `LlamaClient.abort` — 2 tests (stops mid-stream; no-op when idle).
- `LlamaRunner.find_llama_server` — 2 tests (found in PATH; not found).
- `LlamaRunner.find_gguf_models` — 5 tests (mixed extensions; non-existent dir; extra_paths; recursive depth; non-Windows).
- `LlamaRunner.start_server` — 3 tests (already running; success after 3 polls; timeout).
- `LlamaRunner.stop_server` — 3 tests (graceful exit; kill fallback; no-op idempotent).
- `LlamaRunner.get_install_command` — 1 test (returns the literal string).

### Special test: `start_server` re-spawns after stop

```python
def test_start_server_stops_then_starts(self):
    # First call succeeds with model A; track a Popen handle.
    # Second call with model B must call stop_server (terminate on the tracked
    # handle) before invoking Popen again.
    ...
```

## 11. Apply-phase work plan

The apply agent follows this order so tests stay green at every step:

1. **Create `core/llama_client.py` and `tests/core/test_llama_client.py`** — write tests first (TDD), then implement. Old `ollama_client.py` still exists; existing tests still pass.
2. **Create `core/llama_runner.py` and `tests/core/test_llama_runner.py`** — same TDD pattern.
3. **Run the full test suite** — at this point BOTH old and new modules exist; old tests still pass, new tests pass. No UI changes yet.
4. **Modify `ui/params_panel.py`** — `wx.Choice` → `wx.ComboBox` + scan/explore buttons + `get_model` resolution. Update `tests/ui/test_params_panel_static.py` if its AST checks look for the old button name.
5. **Modify `ui/chat_panel.py`** — extend `_attached_images` to `list[tuple[str, str]]`; update `get_attached_images` to return list of (b64, mime) tuples. The UI-level attachment label is unchanged.
6. **Modify `ui/main_window.py`** — new toolbar buttons, three-state startup, `_scan_models`, `send_message` (drop `model=`), `_on_close` (call `stop_server`), and import the new modules.
7. **Run the full test suite again** — UI AST checks pass against the new layout.
8. **Delete `core/ollama_client.py`, `core/ollama_runner.py`, `tests/core/test_ollama_client.py`, `tests/core/test_ollama_runner.py`** — last step, so the old surface never coexists with the new in a "shippable" commit.
9. **Run the full test suite** — final check. All green.
10. **Bump version** to `0.2.0` in `pyproject.toml` and add a `CHANGELOG.md` entry.

Each step produces a focused commit. Commit 8 (the delete) is the only one that intentionally breaks the build for an instant — keep it separate so revert is one command.

## 12. Open risks

1. **Windows process termination behavior** — `subprocess.Popen.terminate()` on Windows calls `TerminateProcess`, which is the right escape hatch; but if the process is hung in a syscall, the 5-second wait may not be enough. Mitigated by the explicit `kill()` fallback. WSL tests cannot exercise this; the `[windows-only]` verify task must cover it.
2. **SSE parser edge cases in `iter_lines`** — what if `llama-server` emits a single `data: [DONE]` with no trailing newline? `iter_lines` should still yield it as a complete line, but we have no test for that specific edge case. The `test_chat_stream_handles_partial_chunks` test should also cover a final `data: [DONE]` without a trailing newline.
3. **Image MIME inference in `chat_panel`** — the current code does not record the MIME; it just stores base64. The `attach_file` method must be updated to store `(b64, mime)` pairs. If we miss any call site that constructs `_attached_images` directly, the migration will fail at runtime. Mitigation: keep the public `get_attached_images` API change small and tested via the AST checks.
4. **MIME defaulting** — when we cannot infer the MIME (e.g. an extension we don't recognize), we default to `image/jpeg`. Most `llama-server` builds accept this, but a strict model might reject it. The `attach_file` should probably accept only `jpg/jpeg/png/bmp/gif` (current behavior) and reject other extensions loudly.
5. **Strict TDD + the deletion commit** — REQ-LLAMA-016 mandates that the test files be renamed. If we delete `test_ollama_client.py` before `test_llama_client.py` is complete, the suite fails to collect. Apply agent MUST keep both test files until step 8.
6. **Race in `_on_close` → `stop_server`** — `MainWindow._on_close` is a wx handler; `stop_server` is a blocking call (5s wait + kill). This will block the UI thread during shutdown. Acceptable: the app is closing, no one is waiting. Documented in code comment.
7. **The `wx.MessageDialog.ShowModal()` is blocking** — fine on shutdown, but the "not installed" dialog at startup is also modal. Documented as the only modal flow; subsequent states use non-modal status bar + speech.
8. **`_on_close` is not currently bound in the wx event table** — apply phase must add `self.Bind(wx.EVT_CLOSE, self._on_close)` explicitly. Easy to forget.

## Skill resolution

- `paths-injected` — `sdd-design` and `_shared` were loaded from `/home/ic_ma/.config/opencode/skills/` per orchestrator injection.
