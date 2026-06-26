# Proposal: Windows-side Test Coverage (v0.11.0 → v0.12.0 infra)

## Intent

WSL tests cover `core/` well and a few `ui/` modules via AST/static
checks, but **wx-runtime coverage is uneven for v0.10.0/v0.11.0
features**: `PreferencesDialog` (9 tabs, ~80 controls) has no runtime
test file, `VoiceDialog` and the Lectura tab (4 filter CheckBoxes) are
AST-only, and `SystemVoice` (SAPI) has no real SAPI exercise. Also:
`run_tests.bat` line 23 is a redundant re-invocation of files already
covered by line 19's `pytest tests/`, and
`tests/ui/test_keymap_capture.py::TestSixTabOrder` is **stale** —
expects 6 tabs, dialog has 9 (would FAIL on Windows; silently
`importorskip`'d on WSL). `smoke_test.py::_MODULOS_UI` is missing 4 of
the 9 `bellbird/ui/*.py` modules.

## Scope

### In Scope
- 4 new wx-runtime test files (PreferencesDialog, VoiceDialog, Lectura
  tab, SystemVoice) — `importorskip("wx")` pattern, executed by
  `run_tests.bat` on Windows.
- Fix `TestSixTabOrder` to expect 9 tabs in the actual order (incl.
  audio & status); add a label-order test.
- Simplify `run_tests.bat`: drop redundant line 23 list, keep a
  comment block listing the wx-runtime files.
- `smoke_test.py::_MODULOS_UI` → `pkgutil.iter_modules` auto-discovery
  of `bellbird.ui.*`.
- `README.md` "Tests" section with the 3-level table (core/WSL →
  AST/WSL → wx-runtime/Windows → smoke/Windows).
- Update `openspec/lessons-learned.md` with the v0.11.1 entry.

### Out of Scope
- Converting existing AST tests to runtime (out of scope — AST
  catches different bugs cheaply).
- New functional features.
- Editing `bellbird/` source code.

## Capabilities

### New Capabilities
- `windows-tests`: the Windows-side test-coverage layer — wx-runtime
  tests for UI dialogs, runtime smoke checks, and the WSL/Windows
  test-level contract.

### Modified Capabilities
- None.

## Approach

- **Tests first, source unchanged.** Every new file follows the
  existing `tests/ui/test_url_dialog.py` pattern: `importorskip("wx")`,
  module-level `wx.App()` fixture, `dlg.Destroy()` in `finally`.
- **Auto-discovery** for `_MODULOS_UI` (single source of truth = the
  filesystem) so future UI modules are automatically smoke-tested.
- **Comment block** on `run_tests.bat` instead of dual-list
  maintenance: line 19 is the executor, the comment is the index.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/ui/test_preferences_dialog_runtime.py` | New | ~140 LOC, ~7 tests |
| `tests/ui/test_voice_dialog_runtime.py` | New | ~80 LOC, ~5 tests |
| `tests/ui/test_lectura_tab_runtime.py` | New | ~60 LOC, ~3 tests |
| `tests/ui/test_system_voice_runtime.py` | New | ~70 LOC, ~4 tests |
| `tests/ui/test_keymap_capture.py` | Modified | Fix `TestSixTabOrder` + label-order test |
| `run_tests.bat` | Modified | Drop line 23 list, add comment block |
| `smoke_test.py` | Modified | `_MODULOS_UI` → `pkgutil.iter_modules` |
| `README.md` | Modified | New "Tests" section with 3-level table |
| `openspec/specs/system-voice/` | Modified | Add 1 scenario for runtime SAPI test |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| wx-runtime tests flaky across wx versions | Med | Pin wx in dev deps; tests use `wx.App()` fixture pattern from `test_url_dialog.py` |
| SAPI not installed on Windows test box | Low | `SystemVoice` test mocks `win32com.client.Dispatch` via `unittest.mock` |
| `pkgutil.iter_modules` picks up test/aux files | Low | Module has clean `bellbird/ui/*.py` files only; verified by `ls bellbird/ui/` |
| Test count breaks WSL CI | Low | All new tests are `importorskip` → SKIP cleanly on WSL, no impact on 846 baseline |

## Rollback Plan

Revert the commit group. Zero impact on `bellbird/` source code. The
single PR can be reverted with `git revert <merge-sha>`. WSL test
suite remains at 846 passed + 15 skipped baseline.

## Dependencies

- `pytest>=8` (already in dev deps).
- `wxpython>=4.2` (runtime dep, available on Windows test box).
- `pywinauto>=0.6.8 ; sys_platform == 'win32'` (already in dev deps,
  used by `smoke_test.py` Fase 3).

## Success Criteria

- [ ] 4 new wx-runtime test files execute on Windows via
      `run_tests.bat`; SKIP cleanly on WSL.
- [ ] `TestSixTabOrder` passes on Windows (9 tabs, current order).
- [ ] `run_tests.bat` has a single `pytest tests/` invocation + a
      comment block listing the wx-runtime files.
- [ ] `smoke_test.py` Fase 2 covers all 9 `bellbird/ui/*.py` modules
      via `pkgutil.iter_modules`.
- [ ] `README.md` has a "Tests" section with the 3-level table.
- [ ] WSL test suite remains 846 passed + 15 skipped (zero
      regressions).
- [ ] Cero cambios en `bellbird/` source.

## Open Questions

- Keep the explicit list on line 23 of `run_tests.bat` as a
  comment (so Miguel sees which files are wx-runtime at a glance) or
  drop it entirely? **Recommend: keep as a comment block** listing
  which `tests/ui/*.py` files are wx-runtime, then the single
  `pytest tests/` call.
