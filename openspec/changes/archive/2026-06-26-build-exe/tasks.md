# Tasks: Bellbird Windows Build Pipeline

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: n/a (single PR, single WU)
400-line budget risk: Low (forecast ~150–300 lines total)
800-line budget risk: Low

## Work-Unit 1 — Build infra + tests (single WU)

- [x] 1.1 Rewrite `scripts/build_windows.sh` heredocs:
  - Rebrand all embedded strings: OllamaChat → Bellbird, `ollamachat.spec`
    → `bellbird.spec`, `ollamachat_v${VERSION}_${TIMESTAMP}` →
    `bellbird_v${VERSION}_${TIMESTAMP}`, `dist\ollamachat\ollamachat.exe`
    → `dist\Bellbird\Bellbird.exe`, repo URL to the real Bellbird repo
    (Miguel to confirm in apply, default
    `https://github.com/miguel-cinsfran/bellbird`).
  - Fix `bellbird.spec` `Analysis` entry: `bellbird/main.py` (NOT
    `ollamachat/main.py`).
  - Complete `hiddenimports=[...]`: add `wx.adv`, `markdown`,
    `platformdirs`, `gguf`, `html.parser`, `unicodedata` (keep the
    existing `wx`, `accessible_output2`, `accessible_output2.outputs.auto`,
    `requests`). Order does not matter; the test asserts presence.
  - Add `datas=[('bellbird/data/sounds/default/*.wav',
    'data/sounds/default')]` (the pattern that PyInstaller's glob
    handling expects).
  - Add `if exist build rmdir /s /q build` + `if exist dist rmdir
    /s /q dist` to the embedded `build.bat` heredoc, BEFORE the
    `pyinstaller` invocation.
  - Rewrite the `LEEME.txt` heredoc end-user instructions in Spanish
    (Bellbird branding, Python 3.12 + uv, `%LOCALAPPDATA%\Bellbird`
    for config/log, repo URL).
  - Update the script's header docstring (lines 2–22) to match the
    new artifact names.
  - **No** change to the `rsync` exclude list, the test step, or the
    zip fallback.
- [x] 1.2 Add `pyinstaller>=6 ; sys_platform == 'win32'` to
  `[dependency-groups] dev` in `pyproject.toml` (after the existing
  `pywinauto` entry). **Do NOT** bump `[project].version` (stays
  `0.11.0`).
- [x] 1.3 Add a "Build" section to `README.md` (5–10 lines) between
  the existing "Estado" and "Atajos de teclado" blocks. Mention:
  `scripts/build_windows.sh`, kit zip, Windows-side `build.bat`,
  `dist\Bellbird\Bellbird.exe`, Python 3.12 + uv requirement.
- [x] 1.4 Add `tests/build/test_build_windows_script.py` (~100 LOC)
  with the AST/static tests listed in `design.md` §"File-by-file
  Changes" → `tests/build/`. Each test references the spec
  requirement it guards (comment line `# REQ-BUILD-N`). The test
  file MUST be self-contained (no `bellbird/` imports, no `wx`
  imports) and runnable with `uv run --no-sync pytest -xvs
  tests/build/`.
- [x] 1.5 Run `bash -n scripts/build_windows.sh` and
  `uv run --no-sync pytest -xvs tests/build/`. Both must pass.
- **Commit:** `chore(build): rebrand scripts/build_windows.sh, add pyinstaller dev dep, and AST test suite`

## Work-Unit 2 — Manual Windows verification (post-apply, out of band)

> Not an automated task. Documented in `apply-progress.md` and the
> eventual `archive-report.md`. The WSL loop cannot exercise the
> Windows side.

- [ ] 2.1 (Miguel, Windows 11) Run `scripts/build_windows.sh` in
  WSL. Verify the kit zip lands at
  `dist/bellbird_v0.11.0_<timestamp>.zip`.
- [ ] 2.2 (Miguel, Windows 11) Move the zip to the Windows box,
  unzip, run `build.bat`. Verify `dist\Bellbird\Bellbird.exe` is
  produced.
- [ ] 2.3 (Miguel, Windows 11 + NVDA) Launch `Bellbird.exe`. Verify
  the window opens and NVDA announces "Bellbird". Verify a sound
  event (e.g. error beep) actually plays.
- [ ] 2.4 (Miguel, archive step) Record results in
  `openspec/changes/build-exe/archive-report.md` under "Manual
  Verification" (size of `.exe`, launch success, sound check).
- **No commit** — this is verification only.

## Workload / PR Boundary

- **Mode:** single PR (one WU). Total forecast ~150–300 lines.
- **Single commit message** (per project convention, conventional
  commits only, no AI attribution):
  `chore(build): rebrand scripts/build_windows.sh, add pyinstaller dev dep, and AST test suite`
- **Boundary:** build infra only. **Zero** changes to `bellbird/`
  source code. **Zero** changes to `run_tests.bat` or
  `tests/smoke/`. **Zero** version bump in `pyproject.toml`.
- **Risk of sub-agent prompt size:** low (one WU, 5 tasks). No need
  for `size:exception`.

## Pre-archive checklist

Before `sdd-archive`, the orchestrator MUST run:

```bash
git status --short
# Must be clean — no `??` (untracked) or `M` (modified) files in
# the change dir. If apply-progress.md or verify-report.md is
# force-added per the project convention, that's expected.
```

And the verify agent MUST confirm:

- All WU-1 tasks above are checked off in this file.
- `bash -n scripts/build_windows.sh` exits 0.
- `uv run --no-sync pytest -xvs tests/build/` is green.
- The WSL test suite as a whole (`uv run --no-sync pytest -xvs`)
  is still green — no regression to `core/` or `ui/`.

## Out of scope (do NOT do in this change)

- Bump `pyproject.toml` version (`0.11.0` stays).
- Add `bellbird/` source code changes.
- Add `run_tests.bat` entries (new test is WSL-only).
- Code signing, installer, MSIX, CI build matrix.
- Add an application icon (no `.ico` in repo).
- Bump `accessible_output2` or any runtime dep.
- Refactor `core/sound_player.py` (its `__file__`-based resolution
  is already correct under `onedir`).
