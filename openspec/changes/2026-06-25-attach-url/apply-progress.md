# Apply Progress: 2026-06-25-attach-url

## WU-1: Core + Tests ✅ COMPLETED

- **Date**: 2026-06-25
- **Strategy**: single-pr (D2)
- **Execution**: auto (A2)

### Completed Tasks

| Task | Status | Files Changed |
|------|--------|---------------|
| 1.1 `core/web_fetch.py` — FetchResult + fetch_text | ✅ | `bellbird/core/web_fetch.py` (new), `tests/core/test_web_fetch.py` (new) |
| 1.2 Config `url_max_chars: int = 50000` | ✅ | `bellbird/core/config.py`, `tests/core/test_config.py` |
| 1.3 Keymap entry `attach_url: Ctrl+U` → 22 entries | ✅ | `bellbird/core/keymap.py`, `tests/core/test_keymap.py` |
| 1.4 Bump `pyproject.toml` → v0.8.3 | ✅ | `pyproject.toml`, `tests/ui/test_main_window_static.py` |

### Files Changed

| File | Lines Added | Lines Removed |
|------|-------------|---------------|
| `bellbird/core/web_fetch.py` | NEW (127) | 0 |
| `bellbird/core/config.py` | 1 | 0 |
| `bellbird/core/keymap.py` | 1 | 0 |
| `tests/core/test_web_fetch.py` | NEW (325) | 0 |
| `tests/core/test_config.py` | 93 | 0 |
| `tests/core/test_keymap.py` | 45 | 7 |
| `tests/ui/test_main_window_static.py` | 2 | 2 |
| `pyproject.toml` | 1 | 1 |
| **Total** | **595** | **10** |

### Tests Executed

- `tests/core/test_web_fetch.py`: 23/23 ✅
- `tests/core/test_config.py`: 67/67 ✅
- `tests/core/test_keymap.py`: 42/42 ✅
- Full suite (excl. `test_llama_runner.py` subprocess tests + 1 pre-existing flaky): **555 passed, 13 skipped, 1 deselected** ✅

### Commit

```
dcb50b7 feat(core): add web_fetch, attach_url keymap, and url_max_chars config
```

### Implementation Notes

- **`FetchResult` is frozen** — `@dataclass(frozen=True)`. All error paths return `FetchResult(ok=False, ...)`, never raise.
- **Scheme guard** runs before any `requests` call: `^https?://` (case-insensitive). Rejects `file://`, `ftp://`, `gopher://`.
- **HTML cleaning order**: (1) subclass `HTMLParser` strips `<script>`/`<style>` content, (2) `html.unescape()` unescapes entities, (3) `re.sub(r"\s+", " ")` collapses whitespace.
- **Encoding**: `response.text` primary; fallback via `response.content.decode(response.apparent_encoding, errors="replace")`.
- **User-Agent**: Hardcoded `"Bellbird/0.8.3"` with TODO for dynamic read from pyproject.toml.
- **AST guard**: `web_fetch.py` has no `wx` import — verified by test.
- **Config forward-compat**: Unchanged — `__dataclass_fields__` filter already handles unknown keys. No migration needed for `url_max_chars` (default 50000 applied on missing field).
- **Keymap**: `attach_url` at position 22, collision-free (`Ctrl+U` unique).

### Notes for WU-2

- The `_make_announce_timer` pattern needs refactoring to accept a `phrase` parameter (backwards-compat default). Currently hardcodes "Cargando modelo...".
- A separate `_url_fetch_timer` slot (`threading.Timer | None`) must be added to `MainWindow.__init__`, distinct from `_loading_timer`.
- `URLDialog` should be a new `ui/url_dialog.py` module (mirrors `FindDialog`).
- The `archivo` menu needs `menu_attach_url` ("Adjuntar URL", `Ctrl+U`), positioned after Export but before Preferencias.
- Mid-generation gate: `_on_attach_url` must check `_is_generating` first.
- `ChatPanel.attach_url()` — the method signature is designed. Implementation touches `chat_panel.py` and `main_window.py`.
- Register new wx-runtime tests in `run_tests.bat`.
