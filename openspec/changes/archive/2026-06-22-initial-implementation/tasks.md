# Tasks: Initial Implementation of OllamaChat

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2000 lines (22 new files) |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | Single PR (user-approved C2) |
| Delivery strategy | single-pr-default |
| Chain strategy | not_applicable |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: not_applicable
400-line budget risk: High

**Note**: User explicitly approved single PR despite budget risk. Proceed with single PR as decided.

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Full MVP implementation | PR 1 (single) | All 22 files; user-approved exception |

---

## Phase 1: Scaffolding

### 1.1 Initialize pyproject.toml
**Description**: Create project configuration with UV-managed dependencies.
**Files**: `pyproject.toml`
**Content**:
```toml
[project]
name = "ollamachat"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "wxpython>=4.2",
    "accessible-output2>=0.17",
    "requests>=2.31"
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-xvs --no-header --no-cov-on-fail"
```
**Verification**: `uv sync` succeeds, `uv run python -c "import ollamachat"` fails (package not created yet)

### 1.2 Create package skeleton
**Description**: Create directory structure and `__init__.py` files.
**Files**:
- `ollamachat/__init__.py` (empty)
- `ollamachat/core/__init__.py` (empty)
- `ollamachat/ui/__init__.py` (empty)
- `ollamachat/data/` (empty directory, gitignored)
**Verification**: `uv run python -c "import ollamachat; import ollamachat.core; import ollamachat.ui"` succeeds

### 1.3 Create pytest config + tests skeleton
**Description**: Create test directory structure.
**Files**:
- `tests/__init__.py` (empty)
- `tests/core/__init__.py` (empty)
- `tests/ui/__init__.py` (empty)
- `tests/smoke/__init__.py` (empty)
**Verification**: `uv run pytest --collect-only` runs without error (no tests yet)

### 1.4 Create .gitignore
**Description**: Exclude runtime artifacts.
**Files**: `.gitignore`
**Content**:
```
.atl/
opencode.json*
ollamachat/data/
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
*.tmp
```
**Verification**: File exists, `git status` ignores listed patterns

### 1.5 Create AGENTS.md
**Description**: Document project rules for AI agents.
**Files**: `AGENTS.md`
**Content**: Accessibility rules, TDD expectation, never-crash contract, no WebView, BoxSizer only.
**Verification**: File exists, contains key sections

### 1.6 Create requirements.txt
**Description**: Compatibility shim for non-UV users.
**Files**: `requirements.txt`
**Content**:
```
wxpython>=4.2
accessible-output2>=0.17
requests>=2.31
```
**Verification**: File exists, matches `pyproject.toml` dependencies

### 1.7 Create README.md
**Description**: Blind-user documentation, plain text, flat shortcut list.
**Files**: `README.md`
**Content**: Installation, usage, keyboard shortcuts, vision model note.
**Verification**: File exists, no markdown tables, no complex formatting

---

## Phase 2: Core — Speech (Strict TDD)

### 2.1 RED: Write failing tests for Speech
**Description**: Write comprehensive test suite before implementation.
**Files**: `tests/core/test_speech.py`
**Scenarios**:
- Constructor: `ImportError` → silent, `OSError` → silent, success → not silent
- `speak`: with output, silent mode, non-string text
- `output`: with output, silent mode
- `stop`: with output, silent mode
- `announce_token_chunk`: short token (no flush), sentence terminator (flush), 80-char fallback, question mark, newline
- `flush_token_buffer`: non-empty, empty
- Never-crash: `output.speak` raises → no exception, `output.output` raises → no exception
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/core/test_speech.py -xvs` fails with `ModuleNotFoundError`

### 2.2 GREEN: Implement Speech
**Description**: Implement `Speech` class to pass all tests.
**Files**: `ollamachat/core/speech.py`
**Implementation**:
- Constructor: try `Auto()`, catch all exceptions, set `is_silent`
- `speak`, `output`, `stop`: wrap in try/except, return None
- `announce_token_chunk`: accumulate in `_buffer`, flush on `.`, `?`, `!`, `\n` or `len > 80`
- `flush_token_buffer`: speak buffer if non-empty, clear
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/core/test_speech.py -xvs` passes

---

## Phase 3: Core — Conversation (Strict TDD)

### 3.1 RED: Write failing tests for Conversation
**Description**: Write comprehensive test suite before implementation.
**Files**: `tests/core/test_conversation.py`
**Scenarios**:
- `add_message`: user, assistant, with/without images
- `get_messages_for_api`: strips `timestamp`, preserves `images`
- `to_dict` / `from_dict`: round-trip with/without images
- `save` / `load`: round-trip, UTF-8, missing file → `FileNotFoundError`, atomic write (`.tmp` → target)
- `clear`: empties messages, allows re-use
- Images preserve order
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/core/test_conversation.py -xvs` fails with `ModuleNotFoundError`

### 3.2 GREEN: Implement Conversation
**Description**: Implement `Conversation` class to pass all tests.
**Files**: `ollamachat/core/conversation.py`
**Implementation**:
- `add_message`: append dict with `role`, `content`, `timestamp`, optional `images`
- `get_messages_for_api`: strip `timestamp`, preserve `images`
- `to_dict` / `from_dict`: serialize/deserialize
- `save`: write to `.tmp`, `Path.replace` (atomic)
- `load`: read JSON, `from_dict`
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/core/test_conversation.py -xvs` passes

---

## Phase 4: Core — OllamaClient (Strict TDD)

### 4.1 RED: Write failing tests for OllamaClient
**Description**: Write comprehensive test suite before implementation.
**Files**: `tests/core/test_ollama_client.py`
**Scenarios**:
- `check_running`: 200 OK → `True`, 503 → `False`, `ConnectionError` → `False`
- `list_models`: 2 models → list, empty → `[]`, error → `[]`
- `chat_stream`: NDJSON dispatch, `wx.CallAfter` wrapping, abort via `Event` between lines, single `on_done` / `on_error` fire
- Options forwarding: full dict, partial dict, no `null` values
- Vision: `images` key preserved, no `images` → no key
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/core/test_ollama_client.py -xvs` fails with `ModuleNotFoundError`

### 4.2 GREEN: Implement OllamaClient
**Description**: Implement `OllamaClient` class to pass all tests.
**Files**: `ollamachat/core/ollama_client.py`
**Implementation**:
- `check_running`: GET `/api/tags`, catch exceptions, return bool
- `list_models`: GET `/api/tags`, parse `{"models": [...]}`, return list
- `chat_stream`: spawn daemon `Thread`, POST `/api/chat` with `stream=True`, iterate `iter_lines()`, check `_stop_event` between lines, parse NDJSON, wrap callbacks in `wx.CallAfter`
- `abort`: set `_stop_event`
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/core/test_ollama_client.py -xvs` passes

---

## Phase 5: Smoke Test for Speech

### 5.1 Write smoke test for silent mode
**Description**: Verify `Speech` degrades gracefully when `accessible-output2` is missing.
**Files**: `tests/smoke/test_speech_silent.py`
**Scenarios**:
- `ImportError` on `accessible_output2` → `is_silent = True`
- `speak`, `announce_token_chunk` don't raise in silent mode
**Verification**: `uv run pytest tests/smoke/test_speech_silent.py -xvs` passes

---

## Phase 6: UI — ParamsPanel (wx-only)

### 6.1 RED: Write static AST tests for ParamsPanel
**Description**: Verify accessibility compliance via AST inspection (no wx runtime needed).
**Files**: `tests/ui/test_params_panel_static.py`
**Scenarios**:
- Import-only check (no wx instantiation)
- AST check: every control has `name=` parameter
- AST check: every control preceded by `wx.StaticText` label
- AST check: only `wx.BoxSizer` used (no grid sizers)
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/ui/test_params_panel_static.py -xvs` fails with `ModuleNotFoundError`

### 6.2 GREEN: Implement ParamsPanel
**Description**: Implement `ParamsPanel` to pass all tests.
**Files**: `ollamachat/ui/params_panel.py`
**Implementation**:
- Constructor: build UI with model selector, system prompt, sliders (temperature, top_p, repeat_penalty), spin controls (max_tokens, top_k)
- Every control: `name="widget_name"`, preceded by `wx.StaticText` label
- Only `wx.BoxSizer` (vertical + horizontal)
- Slider change handler: update label, `speech.speak(value, interrupt=False)`
- `get_model`, `get_system_prompt`, `get_params` methods
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/ui/test_params_panel_static.py -xvs` passes

### 6.3 [windows-only] Manual NVDA verification
**Description**: Verify slider speech feedback on Windows.
**Files**: None (manual test)
**Scenarios**:
- Tab to slider, NVDA announces label
- Change slider value, NVDA announces new value
**Verification**: Manual test on Windows 11 with NVDA

---

## Phase 7: UI — ChatPanel (wx-only)

### 7.1 RED: Write static AST tests for ChatPanel
**Description**: Verify accessibility compliance via AST inspection.
**Files**: `tests/ui/test_chat_panel_static.py`
**Scenarios**:
- Import-only check
- AST check: every control has `name=` parameter
- AST check: every control preceded by `wx.StaticText` label
- AST check: only `wx.BoxSizer` used
- AST check: no `wx.WebView`
- AST check: input uses `wx.TE_RICH2`
- AST check: `TE_PROCESS_ENTER` handler checks `ShiftDown()`
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/ui/test_chat_panel_static.py -xvs` fails with `ModuleNotFoundError`

### 7.2 GREEN: Implement ChatPanel
**Description**: Implement `ChatPanel` to pass all tests.
**Files**: `ollamachat/ui/chat_panel.py`
**Implementation**:
- Constructor: build UI with conversation display (`wx.TextCtrl` with `wx.TE_RICH2 | wx.TE_MULTILINE | wx.TE_READONLY`), input field (`wx.TextCtrl` with `wx.TE_PROCESS_ENTER`), buttons (send, stop, clear, attach), attachment label
- Every control: `name="widget_name"`, preceded by `wx.StaticText` label
- Only `wx.BoxSizer`
- Input handler: check `ShiftDown()`, Enter → send, Shift+Enter → newline
- `attach_file`: image extensions → base64, other → UTF-8 text
- `append_user_message`, `append_assistant_chunk`, `start_generation`, `end_generation`
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/ui/test_chat_panel_static.py -xvs` passes

### 7.3 [windows-only] Manual NVDA verification
**Description**: Verify conversation review and key handling on Windows.
**Files**: None (manual test)
**Scenarios**:
- Tab through controls, NVDA announces labels
- Enter sends message, Shift+Enter inserts newline
- Escape aborts generation
**Verification**: Manual test on Windows 11 with NVDA

---

## Phase 8: UI — MainWindow (wx-only)

### 8.1 RED: Write static AST tests for MainWindow
**Description**: Verify accessibility compliance and structure via AST inspection.
**Files**: `tests/ui/test_main_window_static.py`
**Scenarios**:
- Import-only check
- AST check: menus present (Archivo, Ayuda)
- AST check: `wx.AcceleratorTable` bindings for Ctrl+N/O/S/F5/Escape
- AST check: `wx.SplitterWindow` with `ParamsPanel` left (280px)
- AST check: status bar present
**TDD Step**: RED — tests fail (module doesn't exist)
**Verification**: `uv run pytest tests/ui/test_main_window_static.py -xvs` fails with `ModuleNotFoundError`

### 8.2 GREEN: Implement MainWindow
**Description**: Implement `MainWindow` to pass all tests.
**Files**: `ollamachat/ui/main_window.py`
**Implementation**:
- Constructor: build UI with `wx.SplitterWindow` (left: `ParamsPanel` 280px, right: `ChatPanel`)
- Menu bar: Archivo (Nuevo, Abrir, Guardar, Salir), Ayuda (Acerca de)
- Accelerator table: Ctrl+N/O/S, F5, Escape
- Status bar: 3 fields
- Startup check: `client.check_running()`, show dialog + speech if False, else `list_models()` → `params_panel.set_models()`
- Send flow: build API payload, call `client.chat_stream()`, disable buttons
- Token callback: `chat_panel.append_assistant_chunk()`, `speech.announce_token_chunk()`
- Done callback: `speech.flush_token_buffer()`, `speech.speak("Respuesta completa")`, save to conversation, re-enable buttons
- Error callback: show dialog + speech, re-enable buttons
- Abort: `client.abort()`
- Save/load: file dialogs, `Conversation.save/load`
**TDD Step**: GREEN — all tests pass
**Verification**: `uv run pytest tests/ui/test_main_window_static.py -xvs` passes

### 8.3 [windows-only] Manual NVDA verification
**Description**: Verify full flow on Windows.
**Files**: None (manual test)
**Scenarios**:
- Startup: Ollama connection prompt
- Send message, hear response streamed
- Stop generation with Escape
- Save/load conversation
- Model refresh with F5
**Verification**: Manual test on Windows 11 with NVDA

---

## Phase 9: Entry Point

### 9.1 Implement main.py
**Description**: Create app entry point.
**Files**: `ollamachat/main.py`
**Implementation**:
```python
import wx
from ollamachat.ui.main_window import MainWindow

class OllamaChatApp(wx.App):
    def OnInit(self) -> bool:
        frame = MainWindow(None, title="OllamaChat")
        frame.Show()
        return True

def main() -> None:
    app = OllamaChatApp()
    app.MainLoop()

if __name__ == "__main__":
    main()
```
**Verification**: `uv run python -c "from ollamachat.main import main"` succeeds (doesn't launch GUI)

---

## Phase 10: Final Integration Smoke

### 10.1 Import smoke test
**Description**: Verify all modules import cleanly.
**Verification**: `uv run python -c "import ollamachat; import ollamachat.core; import ollamachat.ui"` succeeds

### 10.2 Full test suite
**Description**: Run all tests.
**Verification**: `uv run pytest -xvs` passes (all core + smoke + UI static tests)

### 10.3 AST lint for UI modules
**Description**: Verify all UI modules import without wx runtime errors.
**Verification**: `uv run pytest tests/ui/ --collect-only` succeeds

### 10.4 [windows-only] Manual full run
**Description**: End-to-end verification on Windows.
**Verification**: Manual test on Windows 11 with NVDA:
- Start app, see Ollama connection prompt
- Send message, hear response
- Attach image, verify vision works
- Save/load conversation
- Abort generation with Escape

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1 | 7 | Scaffolding (pyproject, package, tests, docs) |
| Phase 2 | 2 | Core: Speech (TDD) |
| Phase 3 | 2 | Core: Conversation (TDD) |
| Phase 4 | 2 | Core: OllamaClient (TDD) |
| Phase 5 | 1 | Smoke test for Speech |
| Phase 6 | 3 | UI: ParamsPanel (TDD + manual) |
| Phase 7 | 3 | UI: ChatPanel (TDD + manual) |
| Phase 8 | 3 | UI: MainWindow (TDD + manual) |
| Phase 9 | 1 | Entry point |
| Phase 10 | 4 | Final integration smoke |
| **Total** | **28** | |

## Implementation Order

1. **Scaffolding first** — establish project structure, dependencies, test infrastructure
2. **Core modules in dependency order** — Speech (no deps) → Conversation (no deps) → OllamaClient (no deps)
3. **Smoke test** — verify Speech degradation before UI work
4. **UI modules in dependency order** — ParamsPanel (standalone) → ChatPanel (standalone) → MainWindow (depends on both)
5. **Entry point** — thin wrapper, last
6. **Integration smoke** — final verification

Each phase is independently testable. Core phases run in WSL. UI phases require Windows for runtime verification but AST tests run anywhere.

---

## Result Contract

**Status**: ✅ Tasks complete

**Executive Summary**:
- 28 tasks across 10 phases, strict TDD ordering (RED → GREEN)
- Core modules fully testable in WSL, UI modules use AST inspection + manual Windows verification
- Single PR approved by user despite 400-line budget risk
- All 22 files from design covered

**Artifacts**:
- `openspec/changes/initial-implementation/tasks.md` (this file)

**Next Recommended**: `sdd-apply` (implement tasks)

**Risks**:
- 400-line budget exceeded (~2000 lines), but user approved single PR
- WSL cannot test UI runtime; manual Windows verification required
- `accessible-output2` behavior may vary; silent mode is fallback

**Skill Resolution**:
- `sdd-tasks` skill loaded
- OpenSpec convention applied
- Strict TDD enforced per user request
- All 7 specs + design reviewed
