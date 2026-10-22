"""Definiciones de los atajos de teclado: defaults, validación y parseo."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ytchat.core import config_predeterminada
from ytchat.core import diagnostico


# ── Atajos de teclado ─────────────────────────────────────────────────────────
# Esquema por FAMILIA: el modificador indica la zona, para que sea intuitivo.
#   Ctrl       → Reproductor (vídeo/audio), como las apps de medios.
#   Alt        → Chat (acciones sobre el directo).
#   Ctrl+Shift → Ventanas que abre la app.
#   Alt+Shift  → Directo y OBS.
#   F          → Voz/lectura TTS (ajustes en caliente).
#   Ctrl+Alt   → Música: flechas, Espacio, una letra o un dígito. En Windows
#   AltGr llega como Ctrl+Alt, así que al capturar se descartan las teclas que
#   AltGr escribe en el teclado en uso.
# Se muestran como aceleradores en la barra de menú (NVDA los lee). Alt con
# letra queda libre para los mnemónicos de menú (Alt+inicial).
#
# Fijos (no editables): F9/F10 velocidad, F11/F12 volumen del TTS, Alt+F4 para
# cerrar y F6 / Shift+F6 para navegar entre regiones.

ATAJOS_DEFAULTS = config_predeterminada.seccion("atajos")

# Estas combinaciones se reservan aunque la gramática editable no admita
# Alt+F4 ni Shift+F6.
ATAJOS_FIJOS_DEFAULTS = {
    "salir": "alt+f4",
    "region_siguiente": "f6",
    "region_anterior": "shift+f6",
}

# Acciones cuya tecla NO debe poder cambiarse en el editor de atajos.
ATAJOS_FIJOS = {
    "velocidad_menos", "velocidad_mas", "volumen_menos", "volumen_mas",
    *ATAJOS_FIJOS_DEFAULTS,
}

# Agrupación para el editor de Preferencias (título de grupo, acciones).
ATAJOS_GRUPOS = [
    ("Reproductor (Ctrl)",
     ["rep_play", "rep_retro", "rep_avanz", "rep_directo", "rep_detener", "rep_mute",
      "rep_vol_menos", "rep_vol_mas", "pantalla_completa"]),
    ("Chat (Alt)",
     ["enviar_chat"]),
    ("Ventanas (Ctrl+Mayús)",
     ["abrir_preferencias", "abrir_historial", "abrir_transmision",
      "descargas_abrir", "musica_ventana", "preguntar_ia"]),
    ("Directo y OBS (Alt+Mayús)",
     ["conectar", "desconectar", "ir_lista", "copiar_enlace",
      "marcar_incidencia", "obs_micro", "avisos_sobrecarga"]),
    ("Voz y lectura (teclas F)",
     ["pausa", "detener_tts", "velocidad_menos", "velocidad_mas",
      "volumen_menos", "volumen_mas", "silenciar_lectura",
      "silenciar_sonidos", "anunciar_estado", "anunciar_autor",
       "describir_escena", "consulta_rapida_ia"]),
    ("Música (Ctrl+Alt)",
     ["musica_play", "musica_siguiente", "musica_anterior",
      "musica_vol_mas", "musica_vol_menos", "musica_que_suena",
      "musica_silenciar", "musica_aleatorio", "musica_repetir",
      "musica_detener", "musica_adelantar", "musica_retroceder"]),
    ("Ventana y navegación (fijos)",
     ["salir", "region_siguiente", "region_anterior"]),
]

# Modificador obligatorio por acción: reproductor → Ctrl, chat → Alt,
# ventanas → Ctrl+Shift, directo → Alt+Shift, voz → F.
# El grupo de atajos fijos no impone modificador.
_AREA_POR_GRUPO = ("ctrl", "alt", "ctrl+shift", "alt+shift", "f", "ctrl+alt", None)
ATAJOS_AREA = {ac: _AREA_POR_GRUPO[i]
               for i, (_titulo, acs) in enumerate(ATAJOS_GRUPOS) for ac in acs}

# Migración al mapa por familias: viejo valor de fábrica y nuevo, por acción.
# Solo migra la acción cuyo valor sigue siendo el viejo de fábrica.
_MIGRACION_ATAJOS = {
    "descargas_abrir":   ("ctrl+s",       "ctrl+shift+d"),
    "musica_ventana":    ("ctrl+alt+m",   "ctrl+shift+m"),
    "obs_micro":         ("ctrl+shift+m", "alt+shift+m"),
    "marcar_incidencia": ("ctrl+shift+i", "alt+shift+i"),
    "copiar_enlace":     ("ctrl+shift+e", "alt+shift+e"),
    "avisos_sobrecarga": ("ctrl+shift+a", "alt+shift+a"),
    "conectar":          ("alt+c",        "alt+shift+c"),
    "desconectar":       ("alt+d",        "alt+shift+d"),
    "ir_lista":          ("alt+l",        "alt+shift+l"),
}

# Versión del mapa de atajos: una carga por debajo migra una sola vez.
VERSION_ATAJOS = 2

_SIMBOLOS_PERMITIDOS = {",", ".", ";", "'", "[", "]", "/", "-"}
# Teclas con nombre admitidas (además de una letra/símbolo o una tecla F,
# sola o con Ctrl como en Ctrl+F2).
_TECLAS_NOMBRE = {"enter", "left", "right", "up", "down", "space", "end"}
# Alt+Shift se prueba antes que Alt para no quedarse con «shift+tecla», y
# admite el orden invertido «shift+alt+tecla», como Ctrl+Alt con Alt+Ctrl.
_RE_ALT_SHIFT = re.compile(r"^(alt\+shift|shift\+alt)\+(.+)$", re.IGNORECASE)
# Ctrl+Shift debe probarse antes que Ctrl para no quedarse con «shift+tecla».
_RE_ATAJO = re.compile(r"^(ctrl\+shift|ctrl|alt)\+(.+)$", re.IGNORECASE)
# Ctrl+Alt es su propia área: flechas, Espacio, una letra o un dígito. Las
# letras y dígitos que AltGr escribe se descartan al capturar, según el
# teclado en uso (ver teclado_altgr).
_RE_CTRL_ALT = re.compile(
    r"^(ctrl\+alt|alt\+ctrl)\+(left|right|up|down|space|[a-z]|[0-9])$",
    re.IGNORECASE)
# Con Mayús solo valen las dos flechas horizontales, en cualquier orden.
_RE_CTRL_ALT_SHIFT = re.compile(
    r"^(ctrl\+alt\+shift|ctrl\+shift\+alt|alt\+ctrl\+shift"
    r"|alt\+shift\+ctrl|shift\+ctrl\+alt|shift\+alt\+ctrl)\+(left|right)$",
    re.IGNORECASE)
_RE_FKEY  = re.compile(r"^f(1[0-2]|[1-9])$", re.IGNORECASE)
_RE_CTRL_FKEY = re.compile(r"^ctrl\+f(1[0-2]|[1-9])$", re.IGNORECASE)
_RE_CTRL_SHIFT_FKEY = re.compile(
    r"^ctrl\+shift\+f(1[0-2]|[1-9])$", re.IGNORECASE)
_RE_F_TODAS = (_RE_FKEY, _RE_CTRL_FKEY, _RE_CTRL_SHIFT_FKEY)

logger = diagnostico.obtener_logger(__name__)


@dataclass(frozen=True, slots=True)
class Atajo:
    accion: str
    texto:  str
    tecla:  str


def todos_los_atajos_default() -> dict[str, str]:
    """Devuelve las combinaciones reservadas por la aplicación."""
    return {**ATAJOS_FIJOS_DEFAULTS, **ATAJOS_DEFAULTS}


def _tecla_editable(key: str) -> bool:
    """¿La tecla pelada vale como atajo editable: nombre, F o una tecla?"""
    return (key in _TECLAS_NOMBRE or bool(_RE_FKEY.match(key))
            or (len(key) == 1 and key.isascii()
                and (key.isalnum() or key in _SIMBOLOS_PERMITIDOS)))


def _normalizar_atajo(valor: str | None) -> str | None:
    """Normaliza a 'ctrl+x' / 'alt+enter' / 'ctrl+left' / 'ctrl+alt+left'
    / 'alt+shift+c' / 'f5' / 'ctrl+f2'. None si no vale.

    Ctrl+Shift, Ctrl, Alt o Alt+Shift + tecla, Ctrl+Alt con flechas,
    Espacio, una letra, un dígito o Mayús con left/right, una tecla F sin
    modificador, o Ctrl más una tecla F (como Ctrl+F2). Las letras y dígitos
    que AltGr escribe se descartan al capturar el atajo, no aquí.
    """
    if valor is None:
        return None
    valor = valor.strip().lower().replace(" ", "")
    if not valor:
        return None
    if _RE_FKEY.match(valor):
        return valor
    for patron, prefijo in ((_RE_CTRL_ALT_SHIFT, "ctrl+alt+shift+"),
                            (_RE_CTRL_ALT, "ctrl+alt+")):
        m = patron.match(valor)
        if m:
            return prefijo + m.group(2)
    m = _RE_ALT_SHIFT.match(valor)
    if m:
        return f"alt+shift+{m.group(2)}" if _tecla_editable(m.group(2)) else None
    m = _RE_ATAJO.match(valor)
    if not m:
        return None
    mod, key = m.group(1), m.group(2)
    if _tecla_editable(key):
        return f"{mod}+{key}"
    return None


def atajo_valido_para_area(accion: str, normalizado: str | None) -> bool:
    """¿El atajo respeta el modificador del área de la acción?

    Reproductor → Ctrl, chat → Alt, voz → tecla F sola, con Ctrl o con
    Ctrl+Mayús (como Ctrl+F2 o Ctrl+Mayús+F2), música → Ctrl+Alt con
    flechas, Espacio, una letra o un dígito. Vacío (desactivado) o acción
    sin área definida se aceptan sin restricción.
    """
    area = ATAJOS_AREA.get(accion)
    if not normalizado or area is None:
        return True
    if area == "f":
        return any(patron.match(normalizado) for patron in _RE_F_TODAS)
    # Ctrl+Shift, Ctrl+Alt y Alt+Shift tienen área propia, no las generales.
    if area == "ctrl" and (normalizado.startswith("ctrl+shift+")
                           or normalizado.startswith("ctrl+alt+")):
        return False
    if area == "alt" and normalizado.startswith("alt+shift+"):
        return False
    return normalizado.startswith(area + "+")


def parsear_atajos(raw: dict | None) -> dict[str, Atajo]:
    raw = {} if raw is None else {k.lower(): v for k, v in raw.items()}
    resultado: dict[str, Atajo] = {}
    teclas_usadas: dict[str, str] = {}

    for accion, default in todos_los_atajos_default().items():
        valor_usuario = raw.get(accion)
        fija = accion in ATAJOS_FIJOS
        if not fija and valor_usuario is not None and valor_usuario.strip() == "":
            continue  # desactivado explícitamente

        normalizado = default if fija else _normalizar_atajo(valor_usuario)
        if not fija and valor_usuario is not None and normalizado is None:
            logger.warning("atajos: valor inválido para %r: %r. Usando default %r.",
                           accion, valor_usuario, default)
            normalizado = _normalizar_atajo(default)
        elif not fija and normalizado is None:
            normalizado = _normalizar_atajo(default)
        if normalizado is None:
            continue

        # El conflicto se mide por la combinación COMPLETA: 'ctrl+d' y 'alt+d'
        # son atajos distintos y no chocan; dos 'alt+d' sí.
        if normalizado in teclas_usadas:
            logger.warning("atajos: conflicto — %r y %r usan %r. Desactivando %r.",
                           teclas_usadas[normalizado], accion, normalizado, accion)
            continue
        teclas_usadas[normalizado] = accion
        tecla = normalizado.split("+", 1)[-1]
        resultado[accion] = Atajo(accion=accion, texto=normalizado, tecla=tecla)
    return resultado


def detectar_conflictos_atajos(raw: dict | None) -> list[tuple[str, str, str]]:
    """Devuelve (acción que pierde, acción que conserva, combinación)."""
    raw = {} if raw is None else {k.lower(): v for k, v in raw.items()}
    conflictos = []
    teclas_usadas: dict[str, str] = {}
    for accion, default in todos_los_atajos_default().items():
        fija = accion in ATAJOS_FIJOS
        valor_usuario = raw.get(accion)
        if not fija and valor_usuario is not None and valor_usuario.strip() == "":
            continue
        normalizado = default if fija else _normalizar_atajo(valor_usuario)
        if not fija and normalizado is None:
            normalizado = _normalizar_atajo(default)
        if normalizado is None:
            continue
        anterior = teclas_usadas.get(normalizado)
        if anterior is not None:
            conflictos.append((accion, anterior, normalizado))
            continue
        teclas_usadas[normalizado] = accion
    return conflictos


def migrar_atajos(valores: dict | None) -> dict[str, str]:
    """Qué acciones pasan al valor nuevo, solo si siguen con el viejo.

    Función pura, sin configparser ni disco: recibe los valores actuales
    (acción → texto) y devuelve acción → valor nuevo. Migra la acción cuyo
    valor actual, ya normalizado, es exactamente el viejo de fábrica; vacío
    o cualquier otro no se toca. Una acción no se migra si el valor nuevo
    lo ocupa otra que se queda: se resuelve por iteraciones y nunca deja
    dos acciones con la misma combinación.
    """
    valores = {} if valores is None else {
        k.lower(): v for k, v in valores.items()}
    actuales: dict[str, str | None] = {}
    for accion, default in todos_los_atajos_default().items():
        if accion in ATAJOS_FIJOS:
            actuales[accion] = _normalizar_atajo(default)
        else:
            actuales[accion] = _normalizar_atajo(valores.get(accion, default))

    candidatas = {accion for accion, (viejo, _nuevo) in _MIGRACION_ATAJOS.items()
                  if actuales.get(accion) == viejo}
    while candidatas:
        nuevas = {a: _MIGRACION_ATAJOS[a][1] for a in candidatas}
        final = {a: nuevas.get(a, actuales.get(a)) for a in actuales}
        choca = {a for a in candidatas
                 if any(final[b] == nuevas[a] for b in actuales if b != a)}
        if not choca:
            break
        candidatas -= choca
    return {a: _MIGRACION_ATAJOS[a][1] for a in candidatas}


def migrar_atajos_config(p, ruta, atajos_raw: dict) -> list[str]:
    """Migra los atajos sobre un parser ya leído y deja la versión al día.

    Si `[sesion] version_atajos` falta, no es entero o es menor que
    `VERSION_ATAJOS`, escribe cada valor nuevo con `guardar_opcion`,
    actualiza `atajos_raw` y graba la versión, aunque no cambie nada.
    Devuelve las acciones migradas. El registro se deja al logger.
    """
    from ytchat.core import config as _config
    try:
        version = p.getint("sesion", "version_atajos")
    except Exception:
        version = 0
    if version >= VERSION_ATAJOS:
        return []
    cambios = migrar_atajos(atajos_raw)
    for accion, valor in cambios.items():
        _config.guardar_opcion(ruta, "atajos", accion, valor)
        atajos_raw[accion] = valor
    _config.guardar_opcion(ruta, "sesion", "version_atajos", str(VERSION_ATAJOS))
    if cambios:
        logger.info("Atajos migrados: %s",
                    ", ".join(f"{a}={v}" for a, v in sorted(cambios.items())))
    return list(cambios)
