# Explore: migrate-llama-cpp

## Status
complete

## Current Ollama integration — interface map

### OllamaClient (ollamachat/core/ollama_client.py)

**Class signature:**
```python
class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        session: requests.Session | None = None,
    ) -> None
```

**Public methods (exact signatures):**

1. `check_running(self) -> bool`
   - GET `{base_url}/api/tags`, timeout=5
   - Returns True if status == 200, False on any exception or non-200
   - No side effects, no state mutation

2. `list_models(self) -> list[str]`
   - GET `{base_url}/api/tags`, timeout=5
   - Parses `models[].name` from JSON
   - Returns `[]` on any failure (never raises)

3. `chat_stream(self, model: str, messages: list[dict], options: dict[str, Any],
                  on_token: Callable[[str], None],
                  on_done: Callable[[], None],
                  on_error: Callable[[str], None]) -> None`
   - POST `{base_url}/api/chat` with body `{"model", "messages", "stream": True, "options"}`
   - Spawns daemon `threading.Thread` and returns immediately (non-blocking)
   - Parses NDJSON lines from `response.iter_lines()`
   - All callbacks go through `wx.CallAfter` (imported inside `_stream_worker` to keep core/ pythonically wx-free at module level)

4. `abort(self) -> None`
   - Sets `self._stop_event` (threading.Event)
   - Checked between NDJSON lines: if set, exits loop → fires `on_done` (NOT on_error)

**Threading model:**
- `_stop_event = threading.Event()` created in `__init__`
- `_stream_thread: threading.Thread | None = None`
- `chat_stream` clears the event, creates and starts a new daemon thread
- The thread imports `wx` locally (to avoid top-level wx dependency in core/)
- All callbacks marshalled via `wx.CallAfter(fn, *args)`
- The `on_done` callback fires even on abort (after the loop exits)

**Error handling pattern:**
- `check_running` / `list_models`: blanket `except Exception: return False/[]` — silent, no logging
- `_stream_worker`: wraps entire body in `try/except Exception`, calls `on_error` with `f"{type(e).__name__}: {e}"`
- Second `try/except` around `wx.CallAfter(on_error, ...)` as last resort if wx is shutting down

### OllamaRunner (ollamachat/core/ollama_runner.py)

**`start_ollama` signature:**
```python
def start_ollama(
    client: OllamaClient, timeout: float = 5.0
) -> tuple[bool, str]:
```

**Return tuple shape:**
- `(True, "Ollama ya está corriendo")` — if already running (no spawn)
- `(True, "Ollama listo")` — if spawn succeeded and server came up within timeout
- `(False, "No se pudo iniciar Ollama: {e}")` — on Popen/OSError
- `(False, "Ollama no responde")` — if timeout expired without server becoming ready

**Polling logic:**
1. Fast path: `client.check_running()` → if True, return immediately
2. Otherwise: `_spawn_ollama()`
3. Poll `client.check_running()` every 0.2s for up to `timeout` seconds (default 5.0)
4. 25 attempts maximum at default timeout

**Subprocess spawn:**
- `subprocess.Popen(["ollama", "serve"], stdout=DEVNULL, stderr=DEVNULL, stdin=DEVNULL)`
- On Windows: adds `creationflags=0x08000000` (CREATE_NO_WINDOW)
- Raises `FileNotFoundError` if binary not on PATH (caught by start_ollama)

**No stop/terminate method exists.** Once spawned, the subprocess is detached and never managed by the app. There is no `stop_server`, no `process.terminate()`, no PID tracking.

**No `get_ollama_command()` generalization:** returns `["ollama", "serve"]` unconditionally — not designed for alternate server binaries.

**Poll interval constant:** `_POLL_INTERVAL_SECONDS = 0.2` (exported, tested)

### MainWindow integration

**Construction of `OllamaClient`:**
```python
self._client = OllamaClient()  # default base_url, no session override
```
- Hardcoded: no config file, no env var, no way to change the endpoint at startup

**Startup check (`_startup_check`):**
- Calls `self._client.check_running()`
- If True: status bar field 0 → "Conectado", speech says "Conectado", calls `_refresh_models()`
- If False: status bar field 0 → "Desconectado", speech says the "No se puede conectar" message, shows `wx.MessageDialog` with wxOK | wxICON_WARNING

**Start Ollama button handler (`_on_start_ollama`):**
- Status bar field 0 → "Iniciando Ollama..."
- Speech: "Iniciando Ollama"
- Calls `start_ollama(self._client)` (blocking — freezes UI for up to 5s)
- Speech: result `message` text
- If ok: status bar field 0 → "Conectado"; refreshes models unless message contains "ya está"
- If not ok: status bar field 0 → "Error"

**Button labels and names (current):**
| Label | name= | Purpose |
|---|---|---|
| "Iniciar Ollama" | `start_ollama_button` | Start server (toolbar) |
| "Enviar" | `send_button` | Send message |
| "Detener" | `stop_button` | Abort generation |
| "Limpiar" | `clear_button` | Clear conversation |
| "Adjuntar" | `attach_button` | Attach file |
| "Actualizar modelos" | `refresh_models_button` | Refresh model list |

**Send message flow (`send_message`):**
1. Read input text from ChatPanel
2. Build messages list: system prompt (if any) + conversation history + new user message (with attached images/text)
3. Add user message to Conversation, append to display
4. Read model from `params_panel.get_model()` and options from `params_panel.get_params()`
5. Initialize `self._current_response = ""`
6. Call `chat_panel.start_generation()` (disables send/attach, enables stop)
7. Call `chat_panel.append_assistant_prefix()`
8. Set status bar field 2 → "Generando respuesta...", speech "Generando respuesta..."
9. Call `self._client.chat_stream(model, messages, options, on_token, on_done, on_error)`

**Speech announcements:**
- Startup: "Conectado" or "No se puede conectar a Ollama en http://localhost:11434..."
- Start button: "Iniciando Ollama" → result message (e.g. "Ollama listo")
- Send: "Generando respuesta..."
- Per token: `_speech.announce_token_chunk(token)` (buffered per `Speech`)
- On done: "Respuesta completa"
- On error: error_text via speech + wx.MessageDialog

### ParamsPanel model selector

**Current widget: `wx.Choice`**
```python
self.model_selector = wx.Choice(self, name="model_selector")
```

**Population (`set_models`):**
```python
def set_models(self, models: list[str]) -> None:
    self.model_selector.Clear()
    for model_name in models:
        self.model_selector.Append(model_name)
    if models:
        self.model_selector.SetSelection(0)
```

**Readback (`get_model`):**
```python
def get_model(self) -> str:
    sel = self.model_selector.GetSelection()
    if sel == wx.NOT_FOUND:
        return ""
    return self.model_selector.GetString(sel)
```

**Sampling controls exported via `get_params()`:**
```python
def get_params(self) -> dict:
    return {
        "temperature": self.temperature_slider.GetValue() / 100.0,  # 0-2.0, default 0.70
        "num_predict": self.max_tokens_spin.GetValue(),             # 64-8192, default 512
        "top_p": self.top_p_slider.GetValue() / 100.0,             # 0-1.0, default 0.90
        "top_k": self.top_k_spin.GetValue(),                        # 1-200, default 40
        "repeat_penalty": self.repeat_penalty_slider.GetValue() / 100.0,  # 1.0-2.0, default 1.10
    }
```

**CRITICAL:** Ollama uses `num_predict`; llama.cpp uses `max_tokens`. The `get_params()` keys must be renamed in the outgoing dict (not the UI labels) to match the OpenAI-compatible API.

### ChatPanel surface area (backend-facing)

- `start_generation()`: disables send + attach buttons, enables stop button
- `end_generation()`: enables send + attach, disables stop
- `send_button`: label "Enviar", name "send_button"
- `stop_button`: label "Detener", name "stop_button"
- `clear_button`: label "Limpiar", name "clear_button"
- `attach_button`: label "Adjuntar", name "attach_button"
- `get_input_text() -> str`
- `get_attached_images() -> list[str]`
- `get_attached_text() -> str | None`
- `append_user_message(text)`
- `append_assistant_prefix()`
- `append_assistant_chunk(token)`
- `_clear_input()`
- `clear_attachment()`

No backend-visible changes needed in ChatPanel except the stop_button already exists and is reused — no new button needed on this panel for the migration. The new `stop_server` button goes on the toolbar in MainWindow, not here.

### Current spec (ollama-integration/spec.md)

**Structure:**
1. Purpose paragraph
2. Requirements (9 total), each with:
   - Requirement heading
   - RFC 2119 prose
   - 1-3 Given/When/Then scenarios per requirement
3. Total scenarios: 16

**Requirements coverage:**
1. Default Base URL and Construction — 2 scenarios
2. Health Check (`check_running`) — 3 scenarios
3. Model Listing (`list_models`) — 3 scenarios
4. Streaming Chat (`chat_stream` signature) — 3 scenarios
5. Abort Semantics (`abort()`) — 2 scenarios
6. Thread-safe Callback Marshalling — 2 scenarios
7. Sampling Options — 2 scenarios
8. Vision (Images) — 2 scenarios

**Key observation:** The spec is API-shape-specific (e.g. `GET /api/tags`, `POST /api/chat`, `models[].name`). A migration to llama.cpp means this entire spec file gets replaced or rewritten, not delta-patched.

### Current tests

**test_ollama_client.py (427 lines, 14 tests):**

Mocking patterns:
- `_ensure_wx_module()` module-level function creates a fake `wx` module with `CallAfter`
- `ensure_wx` fixture (autouse=True) ensures wx is available
- `mock_session` fixture: `Mock(spec=requests.Session)`
- `mock_call_after` fixture: patches `wx.CallAfter` with a fake that records calls and invokes immediately
- Tests call `time.sleep(0.1)` after `chat_stream` to let the daemon thread finish
- For abort tests: a generator with `time.sleep(0.005)` per line simulates slow stream
- All assertions use `call_count` and `call_args_list`

Naming convention: `test_<method>_<scenario>` (e.g. `test_check_running_ok`, `test_abort_stops_stream`, `test_full_options_forwarded`)

**test_ollama_runner.py (145 lines, 8 tests):**

Mocking patterns:
- `client = MagicMock()` with `check_running.return_value = True/False` or `side_effect`
- `patch("ollamachat.core.ollama_runner.subprocess.Popen")` to intercept subprocess
- No wx dependency at all (runner is wx-free by design)

Naming convention: `test_start_ollama_<scenario>`

**Total: 22 tests in core/ for the Ollama integration surface.**

## What the brief asks for — verification

The exploration confirms and adds precision to the brief's key facts:

- **llama-server endpoint shape:** `/health` (health check), `/v1/models` (model listing), `/v1/chat/completions` (chat stream with SSE). Current `check_running` hits `GET /api/tags` — must change to `GET /health`. Current `list_models` parses `models[].name` — must parse the OpenAI `/v1/models` response. Current `chat_stream` posts to `POST /api/chat` with NDJSON — must post to `POST /v1/chat/completions` and parse SSE (`data: ...` lines instead of raw NDJSON).
- **chat_stream signature change:** The `model=` parameter is part of the URL path in llama.cpp's v1 API variant, NOT the request body. Actually, in OpenAI-compatible API, `model` goes in the request body as `"model": "..."`. So the parameter stays — but the body shape differs: `{"messages": [...], "stream": true, "model": "...", "max_tokens": N, "temperature": ...}`. The `options` dict is flattened into the body top-level keys. **Clarification needed**: whether `model` param stays or goes depends on the exact API shape.
- **Winget install ID:** `ggml.llamacpp` — no code concern, affects docs only
- **.gguf discovery locations (5 standard paths):** The model selector will need to scan these paths and present `.gguf` files. The current model list came from `GET /api/tags`. New flow: scan `models/` dirs for `.gguf` files → populate wx.ComboBox.
- **UI selector switches from wx.Choice to wx.ComboBox:** Confirmed — allows typing a .gguf path directly. Must maintain `name="model_selector"` and `StaticText` preceding it.
- **`stop_server` button must be added:** Goes on the toolbar next to `start_ollama_button` in MainWindow. Current code has `start_ollama_button` with label "Iniciar Ollama". New: rename label to "Iniciar llama-server" and add "Detener servidor" button.
- **New tests must mirror existing patterns:** Same `requests.Mock` + `mock_call_after` pattern for the client, same `MagicMock` + `patch("subprocess.Popen")` for the runner.

**Key difference from brief:** The `chat_stream` method still takes a `model` parameter — OpenAI API puts `model` in the request body as a string field, so the signature can stay the same. But the `options` dict shape changes completely (no `num_predict`, use `max_tokens` instead; `repeat_penalty` becomes `repeat_penalty` but at top level).

## Open questions for proposal

1. **Model in API body vs separate param?** Current `chat_stream(model, messages, options, ...)` puts `model` as a top-level key. In the new llama.cpp client, `model` would be a server-level setting (passed via `--model` flag at launch), NOT per-request. Does the new client strip `model` from `chat_stream` entirely, or keep it for flexibility when the server serves multiple models?

2. **gguf file path list vs single server model?** When running `llama-server --model path/to/model.gguf`, the server loads ONE model. The model selector becomes a file picker / file scanner, not a list of loaded models. Can the user pick a .gguf to launch with, or does the model selector change to "choose which model the server loads, then restart"?

   This is THE BIGGEST DESIGN DECISION: is `llama-server` started once with a model and kept running (so changing the model requires a restart), or do we keep a long-running server and use the `POST /v1/chat/completions` model field? The brief says "model selector switches from wx.Choice to wx.ComboBox" which suggests the user can type/find a .gguf — but how does that interact with `llama-server`'s lifecycle?

3. **Parallel server vs single server?** Can the user have multiple llama-server instances for different models? The brief mentions "discovery locations" for .gguf files — is the selector "pick a .gguf to run now" or "pick from a list of available models"?

4. **`create_no_window` vs WSL behavior?** The migration targets Windows first. On WSL we can't test the GUI at all. Should we add a flag to skip GUI tests on Linux without wx?

5. **What about vision (images)?** llama.cpp's `llama-server` supports multimodal via the same OpenAI API (`/v1/chat/completions` with `content: [{type: "text", text: "..."}, {type: "image_url", image_url: {url: "data:image/jpeg;base64,..."}}]`). The migration must change the image format from Ollama's `images` key to OpenAI's `content` array with `image_url`. This is a deeper change than the brief suggests.

6. **OllamaRunner is now LlamaRunner — what about the `ollama serve` process management?** The subprocess command changes from `["ollama", "serve"]` to something like `["llama-server", "--host", "127.0.0.1", "--port", "8080", "--model", "/path/to/model.gguf"]`. The model becomes a startup argument. This ties the model selector to the server lifecycle: changing the model means stopping and restarting `llama-server`.

7. **Default port change?** Ollama defaults to `:11434`. llama-server defaults to `:8080`. The `base_url` in the new client should probably change to `http://localhost:8080`.

## Risks / gotchas

1. **Threading + CallAfter pattern is fragile and MUST be preserved exactly.** The current client imports `wx` inside `_stream_worker` (line 113) to keep `core/` wx-free at module level. Any refactor of the streaming worker must keep this pattern.

2. **SSE parsing is more complex than NDJSON.** llama.cpp's `llama-server` uses Server-Sent Events (`data: {"content":"...","stop":false}\n\n`). The streaming loop must:
   - Strip the `data: ` prefix from each line
   - Check for `data: [DONE]` as the termination signal (not `"done": true`)
   - Handle empty lines (SSE event separators)
   - The `on_done` callback must fire when `[DONE]` is received, not at the end of `iter_lines()`

3. **`num_predict` → `max_tokens` rename in `get_params()`.** The params dict keys need to change. Ollama uses `num_predict`, llama.cpp uses `max_tokens`. The `get_params` method in ParamsPanel currently returns Ollama keys. The UI labels ("Máximo de tokens") stay the same, but the dict key changes.

4. **`repeat_penalty` parameter exists in both APIs** — same key, same semantics. No rename needed for this one. But for OpenAI-compatible API, it goes at the top level of the body alongside `temperature`, `max_tokens`, not inside an `options` sub-dict.

5. **The `list_models` → `find_gguf_files` semantic change is significant.** `list_models()` previously returned model names from the server. The new method will scan directories for `.gguf` files. Two possible approaches:
   - Filesystem scan only (no server interaction needed)
   - Server health check + filesystem scan combined
   Either way, the return type stays `list[str]` but the semantics change from "remote API call" to "local filesystem scan".

6. **The health check endpoint changes shape.** `GET /health` returns `{"status": "ok"}` (or similar), not a HTTP 200 with model list. The migration could either:
   - Create a separate health check endpoint call (`GET /health`)
   - Reuse a simple endpoint like `GET /v1/models` and check for 200
   Either works, but the mock/spec must change.

7. **stop_server is a new subprocess management concern.** The current code spawns and forgets. The new code needs PID tracking + `process.terminate()` + cleanup. This is the riskiest new code because:
   - Windows process termination differs from Unix
   - Race conditions on terminate + restart
   - The `start_ollama` timeout polling pattern must adapt for llama-server startup time

8. **The specs file is entirely replaced, not delta-patched.** The current `openspec/specs/ollama-integration/spec.md` describes Ollama-specific endpoints (`/api/tags`, `/api/chat`, `models[].name`). The migration creates a new spec (or a new capability domain: `llama-cpp-integration`). The archive phase must know to obsolete/remove the old spec.

## Executive summary

The migration from Ollama to llama.cpp is a **medium-to-high complexity change** that touches every layer of the backend client while leaving the UI structure mostly intact. The streaming client (`OllamaClient`) needs a full rewrite of its HTTP calls (endpoints, body shape, SSE parsing), while the runner (`OllamaRunner`) needs subprocess PID tracking and terminate support — the current spawn-and-forget pattern won't work. The highest-risk area is the **model-server lifecycle relationship**: changing models requires restarting `llama-server`, which is a UX departure from Ollama's always-running daemon model. The threading/`CallAfter` marshalling pattern is the most fragile part of the codebase and must be preserved exactly. The UI controls (params panel, chat panel, toolbar buttons) only need label/text changes plus one new button. Test coverage must be preserved and expanded: the current 22 tests establish a clear mocking pattern that the new code should follow. The brief's biggest unaddressed question is whether `model` stays as a per-request parameter or becomes a server startup argument — this decision drives the entire architecture.

## Skill resolution
- **paths-injected** — loaded `sdd-explore` and `_shared` from `/home/ic_ma/.config/opencode/skills/` per orchestrator injection
