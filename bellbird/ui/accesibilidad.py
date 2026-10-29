"""Lector de pantalla (Prism, opcional)
Si Prism no está instalado o no hay un lector de pantalla activo, los
`anunciar()` son no-ops silenciosos; la app funciona igual.

Nombre accesible reforzado (MSAA)
Patrón tomado de eleven-tts-studio: en Windows, `SetName` por sí solo no
siempre lo anuncian NVDA/JAWS de forma fiable (sobre todo en deslizadores y en
ventanas genéricas como la superficie de vídeo). Reforzamos con un
`wx.Accessible` explícito que expone el nombre por MSAA. Solo se usa en los
controles donde el nombre flojea; los estándar (botones, casillas) ya se leen
bien con `name=` y no hace falta.
"""

from __future__ import annotations

import logging

import wx

from bellbird.core import diagnostico


logger = diagnostico.obtener_logger(__name__)

_lector = None


def _lector_init():
    global _lector
    try:
        from bellbird.voice.lector import Lector
        _lector = Lector()
        logger.info("Lector de pantalla: %s", _lector.nombre() or "ninguno")
    except Exception as exc:
        logger.warning("La aplicación se quedó sin salida para lector de pantalla: %s", exc)


def anunciar(texto: str, urgente: bool = True) -> None:
    if _lector is None:
        logger.info("ANUNCIO sin lector %s", texto)
        return
    if not wx.IsMainThread():
        # Prism habla por COM (JAWS) y no es seguro desde otros hilos; el
        # vigilante de OBS y las descargas anuncian desde los suyos, así que se
        # reenvía al hilo de la interfaz, que es donde se crea y se usa el
        # lector porque JAWS crea su COM ahí.
        try:
            wx.CallAfter(anunciar, texto, urgente)
        except Exception as exc:
            logger.debug("No se pudo pasar el anuncio al hilo de la interfaz: %s", exc)
        return
    logger.info("ANUNCIO %s", texto)
    try:
        # Casi todos responden a una tecla y deben llegar antes del próximo foco.
        _lector.speak(texto, interrupt=urgente)
    except Exception as exc:
        logger.warning("No se pudo anunciar con voz: %s", exc)
    # También a la línea braille, como hace TWBlue (output.speak): quien usa
    # pantalla braille sin voz recibe igualmente los anuncios de la app.
    try:
        _lector.braille(texto)
    except Exception as exc:
        logger.debug("No se pudo enviar el anuncio a la línea braille: %s", exc)


class _NombreAccesible(wx.Accessible):
    """Expone el nombre del control por MSAA. Solo nombra el control en sí
    (childId 0); las filas/hijos (p. ej. cada línea de una lista) las deja al
    proveedor por defecto, o todas se anunciarían con el nombre de la lista."""

    def __init__(self, nombre: str):
        super().__init__()
        self._nombre = nombre

    def GetName(self, childId):
        if childId == 0:
            return (wx.ACC_OK, self._nombre)
        return (wx.ACC_NOT_IMPLEMENTED, "")


def nombre_accesible(ctrl, nombre: str, msaa: bool = True) -> None:
    """Refuerza el nombre accesible de un control. Mantiene los tooltips ricos
    que ya tengamos (solo pone uno si falta) y no altera el rol ni el valor: el
    `wx.Accessible` solo sobrescribe el nombre y delega el resto.

    `msaa=False` se salta el `wx.Accessible` (deja SetName/tooltip/HelpText
    igual). Úsalo en listas de CONTENIDO DINÁMICO (chat, comentarios): al
    instalar un `wx.Accessible` en Python, TODAS las consultas MSAA de NVDA
    sobre ese control (también las de cada fila al navegar con flechas) pasan
    por el proxy de wx y el hilo de GUI. Con la lista recibiendo Append/Delete
    constantes por los mensajes que llegan, esas consultas se quedan esperando
    y la navegación se traba a trompicones. Las listas estáticas (voces,
    historial…) no sufren esto y siguen con el refuerzo."""
    ctrl.SetName(nombre)
    if not ctrl.GetToolTip():
        ctrl.SetToolTip(nombre)
    try:
        ctrl.SetHelpText(nombre)   # JAWS lee el help text en algunos controles
    except Exception as exc:
        logger.debug("El control no admite texto de ayuda: %s", exc)
    if not msaa:
        return
    try:
        acc = _NombreAccesible(nombre)
        ctrl.SetAccessible(acc)
        ctrl._nombre_accesible = acc   # evita que el GC se lo lleve
    except Exception as exc:  # fuera de Windows o sin MSAA: el name/tooltip siguen aplicando
        logger.debug("Sin MSAA para el nombre accesible: %s", exc)


class ContadorAccesible(wx.SpinCtrl):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Bind(wx.EVT_SET_FOCUS, self._on_focus)

    def _on_focus(self, event):
        # Selecciona el valor para reemplazarlo sin borrarlo antes.
        self.SetSelection(0, len(self.GetTextValue()))
        event.Skip()


class WxAnnouncingHandler(logging.Handler):
    """Reenvía los mensajes del logger al lector de pantalla."""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        if not registro_es_anunciable(record.name):
            return
        try:
            anunciar(self.format(record))
        except Exception as exc:
            logger.debug("No se pudo anunciar un registro: %s", exc)


# Lista blanca: solo estos loggers llegan al lector. Lo no listado se registra
# pero no se habla, para que un logger.info nuevo no se convierta en voz por descuido.
_LOGGERS_ANUNCIABLES = frozenset({
    "bellbird.obs_vigilante",  # avisa cuando OBS vuelve a responder
})


def registro_es_anunciable(nombre_logger: str | None) -> bool:
    """Decide si un registro del log debe llegar al lector de pantalla."""
    # Lista blanca: solo lo explicitamente permitido se habla; lo desconocido se calla.
    return bool(nombre_logger) and nombre_logger in _LOGGERS_ANUNCIABLES
