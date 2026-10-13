"""Reproductor de sonidos.

Usa MCI (winmm.dll vía ctypes) en lugar de `winsound.PlaySound` porque
este último solo admite UN sonido a la vez: el tick de un mensaje nuevo
cortaría el ding del Super Chat anterior. Cada reproducción abre un
alias MCI propio, así dos sonidos pueden solaparse.

Todo MCI vive en un único hilo de sonido: `reproducir` solo encola la
ruta y vuelve, así ningún sonido congela la ventana aunque el disco vaya
lento. Ese mismo hilo abre, reproduce y barre los alias.

Fuera de Windows el módulo es un no-op silencioso, para que el mismo
código se pueda probar en Linux.
"""

from __future__ import annotations

import itertools
import logging
import queue
import sys
import threading
import time
from pathlib import Path

from ytchat.core import diagnostico

logger = diagnostico.obtener_logger(__name__)


_backend_winmm: bool = False
_winmm = None

_eventos: dict[str, Path] = {}
_volumen: float = 0.7
_activo:  bool  = True
_silenciado_usuario: bool = False   # Toggle en caliente (F7).

_alias_activos: dict[str, float] = {}
_alias_lock = threading.Lock()
_alias_contador = itertools.count(1)
_alias_prefijo = "ytcsnd"

# Cola de rutas pendientes para el hilo de sonido. Acotada: en una
# avalancha de mensajes no sirve encadenar ticks atrasados, el nuevo se
# descarta en silencio cuando está llena.
_MAX_PENDIENTES = 4
_cola_sonidos: queue.Queue = queue.Queue(maxsize=_MAX_PENDIENTES)

_hilo_sonido: threading.Thread | None = None
_parada_sonido = threading.Event()

# MCI reserva memoria por cada alias abierto. Si nunca los cerramos, se
# acumulan. El barrido cierra cada alias cuando MCI dice que ya no suena
# (`status <alias> mode`); el TTL es solo un tope de seguridad por si MCI no
# contesta, y es holgado para no cortar temas de usuario largos.
_TTL_ALIAS_SEG = 30.0


def _init_backend() -> None:
    global _backend_winmm, _winmm
    if _backend_winmm or sys.platform != "win32":
        return
    try:
        import ctypes
        _winmm = ctypes.WinDLL("winmm.dll")
        _winmm.mciSendStringW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p,
        ]
        _winmm.mciSendStringW.restype = ctypes.c_uint
        _backend_winmm = True
    except Exception as exc:
        logger.warning("sound_player: winmm.dll no disponible (%s). "
                       "Se usará winsound como fallback.", exc)


def _mci(cmd: str) -> int:
    assert _winmm is not None
    return int(_winmm.mciSendStringW(cmd, None, 0, None))


def _mci_consulta(cmd: str) -> str:
    """Comando MCI con respuesta (p. ej. `status x mode`). "" si falla."""
    assert _winmm is not None
    import ctypes
    buf = ctypes.create_unicode_buffer(128)
    rc = int(_winmm.mciSendStringW(cmd, buf, len(buf), None))
    return buf.value.strip() if rc == 0 else ""


def _alias_vencido(edad_seg: float, modo: str) -> bool:
    """¿Toca cerrar el alias? Cuando MCI ya no lo da como `playing` (terminó,
    o no contesta) o cuando supera el tope de seguridad."""
    return modo.lower() != "playing" or edad_seg >= _TTL_ALIAS_SEG


# ── API pública ───────────────────────────────────────────────────────────────

def cargar(config_sonidos: dict) -> None:
    """Configura el reproductor a partir del dict devuelto por config_loader."""
    global _eventos, _volumen, _activo
    _eventos = {k: v for k, v in config_sonidos.get("eventos", {}).items() if v}
    _volumen = max(0.0, min(1.0, float(config_sonidos.get("volumen", 0.7))))
    _activo  = bool(config_sonidos.get("activar", True))
    _vaciar_cola()
    if _activo and _eventos:
        _init_backend()
        if _backend_winmm:
            _iniciar_hilo_sonido()
    logger.info("sound_player: %d evento(s), activo=%s, vol=%.2f",
                len(_eventos), _activo, _volumen)


def silenciar_todo(silenciar: bool) -> None:
    global _silenciado_usuario
    _silenciado_usuario = bool(silenciar)


def esta_silenciado() -> bool:
    return _silenciado_usuario or not _activo


def reproducir(evento: str) -> None:
    """Nunca lanza: cualquier fallo se ignora en debug. Seguro desde cualquier hilo.

    Con backend winmm solo encola la ruta y vuelve: ni `resolve`, ni
    `exists`, ni MCI en el hilo que llama. El hilo de sonido comprueba que
    el archivo existe antes de reproducirlo.
    """
    if _silenciado_usuario or not _activo:
        return
    ruta = _eventos.get(evento)
    if not ruta:
        return
    if _backend_winmm:
        _iniciar_hilo_sonido()
        try:
            _cola_sonidos.put_nowait(ruta)
        except queue.Full:
            pass
    else:
        if not ruta.exists():
            return
        _reproducir_fallback(ruta)


def cerrar() -> None:
    _parada_sonido.set()
    if _hilo_sonido and _hilo_sonido.is_alive():
        _hilo_sonido.join(timeout=1.0)
    _vaciar_cola()
    if _backend_winmm:
        _cerrar_alias_abiertos()


# ── Backend MCI ───────────────────────────────────────────────────────────────

def _reproducir_winmm(ruta: Path) -> None:
    alias = f"{_alias_prefijo}{next(_alias_contador)}"
    ruta_abs = str(ruta.resolve())
    try:
        # Comillas alrededor de la ruta porque puede contener espacios o
        # acentos que MCI interpretaría como separadores de argumentos.
        rc = _mci(f'open "{ruta_abs}" type waveaudio alias {alias}')
        if rc != 0:
            return
        # MCI acepta volumen 0..1000.
        _mci(f"setaudio {alias} volume to {int(_volumen * 1000)}")
        if _mci(f"play {alias}") != 0:
            _mci(f"close {alias}")
            return
        with _alias_lock:
            _alias_activos[alias] = time.monotonic()
    except Exception:
        try:    _mci(f"close {alias}")
        except Exception: pass


def _iniciar_hilo_sonido() -> None:
    global _hilo_sonido
    if _hilo_sonido is not None and _hilo_sonido.is_alive():
        return
    _parada_sonido.clear()
    _hilo_sonido = diagnostico.crear_hilo(_bucle_sonido, "Sonidos")
    _hilo_sonido.start()


def _vaciar_cola() -> None:
    try:
        while True:
            _cola_sonidos.get_nowait()
    except queue.Empty:
        pass


def _bucle_sonido() -> None:
    while not _parada_sonido.is_set():
        try:
            ruta = _cola_sonidos.get(timeout=0.5)
        except queue.Empty:
            pass
        else:
            _reproducir_en_hilo(ruta)
        try:
            _barrer_alias()
        except Exception as exc:
            logger.debug("sonidos: %s", exc)
    # Los alias abiertos se cierran desde este mismo hilo antes de terminar.
    try:
        _cerrar_alias_abiertos()
    except Exception as exc:
        logger.debug("sonidos al cerrar: %s", exc)


def _reproducir_en_hilo(ruta: Path) -> None:
    """Reproduce una ruta encolada. La comprobación de que el archivo existe
    se hace acá, en el hilo de sonido, nunca en el hilo que llama."""
    try:
        if not ruta.exists():
            return
        _reproducir_winmm(ruta)
    except Exception as exc:
        logger.debug("sonidos: %s", exc)


def _cerrar_alias_abiertos() -> None:
    with _alias_lock:
        alias_abiertos = list(_alias_activos.keys())
        _alias_activos.clear()
    for a in alias_abiertos:
        try:
            _mci(f"close {a}")
        except Exception:
            pass


def _barrer_alias() -> None:
    """Cierra los alias que ya terminaron de sonar (o pasaron el tope)."""
    now = time.monotonic()
    with _alias_lock:
        candidatos = list(_alias_activos.items())
    cerrar_estos = []
    for alias, ts in candidatos:
        # Se pregunta a MCI fuera del candado: la consulta puede tardar.
        try:    modo = _mci_consulta(f"status {alias} mode")
        except Exception: modo = ""
        if _alias_vencido(now - ts, modo):
            cerrar_estos.append(alias)
    with _alias_lock:
        for a in cerrar_estos:
            _alias_activos.pop(a, None)
    for a in cerrar_estos:
        try:    _mci(f"close {a}")
        except Exception: pass


def _reproducir_fallback(ruta: Path) -> None:
    # Camino de último recurso: un sonido a la vez; un segundo evento
    # durante el primero lo cortará.
    try:
        import winsound
        winsound.PlaySound(
            str(ruta),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
    except Exception:
        pass
