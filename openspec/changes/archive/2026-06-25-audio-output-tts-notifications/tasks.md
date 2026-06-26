# Tasks: Audio Output — TTS on demand + SAPI + Notifications + Sounds

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 750–950 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Delivery strategy | ask-on-risk |
| Suggested split | WU-1 core (core+tests) → WU-2 (UI + wx-tests) |
| Chain strategy | size-exception |

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| WU-1 | Core + tests (13 tasks, ~400-500 LOC, no wx) | Commit 1 | `master` direct; all `core/` modules + `tests/core/` |
| WU-2 | UI + wx-tests (11 tasks, ~350-450 LOC, wx) | Commit 2 | `master` direct; `ui/` + `tests/ui/` + `run_tests.bat` |

---

## WU-1: Core + Tests (no wx, ~400-500 LOC)

#### T1A — config fields: add 6 new fields + round-trip tests
- type: test
- files: `bellbird/core/config.py`, `tests/core/test_config.py`
- deliverable: 6 fields round-trip; forward-compat regression guards pass
- depends_on: —
- spec_ref: `app-configuration` §Added Requirements, 6 scenarios

#### T1B — keymap entry: `read_selected_message` → F8
- type: test
- files: `bellbird/core/keymap.py`, `tests/core/test_keymap.py`
- deliverable: entry exists in `DEFAULT_KEYMAP`, no collision, round-trips on `set_override`
- depends_on: —
- spec_ref: proposal §Keybindings

#### T1C — `core/system_voice.py` test first
- type: test
- files: `tests/core/test_system_voice.py`
- deliverable: tests for voices(), set_voice, set_rate, speak, platform guards, never-crash
- depends_on: T1A (SystemVoice uses config voice_name)
- spec_ref: `system-voice` §Requirements, all scenarios

#### T1D — `core/system_voice.py` impl
- type: impl
- files: `bellbird/core/system_voice.py`
- deliverable: `SystemVoice` class with line-local `win32com.client`, no `import wx`, no-op outside win32
- depends_on: T1C
- spec_ref: `system-voice` §Requirements

#### T1E — `Speech.speak_with_system_voice` test first
- type: test
- files: `tests/core/test_speech.py`
- deliverable: tests for new method, delegation to SystemVoice, never-crash, independent of `speak()`
- depends_on: T1D
- spec_ref: `speech` §v0.10.0 Requirement: speak_with_system_voice

#### T1F — `Speech.speak_with_system_voice` impl
- type: impl
- files: `bellbird/core/speech.py`
- deliverable: new method delegates to `SystemVoice.speak`, never-crash preserved
- depends_on: T1E
- spec_ref: `speech` §v0.10.0 Requirement

#### T1G — `core/sound_player.py` test first
- type: test
- files: `tests/core/test_sound_player.py`
- deliverable: tests for path resolution, missing file, theme="none", non-win32, never raises
- depends_on: T1A (config fields for sound_theme)
- spec_ref: `notifications` §SoundPlayer.play

#### T1H — `core/sound_player.py` impl
- type: impl
- files: `bellbird/core/sound_player.py`
- deliverable: `SoundPlayer.play()` with `winsound` line-local, `Path.is_file()` guard
- depends_on: T1G
- spec_ref: `notifications` §SoundPlayer.play

#### T1I — `core/focus.py` protocol + AST test
- type: test
- files: `bellbird/core/focus.py`, `tests/core/test_focus.py`
- deliverable: `FocusChecker` protocol defined, AST test asserts no `wx` import
- depends_on: —
- spec_ref: `notifications` §FocusChecker protocol

#### T1J — `core/notifier.py` test first
- type: test
- files: `tests/core/test_notifier.py`
- deliverable: tests for focus-aware dispatch, notifications_enabled, sounds_enabled, sound_theme="none", never-crash, no reasoning path
- depends_on: T1G, T1I
- spec_ref: `notifications` §Notifier Requirements

#### T1K — `core/notifier.py` impl
- type: impl
- files: `bellbird/core/notifier.py`
- deliverable: `Notifier` with focus + toast + sound policy; no `import wx`
- depends_on: T1J
- spec_ref: `notifications` §Requirements

#### T1L — sound assets + generation script
- type: chore
- files: `bellbird/data/sounds/default/*.wav`, `scripts/generate_sound_assets.py`
- deliverable: 5 WAV files (50ms, 880Hz) + re-runnable generation script
- depends_on: T1H
- spec_ref: design §8 Sound Assets

#### T1M — WU-1 integration: green suite + apply-progress.md
- type: chore
- files: — (run `uv run --no-sync pytest -xvs`)
- deliverable: all core tests pass; `apply-progress.md` created with WU-1 hash
- depends_on: T1A through T1L
- spec_ref: proposal §Acceptance criteria

---

## WU-2: UI + wx-tests (~350-450 LOC)

#### T2A — `ui/voice_dialog.py` test first (AST + runtime)
- type: test
- files: `tests/ui/test_voice_dialog_static.py`, `tests/ui/test_voice_dialog_runtime.py`
- deliverable: AST asserts `wx.Choice("voice_choice")`, `wx.Slider("rate_slider")`, OK/Cancel buttons with `name=`, preceding `wx.StaticText`
- depends_on: T1D (SystemVoice API)
- spec_ref: design §5 VoiceDialog

#### T2B — `ui/voice_dialog.py` impl
- type: impl
- files: `bellbird/ui/voice_dialog.py`
- deliverable: `wx.Dialog` with voice choice + rate slider + OK/Cancel; returns `(voice_name, rate)`
- depends_on: T2A
- spec_ref: design §5 VoiceDialog

#### T2C — `ui/wx_notifier.py` test first (AST + runtime)
- type: test
- files: `tests/ui/test_wx_notifier_static.py`, `tests/ui/test_wx_notifier_runtime.py`
- deliverable: AST asserts `import wx.adv` is line-local; runtime test calls `Show(0)`
- depends_on: —
- spec_ref: `notifications` §wx_notifier Requirements

#### T2D — `ui/wx_notifier.py` impl
- type: impl
- files: `bellbird/ui/wx_notifier.py`
- deliverable: `WxToastSender` wrapping `wx.adv.NotificationMessage`, line-local import
- depends_on: T2C
- spec_ref: `notifications` §wx_notifier Requirements

#### T2E — Preferences Audio tab test first
- type: test
- files: `tests/ui/test_preferences_dialog_static.py`
- deliverable: AST checks for Audio tab, controls with `name=`, preceding `wx.StaticText`, `sound_theme` choice
- depends_on: T2B, T2D
- spec_ref: design §5 Audio tab

#### T2F — Preferences Audio tab + `_ACTION_LABELS` impl
- type: impl
- files: `bellbird/ui/preferences_dialog.py`
- deliverable: Audio tab with 4 groups, `"read_selected_message"` label, wired to config; `_apply_config` saves new fields
- depends_on: T2E
- spec_ref: design §5 Preferences Audio tab, proposal §Keybindings

#### T2G — `chat_panel.get_selected_message_text()` test first
- type: test
- files: `tests/ui/test_chat_panel_static.py`
- deliverable: AST test asserts `get_selected_message_text()` exists
- depends_on: —
- spec_ref: design §1 Data flow

#### T2H — `chat_panel.get_selected_message_text()` impl
- type: impl
- files: `bellbird/ui/chat_panel.py`
- deliverable: helper returns text of selected row from `_history`
- depends_on: T2G
- spec_ref: design §1 Data flow

#### T2I — `main_window.py` notifier + F8 handler test first
- type: test
- files: `tests/ui/test_main_window_runtime.py`
- deliverable: tests assert `_on_read_selected_message` exists, bound to F8, notifier wired at 5 event sites
- depends_on: T1K (Notifier), T2D (WxToastSender), T2H (get_selected_message_text)
- spec_ref: `notifications` §Five notifier event sites

#### T2J — `main_window.py` notifier wiring + F8 handler impl
- type: impl
- files: `bellbird/ui/main_window.py`
- deliverable: `_build_accelerators` handler, 5 notifier calls, `_on_read_selected_message`, `_NullToastSender` inner class
- depends_on: T2I
- spec_ref: `notifications` §Five notifier event sites, design §6

#### T2K — WU-2 integration: green suite + bump + apply-progress.md
- type: chore
- files: `pyproject.toml`, `run_tests.bat`, `apply-progress.md`
- deliverable: `0.10.0` bumped; all tests green; new wx-runtime tests in `run_tests.bat`; WU-2 hash recorded
- depends_on: T2A through T2J
- spec_ref: proposal §Acceptance criteria

---

## Review Workload Forecast

- Total tasks: 24 (13 WU-1 + 11 WU-2)
- Total estimated LOC: 750–950
- WU-1 LOC: 400–500
- WU-2 LOC: 350–450
- Chained PRs recommended: No
- 400-line budget risk: Medium
- Decision needed before apply: No

Note: Each WU is a single commit. AGENTS.md forbids branches/PRs — all commits go direct to `main`.
