# Design: Windows-side Test Coverage

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Level 1 — WSL (developer machine)                               │
│  uv run --no-sync pytest -xvs                                   │
│    ├─ tests/core/  → real unit tests, wx-free                   │
│    ├─ tests/ui/test_*_static.py  → AST walks, no wx import       │
│    └─ tests/ui/test_*_runtime.py → importorskip("wx") → SKIP     │
├──────────────────────────────────────────────────────────────────┤
│  Level 2 — Windows (Miguel, post-pull)                           │
│  run_tests.bat                                                   │
│    └─ uv run pytest tests/ -v --tb=short                        │
│         └─ all tests, including wx-runtime → real wx execution   │
├──────────────────────────────────────────────────────────────────┤
│  Level 3 — Windows + pywinauto (Miguel, manual)                  │
│  uv run python smoke_test.py                                     │
│    ├─ Fase 1: core/ imports                                      │
│    ├─ Fase 2: bellbird/ui/*.py imports (auto-discovered)         │
│    └─ Fase 3: live UIA tree walk via pywinauto                   │
└──────────────────────────────────────────────────────────────────┘
```

The 4 new test files all live in Level 1's third bucket (SKIP on WSL
via `importorskip`) but execute for real on Level 2. They cover
runtime behaviour that AST cannot see: control state load/save,
ClickHandler outcomes, accessor round-trips, and the
`SystemVoice` never-crash contract on every code path.

## Key decisions

### Why AST tests stay
AST tests are cheap (~10 LOC per test) and catch structural drift
that runtime tests don't: missing `name=`, missing preceding
`StaticText`, forbidden `GridSizer`, `&` mnemonic collisions, the
`HINTS` table bidirectionality. Runtime tests are expensive
(construct real wx, set up `wx.App()`, manage lifecycle). The two
levels are complementary. Converting AST to runtime would inflate
test maintenance without changing the bug surface.

### Why wx-runtime tests are SKIPped on WSL
`AGENTS.md` §Tests mandates: any test that requires wxPython uses
`pytest.importorskip("wx")` so WSL's `uv run --no-sync pytest -xvs`
runs without `wx` installed. The 4 new test files follow the same
pattern as `test_url_dialog.py`, `test_chat_panel_runtime.py`,
`test_find_dialog.py`, etc. The cost: zero new failures on WSL. The
benefit: real wx coverage on Windows.

### `run_tests.bat` simplification
Today, `run_tests.bat` line 19 runs `pytest tests/` (recursive
discovery) and line 23 runs the same files plus 4 more, with the
exact list already 4 entries stale (`test_chat_quick_actions.py`,
`test_keymap_accelerator.py`, `test_keymap_capture.py`,
`test_server_watchdog.py` are wx-runtime but not on line 23).
**Decision:** drop the dual-list, keep a comment block on line 23
that enumerates wx-runtime files for documentation. Line 19 is the
single executor. Future tests get discovered automatically; the
comment is updated only when the user wants an at-a-glance
inventory.

### `TestSixTabOrder` fix
The test was written for the v0.8.1/0.8.2 6-tab state. After
v0.10.0 (Audio) and v0.11.0 (Lectura), the dialog has 9 tabs.
The fix: update `len(labels) == 6` → `len(labels) == 9` and the
expected list to match the actual `AddPage` literals including
`&` mnemonics (the AST visitor captures the full string). The
fix lives in the test, not the dialog — the dialog is correct.

### Smoke test auto-discovery
`pkgutil.iter_modules(bellbird.ui.__path__)` returns the list of
modules in the package, exactly the set `_MODULOS_UI` should cover.
It runs on any Python that has `bellbird.ui` importable (i.e.
already verified by Fase 1). A new `bellbird/ui/foo.py` is
auto-included without editing `smoke_test.py`. This eliminates
the maintenance debt that produced the 4 missing modules in the
first place.

## File-by-file changes

### New files (4)
- `tests/ui/test_preferences_dialog_runtime.py` (~140 LOC, ~7 tests)
  - `TestPreferencesDialogInstantiation` — construct, verify type, verify name
  - `TestPreferencesDialogOKRoundtrip` — OK on unmodified config
  - `TestPreferencesDialogSystemPrompt` — change prompt, _apply_config, verify
  - `TestPreferencesDialogLecturaFilter` — toggle one filter, _apply_config, verify
  - `TestPreferencesDialogPresetSelection` — select preset, _apply_preset_to_controls
  - `TestPreferencesDialogAudioVoice` — change voice/rate, verify accessors
  - `TestPreferencesDialogControlNames` — `FindWindowByName` for documented names
- `tests/ui/test_voice_dialog_runtime.py` (~80 LOC, ~5 tests)
  - `construct_with_choices` — verify Choice populated
  - `get_voice_returns_initial` — verify `current_voice`
  - `get_rate_returns_initial` — verify `current_rate`
  - `change_choice_updates_get_voice` — select "B", verify
  - `change_slider_updates_get_rate` — set 7, verify
- `tests/ui/test_lectura_tab_runtime.py` (~60 LOC, ~3 tests)
  - `all_4_filters_default_checked` — verify defaults
  - `uncheck_filter_updates_config` — toggle one, _apply_config, verify
  - `filter_state_round_trips_reopen` — set False on config, reopen, verify
- `tests/ui/test_system_voice_runtime.py` (~70 LOC, ~4 tests)
  - `non_win32_speak_is_noop` — guarded by `sys.platform`
  - `win32_without_sapi_swallow_exceptions` — mock `win32com.client.Dispatch` to raise
  - `set_voice_empty_returns_false` — direct
  - `set_rate_clamps` — direct, observe no exception

### Modified files (4)
- `tests/ui/test_keymap_capture.py` — update `TestSixTabOrder` to 9 tabs + label-order test. Add a comment that the order is the source-of-truth (no hard-coded elsewhere).
- `run_tests.bat` — drop line 23 list, add a 4-6 line comment block listing wx-runtime files.
- `smoke_test.py` — replace `_MODULOS_UI` literal with a function `_discover_ui_modules()` that calls `pkgutil.iter_modules`. Keep `_MODULOS_CORE` as-is (it's a curated core list, not a UI list).
- `README.md` — add `## Tests` section with the 3-level table.

### Unchanged
- `bellbird/` source code (zero diffs).
- `pyproject.toml` (no version bump — test infra, not a feature).
- `openspec/research/lessons-learned.md` (gets a v0.11.1 entry in the
  archive step, not now).

## Test plan

### WSL verification
```
$ uv run --no-sync pytest -xvs
```
Expected: 846 passed, 15 skipped (or +N skipped for the 4 new files'
`importorskip` calls). Zero new failures. Zero regressions on
existing tests.

### Windows verification (Miguel)
```
$ run_tests.bat
```
Expected: ~861 + 4N passed, ~15 + 4N skipped where 4N = tests in the 4
new files that were SKIPped on WSL. The new tests must EXECUTE
(real wx.App() created, real widgets instantiated). No
`assert` failures, no `NameError`, no `AttributeError`.

### Smoke test verification (Windows)
```
$ uv run python smoke_test.py --no-gui
```
Expected: Fase 1 lists 9 core modules [ok], Fase 2 lists 9 UI modules
[ok] (auto-discovered). Exit 0.

## Out of scope

- Converting AST tests to runtime (kept as-is).
- New functional features.
- Test for the v0.6.1 housekeeping debt (dead `_startup_check`).
- Bumping version (`pyproject.toml` stays at 0.11.0).
