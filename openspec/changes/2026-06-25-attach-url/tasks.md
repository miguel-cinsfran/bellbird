# Tasks: Adjuntar URL (Ctrl+U)

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: Medium

## Work-Unit 1 — Core + Tests (wx-free, WSL)

- [x] 1.1 `core/web_fetch.py`: `FetchResult` frozen dataclass + `fetch_text(url, *, timeout=10, max_chars=50000)` with scheme guard, requests, HTMLParser strip, unescape, truncation. `tests/core/test_web_fetch.py`: ~15 tests (happy, scheme reject, timeout, 404, truncation, UA, encoding, redirect, AST guard).
- [x] 1.2 Config `url_max_chars: int = 50000` in `BellbirdConfig`. Tests: default, round-trip, missing-key forward-compat, AST guard on `_MIGRATIONS`.
- [x] 1.3 Keymap entry `attach_url: Binding(CTRL, ord("U"), "Ctrl+U")` in `DEFAULT_KEYMAP` → 22 entries. Tests: id set, label, collision-free.
- [x] 1.4 Bump `pyproject.toml` version → `0.8.3`. Verify `uv run --no-sync pytest -xvs` green.
- **Commit**: `feat(core): add web_fetch, attach_url keymap, and url_max_chars config`

## Work-Unit 2 — UI + Tests wx (Windows)

- [ ] 2.1 Refactor `_make_announce_timer` to accept `phrase` parameter (default backwards-compat). Existing call sites unaffected.
- [ ] 2.2 `ui/url_dialog.py`: `wx.Dialog(name="url_dialog")` + StaticText + TextCtrl(name="url_input") + 2 native buttons. `SetFocus` on open, `SetEscapeId`. BoxSizer only. `tests/ui/test_url_dialog_runtime.py` (importorskip wx).
- [ ] 2.3 `ChatPanel.attach_url(url, text, origin_label)`: set `_attached_text`, clear images, update label, speak. No-op for empty text. Tests: populate, clears image, empty no-op, Conversation intact.
- [ ] 2.4 `_on_attach_url()`: gate (if generating → speak + return), open URLDialog, regex-validate scheme, on error speak+keep-open, on valid → speak + `_url_fetch_timer` + daemon thread. Tests: mid-gen gate, idle opens.
- [ ] 2.5 `_fetch_url_worker` + `_on_fetch_complete`: worker calls `web_fetch.fetch_text`, posts via `CallAfter`. On complete: cancel timer → ok? attach_url + speech + truncation speech → !ok? speech error. No MessageDialog ever. Tests: success, truncation, error path.
- [ ] 2.6 Wire `"attach_url": lambda: self._on_attach_url()` in `_build_accelerators` handlers. Add `menu_attach_url` ("Adjuntar URL", Ctrl+U) in Archivo menu between Export and Preferencias, enable/disable with generation lifecycle.
- [ ] 2.7 `_url_fetch_timer` slot (`threading.Timer | None`) in `__init__`, separate from `_loading_timer`. Document race avoidance.
- [ ] 2.8 Register `test_url_dialog_runtime.py` in `run_tests.bat`. Verify `uv run --no-sync pytest -xvs` green.
- **Commit**: `feat(ui): add URL dialog, attach_url handler, and menu item for Ctrl+U`
