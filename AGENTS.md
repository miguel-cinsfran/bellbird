# OllamaChat

Cliente de escritorio accesible para chatear con modelos locales .gguf via llama-server (llama.cpp).
Diseñado para usuarios ciegos en Windows 11 con NVDA o JAWS.

Stack: Python 3.12, wxPython 4.2+, accessible-output2 0.17+, requests 2.31+.
Tests: pytest (140/140 en v0.3.0).

## Reglas criticas (no negociables)

- Cada control interactivo tiene `name=` descriptivo
- Cada control esta precedido en el sizer por `wx.StaticText` (MSAA asocia la etiqueta adyacente)
- Solo `wx.BoxSizer` horizontal o vertical. **Nunca** grid sizers (rompen el orden de lectura de NVDA)
- Fallos de accessible-output2 nunca crashean la app (try/except en cada metodo publico de `Speech`)
- Todos los callbacks desde hilos de fondo van por `wx.CallAfter` sin excepcion
- Sin `wx.WebView` (inaccesible). Usar `wx.TextCtrl` con `wx.TE_RICH2`
- Para detectar Shift/Ctrl/etc. usar `event.ShiftDown()`, nunca `wx.GetKeyState`
- Encoding `utf-8` explicito en toda lectura/escritura de archivos
- Compatible con Python 3.12, sin sintaxis de versiones posteriores

## Reglas adicionales de controles (investigadas en fuentes de NVDA)

- **No usar `wx.MessageDialog` para botones con labels personalizados en español** (regresiones MSAA). Para dialogos con 2+ botones custom: `wx.Dialog` + `wx.Button` nativos. Stock labels (YES_NO) sí OK para close confirm.
- **No usar `wx.richtext.RichTextCtrl`** ni `wx.html.HtmlWindow` para contenido que el usuario necesite leer con NVDA. Para HTML renderizado: `webbrowser.open()` con archivo temporal `.html` en browser nativo (Edge/Chrome con NVDA modo virtual).
- **Operaciones de mas de 2 segundos** (arrancar servidor, ejecutar comandos) en hilo de fondo con anuncios periodicos via `wx.CallAfter(speech.speak, ...)`. Nunca bloquear el hilo principal en silencio.
- **`wx.ListBox`** es el control mas accesible para listas navegables. Preferir sobre `wx.Choice`, `wx.ListCtrl` o `wx.CheckListBox`. Vista dual: ListBox (historial) + TextCtrl (stream) son dos controles separados.
- **Cuando el foco entra a un dialogo**, llamar `SetFocus()` en el primer control relevante.
- **`winsound` y modulos Windows-only** requieren guard: `if sys.platform == 'win32'` E import line-local DENTRO del guard.
- **Alt+numero** = atajos directos a controles. F2 = estado sesion. F6 = ciclar paneles. Enter = enviar (sin Shift). Shift+Enter = newline.

## Layout del proyecto

```
ollamachat/
  main.py
  core/               # wx-free, testeable
    speech.py, conversation.py, llama_client.py, llama_runner.py,
    text_utils.py [v0.3.0], logger.py
    permission_manager.py, tool_executor.py [v0.4.0]
  ui/                 # wx, testeable en Windows
    main_window.py, chat_panel.py, params_panel.py,
    message_detail_dialog.py [v0.3.0]
    permission_dialog.py [v0.4.0]
  data/               # gitignored runtime
tests/{core,ui,smoke}/
openspec/             # artefactos SDD
```

## Tests

- Windows: `uv sync` y despues `uv run pytest -xvs`.
- WSL / Linux sin wxPython: usar `uv run --no-sync pytest -xvs`. Tests de `core/` y smoke + AST de UI pasan (AST leen source, no importan wx).

## Como iterar

Bumpear version en `pyproject.toml` (semver), tests en WSL con `uv run --no-sync pytest -xvs`, copiar a Windows y verificar UI con NVDA. No usar tablas en docs para usuarios finales (NVDA lee celda por celda).

## Arquitectura

- `core/` no importa `wx` a nivel de modulo (`llama_client.py` lo importa dentro de `_stream_worker`).
- `ui/` depende de `core/` y de `wx`. Nunca al reves.
- `data/` es el unico side-effect persistente; gitignored.
- `Speech` envuelve accessible-output2 con try/except en cada metodo.
- `Conversation.save` hace atomic write a `.tmp` + `Path.replace`.
- `LlamaClient.chat_stream` lanza daemon thread, parsea SSE linea por linea, abort via `threading.Event`, callbacks por `wx.CallAfter`.
- `LlamaRunner` es wx-free; `start_server` siempre pasa `--jinja` y `--n-gpu-layers 99`.

## Decisiones de diseno

Estructura `ollamachat/{core,ui,data}/` (no cambiarla). Sin `ruff`/`mypy` (pytest + verify cubren). `AGENTS.md` se mantiene. Branch `main`. Strict TDD en `core/`. Verificacion manual de UI en Windows.

## Lecciones aprendidas (v0.3.0)

### Process
- **Verify post-apply DEBE leer TODOS los archivos cambiados.** Spot check inline perdió 3 bugs (B1, B2, B3) en v0.3.0 v1. El verify v2 (focused inline de archivos no leídos) encontró 5; v3 (focused en detail dialog) encontró 1 mas. Regla: sub-agente de verify, no spot check.
- **AST tests: chequean ESTRUCTURA (indentación), no posición.** El B3 v1 usaba `rfind` y pasaba en código viejo y nuevo; el v2 chequea `append_indent > if_indent` y atrapa la regresión.
- **`size:exception` está OK** si forecast > budget. Single PR estructurado en commits work-unit (15 para v0.3.0) es revisable commit por commit.

### Sub-agents
- `qwen3.7-plus` (design/tasks/verify) se colgó 2 veces con contexto largo sin error visible. Si cambia el modelo, registrar acá el resultado.
- `deepseek-v4-flash` (apply/archive) anduvo bien para tareas de ejecución.
- `minimax-m3` (propose/spec/orquestador) anduvo bien para tareas de síntesis.
- **Táctica**: si un sub-agente cuelga, el orquestador escribe el artefacto inline como senior architect. Ya funcionó en `design.md` y `tasks.md` de v0.3.0.

### Code patterns (código wx multi-thread)
- `event.GetUnicodeKey()` (no `GetKeyCode()`) para chars no-ASCII. Importante para usuarios en español (B4 fix).
- `wx.CallAfter` es el único puente thread→main permitido. `threading.Timer.daemon = True`.
- `threading.Timer.cancel()` es idempotente; cancelar en done handler Y defensivamente en `_on_close`.
- `self._is_closing` flag en `_on_close` para evitar `wx.CallAfter` post-destroy (B2 fix).
- `threading.Thread` daemon + try/finally con defaults ANTES del try (B1 fix: UnboundLocalError en `_model_load_worker`).

### For v0.4.0
- No skipear verify sub-agente.
- Tool calling usará `wx.Dialog` + `wx.Button` nativos (no `MessageDialog`).
- Cada control wx: `name=` + StaticText previo + solo BoxSizer.

## Estado actual

- Version: 0.3.0 (140/140 tests, listo para tag).
- Backend: llama-server (llama.cpp) via API OpenAI-compatible.
- Pendiente: verificación manual en Windows (4 tareas `[windows-only]`: NVDA Tab order chat panel, F2 announcement, Alt+N shortcuts, popup Tab order).

## Proximos cambios

- v0.4.0: Tool calling (PROMPT_TOOL_CALLING.txt) — PermissionManager, PermissionDialog, ToolExecutor (PowerShell), shell_execute tool.

## Entorno

- WSL Ubuntu: no corre wx windows, solo lógica testeable. Tests UI = AST checks sobre source.
- Engram (`mem_save`/`mem_session_summary`) **no está disponible** en este entorno. Persistir via OpenSpec files.

## SDD workflow

- Cambios: `openspec/changes/<name>/` con proposal/specs/design/tasks/verify-report/archive-report.
- Archivados: `openspec/changes/archive/<fecha>-<name>/`.
- Specs main: `openspec/specs/<capability>/spec.md`.
- Para arrancar: `sdd-new-gentleman` o delegar a `sdd-propose-gentleman` con el contexto.
