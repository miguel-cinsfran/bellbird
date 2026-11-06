"""Cambiar nombre, duplicar y eliminar una fuente de la pestaña Escena."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import consultas_transmision, fuentes_obs
from guyrapu.obs.obs_panel import NOMBRE_FUENTE
from guyrapu.ui import preferencias_camara
from guyrapu.ui.accesibilidad import anunciar


class AccionesEdicion:
    """Las acciones que cambian la vida de la fuente, no su forma."""

    def __init__(self, pagina, pila):
        self._pagina = pagina
        self._gestor = pagina._gestor
        self._operaciones = pagina._operaciones
        self._pila = pila

    def renombrar(self):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        if self._operaciones.en_vuelo:
            return
        if fuente == NOMBRE_FUENTE:
            anunciar(_("Chat en el vídeo no se puede cambiar de nombre: "
                       "Guyrapu lo reconoce por él."))
            return
        nuevo = self._pedir_nombre_libre(fuente)
        if nuevo is None:
            return
        self._operaciones.en_hilo(
            lambda: self._renombrar_en_hilo(escena, fuente, nuevo),
            lambda filas: self._renombrado(filas, fuente, nuevo))

    def _pedir_nombre_libre(self, actual):
        while True:
            nuevo = self._pedir_nombre(actual)
            self._enfocar()
            if nuevo is None:
                return None
            nuevo = nuevo.strip()
            if not nuevo or nuevo == actual:
                return None
            if self._nombre_ocupado(nuevo):
                anunciar(_("Ya hay una fuente con ese nombre."))
                continue
            return nuevo

    def _pedir_nombre(self, actual):
        with wx.TextEntryDialog(
                self._pagina, _("Nombre nuevo:"), _("Cambiar nombre"),
                actual) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.GetValue()

    def _nombre_ocupado(self, nombre):
        buscado = nombre.casefold()
        return any(
            fila.nombre.casefold() == buscado
            for fila in self._pagina._filas)

    def _renombrar_en_hilo(self, escena, fuente, nuevo):
        fuentes_obs.renombrar(self._gestor, escena, fuente, nuevo)
        return consultas_transmision.leer_filas(self._gestor, escena)

    def _renombrado(self, filas, antes, nuevo):
        self._pila.cambiar_nombre(antes, nuevo)
        preferencias_camara.recordar_cambio_de_nombre(
            self._principal(), antes, nuevo)
        self._pagina.cargar(filas, nuevo)
        self._enfocar()
        anunciar(_("{antes} cambiada a {nombre}. El nombre cambia en todas "
                   "las escenas que la usan.").format(
                       antes=antes, nombre=nuevo))

    def duplicar(self):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        if self._operaciones.en_vuelo:
            return
        fila = self._fila()
        motivo = fuentes_obs.motivo_para_no_duplicar(
            fuente, fila.tipo if fila is not None else "")
        if motivo:
            anunciar(motivo)
            return
        self._operaciones.en_hilo(
            lambda: self._duplicar_en_hilo(escena, fuente, fila),
            lambda datos: self._duplicado(datos, fuente))

    def _duplicar_en_hilo(self, escena, fuente, fila):
        nombre = fuentes_obs.duplicar(
            self._gestor, escena, fuente,
            tipo=fila.tipo if fila is not None else "")
        return nombre, consultas_transmision.leer_filas(
            self._gestor, escena)

    def _duplicado(self, datos, fuente):
        nombre, filas = datos
        self._pagina.cargar(filas, nombre)
        self._enfocar()
        anunciar(_("{fuente} duplicada como {copia}.").format(
            fuente=fuente, copia=nombre))

    def eliminar(self):
        escena, fuente = self._destino()
        if not fuente:
            self._sin_seleccion()
            return
        if self._operaciones.en_vuelo:
            return
        siguiente = self._fuente_siguiente()
        if not self._confirmar_eliminar(fuente):
            self._enfocar()
            return
        self._operaciones.en_hilo(
            lambda: self._eliminar_en_hilo(escena, fuente),
            lambda filas: self._eliminado(filas, escena, fuente, siguiente))

    def _fuente_siguiente(self):
        indice = self._pagina.lst_fuentes.GetSelection()
        filas = self._pagina._filas
        if 0 <= indice + 1 < len(filas):
            return filas[indice + 1].nombre
        if 0 <= indice - 1 < len(filas):
            return filas[indice - 1].nombre
        return ""

    def _confirmar_eliminar(self, fuente):
        dialogo = wx.MessageDialog(
            self._pagina,
            _("¿Eliminar {fuente} de esta escena?").format(fuente=fuente),
            _("Eliminar fuente"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        try:
            dialogo.SetYesNoLabels(_("&Eliminar"), _("&Cancelar"))
            return dialogo.ShowModal() == wx.ID_YES
        finally:
            dialogo.Destroy()

    def _eliminar_en_hilo(self, escena, fuente):
        fuentes_obs.eliminar(self._gestor, escena, fuente)
        return consultas_transmision.leer_filas(self._gestor, escena)

    def _eliminado(self, filas, escena, fuente, siguiente):
        self._pila.olvidar(escena, fuente)
        self._pagina.cargar(filas, siguiente)
        self._enfocar()
        anunciar(_("{fuente} eliminada de la escena.").format(fuente=fuente))

    def _destino(self):
        return self._pagina._destino()

    def _fila(self):
        return self._pagina._fila()

    def _principal(self):
        return getattr(self._pagina._ventana, "_principal", None)

    def _enfocar(self):
        self._pagina.lst_fuentes.SetFocus()

    def _sin_seleccion(self):
        anunciar(_("Sin selección"))
