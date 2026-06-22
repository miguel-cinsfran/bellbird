# OllamaChat

Proyecto: OllamaChat — accessible desktop chat for blind users.
Stack: Python 3.12, wxPython, accessible-output2, requests.

## Critical Rules

- Every interactive control has `name=`, preceded by `wx.StaticText` label
- Only `wx.BoxSizer` for layout (no GridSizer/FlexGridSizer/GridBagSizer)
- Speech failures never crash — catch all exceptions in `Speech` methods
- All thread callbacks go through `wx.CallAfter`
- Strict TDD on `core/` — write tests first
- No `wx.WebView` anywhere

## Layout

```
ollamachat/
├── core/     # wx-free, fully testable
├── ui/       # wx widgets, Windows-only runtime
└── data/     # runtime persistence, gitignored
```

## Test

- **Windows (con wxPython)**: `uv sync` primero, después `uv run pytest -xvs`. 69/69 pasan.
- **WSL / Linux sin wxPython**: wxPython no tiene wheel de Linux por defecto, falla al compilar desde source. Usá `uv run --no-sync pytest -xvs` para correr los tests sin re-sincronizar. Los 52 tests de `core/` y smoke + 17 tests AST de UI pasan igual (los AST leen el código fuente, no importan wx).

## Screens

- Avoid tables in user-facing docs (screen reader friendly)
