# Proposal: migrate-llama-cpp

## Why
Ollama is a long-running daemon that serves any model on demand. The user wants to run local `.gguf` files directly via `llama-server` (llama.cpp's OpenAI-compatible HTTP server on port 8080) so there is no extra daemon to install, fine-grained control over `--ctx-size` and `--n-gpu-layers`, and direct `.gguf` portability. This is a **backend swap**, not a redesign: the UI structure, accessibility rules, sampling controls, and architecture stay; only the transport changes from NDJSON-over-Ollama to SSE-over-llama.cpp.

## What changes
- **`core/llama_client.py` (NEW)** — `LlamaClient(base_url, session)` with `check_running()` (GET `/health`, status 200 + `{"status": "ok"}`), `get_loaded_model()` (GET `/v1/models` → first `id`), `chat_stream(messages, options, on_token, on_done, on_error)` (no `model=` param; hardcodes `"model": "local"` in body), `abort()` (threading.Event). Threading model: daemon `threading.Thread`, local `import wx` inside `_stream_worker`, all callbacks via `wx.CallAfter`. SSE parser strips `data: `, ignores `data: [DONE]`, parses JSON, extracts `choices[0].delta.content`.
- **`core/llama_runner.py` (NEW)** — `find_llama_server() -> str | None` (PATH probe, with `winget` install hint fallback), `find_gguf_models(extra_paths: list[str] = None) -> list[str]` (recursive scan of 5 standard dirs + extras, sorted by basename), `start_server(model_path, client, port=8080, ctx_size=4096, n_gpu_layers=99, timeout=60.0) -> (bool, str)`, `stop_server() -> None`, `get_install_command() -> "winget install ggml.llamacpp"`. Module-level `_server_process: subprocess.Popen | None` for PID tracking. `--jinja` always passed.
- **`core/ollama_client.py` (DELETE)**, **`core/ollama_runner.py` (DELETE)** — no shim. Per user decision; full migration.
- **`ui/params_panel.py` (MODIFY)** — `wx.Choice` → `wx.ComboBox` (name `model_selector`). Internal `_basename_to_path: dict[str, str]`. Display basenames only. `get_model() -> str` returns full path. New buttons: `scan_models_button` ("Buscar modelos") + `browse_model_button` ("Explorar...", opens `wx.FileDialog` with `*.gguf` wildcard). StaticText label `"Modelo (.gguf):"`. Replaces `refresh_models_button`.
- **`ui/main_window.py` (MODIFY)** — Rename "Iniciar Ollama" → "Iniciar servidor". ADD `stop_server_button` ("Detener servidor", disabled when not running). Rename `_refresh_models` → `_scan_models`, announces count. New handler `_on_stop_server`. Three-state startup check: `find_llama_server() is None` → dialog + voice "llama-server no instalado, instalalo con winget install ggml.llamacpp"; `check_running() is False` → voice "Servidor detenido. Seleccioná un modelo y pulsá Iniciar servidor"; else → "Conectado" + announce loaded model. `send_message` drops `model=` kwarg.
- **`ui/chat_panel.py` (TOUCH)** — `send_message` builds messages in OpenAI content-array format when images present. Image messages become `{"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}}]}`. No `images=` kwarg.
- **`tests/core/test_llama_client.py` (REWRITE)** + **`tests/core/test_llama_runner.py` (REWRITE)** — new test files, mirror `mock_session` + `mock_call_after` pattern, add SSE-specific scenarios (`[DONE]` terminator, partial chunks, malformed JSON).
- **`tests/ui/*_static.py`** — no change expected.
- **`openspec/specs/ollama-integration/spec.md`** — REPLACED by `openspec/specs/llama-integration/spec.md` (NEW). Archive flow removes old.
- **`AGENTS.md` (UPDATE)** — module map, runner description, server states.
- **`pyproject.toml`** — no dep change. `requests` stays.
- **`README.md` (UPDATE)** — winget install command, `.gguf` locations.
- **`CHANGELOG.md` (UPDATE)** — `[0.2.0]` entry.

## Decisions made
- **Image attachments: PRESERVE** — map `images: list[str]` (base64) to OpenAI `content` array with `image_url` blocks. Dropping is a regression; llama.cpp supports it natively.
- **Server restart on model change: `start_server` calls `stop_server()` first** if a process is alive, then spawns fresh. Atomic from the caller's perspective.
- **Startup timeout: 60s default** (per function signature). Polling 0.2s. The 30s number was a brief typo; 60s is more forgiving for large models.
- **`find_gguf_models`** — confirmed name, signature `(extra_paths: list[str] = None) -> list[str]` of full paths, sorted by basename.
- **`params_panel.get_model()`** — returns full path; basename shown in ComboBox; internal `_basename_to_path` dict.
- **Backward compat: DELETE old files**, no shims. Per brief.

## Architecture shift
llama-server serves **one model at a time**, set at startup via `--model`. This is the non-mechanical bit:

| Aspect | Ollama (was) | llama-server (now) |
|---|---|---|
| Daemon | Always-on, multi-model | One process per model |
| Model selection | `list_models()` over HTTP | Filesystem scan for `.gguf` |
| "Start server" | Cheap, instant | 10–60s for large models |
| "Stop server" | Did not exist | Required; frees VRAM |
| Selector widget | `wx.Choice` of names | `wx.ComboBox` of file paths |
| Voice announcements | Per state change | **Critical** at every transition |

## Affected user-facing flows
1. **Startup** — check `find_llama_server()` → if `None`, dialog + voice "llama-server no instalado, instalalo con winget install ggml.llamacpp". If installed but not running, voice "Servidor detenido. Seleccioná un modelo y pulsá Iniciar servidor". If running, "Conectado" + announce loaded model.
2. **First chat** — pick `.gguf` (ComboBox / type / "Explorar...") → "Iniciar servidor" → voice "Cargando modelo..." while polling `/health` → "Modelo listo" → send.
3. **Switch model** — pick new `.gguf` → "Iniciar servidor" → `stop_server()` then `start_server()` → voice "Reiniciando servidor con modelo nuevo".
4. **Scan models** — "Buscar modelos" → `find_gguf_models()` → ComboBox repopulates → voice "N modelos encontrados".

## Out of scope
- Multi-model simultaneous serving (llama-server limitation by design)
- UI for `--n-gpu-layers` (hardcoded 99; system auto-fits)
- UI for `--ctx-size` (hardcoded 4096; SUGGESTION in verify)
- PyInstaller / distribution
- Renaming the `ollamachat` package
- New UI features beyond backend swap
- Tool calling / PowerShell execution (separate future change)

## Risks
- **Subprocess lifecycle on Windows** — `CREATE_NO_WINDOW`, `Popen.poll()`, graceful `terminate()` (5s) then kill. WSL tests can't cover this → `[windows-only]` verification.
- **SSE parser edge cases** — `data:` line spanning multiple `recv()` calls, partial JSON, malformed JSON, `[DONE]` terminator, blank lines. Each gets a focused test.
- **Image migration** — could break flows the explore didn't surface. Mitigation: apply phase writes a round-trip test through `chat_stream`.
- **Strict TDD** — orchestrator must not allow implementation without a failing test first.

## Acceptance criteria
- `uv run --no-sync pytest -xvs` passes in WSL (all core + AST + smoke).
- All 9 AGENTS.md accessibility rules honored in new `params_panel` and `main_window`.
- `find_gguf_models` returns deterministic, sorted list (by basename).
- `start_server` returns `(True, msg)` when server is already responding (no duplicate Popen).
- `stop_server` is idempotent.
- `chat_stream` aborts between chunks when `abort()` called.
- SSE parser handles: data lines, `[DONE]`, blank lines, partial chunks, malformed JSON (skips).
- `stop_server_button` disabled when not running, enabled when running.

## Verification plan
- **WSL**: `uv run --no-sync pytest -xvs` — 100% pass. Includes new `test_llama_client.py` + `test_llama_runner.py`.
- **WSL**: AST checks on `ui/` continue to pass.
- **Windows** `[windows-only]`: install llama-server via winget, point at a real `.gguf`, start, chat, switch model, stop. 4 manual tasks.

## Rollback
- Git revert the migration commit. Old Ollama code is in history.
- During the change window, users see "llama-server no instalado" with the install command in the dialog.
- If Windows-only verification finds a critical break, revert and report the migration is blocked.

## Skill resolution
- **paths-injected** — `sdd-propose` content was provided inline by the orchestrator; loaded `cognitive-doc-design` from `/home/ic_ma/.config/opencode/skills/`.
