"""Definiciones de los atajos de teclado: defaults, validación y parseo."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ytchat.core import config_predeterminada
from ytchat.core import diagnostico


# ── Atajos de teclado ─────────────────────────────────────────────────────────
# Esquema por ÁREA: el modificador indica la zona, para que sea intuitivo.
#   Ctrl  → Reproductor (vídeo/audio), como las apps de medios.
#   Alt   → Conexión y chat (acciones sobre el directo).
#   F     → Voz/lectura TTS (ajustes en caliente) y navegación.
#   Ctrl+Alt → grupo de música: flechas, Espacio, una letra o un dígito. En
#   Windows AltGr llega como Ctrl+Alt, así que al capturar se descartan las
#   teclas que AltGr escribe en el teclado en uso.
# Se muestran como aceleradores en la barra de menú (NVDA los lee). No chocan
# con los mnemónicos de menú (Alt+inicial) porque usamos otras letras.
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
      "rep_vol_menos", "rep_vol_mas", "descargas_abrir", "pantalla_completa"]),
    ("Conexión y chat (Alt)",
     ["conectar", "desconectar", "enviar_chat", "ir_lista"]),
    ("Ventanas y paneles (Ctrl+Shift)",
     ["abrir_preferencias", "abrir_historial", "marcar_incidencia",
       "abrir_transmision", "copiar_enlace", "obs_micro",
       "avisos_sobrecarga"]),
    ("Voz y lectura (teclas F)",
     ["pausa", "detener_tts", "velocidad_menos", "velocidad_mas",
      "volumen_menos", "volumen_mas", "silenciar_lectura",
      "silenciar_sonidos", "anunciar_estado", "anunciar_autor",
      "describir_escena"]),
    ("Música (Ctrl+Alt)",
     ["musica_play", "musica_siguiente", "musica_anterior",
      "musica_vol_mas", "musica_vol_menos", "musica_que_suena",
      "musica_ventana", "musica_listas"]),
    ("Ventana y navegación (fijos)",
     ["salir", "region_siguiente", "region_anterior"]),
]

# Modificador obligatorio por acción: reproductor → Ctrl, app → Alt, voz → F.
# El grupo de atajos fijos no impone modificador.
_AREA_POR_GRUPO = ("ctrl", "alt", "ctrl+shift", "f", "ctrl+alt", None)
ATAJOS_AREA = {ac: _AREA_POR_GRUPO[i]
               for i, (_titulo, acs) in enumerate(ATAJOS_GRUPOS) for ac in acs}

_SIMBOLOS_PERMITIDOS = {",", ".", ";", "'", "[", "]", "/", "-"}
# Teclas con nombre admitidas (además de una letra/símbolo o una tecla F,
# sola o con Ctrl como en Ctrl+F2).
_TECLAS_NOMBRE = {"enter", "left", "right", "up", "down", "space", "end"}
# Ctrl+Shift debe probarse antes que Ctrl para no quedarse con «shift+tecla».
_RE_ATAJO = re.compile(r"^(ctrl\+shift|ctrl|alt)\+(.+)$", re.IGNORECASE)
# Ctrl+Alt es su propia área: flechas, Espacio, una letra o un dígito. Las
# letras y dígitos que AltGr escribe se descartan al capturar, según el
# teclado en uso (ver teclado_altgr).
_RE_CTRL_ALT = re.compile(
    r"^(ctrl\+alt|alt\+ctrl)\+(left|right|up|down|space|[a-z]|[0-9])$",
    re.IGNORECASE)
_RE_FKEY  = re.compile(r"^f(1[0-2]|[1-9])$", re.IGNORECASE)
_RE_CTRL_FKEY = re.compile(r"^ctrl\+f(1[0-2]|[1-9])$", re.IGNORECASE)

logger = diagnostico.obtener_logger(__name__)


@dataclass(frozen=True, slots=True)
class Atajo:
    accion: str
    texto:  str
    tecla:  str


def todos_los_atajos_default() -> dict[str, str]:
    """Devuelve las combinaciones reservadas por la aplicación."""
    return {**ATAJOS_FIJOS_DEFAULTS, **ATAJOS_DEFAULTS}


def _normalizar_atajo(valor: str | None) -> str | None:
    """Normaliza a 'ctrl+x' / 'alt+enter' / 'ctrl+left' / 'ctrl+alt+left'
    / 'f5' / 'ctrl+f2'. None si no vale.

    Ctrl+Shift, Ctrl o Alt + tecla, Ctrl+Alt con flechas, Espacio, una
    letra o un dígito, una tecla F sin modificador, o Ctrl más una tecla F
    (como Ctrl+F2). La exclusión de las letras y dígitos que AltGr escribe
    se decide al capturar el atajo, no aquí.
    """
    if valor is None:
        return None
    valor = valor.strip().lower().replace(" ", "")
    if not valor:
        return None
    if _RE_FKEY.match(valor):
        return valor
    m = _RE_CTRL_ALT.match(valor)
    if m:
        return f"ctrl+alt+{m.group(2)}"
    m = _RE_ATAJO.match(valor)
    if not m:
        return None
    mod, key = m.group(1), m.group(2)
    if key in _TECLAS_NOMBRE or _RE_FKEY.match(key):
        return f"{mod}+{key}"
    if len(key) == 1 and key.isascii() and (key.isalnum() or key in _SIMBOLOS_PERMITIDOS):
        return f"{mod}+{key}"
    return None


def atajo_valido_para_area(accion: str, normalizado: str | None) -> bool:
    """¿El atajo respeta el modificador del área de la acción?

    Reproductor → Ctrl, app → Alt, voz → tecla F sola o con Ctrl
    (como Ctrl+F2), música → Ctrl+Alt con flechas, Espacio, una letra o un
    dígito. Vacío (desactivado) o acción sin área definida se aceptan sin
    restricción.
    """
    area = ATAJOS_AREA.get(accion)
    if not normalizado or area is None:
        return True
    if area == "f":
        return bool(_RE_FKEY.match(normalizado)
                    or _RE_CTRL_FKEY.match(normalizado))
    # Ctrl+Shift y Ctrl+Alt tienen área propia, no la general de Ctrl.
    if area == "ctrl" and (normalizado.startswith("ctrl+shift+")
                           or normalizado.startswith("ctrl+alt+")):
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
