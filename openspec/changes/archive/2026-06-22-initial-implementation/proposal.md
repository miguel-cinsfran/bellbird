# Proposal: Initial Implementation of OllamaChat

## Intent

OllamaChat is a Windows 11 desktop chat client for completely blind users (NVDA, JAWS) to talk to local Ollama LLMs. Web chat UIs and terminal CLIs fail screen-reader users; existing Ollama front-ends ignore accessibility. This change ships the first usable MVP: pick a model, send a message, hear the answer streamed via accessible-output2, attach images, save/reload conversations. Accessibility is the requirement, not a feature.

## Scope

### In Scope
- `main.py` entry, `wx.App` + `MainWindow` 1100x700.
- Core: `OllamaClient` (REST + NDJSON streaming + abort), `Conversation` (JSON persistence), `Speech` (accessible-output2 wrapper, never-crash).
- UI: `MainWindow` (splitter, menus, status bar, accelerators, startup check), `ParamsPanel` (model + sampling controls), `ChatPanel` (display, input, send, stop, clear, attach, attachment label).
- Vision: jpg/jpeg/png/bmp/gif → base64 into Ollama `images`; other files → UTF-8 text.
- Persistence: conversations to `data/` as UTF-8 JSON `indent=2`.
- Speech: token chunking (sentence boundary, 80-char fallback), interrupt, "Respuesta completa" on done.
- Keys: Ctrl+N/O/S, F5, Escape, Enter, Shift+Enter, Alt+F4.
- Blind-user README, `pyproject.toml`, `uv init`, pytest, `.gitignore`, `AGENTS.md`, git init.
- Strict-TDD tests for `core/` (no wx) + smoke test for `Speech`.

### Out of Scope
Cloud LLMs, multi-user, auth, telemetry. Mobile/web. Model download UI. Theming. Search/tagging. Plugins. Auto-update.

## Capabilities

> Contract with `sdd-spec`. No existing specs — all new.

### New Capabilities
- `chat`: display, input, send/stop/clear/attach, file dialog, attachment label, `[Usuario]` / `[Asistente]` prefixes, key handling.
- `ollama-integration`: `check_running`, `list_models`, `chat_stream` (NDJSON, `Thread` + `Event`, `wx.CallAfter`), options (temperature, num_predict, top_p, top_k, repeat_penalty), vision `images`.
- `parameters`: `ParamsPanel` controls + `get_params` / `get_model` / `get_system_prompt` / `set_models`, real-time labels, slider speech feedback.
- `conversation-persistence`: `Conversation` (role, content, timestamp, optional images), `to_dict` / `from_dict`, classmethod `save` / `load`, `clear`.
- `speech`: `Speech` over `accessible_output2.outputs.auto.Auto`, `speak` / `output` / `stop` / `announce_token_chunk` (sentence boundary, 80-char fallback) / `flush_token_buffer`, never-crash.
- `accessibility-guidelines`: every control has `name=`, preceded by `wx.StaticText` label, only `wx.BoxSizer` (no grid), sliders update labels + `speech.speak(..., interrupt=False)`, status bar + error dialogs also speak.
- `app-shell`: `MainWindow` with `wx.SplitterWindow` (left 280px), menu bar (Archivo, Ayuda), `wx.AcceleratorTable`, status bar, startup Ollama check, save/load dialogs.

### Modified Capabilities
None.

## Approach

- **GUI**: `wxPython 4.2+` (native Win32, MSAA, no WebView).
- **Speech**: `accessible-output2` `auto` output; every exception swallowed.
- **Streaming**: `requests` POST `/api/chat` `stream=True`, line-buffered NDJSON, `on_token` via `wx.CallAfter`, `threading.Event` abort between lines; one daemon thread per generation.
- **Persistence**: stdlib `json`, `encoding="utf-8"`, `indent=2`.
- **Vision**: extension check → image bytes base64-encoded; else read as UTF-8 text into message body; filename announced via `speech.speak`.
- **TDD**: strict RED-GREEN-REFACTOR; `core/` wx-free; `Speech` smoke-tested with mocked `auto` output.
- **Layout**: keep `ollamachat/{core,ui,data}/` (see Open Questions).
- **Python**: 3.12 only, UV-managed.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `ollamachat/main.py` | New | App entry, 1100x700 |
| `ollamachat/core/{ollama_client,conversation,speech}.py` | New | Headless logic |
| `ollamachat/ui/{main_window,chat_panel,params_panel}.py` | New | wx widgets |
| `ollamachat/data/` | New | Runtime persistence (gitignored) |
| `ollamachat/{requirements.txt,README.md}` | New | Pinned deps; blind-user docs |
| `pyproject.toml`, `.gitignore`, `AGENTS.md` | New | UV; exclude `.atl/`, `opencode.json*`, `data/`, `__pycache__/`, `.venv/`; project agent rules |
| `tests/core/` | New | pytest suite, no wx |
| `openspec/changes/initial-implementation/` | New | SDD artifacts |

## Risks

| Risk | L | Mitigation |
|-----|---|------------|
| WSL has no wx display | H | `core/` tested headlessly; UI verified manually on Windows |
| accessible-output2 diff WSL vs Windows | M | `Speech` swallows all exceptions |
| Vision model compatibility | M | Pass `images` only when attached; README notes vision model required (e.g. `llava`) |
| MSAA labeling pitfalls (grid sizers, missing `name=`) | M | Codified in `accessibility-guidelines` |
| Non-image file attach | L | Fallback: read as UTF-8 text into message body |
| Ollama schema drift | L | Target documented NDJSON; errors via `on_error` + status bar |
| `Event` abort race with in-flight line | L | Checked between lines |

## Rollback Plan

No prior version. To abandon, delete `openspec/changes/initial-implementation/`. Once committed: `git reset --hard HEAD~1` (or delete feature branch). No migrations, no API contracts.

## Dependencies

- Ollama at `http://localhost:11434`.
- Python 3.12 via UV 0.11.17.
- Runtime: `wxpython>=4.2`, `accessible-output2>=0.17`, `requests>=2.31`. Dev: `pytest`, `pytest-cov` (coverage).
- No cloud, no Docker, no internet at runtime.

## Success Criteria

- [ ] `uv run python -c "import ollamachat"` imports cleanly.
- [ ] `uv run pytest -xvs` passes for all `core/` (no wx import).
- [ ] `Speech` smoke test confirms graceful degradation on TTS failure.
- [ ] `OllamaClient.chat_stream` test: NDJSON dispatch, `wx.CallAfter`, `stop_event`, single `on_done` / `on_error`.
- [ ] `Conversation.save` / `load` round-trip with and without images.
- [ ] Manual NVDA verification on Windows 11 (user-driven).
- [ ] README is plain text, flat shortcut list, no marketing speak.
- [ ] `.gitignore` excludes `.atl/`, `opencode.json*`, `data/`, `__pycache__/`, `.venv/`, `*.egg-info/`.
- [ ] `AGENTS.md` documents a11y rules, TDD expectation, never-crash contract.
- [ ] Scaffolding is part of implementation tasks, not pre-proposal.

## Open Questions (resolved)

- **Directory structure**: user marked `ollamachat/{core,ui,data}/` as *optional*. **Resolution: keep it.** Textbook separation — `core/` headless + testable, `ui/` wx, `data/` runtime. Refining would add ceremony without benefit. Orchestrator decided based on actual fit: this layout is the minimum needed to separate testable from non-testable code, and any refinement would add layers without solving a real problem.
- **AGENTS.md**: user asked to "consider" it. **Resolution: include** a short file with a11y rules, TDD expectation, never-crash contract.
- **ruff + mypy**: dev tools with permissive config. **Resolution: drop** for the MVP. `sdd-verify-gentleman` + strict TDD cover the value these would add; the project is small enough that style/type noise would outweigh the benefit. Can be added later in 5 minutes if needed.
