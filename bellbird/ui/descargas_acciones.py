"""Lo que el usuario pide sobre una fila de descargas.

Razón del módulo: ejecutar la acción elegida en el menú o con el teclado.
Recibe la fila y sus dependencias por parámetro, sin leer la página.
"""

from __future__ import annotations

import os
import subprocess

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.downloads import filas_descargas
from bellbird.downloads.filas_descargas import (
    ACTIVAS, FINALES, clave_de_entrada)
from bellbird.downloads import historial_descargas
from bellbird.ui.gui import anunciar, copiar_al_portapapeles
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


class AccionesDescarga:
    """Ejecuta cada acción del menú sobre la fila dada."""

    def __init__(self, gestor, ruta, preparar_opciones, al_cambiar):
        self._gestor = gestor
        self._ruta = ruta
        self._preparar_opciones = preparar_opciones
        self._al_cambiar = al_cambiar

    def _falta(self, texto: str) -> None:
        try:
            _snd.reproducir("error")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(texto)

    def abrir_archivo(self, fila) -> None:
        if fila is None or "abrir_archivo" not in filas_descargas.acciones(fila):
            return
        try:
            if not fila.ruta or not os.path.exists(fila.ruta):
                raise OSError("falta")
            os.startfile(fila.ruta)
        except Exception as error:
            logger.debug("abrir archivo: %s", error)
            self._falta(_("El archivo ya no está disponible."))

    def abrir_carpeta(self, fila) -> None:
        if fila is None or "abrir_carpeta" not in filas_descargas.acciones(fila):
            return
        try:
            if fila.ruta and os.path.exists(fila.ruta):
                subprocess.Popen(["explorer", "/select,", fila.ruta])
                return
            if fila.carpeta and os.path.exists(fila.carpeta):
                os.startfile(fila.carpeta)
                return
        except Exception as error:
            logger.debug("abrir carpeta: %s", error)
        self._falta(_("La carpeta ya no está disponible."))

    def cancelar(self, fila) -> None:
        if fila is None:
            self._falta(_("Selecciona una descarga."))
            return
        item = self._gestor.obtener(fila.clave)
        if item is None or item.estado in FINALES:
            self._falta(_("La descarga ya terminó"))
            return
        self._gestor.cancelar(item.id)
        anunciar(_("Cancelando descarga"))

    def reintentar(self, fila) -> None:
        if fila is None or "reintentar" not in filas_descargas.acciones(fila):
            return
        self._preparar_opciones()
        url = filas_descargas.url_utilizable(fila.url)
        self._gestor.encolar(url, lambda *_a: None, lambda *_a: None)
        self._gestor.olvidar(fila.clave)
        self._quitar(fila.clave)
        anunciar(_("Agregado a la cola"))

    def volver_a_descargar(self, fila) -> None:
        if fila is None or "volver_a_descargar" not in filas_descargas.acciones(fila):
            return
        self._preparar_opciones()
        url = filas_descargas.url_utilizable(fila.url)
        self._gestor.encolar(url, lambda *_a: None, lambda *_a: None)
        anunciar(_("Agregado a la cola"))

    def copiar(self, fila) -> None:
        if fila is None or "copiar" not in filas_descargas.acciones(fila):
            return
        copiar_al_portapapeles(filas_descargas.url_utilizable(fila.url))
        try:
            _snd.reproducir("copiar")
        except Exception as error:
            logger.debug("sin sonido: %s", error)
        anunciar(_("Enlace copiado"))

    def eliminar(self, fila) -> None:
        if fila is None:
            return
        if fila.estado in ACTIVAS:
            self._falta(_("Cancela la descarga antes de eliminarla."))
            return
        self._gestor.olvidar(fila.clave)
        self._quitar(fila.clave)
        anunciar(_("Eliminada de la lista"))

    def cancelar_todas(self) -> None:
        activas = [i for i in self._gestor.lista() if i.estado in ACTIVAS]
        if not activas:
            self._falta(_("No hay descargas en curso"))
            return
        for item in activas:
            self._gestor.cancelar(item.id)
        if len(activas) == 1:
            anunciar(_("Cancelando 1 descarga"))
        else:
            anunciar(_("Cancelando {cantidad} descargas").format(cantidad=len(activas)))

    def eliminar_completadas(self) -> None:
        historial = historial_descargas.cargar(self._ruta)
        hechas = [e for e in historial if e.get("estado") == "completado"]
        if not hechas:
            self._falta(_("No hay descargas completadas"))
            return
        self._quitar_muchas({clave_de_entrada(e) for e in hechas})
        if len(hechas) == 1:
            anunciar(_("1 descarga eliminada de la lista"))
        else:
            anunciar(_("{cantidad} descargas eliminadas de la lista").format(
                cantidad=len(hechas)))

    def vaciar(self, padre) -> None:
        historial = historial_descargas.cargar(self._ruta)
        terminadas = [e for e in historial if e.get("estado") in FINALES]
        if not terminadas:
            self._falta(_("No hay descargas terminadas"))
            return
        mensaje = _("Elimina de la lista las descargas terminadas. "
                    "No borra ningún archivo del disco. ¿Deseas continuar?")
        if wx.MessageBox(mensaje, _("Vaciar lista"),
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, padre) != wx.YES:
            return
        resto = [e for e in historial if e.get("estado") not in FINALES]
        for entrada in terminadas:
            self._gestor.olvidar(clave_de_entrada(entrada))
        historial_descargas.guardar(self._ruta, resto)
        self._al_cambiar()
        if len(terminadas) == 1:
            anunciar(_("1 descarga eliminada de la lista"))
        else:
            anunciar(_("{cantidad} descargas eliminadas de la lista").format(
                cantidad=len(terminadas)))

    def _quitar(self, clave: str) -> None:
        historial = historial_descargas.cargar(self._ruta)
        resto = [e for e in historial if clave_de_entrada(e) != clave]
        historial_descargas.guardar(self._ruta, resto)
        self._al_cambiar()

    def _quitar_muchas(self, claves: set) -> None:
        historial = historial_descargas.cargar(self._ruta)
        resto = [e for e in historial if clave_de_entrada(e) not in claves]
        for clave in claves:
            self._gestor.olvidar(clave)
        historial_descargas.guardar(self._ruta, resto)
        self._al_cambiar()
