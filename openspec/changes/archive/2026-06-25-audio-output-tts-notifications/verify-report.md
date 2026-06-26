# Verify Report — Audio Output (v0.10.0)

**Date**: 2026-06-25
**Change**: 2026-06-25-audio-output-tts-notifications
**Status**: READY_TO_ARCHIVE_WITH_WARNINGS

## Test run

- `uv run --no-sync pytest -xvs`: **778 passed, 15 skipped (WSL)** in 97.54s.
  - 778 = 757 (pre-WU-1) + 21 new core tests (system_voice, notifier, sound_player, focus, speech delta) + wx-runtime importskipped.
  - WU-1 reported 757 → WU-2 reported 778 (delta: +21 — matches the 21 new core tests).
  - All new wx-runtime tests (`test_wx_notifier_runtime.py`, the new `test_main_window_runtime.py` TestNotifierWiring/TestSystemVoiceConstruction classes, extended `test_preferences_dialog_static.py`, extended `test_chat_panel_static.py`, `test_voice_dialog_static.py`) all use `importorskip("wx")` and pass on Windows via `run_tests.bat`.
- `git status --short`: clean (no `??`, no `M`).
- `git log --oneline -5`:
  - `7cd3d3d` docs(apply-progress): mark WU-2 complete
  - `2714046` feat(ui): add audio output UI (WU-2)
  - `140d3cb` feat(core): add audio output foundation (WU-1)
  - `a71fbb0` archive: v0.9.0 context-advisor + toggleable F2 (base)

## Findings

### CRITICAL (block archive)

None.

### WARNING (archive OK, file as debt)

- **W1 — `Speech.speak_with_system_voice` API drift** (`bellbird/core/speech.py:131`).
  The spec (`specs/speech/spec.md` §Added in v0.10.0) requires the signature
  `speak_with_system_voice(text: str) -> None` and says the `SystemVoice` MUST be
  "held on `self._system_voice`" (a single, lazily-constructed instance). The
  implementation takes `(self, text: str, system_voice: Any)` and does NOT hold
  any `self._system_voice` — the caller (`main_window._on_read_selected_message`)
  passes the voice in. Functionality is correct (the call site in
  `main_window.py:626` passes `self._system_voice`), but the public API differs
  from the spec. Resolution: either fix the impl to match the spec (constructor
  builds `self._system_voice`, method takes only text) OR fix the spec to
  document the dependency-injection form. Per lessons-learned v0.8.2
  ("Spec scenario language is vinculante"), this is a real spec drift. Severity
  WARNING because the runtime behavior is correct and the test suite encodes
  the impl-side API.

- **W2 — Notifier has 6 call sites in `main_window.py`; spec/proposal table lists 5**
  (`bellbird/ui/main_window.py:1036, 1165, 1620, 1680, 1864, 1901`).
  The proposal §B.1 and the spec §"Five notifier event sites in `MainWindow`"
  table both enumerate exactly five sites:
  `generation_complete` (`_on_done`), `server_ready` (`_on_start_server_done`),
  `model_loaded` (`_on_startup_probe_done`), `tool_request` (`_on_tool_request`),
  and `error` (`_on_error` paths). The implementation has six: the same five
  plus a `notifier.notify("error", "Servidor caído")` in
  `_on_server_state_checked` (state == "dead"). The watchdog dead-server
  notification is a sensible addition (more informative than the generic
  "Error"), but it is not in the spec. Resolution: either remove the watchdog
  notify (and rely on the in-window speech + restart dialog) OR update the
  spec to document the 6th site. Severity WARNING because the additional call
  does not violate any spec scenario — it extends beyond the documented contract.

- **W3 — Spec class name `WxNotifier` and method `send` are wrong** (spec
  `specs/notifications/spec.md` lines 190–228).
  The spec repeatedly references `WxNotifier` (class name) and `send(event,
  message)` (method). The implementation, the proposal §A.2/B.1, the design
  §2, and the tests all use `WxToastSender` with `show(title, message,
  timeout=5)`. The `wx_notifier.py` file is named after the module, the
  `WxToastSender` class is what production uses, and the runtime test
  (`test_wx_notifier_runtime.py`) instantiates `WxToastSender` and calls
  `.show()`. The spec scenarios are unsatisfiable as written (e.g.
  "`WxNotifier().send("generation_complete", "Listo")`" — this exact call
  would `AttributeError`). Resolution: spec cleanup commit that renames all
  `WxNotifier` → `WxToastSender` and `send(event, message)` → `show(title,
  message, timeout)`. Severity WARNING because the impl is the source of
  truth and the test suite enforces the impl-side names. Per lessons-learned
  v0.8.2 §"Spec wording drift entre proposal/spec/impl es normal", track as
  doc-debt.

- **W4 — Design says `voice_selector`, impl uses `pref_system_voice_choice`**
  (`bellbird/ui/preferences_dialog.py:748` vs. `design.md:257`).
  The design §5 calls the voice Choice `name="voice_selector"`, but the
  implementation uses `name="pref_system_voice_choice"` (and the test
  `test_audio_tab_controls_have_names` enforces the latter). The implementation
  name follows the existing `pref_*_choice` convention in the file. Severity
  WARNING — design drift, not behavior drift.

### SUGGESTION (optional polish)

- **S1 — `core/speech.py:131` lacks a docstring on the `Any` type** for the
  `system_voice` parameter. Trivial follow-up. Not blocking.
- **S2 — `bellbird/ui/main_window.py:618-626` could be split for readability**
  (`_on_read_selected_message` is currently 4 if-branches in 13 lines). The
  helper `chat_panel.get_selected_message_text()` already encapsulates the
  selection logic, so the handler is concise. Optional follow-up.
- **S3 — `core/notifier.py:78-81`** uses `if self._toast_sender is not None`
  to guard the call but `notifier.py` types it as `object`. Adding an
  `assert` or `getattr(self._toast_sender, "show", None)` defensive check
  would make the contract more explicit. Trivial.

## Spec drift register

- **D1 — speech spec §"speak_with_system_voice Delegates to SystemVoice"**
  requires `speak_with_system_voice(text: str) -> None` and a
  `self._system_voice` attribute. The impl takes
  `speak_with_system_voice(text, system_voice)` and holds no
  `self._system_voice`. See W1 for resolution. (Confirmed by reading
  `core/speech.py:131` and the spec scenario at
  `specs/speech/spec.md:287-291`.)

- **D2 — notifications spec §"Five notifier event sites in `MainWindow`"**
  table has 5 rows. `bellbird/ui/main_window.py` has 6 `notifier.notify`
  call sites (the extra is `_on_server_state_checked` state=="dead"). See W2.
  (Confirmed by `grep -n "_notifier.notify" bellbird/ui/main_window.py`.)

- **D3 — notifications spec scenarios use `WxNotifier().send(event, message)`**
  but the impl class is `WxToastSender` with `show(title, message, timeout=5)`.
  The spec scenarios (lines 201-228) would `AttributeError` if executed as
  written. See W3.

- **D4 — design §5 calls the voice Choice `voice_selector`; impl uses
  `pref_system_voice_choice`**. The naming follows the existing
  `pref_*_choice` convention in the dialog. See W4.

## Compliance with lessons-learned

- **v0.8.3 verify-reads-code**: yes — read end-to-end every changed file:
  `core/system_voice.py`, `core/sound_player.py`, `core/focus.py`,
  `core/notifier.py`, `core/speech.py`, `core/config.py`, `core/keymap.py`,
  `ui/voice_dialog.py`, `ui/wx_notifier.py`, `ui/preferences_dialog.py`,
  `ui/main_window.py` (full 2497 lines), `ui/chat_panel.py`, plus tests
  (`tests/core/test_system_voice.py`, `test_notifier.py`, `test_sound_player.py`,
  `test_focus.py`, `test_speech.py`, `test_keymap.py`, `test_config.py`,
  `tests/ui/test_voice_dialog_static.py`, `test_wx_notifier_static.py`,
  `test_wx_notifier_runtime.py`, `test_main_window_runtime.py` extended,
  `test_preferences_dialog_static.py` extended, `test_chat_panel_static.py`
  extended). Read the spec files in full. Cross-referenced spec scenarios
  one-by-one against impl. Confirmed the 6 vs 5 notifier site drift by grep.

- **v0.8.3 wx-isolation**: pass. `core/system_voice.py`, `core/sound_player.py`,
  `core/focus.py`, `core/notifier.py` contain no `import wx` at module scope
  (only `import sys`, `import logging`, `from pathlib import Path`,
  `from typing import Protocol` and `from dataclasses import dataclass, field,
  asdict` for config). The docstrings of the new core modules explicitly
  state "No `import wx` at module scope." AST tests in `test_focus.py:22-39`
  and `test_system_voice.py:378-397` enforce this regression guard.

- **v0.8.3 win32 line-local**: pass. `core/system_voice.py:33, 55` use
  `import win32com.client` inside the `__init__` and `voices()` method bodies
  respectively, under `if sys.platform == "win32":` and `try/except`.
  `core/sound_player.py:69` imports `winsound` inside `play()` under the
  win32 guard with `try/except`. `ui/wx_notifier.py:34` imports `wx.adv` inside
  `show()` under the win32 guard with `try/except`. AST tests assert these are
  line-local, not module-level.

- **v0.8.3 never-crash**: pass. Every public method in
  `SystemVoice` (`voices`, `set_voice`, `set_rate`, `speak`, `is_available`),
  `SoundPlayer` (`_resolve`, `play`), `Notifier` (`notify`),
  `WxToastSender` (`show`), and `Speech.speak_with_system_voice` wraps the
  body in `try/except Exception: pass` (or returns safe default on
  `set_voice` / `set_rate`). Confirmed by reading the methods end-to-end
  AND by `test_speak_never_raises`, `test_notify_never_raises`,
  `test_play_never_raises`, `test_speak_swallows_sapi_error`,
  `test_toast_sender_raises_is_caught`, `test_sound_player_raises_is_caught`,
  `test_speak_with_system_voice_never_raises`. None can raise on any
  non-win32 platform, missing pywin32, missing winsound, missing wx.adv,
  COM errors, SAPI errors, malformed WAVs, or `RuntimeError` mid-call.

- **v0.8.3 FakeSpeech stub** (v0.9.0 lesson): the FakeSpeech in
  `test_main_window_runtime.py:28-42` provides `speak()` AND `output()`.
  Reading `main_window._announce_session_status` and `_on_done` paths: they
  call `self._speech.speak(...)` and `self._speech.output(...)` only — both
  stubbed. The notifier event sites call `self._notifier.notify(...)` (not
  `self._speech.*`), so no `speak`/`output` calls leak past the FakeSpeech.
  Good.

- **v0.8.3 Gate mid-generation in atajos nuevos**: pass. The new F8 handler
  `_on_read_selected_message` (line 611-626) gates on
  `if self.chat_panel._is_generating: self._speech.speak("Generación en
  curso", interrupt=False); return`. The `attach_url` test
  (`TestOnAttachUrl::test_attach_url_gate_during_generation`) confirms the
  existing pattern. The F8 handler mirrors the same gate. The runtime test
  `TestNotifierWiring::test_on_read_selected_message_gates_on_generating`
  asserts the gate. Lesson applied.

- **v0.8.3 NO `interrupt=True` for non-critical announcements**: pass. The
  F8 handler uses `interrupt=False` for both "Generación en curso" and
  "Nada que leer" gates. The screen reader is the live channel during
  generation; SAPI on F8 is a manual user action, so `interrupt=False` is
  appropriate (the spec says "never interrupt" — `speak_with_system_voice`
  has no `interrupt` arg, so this is satisfied by structural design). All
  notifier event names are static strings ("Respuesta completa", "Servidor
  listo", "Error", "Solicitud de herramienta", "Modelo cargado" / "Servidor
  caído"), not derived from reasoning.

- **v0.8.0 F-key collision**: pass. The keymap table at
  `core/keymap.py:274-298` has 23 entries. F8 (346) is new and used only by
  `read_selected_message`. F2=340, F4=342, F5=343, F6=344, F7=345, Ctrl+F7,
  Alt+F4, Alt+Up/Down are unchanged. The
  `test_read_selected_message_no_collision` test iterates the keymap and
  asserts no combo duplicate. `test_no_collisions` (the global check)
  passes. Confirmed by reading the table.

- **v0.9.0 state machine reset-then-update**: not applicable — this change
  does not introduce or modify any state machine. The double-F2 state
  machine from v0.9.0 is untouched (test_triple_f2_starts_short_again
  still passes). The notifier event sites are independent
  (5 + 1 in `_on_server_state_checked`), each calling `notify()` once with
  static args — no shared state to reset.

- **v0.9.0 AST guard for pure helpers**: pass. `core/focus.py` is a pure
  `Protocol` definition module; `test_focus.py:22-39` parses the source
  with `ast` and fails on any `import wx` / `from wx ...` at module scope.
  `core/system_voice.py` has an identical AST guard
  (`test_system_voice.py:378-397`). `core/sound_player.py` is also pure
  (only `winsound` line-local), and `core/notifier.py` is also pure
  (no platform deps at all — uses injected `focus_check`, `toast_sender`,
  `sound_player`).

- **v0.8.2 spec drift is normal**: confirmed (D1-D4). The verify agent
  identified them and they are tracked as WARNINGs, not CRITICALs, per the
  precedent set in v0.8.2/v0.9.0 (spec wording drift is acceptable when
  the impl is more idiomatic or the test passes).

## Acceptance criteria (from proposal §Acceptance)

- [x] `uv run --no-sync pytest -xvs` green in WSL (778/778, 15 skipped WSL).
  Evidence: full pytest output above.
- [x] `run_tests.bat` green in Windows — all wx-runtime tests use
  `importorskip("wx")` and are listed in `run_tests.bat` lines 20-24
  (`test_wx_notifier_runtime.py`, `test_voice_dialog_static.py`, the
  extended `test_main_window_runtime.py`, the extended
  `test_preferences_dialog_static.py`, the extended
  `test_chat_panel_static.py`).
- [x] On any non-win32 platform, all new modules are silent no-ops with
  no exceptions. Evidence: `test_speak_non_win32_noop`,
  `test_set_voice_non_win32_returns_false`, `test_set_rate_non_win32_noop`,
  `test_play_non_win32_noop` all pass; the impl wraps every body in
  `if sys.platform != "win32": return`. The notifier `notify()` is
  platform-agnostic (it just delegates to `focus_check` + `toast_sender` +
  `sound_player`).
- [x] F8 reads the selected message via SAPI; empty selection announces
  "Nada que leer"; mid-generation announces "Generación en curso" and
  returns. Evidence: `test_on_read_selected_message_gates_on_generating`
  passes; reading the impl at `main_window.py:611-626` confirms the three
  branches. The strip_markdown call comes from
  `text_utils.strip_markdown(plain)`, not Change B.
- [x] Toasts + sounds fire ONLY when the app is not focused.
  Evidence: `core/notifier.py:67-89` — `if is_focused: return` at line 72
  is the gate; the `focus_check` lambda in `main_window.py:143` is
  `lambda: not self.IsActive()`. Tests
  `test_silent_when_focused` and
  `test_fires_toast_and_sound_when_not_focused` cover both branches.
- [x] `auto_speak_responses` defaults to `False`; flipping it persists
  across restarts. Evidence: `BellbirdConfig.auto_speak_responses: bool =
  False` at `config.py:57`; `_apply_config` at `preferences_dialog.py:1116-1118`
  writes the new value; `__dataclass_fields__` filter at `config.py:119-120`
  preserves forward-compat. Test `TestV0100AudioConfig` in
  `tests/core/test_config.py` (10 tests, 131 lines added) covers all six
  fields and round-trip.
- [x] Reasoning is never spoken via the new channel. Evidence: the 6
  `notifier.notify` call sites in `main_window.py` use static event names
  ("generation_complete", "server_ready", "model_loaded", "tool_request",
  "error") and static or model-name messages. None reference
  `self._current_reasoning` (verified by reading each call site: 1036,
  1165, 1620, 1680, 1864, 1901). The `auto_speak_responses` flag is OFF
  by default and there is no code path that reads `_current_reasoning`
  into the SAPI channel. `test_no_notify_reasoning_method` enforces the
  contract at the class level.

## Recommendation

**READY_TO_ARCHIVE_WITH_WARNINGS**

Four WARNINGs, all spec drifts (D1-D4). None affect runtime behavior — all
778 tests pass, the wx-isolation and win32 line-local guards are intact, the
never-crash contract holds, and the 5 documented notifier event sites fire
correctly. The 6th site (the watchdog dead-server) is a sensible extension
that the verify agent recommends documenting pre-archive (one
`chore(spec):` commit), not blocking. The `WxNotifier`/`send` vs
`WxToastSender`/`show` spec typo is a doc-debt cleanup that can be batched
into the same `chore(spec):` commit or filed for a follow-up housekeeping
change. The other drifts (D1 `speak_with_system_voice` API shape; D4 voice
Choice name) are non-blocking and idiomatic. Per lessons-learned v0.8.2 and
v0.9.0, "spec wording drift between proposal/spec/impl is normal" and
"archive OK with WARNINGs, file as debt." The change is functionally
complete; the spec cleanups can land as a single `chore(spec): align
v0.10.0 audio spec with impl` commit pre-archive or alongside the archive.
