# Apply Progress — build-exe

**Date:** 2026-06-26
**Change:** build-exe (v0.11.0)
**Status:** WU-1 complete

## What Was Done

Implemented all 5 WU-1 tasks for the Bellbird Windows build pipeline:

- **Task 1.1** — Rewrote `scripts/build_windows.sh` with full rebrand from
  OllamaChat to Bellbird, complete hidden imports (10 entries), sound datas,
  build.bat cleanup, uv preference, LEEME.txt rewrite.
- **Task 1.2** — Added `pyinstaller>=6 ; sys_platform == 'win32'` to
  `[dependency-groups] dev` in `pyproject.toml`.
- **Task 1.3** — Added "Build (Windows .exe)" section to README.md (~10 lines).
- **Task 1.4** — Created `tests/build/test_build_windows_script.py` (32 AST/static tests).
- **Task 1.5** — Ran `bash -n scripts/build_windows.sh` (OK), `pytest -xvs tests/build/` (32/32 passed),
  and full suite (846 passed, 15 skipped).

## Commits

| Hash | Subject |
|---|---|
| `babd4c3` | chore(build): add pyinstaller to dev deps with platform marker + README build section |
| `b449c3f` | feat(build): rebrand build_windows.sh to Bellbird with complete spec + cleanup |
| `ab6e143` | test(build): add AST tests for build_windows.sh script |

## Test Count Delta

- New `tests/build/` tests: **32**
- Previous total: **814 passed** (v0.11.0 baseline)
- New total: **846 passed, 15 skipped**
- Delta: +32 tests, 0 regressions

## Deviations from tasks.md

None. All tasks implemented as specified.

## Files Changed

| File | Lines | Status |
|---|---|---|
| `scripts/build_windows.sh` | +42 / -31 | Rebrand + hidden imports + datas + cleanup + LEEME |
| `pyproject.toml` | +1 | Added pyinstaller dev dep with platform marker |
| `README.md` | +15 | Added Build section |
| `tests/build/__init__.py` | +0 | New package (empty) |
| `tests/build/test_build_windows_script.py` | +352 | 32 AST/static tests |

## Next

Ready for verify phase.
