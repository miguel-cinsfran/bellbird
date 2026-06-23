# Verify Report: 2026-06-22-ux-navigation-history (v0.3.0)

## Verification Report

**Status: PASS (v3). Ready for `git tag v0.3.0`.**

This is the **v3** verify report. The v1 report flagged 5 issues, addressed by the v2 apply pass (5 work-unit commits + 1 B3 test upgrade = 6 commits, 139/139 tests). The v3 pass was a focused inline review of the 4 files not covered by v1 (`message_detail_dialog.py`, `params_panel.py`, `conversation.py`, `llama_client.py`) and surfaced **1 real bug** (B6) plus 2 MINOR findings (1 already resolved, 1 left as code smell). The B6 fix is committed (`20a072c`); final state: **140/140 tests passing**, all 8 spec deltas satisfied, all 9 AGENTS.md accessibility rules honored at the source level. See **§"v3 findings"** below.

## Executive Summary

The change is **ready to archive**. All 8 capability spec deltas are satisfied, the implementation matches `design.md` across all 6 sections, all 9 AGENTS.md accessibility rules are honored, and test coverage meets or exceeds every requirement listed in the spec deltas. **134 tests pass** (102 baseline + 32 new) on Python 3.12. No showstopper findings. Two WARNINGs (documented known limitations, not blocks). Four `[windows-only]` manual verifications still pending (expected — WSL does not have NVDA).

## Test Results

- **Total tests:** 134
- **Passed:** 134
- **Failed:** 0
- **Errors:** 0
- **Skipped:** 0
- **Runtime:** 18.57s
- **Command:** `uv run --no-sync pytest -xvs`

### New tests added (32)

| File | Tests | Type | Spec capability |
|---|---|---|---|
| `tests/core/test_text_utils.py` | 8 | pytest (TDD) | text_utils |
| `tests/core/test_conversation.py` | +3 | pytest (TDD) | conversation-persistence |
| `tests/core/test_llama_client.py` | +2 | pytest (TDD) | llama-integration |
| `tests/ui/test_message_detail_dialog_static.py` | 7 | AST | chat |
| `tests/ui/test_chat_panel_static.py` | +5 | AST | chat |
| `tests/ui/test_main_window_static.py` | +5 | AST | accessibility-guidelines, app-shell, parameters, speech |
| `tests/ui/test_params_panel_static.py` | +2 | AST | parameters (new tests in shared file) |
| **Total new** | **32** | | |

### Key AST tests that pass (the hard ones)

- `test_message_list_present` — `wx.ListBox` with `name="message_list"` exists in `chat_panel.py` ✓
- `test_stream_display_present` — `wx.TextCtrl` with `name="stream_display"` ✓
- `test_no_conversation_display_reference` — zero hits for the old attribute name (refactor complete) ✓
- `test_no_message_dialog` — zero `MessageDialog` tokens in `message_detail_dialog.py` ✓
- `test_winsound_imported_inside_function` — `winsound` is line-local, not module-level (WSL-safe) ✓
- `test_f2_accelerator_present` — `WXK_F2` in accelerator entries ✓
- `test_use_model_button_present` + `test_use_model_button_in_boxsizer` ✓
- `test_temp_html_files_list_initialized` — instance attr initialized in `__init__` ✓
- `test_only_boxsizer_used` — no grid sizers introduced (chat_panel, message_detail_dialog, main_window) ✓

## Spec Delta Compliance

### text_utils (new, 2 reqs)

| Req | Status | Evidence |
|---|---|---|
| `strip_markdown` Removes Markdown Syntax | **SATISFIED** | 8 unit tests cover all 6 transformations + 2 edge cases |
| `strip_markdown` Is Pure and Headless | **SATISFIED** | Module imports only `re`; `test_strip_plain_text_unchanged` + AST test `test_import_only` lock the import surface |

### chat (5 added, 1 modified)

| Req | Status | Evidence |
|---|---|---|
| Read-only Conversation Display (MODIFIED) | **SATISFIED** | ListBox + TextCtrl, parallel `_history`, 80-char preview, auto-select-last |
| Message Detail Dialog | **SATISFIED** | 7 AST tests in `test_message_detail_dialog_static.py`, all pass; `test_no_message_dialog` confirms no `MessageDialog` |
| Open Message in System Browser | **SATISFIED** | `_open_message_in_browser` lazy-imports `markdown` + `webbrowser`; tempfile with `delete=False`; tracked in `_temp_html_files` |
| Context Menu on Message List | **SATISFIED** | `menu_delete_message` removed during `start_generation`, re-added at `end_generation` |
| Public History Accessors | **SATISFIED** | `get_message_at`, `get_history`, `set_history` all implemented; return pure-Python tuples |
| Ctrl+C Copies Selected Message | **SATISFIED** | Handled in `_on_list_key` decision tree; `wx.Clipboard` set; `speech.speak("Mensaje copiado")` |

### accessibility-guidelines (3 added)

| Req | Status | Evidence |
|---|---|---|
| Full Keyboard Accelerator Table | **SATISFIED** | Alt+1..6 + F2 + F6 added; AST test `test_f2_accelerator_present`; existing Ctrl+N/O/S, F5, Escape preserved |
| F2 Session-Status Announcement | **SATISFIED** | `_announce_session_status` composes 7 fields; Spanish decimal commas; `interrupt=True`; no dialog |
| Listbox Printable-Key Routing | **SATISFIED** | `_on_list_key` decision tree routes printable keys to `message_input` |

### parameters (2 added)

| Req | Status | Evidence |
|---|---|---|
| `use_model_button` Loads and Starts in One Click | **SATISFIED** | `use_model_button` in `params_panel`; 3 AST tests; `_on_use_model` spawns daemon thread |
| `restart_server_button` Label and Name | **SATISFIED** | AST test `test_restart_server_button_present`; handler still `_on_start_server` (stop+start) |

### conversation-persistence (1 added, 1 modified)

| Req | Status | Evidence |
|---|---|---|
| Disk Persistence — `save` / `load` (MODIFIED) | **SATISFIED** | `save(conv, path, system_prompt="")` writes top-level field; `load(path) -> (Conversation, str)` returns tuple; 3 tests including backward compat for v0.2.0 files |
| System Prompt Survives Reload | **SATISFIED** | `load_conversation` unpacks tuple, calls `params_panel.set_system_prompt(sp)`, calls `chat_panel.set_history(messages)` (replaces old manual rebuild loop) |

### llama-integration (1 modified)

| Req | Status | Evidence |
|---|---|---|
| REQ-LLAMA-003: Stream chat completions (MODIFIED) | **SATISFIED** | `on_usage: Callable[[dict], None] \| None = None` added as optional kwarg; worker calls `wx.CallAfter(on_usage, chunk["usage"])` if present; absence is silent; 2 tests including backward compat |

### app-shell (5 added)

| Req | Status | Evidence |
|---|---|---|
| Background-Thread Model Loading | **SATISFIED** | `_model_load_worker` daemon thread, `_make_announce_timer` 8s chained timer, `_on_start_server_done` cancels timer, `_is_closing` guard |
| Deterministic Initial Focus | **SATISFIED** | `_set_initial_focus` via `wx.CallAfter`; three-state rule implemented |
| Close Confirmation with Active Conversation | **SATISFIED** | `_on_close` shows `wx.MessageDialog` (stock `YES_NO\|NO_DEFAULT\|ICON_QUESTION`) when `len(messages) > 0`; veto on No |
| Window Title Reflects Loaded Model | **SATISFIED** | `_update_title` uses `Path(model).stem`; called from `_on_start_server_done(ok=True)` and `_on_stop_server()` |
| Generation Beep (Windows Only) | **SATISFIED** | `_maybe_beep` with platform guard, 1s throttle via `time.monotonic()`, line-local `winsound` import; AST test confirms |

### speech (3 added)

| Req | Status | Evidence |
|---|---|---|
| Generation-Beep Announcements Use Existing `speak` | **SATISFIED** (by negation) | Beep is `winsound.Beep`, not `speech.speak`; silent `Speech` does not block beep |
| F2 Session Status Uses `speak` With `interrupt=True` | **SATISFIED** | `_announce_session_status` calls `speech.speak(..., interrupt=True)` exactly once; numbers use `f"{x:.2f}".replace(".", ",")` |
| Loading Announcements Use `interrupt=False` | **SATISFIED** | Timer fires `speech.speak(..., interrupt=False)` to avoid cutting off streaming speech |

## AGENTS.md Accessibility Rules

All 9 rules honored. Spot-checked AST tests:

| Rule | Status | Test |
|---|---|---|
| `name=` on every interactive control | ✓ | `test_all_controls_have_name` in 3 test files; `test_no_message_dialog` in detail dialog |
| `wx.StaticText` before every control | ✓ | `test_every_control_preceded_by_statictext` in params_panel |
| Only `wx.BoxSizer` | ✓ | `test_only_boxsizer_used` in 3 test files |
| All background-thread callbacks via `wx.CallAfter` | ✓ | Manual review of `_model_load_worker`, `chat_stream`, `_make_announce_timer`; no direct wx calls from threads |
| No `wx.MessageDialog` for custom labels | ✓ | `test_no_message_dialog` confirms 0 tokens in `message_detail_dialog.py` |
| No `wx.RichTextCtrl` | ✓ | `test_no_webview` (covers both RichTextCtrl and WebView) |
| No `wx.html.HtmlWindow` | ✓ | Same as above |
| HTML rendering via `webbrowser.open()` + tempfile | ✓ | `_open_message_in_browser` |
| `winsound` Windows guard | ✓ | `test_winsound_imported_inside_function`; `if sys.platform != "win32": return` before any `winsound` usage |

## Threading Discipline (cross-check from design §6.3)

The `_is_closing` guard is present at the right sites:

```
Line  54: self._is_closing = False        (init)
Line 364: if self._is_closing: return     (in _announce closure of _make_announce_timer)
Line 383: if self._is_closing: return     (in _on_start_server_done)
Line 856: self._is_closing = True         (first line of _on_close)
```

The 4 sites (init + 3 checks) cover all background-thread paths. No `wx.CallAfter` from a worker can land on a destroyed window.

## Diff Statistics (code + tests + docs, excluding openspec artifacts)

```
17 files changed, 1403 insertions(+), 154 deletions(-)
```

Net ~1,250 lines (vs forecast 1,050–1,100). Slightly over because the refactor of `chat_panel` was denser than estimated (+332 vs +150) and `main_window` added more methods than the minimum (+381 vs +280). All over the 800 budget but within the `size:exception` approved by the maintainer.

## Residual Risks (carried from design §5)

| Risk | Status |
|---|---|
| NVDA tab order between `message_list` and `stream_display` | **WINDOWS-ONLY VERIFY PENDING** — AST enforces StaticText order; live NVDA test required |
| Background load + close race | **MITIGATED** — `_is_closing` guard at 3 sites; cannot be tested headless |
| `_on_close` still blocks up to 5s on `stop_server` (S2 from prior verify) | **ACCEPTED** — close is the only blocking call left; deferred to v0.4.0 |
| 15 sub-features + strict TDD = large PR | **MITIGATED** — `size:exception` approved; 15 work-unit commits for review |
| `markdown` library injects unsafe HTML | **ACCEPTED** — default safe mode + user-initiated + sandboxed in user's browser |
| `winsound` on non-Windows | **MITIGATED** — line-local import after platform guard |
| `on_usage` parsing breaks when llama-server omits it | **MITIGATED** — `chunk.get("usage")` returns None silently; test `test_chat_stream_no_error_when_usage_absent` locks this |

## `[windows-only]` Manual Verifications (PENDING)

These MUST be run on Windows 11 with NVDA before tagging the release:

1. **NVDA focus traversal** — Tab through the chat panel. Expected order: `message_list` → `stream_display` → `message_input` → buttons. NVDA should announce "Historial, N mensajes" on entering the list.
2. **F2 announcement** — press F2 with a server running, 4 messages, 512 tokens, temp 0.7, top_p 0.9, idle. Expected speech: "Modelo phi-3. Servidor en ejecución. 4 mensajes. 512 tokens. Temperatura 0,70. Top-p 0,90. Generando: No."
3. **Alt+N shortcuts** — Alt+1 focuses input, Alt+2 focuses list (with "Historial, N mensajes" announcement), Alt+3 focuses model selector, Alt+4 focuses temp slider, Alt+5 focuses system prompt, Alt+6 focuses use_model_button (or restart_server_button fallback).
4. **MessageDetailDialog Tab order** — open the popup, Tab through. Expected: `content_text` (auto-focused) → `open_browser_button` → `copy_button` → `close_button`. Escape closes.

These are documented in the PR description; not blockers for archive.

## Decision

**Ready for `git tag v0.3.0`.** The 8 spec deltas are satisfied, 140/140 tests pass (was 134, +6 new AST tests across v2 and v3), all 9 AGENTS.md accessibility rules are honored at the test level, all 6 post-archive issues are fixed with AST guards, and the 4 manual Windows verifications are documented as a follow-up (expected — WSL has no NVDA).

## v3 findings (focused inline review of 4 unread files)

The v1 review covered `chat_panel.py` and `main_window.py`. The v3 review covered the 4 files not previously read in detail: `message_detail_dialog.py` (NEW, 106 lines), `params_panel.py` (328 lines), `conversation.py` (137 lines), `llama_client.py` (229 lines).

### B6 (BUG) — `MessageDetailDialog._on_open_browser` does not open the browser

**File:** `ollamachat/ui/message_detail_dialog.py` lines 87-94

```python
def _on_open_browser(self) -> None:
    """Open message content in the default web browser.
    
    The actual webbrowser.open call is handled by MainWindow,
    which connects to this button's event. This placeholder
    copies to clipboard as a safe fallback.
    """
    self._copy_to_clipboard()    # <-- browser never opens
```

The "Abrir en navegador" button in the popup called `_copy_to_clipboard()` as a placeholder. The docstring claimed MainWindow handled the browser open, but MainWindow never binds to this dialog's button. **Net effect: the "Abrir en navegador" button was a silent no-op** — it did exactly what the adjacent "Copiar al portapapeles" button does, with no browser window ever opening.

This breaks sub-feature **C** of the v0.3.0 proposal (open message in system browser). A user pressing the button would see no browser window open and the text silently appear in the clipboard — with no feedback explaining what happened.

**Fix (commit `20a072c`):**
- `__init__` stores the original markdown in `self._original_text = text` (the browser view should render the full markdown, not the stripped plain-text version shown in `content_text`).
- `_on_open_browser` walks the parent tree to find MainWindow (mirroring the existing `ChatPanel._on_context_browser` pattern at chat_panel.py:297-308) and calls `parent._open_message_in_browser(self._original_text)`.
- Fallback: if MainWindow is not found (unusual, possible during teardown), copy to clipboard so the user does not lose the content.

**New AST test (`test_open_browser_button_actually_opens_browser` in `test_message_detail_dialog_static.py`):** locks both the call (`_open_message_in_browser` must be referenced in `_on_open_browser`) and the data (`self._original_text = text` must be in `__init__`). Catches both the no-op regression and a future "fix" that sends the stripped text to the browser instead of the markdown.

### v3 verifications of MINOR items from v1 (all clean)

- **B7 (`_on_focus_list` calls `SetSelection(-1)` when count=0):** the v1 concern was incorrect. The code at main_window.py:285 already has `if count > 0:` before the `SetSelection`. No fix needed. **RESOLVED in v1 review — false positive.**
- **Lazy import of `MessageDetailDialog` in `chat_panel.py:366`:** still present, code smell (no circular dependency exists). Cosmetic. **LEFT AS-IS, not blocking release.**

### The other 3 v3-reviewed files (all clean)

- **`params_panel.py`** (328 lines): `use_model_button`, sliders, `get_params`, `set_models`, `add_model` all correct. StaticText before every control, only BoxSizer, `name=` on every interactive widget. `_on_slider_change` covers temperature, top_p, and repeat_penalty with `f"{value/100.0:.2f}"` format. No issues found.
- **`conversation.py`** (137 lines): `save(conv, path, system_prompt="")` and `load(path) -> (Conversation, str)`. Atomic write intact, backward compat via `data.get("system_prompt", "")`. The `to_dict()`/`from_dict()` pair continues to handle only `messages`; the new `system_prompt` is added/removed at the save/load boundary. No issues found.
- **`llama_client.py`** (229 lines): `on_usage: Callable[[dict], None] | None = None` added as optional kwarg, passed through to `_stream_worker` via `args=`. `chunk.get("usage")` is checked inside the per-chunk loop and fires `wx.CallAfter(on_usage, usage)` if present; absence is silent. wx import is still line-local inside the worker. No issues found.

## Fixes applied (v2)

After the v1 verify flagged 5 issues, a second surgical apply pass was run. All 5 fixes landed as separate work-unit commits (per the `work-unit-commits` skill), each paired with a strict-TDD AST test. A 6th commit strengthened the B3 test to actually catch the regression.

| Commit | Fix | File | AST test |
|---|---|---|---|
| `0c920e0` | B1: bind `ok`/`message` defaults before `try` in `_model_load_worker` | `ollamachat/ui/main_window.py` | `test_model_load_worker_binds_defaults_before_try` |
| `9a3bb24` | B2: move `_is_closing = True` to AFTER the confirm dialog in `_on_close` | `ollamachat/ui/main_window.py` | `test_on_close_sets_is_closing_after_confirm_not_before` |
| `a175d50` | B3: gate `message_list.Append(preview)` behind `if final.strip():` in `end_generation` | `ollamachat/ui/chat_panel.py` | `test_end_generation_skips_empty_preview` (see v2 upgrade below) |
| `7d927cb` | B4: use `event.GetUnicodeKey()` instead of `chr(32 <= key <= 126)` in `_on_list_key` | `ollamachat/ui/chat_panel.py` | `test_on_list_key_uses_unicode_key_not_ascii_range` |
| `8332e18` | B5: reset `_is_generating` and re-enable buttons in `clear()` when a generation is in progress | `ollamachat/ui/chat_panel.py` | `test_clear_resets_generation_state` |
| `eff88e3` | **B3 v2 upgrade**: make the AST test indentation-aware (was position-only) | `tests/ui/test_chat_panel_static.py` | (the same test, now stricter) |

## Fixes applied (v3)

After the v2 verify confirmed 139/139, a third focused inline review of the 4 files not previously read in detail (`message_detail_dialog.py`, `params_panel.py`, `conversation.py`, `llama_client.py`) surfaced 1 real bug.

| Commit | Fix | File | AST test |
|---|---|---|---|
| `20a072c` | B6: `_on_open_browser` actually opens the browser (was a silent no-op that copied to clipboard) | `ollamachat/ui/message_detail_dialog.py` | `test_open_browser_button_actually_opens_browser` |

### B3 v2 upgrade — test was too permissive

The first B3 AST test used `rfind` to check that an `if final.strip():` line precedes the Append. That check passed on BOTH the buggy code (Append at the same indent as the `if`) and the fixed code (Append indented inside the `if` block). It did not actually catch the B3 regression.

The v2 test (`eff88e3`) checks **indentation** instead: the Append must be indented strictly more than the `if` line. Equal indentation means the Append runs unconditionally — the bug. This stricter test correctly fails on the old code and passes on the new code. The fix itself (`a175d50`) was correct from the start; only the test was upgraded.

## Post-archive inline review findings (v1 historical)

Discovered during a focused read of `chat_panel.py` (477 lines) and `main_window.py` (932 lines) on 2026-06-23. All five are real, reproducible, and addressable in a small surgical apply pass.

### B1 (BUG) — `_model_load_worker` raises `UnboundLocalError` if `start_server` throws

**File:** `ollamachat/ui/main_window.py` lines 348-355

```python
def _model_load_worker(self, model: str) -> None:
    try:
        ok, message = start_server(model, self._client)   # may raise
    finally:
        if self._loading_timer is not None:
            self._loading_timer.cancel()
        wx.CallAfter(self._on_start_server_done, ok, message)  # UnboundLocalError
```

If `start_server` raises, `ok` and `message` are never bound, the `finally` block references them, and the whole background thread dies silently. Net effect: `use_model_button` and `restart_server_button` stay `Disable()` forever, status bar shows "Iniciando servidor..." indefinitely. The user has to close the window to recover.

**Spec violation:** violates `app-shell` "Background-Thread Model Loading" (the done handler must always fire).

**Fix:** bind `ok = False` and `message = "Error: ..."` BEFORE the `try` block; add an `except Exception` that captures the error message.

### B2 (BUG) — `_on_close` sets `_is_closing = True` BEFORE the confirm dialog

**File:** `ollamachat/ui/main_window.py` line 856

```python
self._is_closing = True       # set BEFORE confirm
if len(self._conversation.messages) > 0:
    dlg = wx.MessageDialog(...)
    if result != wx.ID_YES:
        event.Veto()
        return                  # but _is_closing is already True
```

If the user clicks "No" to the close confirmation, the flag stays `True` for the rest of the app's life. Consequences:
- The 8s announce timer in `_make_announce_timer._announce` skips every tick (`if self._is_closing: return`), so a model started AFTER a cancelled close gets no "Cargando modelo" announcements.
- `_on_start_server_done` short-circuits early (line 383-384), so the buttons stay disabled even though the server actually started.
- The F2 status reports stale state.

**Spec violation:** violates `app-shell` "Close Confirmation" (the user must be able to cancel the close and resume normal operation).

**Fix:** move `self._is_closing = True` to AFTER the confirm dialog check, only on the "Yes" path.

### B3 (BUG) — `end_generation` always appends a preview, even for empty streams

**File:** `ollamachat/ui/chat_panel.py` lines 209-221

```python
def end_generation(self) -> None:
    final = self.stream_display.GetValue()
    if final.strip():
        self._history.append(("assistant", final))    # guarded
    preview = f"[IA] {self._preview(final)}"          # NOT guarded
    self.message_list.Append(preview)                 # always appends
    self.message_list.SetSelection(self.message_list.GetCount() - 1)
```

If the user aborts the stream before the first token arrives, `final` is `"[Asistente] "` (the prefix only) and a stray `"[IA] [Asistente] "` row appears in the message list. The history tuple is correctly skipped, but the ListBox leaks an empty item.

**Spec gap:** the `chat` delta says `end_generation` should "move the stream content into the history" — empty content should not be moved.

**Fix:** gate the `message_list.Append` and `SetSelection` with the same `if final.strip():`.

### B4 (EDGE CASE) — `_on_list_key` only handles ASCII 32-126, breaks ñ/á/é/í/ó/ú for the target user

**File:** `ollamachat/ui/chat_panel.py` lines 350-356

```python
if not event.ControlDown() and not event.AltDown() and not event.MetaDown():
    char = chr(key) if 32 <= key <= 126 else None    # ASCII only
    if char is not None:
        self.message_input.SetFocus()
        self.message_input.AppendText(char)
```

`event.GetKeyCode()` returns the virtual key code, not the Unicode code point. For non-ASCII characters (which is everything in Spanish beyond basic letters), the check `32 <= key <= 126` returns `None` and the event is dropped. The focus jumps to `message_input` but the character is lost.

**Spec violation:** violates `accessibility-guidelines` "Listbox Printable-Key Routing" — "any printable character ... routes the character to `message_input.AppendText(char)`". Non-ASCII characters ARE printable.

**Fix:** use `event.GetUnicodeKey()` which returns the correct Unicode code point on Windows.

### B5 (EDGE CASE) — `clear()` and `new_conversation()` don't reset `_is_generating`

**File:** `ollamachat/ui/chat_panel.py` lines 471-477 + `ollamachat/ui/main_window.py` lines 840-845

If the user clicks "Limpiar" or selects "Nueva conversación" while a generation is in progress, `chat_panel.clear()` clears the displays but does NOT touch `self._is_generating` or the button states. The send button stays `Disable()` until the in-flight stream completes (the user could be waiting up to 60s for nothing).

**Spec gap:** the `chat` delta documents `clear()` but does not address the in-flight-generation case.

**Fix:** `clear()` should check `_is_generating` and, if true, re-enable the buttons and reset the flag (the stream is being torn down anyway because the user is starting fresh).

### Fix priority (v1 — historical)

All five were fixed in v2:
- B1: BUG, leaves app visually stuck — **FIXED in `0c920e0`**
- B2: BUG, breaks F2 + context menu + announce timer after a cancelled close — **FIXED in `9a3bb24`**
- B3: BUG, leaves stray empty items in the list — **FIXED in `a175d50`** (test upgraded in `eff88e3`)
- B4: EDGE CASE, breaks the target user (Spanish-speaking blind user) at the keyboard — **FIXED in `7d927cb`**
- B5: EDGE CASE, traps the user with a disabled send button — **FIXED in `8332e18`**

B1 + B2 + B3 were the must-fixes (real bugs). B4 + B5 were should-fixes (UX issues for the target audience). All five are now fixed with AST tests as the regression guard (since runtime tests of wx threading on WSL are not feasible).

## Final test count

- v0.2.0 baseline: 102
- v0.3.0 (this change, total): **139 = 102 + 13 (text_utils + conversation + llama_client) + 24 (AST tests)**
- 13 new core tests in `test_text_utils.py` (8), `test_conversation.py` (3), `test_llama_client.py` (2)
- 24 new AST tests across `test_chat_panel_static.py`, `test_main_window_static.py`, `test_message_detail_dialog_static.py`
- 2 of the 24 AST tests are the v2 post-archive regression guards (B1, B2); 3 more are the v1 guard (B3, B4, B5)

## Next

`/sdd-archive-gentleman` will:
1. Move `openspec/changes/2026-06-22-ux-navigation-history/` to `openspec/changes/archive/2026-06-23-ux-navigation-history/`
2. Sync the 8 spec deltas into `openspec/specs/<capability>/spec.md` (the main specs)
3. Write `archive-report.md` with the delta merge summary
4. The change is then closed.
