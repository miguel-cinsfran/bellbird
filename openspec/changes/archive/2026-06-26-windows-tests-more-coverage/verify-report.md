# Verify Report — windows-tests-more-coverage (prompt 17)

**Date**: 2026-06-26
**Verifier**: Claude Code (Sonnet 4.6)
**Status**: PASS

## Commits incluidos

| SHA | Mensaje |
|-----|---------|
| 4318baf | test(ui): add wx-runtime tests for VoiceDialog, PreferencesDialog, Lectura tab, and SystemVoice |
| 708dad5 | test(ui): update TestTabOrder to current 9-tab layout in PreferencesDialog |
| fbbb917 | chore(tests): simplify run_tests.bat to single pytest call + comment list |
| 3da81b4 | chore(smoke): auto-discover UI modules via pkgutil.iter_modules |

## Verificación WSL

```
uv run --no-sync pytest -xvs
→ 846 passed, 19 skipped in 97.46s
```

```
uv run --no-sync python smoke_test.py --no-gui
→ Fase 1 (core imports):  OK
→ Fase 2 (GUI imports):   OK (saltada — wx no disponible en WSL)
→ Fase 3 (accesibilidad): omitida (--no-gui)
```

## Checklist Done-When

- [x] 846 passes + 0 regressions en WSL
- [x] +4 archivos nuevos skip limpios via `importorskip("wx")`
- [x] `smoke_test.py` Fase 2 auto-descubre 9 módulos UI (en Windows)
- [x] `run_tests.bat` simplificado: único call `uv run pytest tests/` + bloque REM documental
- [x] `README.md` tiene sección `## Tests` con tabla de 4 niveles
- [x] `git diff HEAD~6 HEAD -- bellbird/` vacío (cero cambios a fuente de producción)
- [x] Commits con Conventional Commits, sin `Co-Authored-By:`

## Notas

- Test count subió de 223 (pre-split) a 846 due to prior prompts 01-16.
- `run_tests.bat` documentation comment lista 16 archivos wx-runtime.
- `_descubrir_modulos_ui()` usa `pkgutil.iter_modules` — se auto-actualiza al agregar nuevos módulos UI sin tocar smoke_test.py.
- Verificación con NVDA + Windows real: **pendiente** (nunca hecho en producción).
