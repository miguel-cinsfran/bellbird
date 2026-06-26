# Archive Report — Audio Output (v0.10.0)

**Archived on**: 2026-06-25

**Commits in this change**:
- `140d3cb`: feat(core): add audio output foundation (TTS on demand + SAPI + notifications + sounds)
- `2714046`: feat(ui): add audio output UI (F8 TTS + Audio tab + notifications) (v0.10.0 WU-2)
- `7cd3d3d`: docs(apply-progress): mark WU-2 complete (audio output UI, 778 tests)
- `68a4a4c`: chore(spec): align v0.10.0 audio spec with impl (pre-archive remediation)

**Final test run**: 778 passed, 15 skipped (WSL) — green in `uv run --no-sync pytest -xvs`.

**What landed**:
- F8 keybind: reads the selected message with the system voice (SAPI).
- Audio tab in Preferencias: voz del sistema + lectura automática + notificaciones + sonidos + tema.
- Toasts + sonidos when the app is not focused (5+1 event sites).
- Sound theme: `bellbird/data/sounds/default/*.wav` (5 short beeps).
- 6 new `BellbirdConfig` fields: system_voice_name, system_voice_rate, auto_speak_responses, notifications_enabled, sounds_enabled, sound_theme.

**Verdict at archive time**: READY_TO_ARCHIVE_WITH_WARNINGS (4 spec drifts remediated pre-archive).

**Lessons applied**:
- v0.8.2 WU-1/WU-2 split (mirrors #11 / #12 / #0.9.0 pattern).
- v0.8.3 verify-reads-code — verify agent audited real code, not just tests.
- v0.8.3 pre-archive `chore(spec):` remediation (mirrors #11 pattern).
- v0.9.0 wx-free core — all 4 new core modules have AST tests enforcing the no-wx rule.
- v0.9.0 state machine: n/a.

**Open follow-ups (deferred, non-blocking)**:
- S1, S2, S3 from the verify report (docstring, readability, defensive check) — file for v0.10.1 housekeeping.
- WAV asset generation: shipped as 5 identical 50ms 880Hz beeps. Richer themes deferred.

**References**:
- proposal: `openspec/changes/archive/2026-06-25-audio-output-tts-notifications/proposal.md`
- specs: `openspec/changes/archive/2026-06-25-audio-output-tts-notifications/specs/`
- design: `openspec/changes/archive/2026-06-25-audio-output-tts-notifications/design.md`
- verify: `openspec/changes/archive/2026-06-25-audio-output-tts-notifications/verify-report.md`
- canonical specs synced: `openspec/specs/speech/`, `openspec/specs/system-voice/`, `openspec/specs/notifications/`, `openspec/specs/app-configuration/`.
