# Capability: Windows Test Coverage

## Purpose

The Windows-side runtime test layer. Where `tests/core/*` exercises
wx-free logic on WSL and `tests/ui/test_*_static.py` validates UI
structure via AST on WSL, this capability covers **real wx-runtime
instantiation** of UI dialogs that only execute on Windows
(`pytest.importorskip("wx")`). It also covers the smoke-test module
list maintenance and the `run_tests.bat` pipeline so that Miguel's
Windows test loop stays a single command.

The goal is stronger regression coverage for v0.10.0/v0.11.0 features
that AST cannot exercise: `PreferencesDialog` instantiation, OK/Cancel
flow, control state load/save, `VoiceDialog` get_voice/get_rate, the
4 Lectura tab CheckBoxes toggling, and `SystemVoice` SAPI no-crash
contract.

## Requirements

### Requirement: PreferencesDialog has wx-runtime coverage

`tests/ui/test_preferences_dialog_runtime.py` MUST exist, gated by
`pytest.importorskip("wx")`. It MUST instantiate `PreferencesDialog`
against a `BellbirdConfig`, walk the controls, and verify the OK/Cancel
flow, the Lectura tab filter CheckBoxes, and that every interactive
control has a `name=` attribute. The file MUST be picked up by
`run_tests.bat` (line 19's `pytest tests/`).

#### Scenario: Dialog constructs and shows without crash
- GIVEN a fresh `wx.App()` and a `BellbirdConfig()`
- WHEN `PreferencesDialog(None, config)` is constructed
- THEN no exception is raised and the dialog is a `wx.Dialog`

#### Scenario: OK on unmodified config round-trips
- GIVEN a `BellbirdConfig()` with `system_prompt="hola"`
- WHEN `_apply_config()` is called without user changes
- THEN `dlg._config.system_prompt == "hola"`

#### Scenario: Changing system prompt control updates config
- GIVEN a PreferencesDialog bound to a `BellbirdConfig`
- WHEN the system prompt TextCtrl value is set to "nuevo" and
  `_apply_config()` runs
- THEN `dlg._config.system_prompt == "nuevo"`

#### Scenario: Toggling a Lectura filter updates the config
- GIVEN PreferencesDialog with default config (all filters `True`)
- WHEN `pref_filter_urls` CheckBox is unchecked and `_apply_config()` runs
- THEN `dlg._config.filter_strip_urls is False`

#### Scenario: Every interactive control has a name
- GIVEN a constructed PreferencesDialog
- WHEN `FindWindowByName` is called for the documented control names
  (e.g. `pref_filter_markdown`, `pref_presets_list`, `pref_ok_button`,
  `pref_audio_choice`)
- THEN each lookup returns a non-`None` window

### Requirement: VoiceDialog has wx-runtime coverage

`tests/ui/test_voice_dialog_runtime.py` MUST exist, gated by
`importorskip("wx")`. It MUST instantiate `VoiceDialog`, verify initial
state, and verify that selecting a voice or moving the rate slider
updates the accessors.

#### Scenario: Dialog constructs with choices
- GIVEN `voices=["A", "B"]` and `current_voice="B"`
- WHEN `VoiceDialog(None, voices, current_voice="B")` is built
- THEN the Choice has selection `"B"`

#### Scenario: `get_voice()` returns initial value
- GIVEN a constructed `VoiceDialog` with `current_voice="A"`
- WHEN `get_voice()` is called
- THEN the result is `"A"`

#### Scenario: `get_rate()` returns initial value
- GIVEN a constructed `VoiceDialog` with `current_rate=3`
- WHEN `get_rate()` is called
- THEN the result is `3`

#### Scenario: Changing the Choice selection updates `get_voice()`
- GIVEN a constructed `VoiceDialog` with `voices=["A", "B"]`
- WHEN the user selects "B" and `get_voice()` is called
- THEN the result is `"B"`

#### Scenario: Moving the rate slider updates `get_rate()`
- GIVEN a constructed `VoiceDialog`
- WHEN the rate slider is set to 7 and `get_rate()` is called
- THEN the result is `7`

### Requirement: Lectura tab has wx-runtime coverage

`tests/ui/test_lectura_tab_runtime.py` MUST exist, gated by
`importorskip("wx")`. It MUST verify the 4 filter CheckBoxes load from
`config.filter_strip_*` and toggle correctly.

#### Scenario: All 4 filter CheckBoxes default to checked
- GIVEN a fresh `BellbirdConfig()` (defaults: all filters `True`)
- WHEN `PreferencesDialog` is constructed
- THEN `pref_filter_markdown.GetValue() is True`,
  `pref_filter_urls.GetValue() is True`,
  `pref_filter_emojis.GetValue() is True`,
  `pref_filter_code_blocks.GetValue() is True`

#### Scenario: Unchecking `filter_strip_urls` updates the config
- GIVEN a PreferencesDialog with default config
- WHEN `pref_filter_urls` is unchecked and `_apply_config()` runs
- THEN `dlg._config.filter_strip_urls is False`

#### Scenario: Filter state round-trips across dialog reopen
- GIVEN a config with `filter_strip_emojis=False`
- WHEN a new PreferencesDialog is constructed
- THEN `pref_filter_emojis.GetValue() is False`

### Requirement: SystemVoice has wx-runtime coverage (SAPI path)

`tests/ui/test_system_voice_runtime.py` MUST exist, gated by
`importorskip("wx")`. The wx-runtime test is gated by wx because the
file lives under `tests/ui/` and the project's convention
(`AGENTS.md` §Tests) is that everything in `tests/ui/` is Windows-side
via `importorskip("wx")`. The test MUST verify the never-crash
contract on every code path, and on win32-without-SAPI it MUST swallow
exceptions silently.

#### Scenario: Non-win32 methods are silent no-ops
- GIVEN `sys.platform != "win32"`
- WHEN `SystemVoice().speak("hola")` is called
- THEN no exception is raised

#### Scenario: win32 with no SAPI available swallows exceptions
- GIVEN `sys.platform == "win32"` and `win32com.client.Dispatch` raises
  `Exception` (simulated via `unittest.mock`)
- WHEN `SystemVoice(voice_name="X", rate=2)` is constructed
- THEN the constructor returns without raising
- AND `is_available() is False`
- AND `speak("hola")` returns without raising

#### Scenario: Empty voice name returns False from `set_voice`
- GIVEN a `SystemVoice` instance (any platform)
- WHEN `set_voice("")` is called
- THEN the return is `False`

#### Scenario: `set_rate` clamps to `[-10, +10]`
- GIVEN a `SystemVoice` instance
- WHEN `set_rate(15)` is called on win32-with-SAPI (or skipped silently
  on non-win32)
- THEN the internal rate is clamped (observable via no exception
  and `is_available()` semantics)

### Requirement: Stale `TestSixTabOrder` is fixed

`tests/ui/test_keymap_capture.py::TestSixTabOrder` MUST assert the
current 9-tab order: `General, Modelo, Chat, Lectura, Herramientas,
Avanzado, Atajos, Audio, Estado (F2)`. The labels MUST be compared
including the `&` mnemonic prefix (e.g. `&General`), since the AST
visitor captures the full `AddPage` string.

#### Scenario: PreferencesDialog has 9 tabs in the expected order
- GIVEN the source of `bellbird/ui/preferences_dialog.py`
- WHEN the AST visitor extracts all `AddPage` labels
- THEN there are exactly 9 labels
- AND they are (in order): `&General`, `&Modelo`, `C&hat`, `&Lectura`,
  `&Herramientas`, `&Avanzado`, `A&tajos`, `A&udio`, `&Estado (F2)`

### Requirement: `run_tests.bat` is simplified

`run_tests.bat` MUST execute all tests via a single
`uv run pytest tests/ -v --tb=short` invocation on line 19. The
redundant explicit list on line 23 MUST be replaced by a comment
block listing which `tests/ui/*.py` files are wx-runtime, so Miguel
can see at a glance which tests are skipped on WSL.

#### Scenario: `run_tests.bat` has a single pytest invocation
- GIVEN the content of `run_tests.bat`
- WHEN the file is read
- THEN there is exactly one `uv run pytest` call
- AND it targets `tests/` (recursive discovery)

#### Scenario: A comment block lists the wx-runtime files
- GIVEN the content of `run_tests.bat`
- WHEN the comment block is read
- THEN it lists the wx-runtime files (e.g. `test_chat_panel_runtime.py`,
  `test_preferences_dialog_runtime.py`, etc.) as documentation, not
  as an execution list

### Requirement: `smoke_test.py` auto-discovers UI modules

`smoke_test.py::_MODULOS_UI` MUST be replaced with an
auto-discovered list built via `pkgutil.iter_modules(bellbird.ui)`,
so any new `bellbird/ui/*.py` file is automatically included in
Fase 2 (GUI imports). The hardcoded list of 5 entries is removed.

#### Scenario: All `bellbird/ui/*.py` modules are import-tested
- GIVEN the `bellbird/ui/` directory contains 9 `.py` files
- WHEN `fase2_gui()` runs
- THEN all 9 modules are imported and reported as `[ok]`

#### Scenario: A broken import in a new UI module is caught
- GIVEN a new `bellbird/ui/foo.py` with a `NameError` at import time
- WHEN `fase2_gui()` runs
- THEN `fase2_gui` returns `False` and prints
  `[FALLO] import bellbird.ui.foo`

### Requirement: `README.md` documents the test levels

`README.md` MUST have a "Tests" section explaining the 3 levels
(WSL core, WSL AST, Windows wx-runtime) and the smoke test (Windows
+ pywinauto), with a small table mapping each level to its runner
command.

#### Scenario: README has a "Tests" section
- GIVEN the content of `README.md`
- WHEN the file is read
- THEN a `## Tests` section exists
- AND it includes a 4-row table:
  - `core/` → `uv run --no-sync pytest -xvs` (WSL)
  - `ui/` static (AST) → same (WSL)
  - `ui/` runtime → `run_tests.bat` (Windows)
  - `smoke_test.py` → `uv run python smoke_test.py` (Windows +
    pywinauto)
