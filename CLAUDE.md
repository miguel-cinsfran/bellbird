# OllamaChat — guía rápida para Claude Code

## Usuario y contexto

Miguel es ciego, usa NVDA en Windows 11. Toda decisión de UI tiene que pasar
por "¿funciona con lector de pantalla?". Ver `CONOCIMIENTO_WXPYTHON_ACCESIBLE.md`
antes de tocar cualquier control wx.

## Qué es esto

App de escritorio wxPython para chatear con modelos .gguf locales via llama-server
(llama.cpp). Backend: API OpenAI-compatible, SSE streaming, `--jinja` obligatorio.

## Estado actual

- Versión: 0.4.0, tests 186/186
- v0.4.0 archivado en `openspec/changes/archive/2026-06-23-v0.4.0-tool-calling-*/`
- v0.4.0 incluye: tool calling (shell_execute), PermissionDialog, PermissionManager, ToolExecutor
- Bug conocido: mensaje assistant con `tool_calls` no se guarda en Conversation para el segundo turno.
  Llama-server puede rechazar el request si el Jinja template del modelo lo requiere. Ver v0.4.1.
- Verificación con NVDA real en Windows: **pendiente** (nunca se ha probado nada en vivo)

## Correr tests

```bash
# WSL / Linux (no hay wx, funciona igual para core + AST)
uv run --no-sync pytest -xvs

# Windows (después de uv sync)
uv run pytest -xvs
```

Los tests `ui/` en WSL son AST checks sobre el código fuente, no importan wx.

## Reglas críticas de UI (no negociables)

- **Nunca** `wx.MessageDialog` para botones con labels en español — regresión MSAA documentada.
  Usar `wx.Dialog` custom con `wx.Button` nativos.
- **Nunca** `wx.richtext.RichTextCtrl` — "poor choice for screen readers" según docs oficiales.
- **Nunca** `wx.html.HtmlWindow` para contenido legible — sin soporte MSAA/UIA fiable.
- **Nunca** `wx.WebView` — inaccesible para lectores.
- Para HTML renderizado: `webbrowser.open()` + tempfile `.html` (browser con NVDA virtual mode).
- Toda operación >2s: hilo de fondo + anuncios periódicos via `wx.CallAfter(speech.speak, ...)`.
- `wx.ListBox` es el control de lista más accesible con NVDA. Preferir siempre.
- Todo callback desde hilo de fondo: `wx.CallAfter` sin excepción.
- `winsound` y código Windows-only: guard `if sys.platform == 'win32'`.

## Regla de seguridad (tool calling v0.4.0)

El sistema de permisos **nunca** bloquea automáticamente operaciones en directorios
del usuario (Remove-Item, Move-Item, etc. en carpetas propias). Auto-bloqueo
SOLO para paths de sistema: `C:\Windows`, `C:\System32`, `C:\Program Files`,
`Format-Volume`, `Clear-Disk`. Todo lo demás pasa por el diálogo de confirmación.

## Arquitectura

```
ollamachat/core/    # wx-free, 100% testeable en WSL
ollamachat/ui/      # wx, solo verificable en Windows
ollamachat/data/    # runtime, gitignored
openspec/           # artefactos SDD (proposal/design/verify-report)
```

`core/` nunca importa `wx` a nivel de módulo. `ui/` depende de `core/`, nunca al revés.

## Workflow de cambios (SDD)

Cada feature va por `openspec/changes/<nombre>/` con proposal → specs → design → verify-report.
Cambios activos en `openspec/changes/`, archivados en `openspec/changes/archive/`.

Antes de implementar cualquier cosa nueva: leer el spec de la capability en
`openspec/specs/<capability>/spec.md`.

## Workflow con opencode

- Tras cada prompt de opencode: revisar commits + leer verify-report + correr tests **antes** de
  pasar al siguiente prompt.
- Los archivos `PROMPT_*.txt` y `CONOCIMIENTO_WXPYTHON_ACCESIBLE.md` son para lectura humana.
  Borrarlos del directorio raíz antes de abrir el chat de opencode (para que no los lea como contexto).
- Verificación con NVDA real en Windows pendiente. v0.4.0 cambia UI (PermissionDialog, checkbox tools).
  Probar en Windows antes de v0.5.0.

## Contexto profundo

1. `AGENTS.md` — reglas completas, layout, arquitectura, decisiones de diseño
2. `openspec/specs/` — specs por capability
3. `openspec/changes/archive/2026-06-22-migrate-llama-cpp/verify-report.md` — verify v0.2.0
4. `CONOCIMIENTO_WXPYTHON_ACCESIBLE.md` — referencia completa de accesibilidad wxPython/NVDA
