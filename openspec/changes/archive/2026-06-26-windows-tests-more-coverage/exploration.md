## Exploration: Windows Tests Coverage Gaps at v0.11.0

### Current State

**Test infrastructure** uses a dual-discover approach:
- `run_tests.bat` line 19: `uv run pytest tests/` — discovers ALL tests recursively
- `run_tests.bat` line 23: explicit list of "wx-runtime" files — meant to be authoritative but is redundant

This creates a **confusing dual-entry** pattern. Line 19 already runs everything line 23 runs, plus more. The AGENTS.md rule ("todo test wx-runtime nuevo debe quedar en run_tests.bat") is ambiguous — does it mean "listed explicitly on line 23" or "covered by pytest tests/ on line 19"?

### Existing test files in tests/ui/ — classification

| File | Type | Count | Covers |
|------|------|-------|--------|
| `test_chat_panel_runtime.py` | runtime | 13 | ChatPanel stream_display, select_and_announce, attach_url |
| `test_chat_panel_static.py` | static | ~18 | ChatPanel AST: names, sizers, methods |
| `test_main_window_runtime.py` | runtime | ~25 | Recents, export, auto-restore, F2, attach URL, notifier, system_voice |
| `test_main_window_static.py` | static | ~50 | MainWindow AST: menus, accelerators, guards, tool-calling lifecycle |
| `test_find_dialog.py` | runtime | 9 | FindDialog instantiation, focus, query, buttons |
| `test_find_dialog_static.py` | static | 7 | FindDialog AST: names, sizers |
| `test_chat_quick_actions.py` | runtime | 11 | copy_last, delete_last_exchange, edit_message, regenerate, context menu |
| `test_keymap_accelerator.py` | runtime | 7 | AcceleratorTable count, overrides, shortcuts dialog |
| `test_keymap_capture.py` | runtime | 13 | Atajos tab structure, CaptureDialog, conflict detection |
| `test_url_dialog.py` | runtime | 6 | URLDialog instantiation, focus, get_url, buttons |
| `test_message_detail_dialog_runtime.py` | runtime | 2 | Reasoning section visibility |
| `test_message_detail_dialog_static.py` | static | 12 | MessageDetailDialog AST: names, buttons, reasoning logic |
| `test_permission_dialog_runtime.py` | runtime | 4 | PermissionDialog edit re-classify |
| `test_permission_dialog_static.py` | static | 17 | PermissionDialog AST: names, mnemonics, risk labels |
| `test_mainwindow_construction.py` | runtime | 1 | Window shown before I/O |
| `test_server_watchdog.py` | runtime | 4 | Watchdog dialog paths |
| `test_wx_notifier_runtime.py` | runtime | 1 | WxToastSender instantiation |
| `test_wx_notifier_static.py` | static | 5 | wx.adv import guards |
| `test_preferences_dialog_static.py` | static | ~35 | PreferencesDialog AST: tabs, hints, mnemonics, presets, audio controls |
| `test_lectura_tab_static.py` | static | 6 | Lectura tab AST: 4 checkboxes, labels, ordering |
| `test_voice_dialog_static.py` | static | 7 | VoiceDialog AST: choice, slider, buttons, names |
| `test_high_contrast_static.py` | static | 4 | Cross-file AST: no hardcoded colours, no TE_RICH2 |
| `test_abort_flag.py` | static | 6 | _aborted flag ordering |
| `test_chat_panel.py` | manual-only | 0 | Comments only |
| `test_main_window.py` | manual-only | 0 | Comments only |
| `test_params_panel.py` | manual-only | 0 | Comments only |

**Count**: 27 files total: 14 runtime, 10 static/AST, 3 manual-only.

### run_tests.bat line 23 — explicit list analysis

Currently includes 11 files:
- `test_chat_panel_runtime.py`
- `test_find_dialog.py`
- `test_main_window_runtime.py`
- `test_url_dialog.py`
- `test_message_detail_dialog_runtime.py`
- `test_permission_dialog_runtime.py`
- `test_preferences_dialog_static.py`
- `test_lectura_tab_static.py`
- `test_voice_dialog_static.py`
- `test_wx_notifier_static.py`
- `test_wx_notifier_runtime.py`

**Missing from line 23** (but covered by line 19's `pytest tests/`):
- `test_chat_quick_actions.py` — runtime
- `test_keymap_accelerator.py` — runtime
- `test_keymap_capture.py` — runtime
- `test_server_watchdog.py` — runtime
- `test_mainwindow_construction.py` — runtime
- `test_main_window_static.py` — static
- `test_chat_panel_static.py` — static
- `test_find_dialog_static.py` — static
- `test_message_detail_dialog_static.py` — static
- `test_permission_dialog_static.py` — static
- `test_high_contrast_static.py` — static
- `test_abort_flag.py` — static

Because line 19 (`pytest tests/`) is a recursive discovery, all these files DO run on Windows. Line 23 is purely redundant. The only scenario where line 23 matters is if line 19 were removed or broken.

### Smoke test (smoke_test.py) gaps

**Fase 2 (GUI imports)** in `_MODULOS_UI` (line 45-51) only lists 5 modules:
- `bellbird.ui.chat_panel`
- `bellbird.ui.message_detail_dialog`
- `bellbird.ui.permission_dialog`
- `bellbird.ui.preferences_dialog`
- `bellbird.ui.main_window`

**Missing**: `bellbird.ui.voice_dialog`, `bellbird.ui.url_dialog`, `bellbird.ui.find_dialog`, `bellbird.ui.wx_notifier`.

**Fase 3 (UIA tree)** is comprehensive — it walks the actual control tree and checks all interactive controls for name=. Not affected by the module list gap.

### Coverage Gaps — Missing Runtime Tests

#### GAP 1: `PreferencesDialog` — NO runtime test file exists
- **Severity**: HIGH
- **File needed**: `tests/ui/test_preferences_dialog_runtime.py`
- The dialog has 9 tabs with complex logic:
  - **Presets sub-panel** (v0.11.0): ListBox + 3 buttons. No test verifies `apply_preset()` changes config fields, or save/delete lifecycle.
  - **Lectura tab** (v0.11.0): 4 filter CheckBoxes. No test verifies state loads from/saves to `config.text_filters`.
  - **Audio tab** (v0.10.0): voice Choice, rate Slider, 4 checkboxes. Static AST exists but no runtime instantiation test.
  - **Status tab (F2)**: 11 toggle CheckBoxes. Static AST exists but no runtime test loads/saves toggles.
  - **Model page**: temp/min-p sliders, max_tokens spin, presets sub-panel.
  - **Advanced page**: top-p/top-k sliders, repeat slider, seed spin, stop text.
  - **General, Chat, Tools, Keymap** tabs.
  - **`_apply_config`** — no runtime test verifies it writes to config correctly across all tabs.
  - **Dialog OK/Cancel flow** — no test verifies OK saves config and Cancel discards it.

#### GAP 2: `VoiceDialog` — NO runtime test file exists
- **Severity**: MEDIUM
- **File needed**: `tests/ui/test_voice_dialog_runtime.py`
- No test instantiates `VoiceDialog` with real wx, sets selection, and verifies `get_voice()` / `get_rate()`.
- Dialog is used by `preferences_dialog.py` _on_test_voice and _on_select_voice handlers.
- `core/system_voice.py` has AST guards but no runtime integration test.

#### GAP 3: `SystemVoice` SAPI voice selection — NO runtime test
- **Severity**: LOW (SAPI is Windows-only, hard to mock)
- **File needed**: `tests/core/test_system_voice_runtime.py` (with importorskip)
- `core/system_voice.py::SystemVoice` has AST guards (`test_ast_no_wx_import`) but no test constructs and calls `speak_with_system_voice()`.
- Acceptable debt — SAPI calls are inherently hard to test without a real SAPI runtime.

#### GAP 4: `status_formatter.py` + F2 handler — MOSTLY covered
- **Severity**: LOW
- `core/status_formatter.py` has thorough core tests in `test_status_formatter.py`.
- F2 handler (`_announce_session_status`) has runtime tests in `test_main_window_runtime.py` (TestF2StatusFormatter, TestDoubleF2).
- What's missing: end-to-end test that F2 keypress → accelerator → handler → format_status → speech. Currently tested in pieces.

#### GAP 5: `test_keymap_capture.py::TestSixTabOrder` is outdated
- **Severity**: MEDIUM (actively failing test?)
- The test hardcodes `len(labels) == 6` but PreferencesDialog now has **9 tabs**.
- This test was written for the v0.8.1/0.8.2 state (6 tabs) and never updated after Audio (v0.10.0) and Lectura (v0.11.0) were added.
- If the test currently passes, it means `inspect.getsource(PreferencesDialog._build_ui)` somehow gets a stale copy — but that seems unlikely. This is likely a **broken test**.

#### GAP 6: Smoke test `_MODULOS_UI` is incomplete
- **Severity**: LOW (Fase 2 is optional; Fase 3 covers the real tree)
- Missing: `bellbird.ui.voice_dialog`, `bellbird.ui.url_dialog`, `bellbird.ui.find_dialog`, `bellbird.ui.wx_notifier`.

### Risks

1. **`run_tests.bat` dual-discovery creates maintenance drag**. New wx-runtime tests get added to line 19 automatically, but the AGENTS.md rule says they must be "registered in run_tests.bat". If the user interprets that as "added to line 23", the explicit list grows in parallel with line 19, silently diverging. If they interpret it as "pytest tests/ covers it", line 23 is dead code.

2. **`test_keymap_capture.py::TestSixTabOrder` is stale**. It expects 6 tabs; the dialog has 9. If it currently passes (unlikely), it's using a cached/outdated source and the test is deceptive. If it fails, it's a CI-red-herring that got ignored.

3. **PreferencesDialog has ZERO runtime tests for a dialog with 9 tabs and ~80 controls**. Any regression in `_apply_config`, tab switching, or control state loading from config is invisible to the test suite.

4. **Smoke test Fase 2 won't detect import errors** in `voice_dialog.py`, `url_dialog.py`, `find_dialog.py`, or `wx_notifier.py` because they're not in the import list.

### Open Questions

1. **`run_tests.bat` line 23: keep, drop, or restructure?** The cleanest shape is a single `pytest tests/` call on line 19, removing the redundant explicit list on line 23. But the AGENTS.md rule says "registrado en run_tests.bat" — does removing line 23 violate that convention? Alternative: change line 23 to a comment documenting which tests are wx-runtime, rather than re-executing them.

2. **Should `test_keymap_capture.py::TestSixTabOrder` be fixed now (as part of this change) as a pre-condition?** It's not strictly about test COVERAGE, but it's a broken test in the same directory.

3. **What's the scope boundary for "more coverage"?** The prompt asks about runtime tests for new v0.10.0/v0.11.0 components. Does this also include fixing the smoke test module list, or is that a separate concern?

4. **No runtime test for PreferencesDialog OK/Cancel flow** — should we add a comprehensive `test_preferences_dialog_runtime.py`, or is the existing `test_preferences_dialog_static.py` + HINTS coverage considered sufficient? The AST tests verify structure (names, sizers, mnemonics) but don't touch config at runtime.
