# Bellbird

Cliente de escritorio para chatear con modelos de lenguaje locales en Windows.
Diseñado desde cero para usuarios ciegos — funciona con NVDA y JAWS sin configuración adicional.

Usa [llama.cpp](https://github.com/ggerganov/llama.cpp) como backend. Los modelos corren localmente, sin internet, sin APIs externas.

## Estado

v0.4.0 — en desarrollo activo. Sin verificación formal con NVDA todavía.

## Build (Windows .exe)

Bellbird can be packaged as a standalone Windows executable via PyInstaller.
From WSL:

1. Run `scripts/build_windows.sh` — it runs the test suite, then assembles a
   build kit zip under `dist/bellbird_v<version>_<timestamp>.zip`.
2. Copy the zip to a Windows 11 machine and unzip.
3. Double-click `build.bat` inside the unzipped folder (first run takes ~5–10 min).
4. The executable lands at `dist\Bellbird\Bellbird.exe`.

Requirements: Python 3.12+, uv (recommended) or pip. On Windows, `pyinstaller`
and `pywinauto` are declared with `sys_platform == 'win32'` markers and pulled
in only when building.

## Atajos de teclado

| Tecla | Acción |
|-------|--------|
| Enter | Enviar mensaje |
| Shift+Enter | Nueva línea |
| Escape | Detener generación |
| Ctrl+N | Nueva conversación |
| Ctrl+O | Abrir conversación guardada |
| Ctrl+S | Guardar conversación |
| F2 | Anunciar estado de sesión |
| F5 | Buscar modelos disponibles |
| F6 | Ciclar entre paneles |
| F7 | Iniciar servidor |
| Ctrl+F7 | Detener servidor |
| Ctrl+Enter (en historial) | Abrir mensaje en navegador |
| Supr (en historial) | Eliminar mensaje seleccionado |
| Alt+1–6 | Foco directo a controles |
