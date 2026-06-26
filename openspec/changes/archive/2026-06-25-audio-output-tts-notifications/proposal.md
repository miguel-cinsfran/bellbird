# Proposal: Audio Output (TTS on demand + SAPI + Notifications + Sounds)

## Title & Status

**Change**: `2026-06-25-audio-output-tts-notifications` → bumps Bellbird to v0.10.0.
**Status**: Proposal — ready for `sdd-spec`.

## Context & Problem

The screen reader is the primary audio channel for Bellbird's blind users, but it has two blind spots: (1) long assistant responses are hard to "re-read" without re-triggering screen-reader navigation, and (2) when the window is not focused, the user has no idea that a generation finished, the server went down, or the model is asking to run a tool. We unify the **audio output channel** beyond the screen reader with on-demand system-voice TTS (SAPI), toast notifications, and per-event sound cues — all optional, all disabled by default where they would duplicate the screen reader, and all degrading cleanly on non-Windows.

## Goal & Non-Goals

**Goal**
- A.1 TTS on demand — read a selected message with the system voice; auto-read is OFF by default.
- A.2 SAPI selection — pick voice + rate in a small accessible dialog; module no-ops outside `win32`.
- B.1 Notifications — native Windows toast via `wx.adv.NotificationMessage`, only when the app is not focused.
- B.2 Sounds — per-event WAV cues, theme-aware, silent when files are missing or disabled.
- Persistent, forward-compat config (no migration entry needed).

**Non-Goals**
- Do not read reasoning (`<think>…</think>` / `delta.reasoning_content`) out loud — reasoning stays separate (AGENTS.md rule).
- Do not touch the streaming logic (`_stream_worker`, `announce_token_chunk`, `_on_token`) — the existing screen-reader path is the live channel.
- "Presets tab", "hints", and "reading filters" (markdown strip, URL/emoji/code-block toggles) are **Change B** (not this change). This change reuses the existing `core/text_utils.strip_markdown` as-is.
- No new keybinds beyond the one documented below.
- No new dependency on `pywin32` in `core/` at module level — imported line-local under `sys.platform == "win32"`.

## Approach

### A.1 TTS on demand
- **New public surface**: `core/speech.py::Speech.speak_with_system_voice(text: str) -> None` — delegates to `core.system_voice.SystemVoice.speak()`. Never-crash contract preserved.
- **Files**: `bellbird/core/speech.py` (extend); new `bellbird/core/system_voice.py`.
- **WSL-testable**: `system_voice` exposes `voices() -> list[str]` and `set_voice(name: str) -> bool` as pure logic (no `win32com` import until `speak()` is called). Tests stub the `win32com` import. `speak_with_system_voice` on WSL is a no-op (asserted in tests).

### A.2 SAPI selection
- **New public surface**: `core/system_voice.py::SystemVoice` with `voices() -> list[str]`, `set_voice(name: str) -> bool`, `set_rate(rate: int) -> None`, `speak(text: str) -> None`. `list_available_voices() -> list[str]` module-level helper.
- **New UI**: `bellbird/ui/voice_dialog.py` (`wx.Dialog` + `wx.Choice` for voices + `wx.Slider` for rate, all with `name=` + adjacent `wx.StaticText`). Open from a new "Voz del sistema" group in the **Audio** tab (new tab, see below).
- **Files added**: `bellbird/core/system_voice.py`, `bellbird/ui/voice_dialog.py`. `bellbird/ui/preferences_dialog.py` adds an **Audio** tab (after Atajos, before Estado).
- **Testable in WSL**: `core/system_voice.py` — full unit tests (platform guard + no-op on non-win32 + voices stub + rate bounds). `ui/voice_dialog.py` — AST static test + `importorskip("wx")` runtime test, registered in `run_tests.bat`.

### B.1 Notifications
- **New public surface**: `core/notifier.py::Notifier` (pure, takes a `FocusChecker` protocol + `ToastSender` protocol + `SoundPlayer`); `core/focus.py::FocusChecker` protocol. `Notifier.notify(event: str, message: str) -> None` is silent when focused, fires toast+sonido when not.
- **New UI**: `bellbird/ui/wx_notifier.py` (wraps `wx.adv.NotificationMessage` with `Show(timeout)`); provides a `ToastSender` impl. `wx.adv` imported line-local under `if sys.platform == "win32"` and a `try/except ImportError` for systems without `wx.adv` (mirrors the v0.7.0 `core/startup.py` platform-guard pattern).
- **Files added**: `bellbird/core/notifier.py`, `bellbird/core/focus.py`, `bellbird/ui/wx_notifier.py`. `bellbird/ui/main_window.py` instantiates the notifier with `lambda: not self.IsActive()` as the focus check and a toast sender + sound player.
- **WSL-testable**: `core/notifier.py` is fully unit-tested with stubbed focus/sender/player. `wx_notifier.py` is AST + runtime-tested Windows-only.
- **Event sites in `main_window.py`** (toast only when not focused, no code change to the voice path):
  - `_on_done` → "generation_complete" (after the existing `speak("Respuesta completa")`).
  - `_on_start_server_done` (ok=True) → "server_ready".
  - `_on_error` paths → "error".
  - `_on_tool_request` (permission dialog) → "tool_request".
  - `_on_startup_probe_done` (loaded model) → "model_loaded".

### B.2 Sounds
- **New public surface**: `core/sound_player.py::SoundPlayer.play(event: str) -> None` — looks up `data/sounds/<sound_theme>/<event>.wav` (e.g. `generation_complete.wav`, `error.wav`, `server_ready.wav`, `tool_request.wav`, `model_loaded.wav`). Uses `winsound.PlaySound(str, SND_FILENAME | SND_ASYNC)` under `if sys.platform == "win32"`, line-local import, `try/except` around it. No-op elsewhere; silent when file missing.
- **Files added**: `bellbird/core/sound_player.py`, `bellbird/data/sounds/default/{generation_complete,server_ready,error,tool_request,model_loaded}.wav` (1 short beep each, generated via `winsound` or shipped as a tiny WAV — chosen at apply time; minimum viable: 1 file `beep.wav` reused for all events if generation tooling isn't ready).
- **WSL-testable**: full unit tests for path resolution, theme lookup, missing-file fallback. `PlaySound` call is monkeypatched in tests.

## Config fields

New fields on `BellbirdConfig` (all in `bellbird/core/config.py`, no migration needed — defaults are post-change values):

| Field | Type | Default | Notes |
|---|---|---|---|
| `system_voice_name` | `str` | `""` | Empty = first available. |
| `system_voice_rate` | `int` | `0` | SAPI rate, range −10..+10. Validated in dialog. |
| `auto_speak_responses` | `bool` | `False` | **Off by default** — never auto. |
| `notifications_enabled` | `bool` | `True` | Master toast toggle. |
| `sounds_enabled` | `bool` | `True` | Master sound toggle. |
| `sound_theme` | `str` | `"default"` | Subdir of `data/sounds/`. `"none"` → no playback. |

## Keybindings

**One new keybind**: `read_selected_message` → **`F8`** (no modifier, no conflict — F2/F5/F6/F7 + Ctrl+F7 are taken; F8 is free).
- Entry in `DEFAULT_KEYMAP` (`bellbird/core/keymap.py`): `Binding(KEYMAP_MOD_NONE, 346, "F8")` (`wx.WXK_F8` = 346, mirroring the existing `_WXK_F2 = 340` pattern in `core/keymap.py`).
- Handler in `_build_accelerators.handlers` (`bellbird/ui/main_window.py`): `"read_selected_message": lambda: self._on_read_selected_message()`.
- New Spanish label in `_ACTION_LABELS` (`bellbird/ui/preferences_dialog.py`): `"read_selected_message": "Leer mensaje seleccionado"`.
- Handler `_on_read_selected_message()` in `MainWindow`: if `config.auto_speak_responses` AND a `last_completed_assistant` text is available → speak that with SAPI; else take `chat_panel.message_list.GetSelection()` and speak that row's text through `Speech.speak_with_system_voice`. Empty selection → `speech.speak("Nada que leer")`. Mirrors the existing `_maybe_beep` mid-generation gate (lesson v0.8.3: gate quick-actions on `self.chat_panel._is_generating`).
- Strip markdown with `core.text_utils.strip_markdown` before speaking (no other filters — that's Change B).

## Files to add / modify

**Add (core, wx-free)**:
- `bellbird/core/system_voice.py` — SAPI wrapper, no-op outside win32, line-local `win32com` import.
- `bellbird/core/notifier.py` — pure dispatcher (focus + toast + sound policy).
- `bellbird/core/focus.py` — `FocusChecker` protocol (so `core/` stays wx-free).
- `bellbird/core/sound_player.py` — `winsound.PlaySound` wrapper, line-local import, no-op fallback.
- `bellbird/data/sounds/default/*.wav` — theme assets (shipped with the change or generated at apply).

**Add (ui, wx)**:
- `bellbird/ui/voice_dialog.py` — small `wx.Dialog` for voice + rate.
- `bellbird/ui/wx_notifier.py` — `wx.adv.NotificationMessage` wrapper, line-local `wx.adv` import.

**Modify**:
- `bellbird/core/speech.py` — add `speak_with_system_voice(text)` (never-crash preserved).
- `bellbird/core/config.py` — add 6 fields + forward-compat works automatically.
- `bellbird/core/keymap.py` — add `read_selected_message: Binding(KEYMAP_MOD_NONE, 346, "F8")`.
- `bellbird/ui/preferences_dialog.py` — add **Audio** tab + `_ACTION_LABELS["read_selected_message"]`.
- `bellbird/ui/main_window.py` — wire notifier at 5 event sites, register keybind handler, add `_on_read_selected_message`, instantiate notifier in `__init__`.
- `bellbird/ui/chat_panel.py` — add `get_selected_message_text() -> str` helper (testable on WSL via AST).
- `requirements.txt` — add `pywin32` (Windows-only runtime; guarded by platform check).
- `tests/core/test_system_voice.py`, `tests/core/test_notifier.py`, `tests/core/test_sound_player.py`, `tests/ui/test_voice_dialog_static.py`, `tests/ui/test_wx_notifier_static.py`, `tests/ui/test_main_window_runtime.py` (extend) — new test files + extend `test_keymap.py` to assert the new `read_selected_message` entry is collision-free.
- `run_tests.bat` — register any new wx-runtime tests.
- `pyproject.toml` — bump to `0.10.0`.
- `openspec/specs/speech/spec.md` — delta: add `speak_with_system_voice` requirement.

## Open questions & risks

| # | Risk / Open question | Mitigation |
|---|---|---|
| R1 | `SAPI.SpVoice` is COM-bound; `win32com.client` only exists with `pywin32` (Windows). Module must degrade to no-op on other platforms. | `if sys.platform == "win32":` guard + line-local `import win32com.client` inside `try/except ImportError`. Unit test on WSL: `speak_with_system_voice` is a no-op, `voices()` returns `[]`. |
| R2 | `winsound.PlaySound` may raise for missing/corrupt WAV files or for non-NT paths. | Wrap in `try/except Exception: pass`; resolve the path, check `Path.is_file()` first; degrade to silence if missing. |
| R3 | `wx.adv.NotificationMessage` requires a registered taskbar entry on Windows. Tests cannot construct it on WSL. | `wx_notifier.py` imports `wx.adv` line-local under `sys.platform == "win32"`. AST test asserts the import is line-local. Runtime test in `run_tests.bat` instantiates and calls `Show(0)` with a try/except. |
| R4 | SAPI voice list varies by installed TTS engines; a configured voice may disappear. | On missing voice, fall back to `set_voice("")` (first available) and log a warning. `voices()` is the source of truth. |
| R5 | Sounds may be annoying if played during focused app. | Per-spec, toasts and sounds fire only when `IsActive() is False`; same gate that already exists for `_maybe_beep` (lesson v0.8.3). |
| R6 | The Audio tab may grow — Change B (presets, filters) will also land here. | Keep this change's tab **audio-only** (system voice, auto-read, notifications, sounds). Change B adds a separate or extended tab. |
| Q1 | Should `speak_with_system_voice` interrupt current screen-reader speech, or queue? | Spec: **never interrupt** — always `interrupt=False`. Screen reader is the primary; SAPI is supplementary. |
| Q2 | Should the new `F8` shortcut be remappable from day 1? | Yes — it is in `DEFAULT_KEYMAP`, so it appears in the Atajos tab automatically (lesson v0.8.0). |
| Q3 | WAV asset sourcing — bundle or generate at first run? | Bundle 1 short `beep.wav` reused for all 5 events to start; richer themes deferred to a follow-up change. |

## Acceptance criteria

- [ ] `uv run --no-sync pytest -xvs` green in WSL (594+ tests, +new core tests).
- [ ] `run_tests.bat` green in Windows (594+ tests + new wx-runtime tests).
- [ ] On any non-win32 platform, all new modules (`system_voice`, `notifier`, `sound_player`, `wx_notifier`) are silent no-ops with no exceptions.
- [ ] `F8` reads the selected message via SAPI; empty selection announces "Nada que leer"; mid-generation announces "Generación en curso" and returns.
- [ ] Toasts + sounds fire ONLY when the app is not focused (assertable in tests via stub `IsActive`).
- [ ] `auto_speak_responses` defaults to `False`; flipping it persists across restarts (forward-compat via `__dataclass_fields__` filter, no migration).
- [ ] Reasoning is never spoken (assertable: no calls to `speak_with_system_voice` from reasoning paths).

## Workload forecast

- **Estimated LOC**: ~700-900 changed lines (system_voice ~150, notifier ~120, sound_player ~100, voice_dialog ~180, wx_notifier ~80, speech.py +20, config.py +6, keymap.py +1, preferences tab ~120, main_window wiring ~80, chat_panel helper ~15, tests ~250-300).
- **Recommendation: SPLIT into 2 WUs** (per lesson v0.8.2 "split when >=400 lines or 5+ UI tasks"):
  - **WU-1 (core + tests)**: `system_voice.py`, `notifier.py`, `focus.py`, `sound_player.py`, `core/speech.py` extension, `config.py` fields, all `tests/core/` new files, keymap entry. ~400-500 lines, no wx.
  - **WU-2 (ui + wx-tests)**: `voice_dialog.py`, `wx_notifier.py`, preferences Audio tab, `main_window.py` notifier wiring + `_on_read_selected_message`, `_ACTION_LABELS` entry, `chat_panel.get_selected_message_text`, AST + runtime tests, `run_tests.bat` update, `pyproject.toml` bump, requirements.txt.
- **Risk**: if budget is exceeded, split WU-2 further (voice dialog + keymap handler first; main_window wiring + notifier sites second).
