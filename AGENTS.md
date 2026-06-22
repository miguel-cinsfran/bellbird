# OllamaChat

Cliente de escritorio accesible para chatear con Ollama. Diseñado para
usuarios ciegos en Windows 11 con NVDA o JAWS.

Stack: Python 3.12, wxPython 4.2+, accessible-output2 0.17+, requests 2.31+.
Tests: pytest (93/93 pasan en el ultimo verify).

## Reglas criticas (no negociables)

- Cada control interactivo tiene `name=` descriptivo
- Cada control esta precedido en el sizer por `wx.StaticText` (MSAA asocia la etiqueta adyacente)
- Solo `wx.BoxSizer` horizontal o vertical. **Nunca** grid sizers (rompen el orden de lectura de NVDA)
- Fallos de accessible-output2 nunca crashean la app (try/except en cada metodo publico de `Speech`)
- Todos los callbacks desde hilos de fondo van por `wx.CallAfter` sin excepcion
- Sin `wx.WebView` (inaccesible para lectores de pantalla). Usar `wx.TextCtrl` con `wx.TE_RICH2`
- Para detectar Shift/Ctrl/etc. en handlers usar `event.ShiftDown()`, nunca `wx.GetKeyState`
- Encoding `utf-8` explicito en toda lectura/escritura de archivos
- Compatible con Python 3.12, sin sintaxis de versiones posteriores

## Layout del proyecto

```
ollamachat/
  main.py             # entry point
  core/               # wx-free, totalmente testeable
    speech.py         # wrapper accessible-output2 (never-crash)
    conversation.py   # persistencia JSON con atomic write
    ollama_client.py  # REST + NDJSON streaming + abort
    ollama_runner.py  # spawn "ollama serve" + poll
    logger.py         # logger a data/ollamachat.log
  ui/                 # wx, solo testeable en Windows
    main_window.py    # SplitterWindow + menu + status bar + send flow
    chat_panel.py     # display + input + botones
    params_panel.py   # model selector + sliders
  data/               # runtime (gitignored, se crea solo)
tests/
  core/               # TDD estricto, importan el codigo
  ui/                 # AST checks + placeholders [windows-only]
  smoke/              # degradacion silenciosa
openspec/             # artefactos SDD (ver seccion abajo)
scripts/
  build_windows.sh    # genera el kit para Windows
```

## Tests

- Windows: `uv sync` primero, despues `uv run pytest -xvs`. 93/93 pasan.
- WSL / Linux sin wxPython: wxPython no tiene wheel de Linux por defecto, falla al compilar desde source. Usar `uv run --no-sync pytest -xvs`. Los 52 tests de `core/` y smoke + 20 tests AST de UI pasan igual (los AST leen el codigo fuente, no importan wx).

## Como iterar una nueva version

1. Modificar el codigo
2. Bumpear la version en `pyproject.toml` (formato semver: 0.1.x para fixes, 0.x.0 para features)
3. Correr `scripts/build_windows.sh` — corre tests, arma el kit, lo zipea en `dist/`
4. Mover el zip a Windows y correr `build.bat` adentro

No usar tablas en docs que el usuario final va a leer (NVDA lee celda por celda, rompe el flujo). Solo listas.

## Arquitectura en una pagina

- `core/` no importa `wx` salvo `ollama_client.py` que lo hace **solo adentro** del callback wrapper (threading.Event + wx.CallAfter)
- `ui/` depende de `core/` y de `wx`. Nunca al reves.
- `data/` es el unico side-effect persistente; esta gitignored.
- `Speech` envuelve `accessible_output2.outputs.auto.Auto()` con try/except en constructor y en cada metodo. `is_screen_reader_active()` usa `is_system_output()` para distinguir lector real de TTS fallback.
- `Conversation` escribe a `.tmp` y hace `Path.replace` (atomic write).
- `OllamaClient.chat_stream` lanza un `threading.Thread` daemon por request, parsea NDJSON linea por linea, abort via `threading.Event` chequeado ENTRE lineas, todos los callbacks por `wx.CallAfter`.
- `OllamaRunner.start_ollama` es wx-free y testeable; MainWindow solo traduce `(ok, mensaje)` a speech + status bar.
- Logger usa sentinel `_ollamachat_configured` en el logger (no `if logger.handlers`) para no chocar con pytest caplog.

## Decisiones de diseño (referencia rapida)

- Estructura `ollamachat/{core,ui,data}/` (no cambiarla; core testeable headless, ui wx, data runtime)
- Sin `ruff`/`mypy` (dropped para el MVP; pytest + verify cubren la calidad)
- `AGENTS.md` se mantiene
- Branch por defecto: `main` (no `master`)
- Strict TDD activo en `core/`
- Verificacion manual de UI en Windows (4 tareas `[windows-only]` pendientes en el change archivado)

## Donde esta el contexto profundo

Para una sesion nueva, leer en este orden:

1. `README.md` — que es la app y como se usa
2. `openspec/specs/<capability>/spec.md` — que tiene que hacer cada modulo
3. `openspec/changes/archive/2026-06-22-initial-implementation/proposal.md` — el "porque" y el alcance
4. `openspec/changes/archive/2026-06-22-initial-implementation/design.md` — arquitectura detallada + diagramas de secuencia
5. `openspec/changes/archive/2026-06-22-initial-implementation/verify-report-2.md` — el verify final (0 critical, 0 warning)
6. `CHANGELOG.md` — historial de versiones

## Estado actual

- Version: 0.1.1
- Tests: 93/93 pasan
- SUGGESTION pendientes (no bloqueantes): callback wiring consistency, README Python version, documentar el patron de event.ShiftDown
- Verificacion manual en Windows: pendiente (4 tareas `[windows-only]`)

## Entorno

- WSL Ubuntu: no puede correr wx windows, solo logica testeable. wxPython no compila aca.
- Tests UI en WSL: AST checks sobre source + placeholders para Windows.
- Engram (`mem_save`/`mem_session_summary`) **no esta disponible** en este entorno. Persistir via OpenSpec files.

## SDD workflow

- Preflight: pace=interactive, artifact_store=openspec, delivery=single-pr-default, review_budget=400
- Cambios: `openspec/changes/<name>/` con proposal/specs/design/tasks/apply-progress/verify-report
- Archivados: `openspec/changes/archive/<fecha>-<name>/`
- Specs main: `openspec/specs/<capability>/spec.md`
- Para arrancar un nuevo change: usar `sdd-new-gentleman` o delegar a `sdd-propose-gentleman` con el contexto
