"""Salida de anuncios al lector de pantalla por Prism.

Responde a la forma que ya usan `anunciar()`, el grabador de las pruebas y el
de la sonda: `speak(texto, interrupt=False)` y `braille(texto)`. Solo se
recorren lectores de pantalla reales: `create_best()` cae a OneCore o SAPI y
la app hablaría con una segunda voz.

Prism se importa de forma perezosa: si falta, el objeto queda inactivo y todas
sus llamadas son no-ops silenciosos, sin romper la aplicación.
"""

from __future__ import annotations

import time

from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

# Orden de preferencia. Nunca OneCore, SAPI ni UIA: son motores de voz que
# sonarían por encima del lector activo.
LECTORES = ("NVDA", "JAWS", "ZOOM_TEXT", "ZDSR", "PC_TALKER",
            "BOY_PC_READER", "SENSE_READER", "SYSTEM_ACCESS")

# Cada cuánto, como mucho, se vuelve a buscar lector cuando no hay ninguno.
REINTENTO_S = 5.0


def _preparar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.replace("\x00", "")
    if not texto.strip():
        return ""
    return texto


class Lector:

    def __init__(self, fabrica_contexto=None, reloj=time.monotonic):
        self._reloj = reloj
        self._backend = None
        self._nombre = None
        self._proximo_intento = 0.0
        self._prism = None
        self._ctx = None
        self._disponible = False
        self._iniciar(fabrica_contexto)

    def _iniciar(self, fabrica_contexto):
        try:
            import prism
        except Exception as exc:
            logger.warning("Prism no disponible; la aplicación queda sin "
                           "lector de pantalla: %s", exc)
            return
        self._prism = prism
        try:
            self._ctx = (fabrica_contexto() if fabrica_contexto is not None
                         else prism.Context())
        except Exception as exc:
            logger.warning("No se pudo crear el contexto de lectores: %s", exc)
            return
        self._disponible = True
        self._detectar()

    def _detectar(self):
        # JAWS y los demás lectores COM crean su objeto en el hilo que los
        # inicializa, por eso el Lector se crea y se usa en el hilo de la
        # interfaz.
        for nombre in LECTORES:
            try:
                backend = self._ctx.create(getattr(self._prism.BackendId, nombre))
            except self._prism.PrismError:
                continue
            except Exception as exc:
                logger.warning("Lector %s: %s", nombre, exc)
                continue
            if backend is not None:
                self._backend = backend
                self._nombre = getattr(backend, "name", None) or nombre
                return
        self._backend = None
        self._nombre = None
        self._proximo_intento = self._reloj() + REINTENTO_S

    def nombre(self):
        return self._nombre

    def speak(self, texto, interrupt=False):
        if not self._disponible:
            return
        texto = _preparar_texto(texto)
        if not texto:
            return
        if self._backend is None:
            # Si el usuario abrió el lector con la app abierta, el primer
            # anuncio pasados unos segundos ya suena. Antes, no-op.
            if self._reloj() < self._proximo_intento:
                return
            self._detectar()
            if self._backend is None:
                return
        try:
            self._backend.speak(texto, interrupt=interrupt)
        except self._prism.PrismError as exc:
            self._reintentar(exc, texto, interrupt)
        except Exception as exc:
            logger.warning("No se pudo anunciar con el lector: %s", exc)

    def _reintentar(self, exc, texto, interrupt):
        # El backend muerto no se reconecta solo: se descarta y se busca otro
        # en el acto, sin esperar los REINTENTO_S.
        logger.debug("El lector falló; se busca otro: %s", exc)
        self._backend = None
        self._nombre = None
        self._detectar()
        if self._backend is None:
            logger.warning("Se perdió el lector y no se encontró otro: %s", exc)
            return
        try:
            self._backend.speak(texto, interrupt=interrupt)
        except Exception as exc2:
            logger.warning("El lector volvió a fallar: %s", exc2)

    def braille(self, texto):
        if not self._disponible or self._backend is None:
            return
        texto = _preparar_texto(texto)
        if not texto:
            return
        # Sin braille, o con el lector caído, se ignora en silencio.
        try:
            self._backend.braille(texto)
        except Exception:
            pass
