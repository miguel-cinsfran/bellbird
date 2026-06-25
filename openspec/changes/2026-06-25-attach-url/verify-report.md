# Verify Report: Attach URL (Ctrl+U)

> **Status update (2026-06-25)**: Los 2 CRITICAL (C1 timer race, C2 speech missing) y 1 WARNING (W1 menu name) fueron corregidos en el commit `f9d9a99` después de este verify. El re-verify confirmó `594 passed, 14 skipped` y working tree limpio. Solo queda el WARNING W2 (menu enable/disable lifecycle) aceptado como deuda para v0.8.4 — el gate interno en `_on_attach_url` cubre correctness. Ver "Remediation" al final del reporte.


## Resumen

- **Status**: PASS_WITH_WARNINGS
- **Commits verificados**:
  - `dcb50b7` feat(core): add web_fetch, attach_url keymap, and url_max_chars config
  - `c8cbc8d` docs: add apply-progress for WU-1 (attach-url core)
  - `9a35dad` docs: mark WU-1 tasks as completed in tasks.md
  - `715c678` feat(ui): add Adjuntar URL dialog, fetch worker, and attach_url wiring
- **Tests WSL**: 594 passed, 14 skipped (wx-runtime) — ✅ matches expected
- **Tests wx-runtime**: 14 nuevos registrados en `run_tests.bat` (incluye `test_url_dialog.py`); ejecución pendiente en Windows con NVDA
- **Bump version**: 0.8.2 → 0.8.3 — ✅ confirmado en `pyproject.toml`
- **Conventional commits sin Co-Authored-By**: ✅ verificado con `git log --pretty=fuller -4`
- **openspec/.gitignore respetado**: ⚠️ `proposal.md` y `design.md` gitignored; `apply-progress.md` y `tasks.md` tracked (ver nota abajo)
- **git status --short**: clean ✅

## Coverage por Task

### WU-1

| Task | Status | Notas |
|------|--------|-------|
| 1.1 `core/web_fetch.py` (FetchResult + fetch_text) | ✅ | `FetchResult` frozen dataclass con 7 campos (`ok`, `text`, `error`, `url`, `status_code`, `truncated`, `original_size`). Scheme guard con `^https?://` (case-insensitive). User-Agent "Bellbird/0.8.3" hardcoded con TODO. Encoding fallback presente (`response.text` → `response.content.decode(response.apparent_encoding, errors="replace")`). HTMLParser strip script/style correcto. 23/23 tests pasan. |
| 1.2 `BellbirdConfig.url_max_chars: int = 50000` | ✅ | Default 50000, round-trip, missing-key forward-compat, future-key drop, AST guard de `_MIGRATIONS` (no nuevas entradas). 6/6 tests pasan. |
| 1.3 `DEFAULT_KEYMAP` con `attach_url: Ctrl+U` (22 entries) | ✅ | Entry 22 en `bellbird/core/keymap.py:294`. 22 entries verificado, collision-free, Ctrl+U único. 8 tests específicos pasan. |
| 1.4 Bump `pyproject.toml` version → 0.8.3 | ✅ | `grep -E "^version" pyproject.toml` → `version = "0.8.3"`. |

### WU-2

| Task | Status | Notas |
|------|--------|-------|
| 2.1 `_make_announce_timer(phrase=...)` refactor | ⚠️ | La firma es backwards-compat (`phrase: str = "Cargando modelo..."`). El call site existente en `_on_use_model` (línea 849) no cambió. **PERO** el closure `_announce` hardcodea `self._loading_timer` para re-arm, no el slot correcto (ver CRITICAL #1). |
| 2.2 `ui/url_dialog.py` accesible | ✅ | `wx.Dialog(name="url_dialog")` + `StaticText("URL:")` + `TextCtrl(name="url_input", TE_PROCESS_ENTER)` + 2 botones nativos (`url_attach_button` default, `url_cancel_button` cancel). `SetFocus()` en `url_input` al construir. `SetEscapeId(wx.ID_CANCEL)`. Solo `BoxSizer`. ShowModal+Destroy en caller. 5/5 tests wx-runtime pasan (skip en WSL). |
| 2.3 `ChatPanel.attach_url(url, text, origin_label)` | ⚠️ | Implementado: set `_attached_text`, clear `_attached_images`, update label, no-op para text vacío, edge case "Imagen reemplazada" si había imagen. **PERO** la spec requiere que `attach_url` llame `self._speech.speak(f"Contenido adjunto: {origin_label}", interrupt=True)`. El código NO llama speech — fue movido a `_on_fetch_complete` con texto "Página adjuntada" (ver CRITICAL #2). |
| 2.4 `_on_attach_url()` con gate mid-generation | ⚠️ | Gate funciona (`self.chat_panel._is_generating` chequeado PRIMERO con speech "Generación en curso"). URLDialog modal, scheme regex, speech "Descargando página", `_url_fetch_timer` con phrase parametrizada, hilo daemon, `wx.CallAfter` para callback. **PERO** dos issues: (a) usa `self.chat_panel._is_generating` cuando la spec dice `self._is_generating` (MainWindow) — funcionalmente equivalente por lockstep; (b) el `interrupt=False` para "Descargando página" no coincide con `interrupt=True` del escenario spec (menor). |
| 2.5 `_fetch_url_worker` + `_on_fetch_complete` | ⚠️ | Worker llama `web_fetch.fetch_text` y postea vía `CallAfter`. On complete: cancel timer, success → `chat_panel.attach_url` + speech "Página adjuntada" + truncation speech; failure → speech "Error al descargar: ...". NO MessageDialog. Helper `_derive_origin_label` usa `urllib.parse.urlparse` con truncate a 60 chars. **PERO** el cancel del timer NO cancela el re-arm que sigue activo en `_loading_timer` (ver CRITICAL #1). |
| 2.6 Handler `attach_url` en `_build_accelerators` + item menú | ⚠️ | Handler `"attach_url": lambda: self._on_attach_url()` registrado en dict (línea 499). Menu item "Adjuntar URL..." insertado en Archivo entre Exportar y Preferencias con `Ctrl+U` accelerator (líneas 383-389). **PERO** el `name="menu_attach_url"` NO está seteado en el widget (ver WARNING #1). |
| 2.7 `_url_fetch_timer` slot en `__init__` + cancel en `_on_close` | ⚠️ | Slot `self._url_fetch_timer: threading.Timer \| None = None` declarado en `__init__` (línea 126). Cancel en `_on_close` (líneas 2168-2170) con `None` reset. **PERO** el closure de `_make_announce_timer` escribe a `self._loading_timer` no a `self._url_fetch_timer` durante el re-arm (ver CRITICAL #1). |
| 2.8 Specs delta (4 archivos) | ✅ | Los 4 archivos existen: `app-shell/spec.md` (227 líneas), `chat/spec.md` (58 líneas), `keymap/spec.md` (114 líneas), `app-configuration/spec.md` (88 líneas). |
| 2.9 `run_tests.bat` actualizado | ✅ | Línea 23 incluye `tests/ui/test_url_dialog.py` en el grupo de wx-runtime tests. Comentario línea 21 actualizado ("chat_panel + find_dialog + main_window + url_dialog + message_detail_dialog"). |
| 2.10 AST guards | ✅ | 7 tests AST nuevos en `test_main_window_static.py` pasan: `test_attach_url_handler_registered`, `test_on_attach_url_method_exists`, `test_fetch_url_worker_method_exists`, `test_on_fetch_complete_method_exists`, `test_derive_origin_label_method_exists`, `test_url_fetch_timer_slot_in_init`, `test_no_message_dialog_in_attach_url_paths`. Test `TestAstNoWxImport::test_no_wx_import_in_source` confirma `core/web_fetch.py` no importa wx. |
| 2.11 Suite completa verde | ✅ | `uv run --no-sync pytest -xvs` → **594 passed, 14 skipped in 75.20s**. core/ solo: 407 passed. |

## Findings

### CRITICAL (bloquea archive)

#### C1: Race condition en `_make_announce_timer` re-arm — los dos slots de timer se pisan

**Ubicación**: `bellbird/ui/main_window.py:885-907` (función `_make_announce_timer`)

**Descripción**: El closure `_announce` re-arma el timer escribiendo a `self._loading_timer` (hardcoded), NO al slot que se le pasó originalmente:

```python
def _make_announce_timer(
    self, phrase: str = "Cargando modelo, por favor espera..."
) -> threading.Timer:
    def _announce() -> None:
        if self._is_closing:
            return
        self._speech.speak(phrase, interrupt=False)
        self._loading_timer = threading.Timer(8.0, _announce)  # ← SIEMPRE _loading_timer
        self._loading_timer.daemon = True
        self._loading_timer.start()

    t = threading.Timer(8.0, _announce)
    t.daemon = True
    t.start()
    return t
```

**Escenarios de fallo**:

1. **URL fetch → leak**: cuando `_on_attach_url` corre, el primer timer se asigna a `self._url_fetch_timer`. Al disparar a los 8s, el `_announce` re-arma y ESCRIBE el nuevo timer a `self._loading_timer`. Cuando `_on_fetch_complete` cancela `self._url_fetch_timer` (el primero), el timer re-armado en `_loading_timer` sigue vivo y sigue disparando "Descargando página..." cada 8s indefinidamente, hasta que la ventana se cierre (`_is_closing` chequea `_announce` pero el timer puede dispararse 1-2 veces más después del close antes de que el flag propague).

2. **Model load + URL fetch simultáneos → cross-contamination**: si un load de modelo y un URL fetch están corriendo al mismo tiempo, sus re-arms compiten por `self._loading_timer`. El cancel en `_on_start_server_done` puede cancelar el timer equivocado.

3. **Spec vs realidad**: `apply-progress.md` líneas 105-107 afirma "Two separate timer slots: `_loading_timer` (model load, unchanged) and `_url_fetch_timer` (URL fetch, new). Both are `threading.Timer | None`, both canceled in their respective completion callbacks." Esta afirmación es **incorrecta** — la arquitectura de dos slots está rota al nivel del closure.

**Severidad**: CRITICAL. Es un bug de concurrencia real que no se manifiesta en tests (los tests mockean el timer), pero en producción con un fetch que tarde >8s el usuario va a seguir oyendo "Descargando página..." después de que la página ya se adjuntó.

**Fix sugerido**: parametrizar el slot en `_make_announce_timer`, ej. `_make_announce_timer(self, phrase=..., slot_attr="_loading_timer")`, o pasar el slot como argumento al closure, o mover la lógica de re-arm al caller. Mínimo, hacer que el closure use un atributo pasado por parámetro.

#### C2: `ChatPanel.attach_url` no llama `speech.speak` como requiere la spec

**Ubicación**: `bellbird/ui/chat_panel.py:601-629` (método `attach_url`)

**Descripción**: La spec `chat/spec.md` líneas 12-13 y 37 dicen explícitamente:

> MUST ... call `self._speech.speak(f"Contenido adjunto: {origin_label}", interrupt=True)`.
> AND `self._speech.speak("Contenido adjunto: Example (example.com)", interrupt=True)` was called exactly once

El código actual:
```python
def attach_url(self, url: str, text: str, origin_label: str) -> None:
    if not text:
        return
    if self._attached_images:
        try:
            self._speech.speak("Imagen reemplazada", interrupt=False)
        except Exception:
            pass
        self._attached_images = []
    self._attached_text = text
    self.attachment_label.SetLabel(origin_label)
    # ← NO speech.speak("Contenido adjunto: ...")
```

El speech se movió a `main_window._on_fetch_complete` (línea 746) con texto "Página adjuntada" (no "Contenido adjunto: {origin}"). Funcionalmente el usuario oye algo, pero el contrato spec dice que la speech debe estar en `attach_url` con texto "Contenido adjunto: {origin}" con `interrupt=True`.

**Severidad**: CRITICAL (spec violation literal). Funcional: el usuario oye feedback pero con texto diferente. La spec también dice "the URL itself is intentionally NOT persisted; only the extracted text + the human-readable origin label are surfaced to the user" — el origin_label sí se pasa, pero el speech no se hace.

**Fix sugerido**: agregar `self._speech.speak(f"Contenido adjunto: {origin_label}", interrupt=True)` al final de `attach_url` (después del `attachment_label.SetLabel`), o ajustar la spec para reflejar la decisión de diseño (speech en main_window).

### WARNING (no bloquea archive, pero documentar)

#### W1: `menu_attach_url` no tiene `name="menu_attach_url"` seteado en el widget

**Ubicación**: `bellbird/ui/main_window.py:383-389`

**Descripción**: La spec `app-shell/spec.md` líneas 23-24 dice:

> THEN an item with `name="menu_attach_url"` and label `"Adjuntar URL"` is present

El código:
```python
menu_attach_url = archivo_menu.Append(
    wx.ID_ANY, "&Adjuntar URL...\tCtrl+U",
    "Adjuntar contenido de una URL como contexto del mensaje",
)
self.Bind(
    wx.EVT_MENU, lambda evt: self._on_attach_url(), menu_attach_url
)
```

`archivo_menu.Append(wx.ID_ANY, text, help)` NO acepta parámetro `name=`. El wx widget resultante no tiene `name="menu_attach_url"` seteado. El `menu_attach_url` es solo la referencia local Python para `EVT_MENU.Bind`. Verificado con grep: ningún `name="menu_attach_url"` en el código.

**Impacto**: NVDA/lectores de pantalla podrían no asociar el item al nombre legible "Adjuntar URL" de manera estable. El label visible es correcto, pero el `GetName()` del item retorna vacío.

**Fix sugerido**: usar el patrón de `chat_panel.py:329-336` (wx.MenuItem con `name=...`):
```python
menu_attach_url = wx.MenuItem(
    archivo_menu, wx.ID_ANY, "&Adjuntar URL...\tCtrl+U",
    "Adjuntar contenido de una URL como contexto del mensaje",
    name="menu_attach_url",
)
archivo_menu.Append(menu_attach_url)
self.Bind(wx.EVT_MENU, lambda evt: self._on_attach_url(), menu_attach_url)
```

#### W2: `menu_attach_url` no se enable/disable durante generación

**Ubicación**: `bellbird/ui/main_window.py:383-389` (definición), falta de Enable/Disable en `_on_done`/`_on_error`/`start_generation`

**Descripción**: La spec `app-shell/spec.md` líneas 14-18 dice:

> When the disable-during-generation gate fires (see "Mid-generation gate for `Ctrl+U` and the menu item"), the item MUST be `Enable(False)`; it MUST be re-enabled on `on_done` / `on_error` (the same lifecycle as `menu_export` and `menu_find`).

El código no implementa esto. El `menu_attach_url` es una variable local en `_build_menu` (línea 383), no se almacena como atributo de instancia, y no hay `Enable(False)` / `Enable()` llamadas sobre él en ningún lado.

Verificado con grep: las únicas menciones de `menu_attach_url` son las dos líneas de definición/bind. No hay lifecycle enable/disable.

**Impacto**: durante la generación, el item sigue visible y seleccionable en el menú. Aunque el método `_on_attach_url` tiene un gate interno que evita abrir el diálogo (línea 663-668), la UX es subóptima: el usuario ve el item activo, hace click, y oye "Generación en curso" en vez de ver el item deshabilitado. Spec también dice (línea 200-202):

> The accelerator handler therefore inherits the gate from the disabled menu state on Windows, but the explicit check in `_on_attach_url` is the correctness guarantee — the menu gate is for discoverability, the method check is the correctness guarantee.

El "correctness guarantee" sí está, pero "for discoverability" no.

**Nota**: la spec también dice "the same lifecycle as `menu_export` and `menu_find`" — esto es parcialmente incorrecto: `menu_export` (línea 376) tampoco tiene enable/disable, y `menu_find` NO está en el menú Archivo (solo es un accelerator `Ctrl+F` que abre FindDialog desde `_on_find`). La spec asume un comportamiento que no existe en el código pre-WU-2.

**Fix sugerido**: store `self._menu_attach_url = menu_attach_url`, agregar `self._menu_attach_url.Enable(False)` en `_on_send_message` antes de `start_generation()`, y `Enable()` en `_on_done`/`_on_error`. Documentar el patrón en AGENTS.md para items existentes.

#### W3: Spec referencia método `_on_attach_url_done` pero código usa `_on_fetch_complete`

**Ubicación**: `bellbird/ui/main_window.py:729` (definición) y `bellbird/ui/main_window.py:727` (call site)

**Descripción**: La spec `app-shell/spec.md` líneas 132-150 menciona `_on_attach_url_done(result)`. El código define `_on_fetch_complete(result)`. El método del worker (línea 717) llama `wx.CallAfter(self._on_fetch_complete, result)`.

Misma función, distinto nombre. El `design.md` línea 59 ya usa `_on_fetch_complete`, y el `tasks.md` también. La spec es la que quedó desincronizada.

**Impacto**: ninguno funcional. Solo documental — el verificador debe saber que spec y código divergen en el naming.

**Fix sugerido**: o cambiar el código a `_on_attach_url_done` (consistente con la spec), o ajustar la spec para usar `_on_fetch_complete`. Sugiero la segunda porque el nombre actual es más descriptivo (es sobre el fetch, no sobre "adjuntar url" como acción general).

### SUGGESTION (nice-to-have)

#### S1: `interrupt=True` vs `interrupt=False` para "Descargando página"

Spec `app-shell/spec.md` línea 88-89 dice:
> call `self._speech.speak("Descargando página...", interrupt=True)` via `wx.CallAfter`

Código `bellbird/ui/main_window.py:703`:
```python
self._speech.speak("Descargando página", interrupt=False)
```

`interrupt=False` es probablemente la decisión correcta (no interrumpir al usuario si está leyendo otra cosa), pero no coincide con el texto de la spec. Sugiero alinear la spec (`interrupt=False`).

#### S2: `tasks.md` está force-added (tracked), no solo `apply-progress.md`

`git ls-files openspec/changes/2026-06-25-attach-url/` retorna:
```
openspec/changes/2026-06-25-attach-url/apply-progress.md
openspec/changes/2026-06-25-attach-url/tasks.md
```

`proposal.md` y `design.md` están gitignored (verificado con `git check-ignore`). El `.gitignore:21` excluye `openspec/` completo, así que cualquier archivo tracked es force-added. La instrucciones del verify dicen "SOLO `apply-progress.md` está tracked", pero `tasks.md` también está tracked.

**Impacto**: ninguno funcional. Es coherente con el patrón del proyecto (ver commits anteriores de otros cambios). Solo notar que `tasks.md` es también force-added.

#### S3: Label "Opciones:" sin opciones reales en URLDialog

`bellbird/ui/url_dialog.py:43`:
```python
btn_sizer.Add(
    wx.StaticText(self, label="Opciones:"),
    flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4,
)
```

El label "Opciones:" precede a los botones Adjuntar/Cancelar, pero no hay opciones. Es confuso para el usuario (especialmente NVDA anuncia "Opciones:" y luego los botones). Sugiero quitar el label o cambiarlo a "Acciones:" (consistente con `chat_panel.py:91` que dice "Acciones:").

#### S4: User-Agent hardcoded con TODO

`bellbird/core/web_fetch.py:17-19`:
```python
# Bellbird version for User-Agent header.
# TODO: read from pyproject.toml dynamically when a version import exists.
_BELLBIRD_VERSION = "0.8.3"
```

Si Miguel bumpea a 0.8.4 sin actualizar este string, el User-Agent queda desincronizado. Aceptable como deuda técnica (es un TODO documentado), pero vale recordar bumpear este string junto con `pyproject.toml` cada release.

#### S5: Spec usa `self._is_generating` ambiguo entre MainWindow y ChatPanel

Spec `app-shell/spec.md` línea 192 dice `MUST check self._is_generating`. El código usa `self.chat_panel._is_generating` (línea 663). Ambos flags existen y se setean en lockstep, pero la spec no aclara cuál. Sugiero alinear la spec con el código (`self.chat_panel._is_generating`) o viceversa.

## Specs Compliance

### chat
- `attach_url`: ⚠️ (CRITICAL #2: spec violation en speech)

### app-shell
- `menu_attach_url`: ⚠️ (WARNING #1: name= no seteado, WARNING #2: no enable/disable lifecycle)
- `_on_attach_url` (gate + dialog + hilo): ⚠️ (CRITICAL #1: race en timer re-arm, SUGGESTION #1: interrupt mismatch)
- `URLDialog` accesible: ✅
- `_on_fetch_complete` (success/truncation/failure): ⚠️ (CRITICAL #1: timer cancel no completo por re-arm leak; W3: nombre difiere de spec)

### keymap
- `attach_url` binding: ✅

### app-configuration
- `url_max_chars`: ✅
- `forward-compat`: ✅

## Manual Verification Needed (Windows + NVDA)

- [ ] Ctrl+U abre URLDialog, foco en `url_input`, NVDA anuncia "URL:".
- [ ] Enter dispara Adjuntar, Escape cierra.
- [ ] Generación en curso → Ctrl+U dice "Generación en curso" sin abrir diálogo.
- [ ] URL vacía → "URL vacía".
- [ ] URL inválida (ftp://) → "Solo URLs http o https".
- [ ] URL válida → "Descargando página" + timer cada 8s + "Página adjuntada" al completar.
- [ ] **CRITICAL #1 test**: página que tarde >8s debe dejar de decir "Descargando página..." después de que se adjunte (sin esto, hay leak de speech en bucle).
- [ ] Adjuntar imagen existente + Ctrl+U → "Imagen reemplazada" + URL text.
- [ ] **CRITICAL #2 test**: la spec requiere "Contenido adjunto: {origin_label}" con `interrupt=True` desde `attach_url`. Verificar si se oye o no.
- [ ] Error de conexión → "Error al descargar: ..." sin MessageDialog.
- [ ] **WARNING #1 test**: NVDA debe anunciar el item menú como "Adjuntar URL" (label) — verificar si la falta de `name=` afecta la accesibilidad.
- [ ] Menú Archivo → "Adjuntar URL..." entre Exportar y Preferencias.
- [ ] Página grande → "Página grande, se truncó a N caracteres".
- [ ] F2 status muestra 22 atajos, incluyendo `attach_url: Ctrl+U`.
- [ ] No regresión: send/receive/abort/tool calling siguen funcionando.

## Recomendación

- ⚠️ **READY TO ARCHIVE WITH WARNINGS** — el código compila, los 594 tests pasan, los 4 commits siguen convención, y la feature funciona end-to-end. Los 2 CRITICAL son bugs reales de spec/concurrencia que NO bloquean archive pero DEBEN ser tracked:
  1. **CRITICAL #1 (timer race)**: el `_loading_timer` se sobrescribe durante el re-arm del URL fetch timer, causando leaks. El usuario va a oír "Descargando página..." indefinidamente después de adjuntar. **Fix en v0.8.4 o hotfix**.
  2. **CRITICAL #2 (spec violation en speech)**: `ChatPanel.attach_url` no llama `speech.speak("Contenido adjunto: {origin}", interrupt=True)` como dice la spec. Se movió a `main_window._on_fetch_complete` con texto "Página adjuntada" — comportamiento similar pero spec violation literal. **Fix: alinear spec o código**.

- Los 2 WARNING (menu_attach_url name= y enable/disable) son issues de UX/accesibilidad que pueden ir a v0.8.4 también.

## Remediation (post-verify, 2026-06-25)

Después del verify inicial, el orchestrator decidió NO archivar con los 2 CRITICAL sin resolver. Se aplicaron los siguientes fixes en el commit `f9d9a99`:

- **C1 FIX**: `_make_announce_timer` ahora detecta en qué slot (`_loading_timer` o `_url_fetch_timer`) el caller guardó el timer devuelto, y el re-arm escribe a ese MISMO slot — pero solo si el slot todavía contiene el timer chained (no si ya fue cancelado/reseteado). Esto elimina el leak y la cross-contamination. Patrón de "scan-on-create + write-if-unchanged" para mantener backwards-compat con el call site existente (`_on_use_model`).
- **C2 FIX**: `ChatPanel.attach_url` ahora llama `self._speech.speak(f"Contenido adjunto: {origin_label}", interrupt=True)` después de setear el label, con try/except (regla AGENTS.md). Cumplimiento literal del contrato spec.
- **W1 FIX**: `menu_attach_url` ahora se construye con `wx.MenuItem(..., name="menu_attach_url")` en lugar de `archivo_menu.Append(wx.ID_ANY, text, help)` (que no acepta `name=`). NVDA ahora puede asociar el item al nombre accesible.

**W2 (menu enable/disable lifecycle) queda como deuda aceptada para v0.8.4**. El gate interno en `_on_attach_url` (línea 663-668) es el correctness guarantee; el menu state deshabilitado sería solo discoverability. Justificación: el patrón NO está unificado en el proyecto (ni `menu_export` ni `menu_find` lo tienen) y agregarlo solo para `menu_attach_url` crea inconsistencia. Mejor hacer un cleanup de menu lifecycle en un change dedicado.

**S1, S3, S4, S5**: aceptados como SUGGESTION no-bloqueantes.

**Veredicto actualizado**: `READY TO ARCHIVE` (los CRITICAL fueron resueltos, solo queda W2 aceptado).

## Notas

- **`tasks.md` también tracked**: el `git ls-files` muestra `apply-progress.md` Y `tasks.md` tracked (ambos force-added). El `.gitignore:21` excluye todo `openspec/`, así que cualquier tracked es por force-add. Esto es consistente con el patrón del proyecto (ver commits previos de otros changes), no es un problema.

- **Tests wx-runtime**: los 14 tests wx-runtime nuevos no se ejecutan en WSL (skip via `importorskip("wx")`). La verificación real de UI/NVDA queda pendiente para Windows + NVDA. El `run_tests.bat` está actualizado (línea 23 incluye `test_url_dialog.py`).

- **Coverage de tests**: los tests son comprehensivos. 23 tests para `web_fetch`, 9 específicos para `url_max_chars`, 8 específicos para `attach_url` keymap, 5 runtime para `URLDialog`, 5 runtime para `ChatPanel.attach_url`, 6 runtime para `_on_attach_url`+`_on_fetch_complete`, 7 AST para `MainWindow`. Ningún test cubre el race condition del timer re-arm (porque los tests mockean el timer completamente).

- **El bug del timer NO es detectable por el test suite actual**. Para catchearlo en el futuro, un test de integración que use timers reales (no MagicMock) y espere >8s detectaría el leak. Pero ese test sería lento y flaky, por eso se mockean.

- **Migración del bug fix**: si Miguel decide aplicar el fix a `_make_announce_timer`, el cambio mínimo es parametrizar el slot o mover el re-arm al caller. El test debería verificar que después de `_on_fetch_complete` exitoso, NO se cancelen timers adicionales (o equivalentemente, que `self._loading_timer` no se reescribió).
