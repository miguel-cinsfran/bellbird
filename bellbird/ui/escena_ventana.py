"""Ventana Escena: reúne en pestañas lo que se ve y se oye en OBS."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_lanzador
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.obs.restablecimiento import RegistroRestablecimiento
from bellbird.ui import gui_microfono, paleta
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.escena_pagina_agregar import PaginaAgregar
from bellbird.ui.escena_pagina_audio import PaginaAudio
from bellbird.ui.escena_pagina_escena import PaginaEscena
from bellbird.ui.escena_pagina_fuentes import PaginaFuentes
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui.preferencias_comun import boton, nombre_de_etiqueta

logger = diagnostico.obtener_logger(__name__)

TEXTO_AYUDA_ESCENA = N_(
    "Esta ventana reúne en pestañas lo que se ve y se oye en OBS.\n\n"
    "Escena elige cuál se edita, dice qué tiene y cambia cuál se emite. "
    "Recorrer la lista no cambia nada en el directo.\n\n"
    "Fuentes elige una fuente de la escena. La mueve, la cambia de tamaño, "
    "la oculta, la bloquea o cambia su capa. Mover con flechas la mueve "
    "en pasos pequeños: Ctrl da pasos grandes, Mayús pasos de un píxel, "
    "Intro confirma y Esc deshace. Deshacer cambios vuelve a como estaba "
    "todo al abrir esta ventana.\n\n"
    "Agregar captura una ventana del equipo o agrega una cámara de Windows "
    "a la escena actual.\n\n"
    "Audio silencia el micrófono de OBS y elige cuál se usa.")


class VentanaEscena(wx.Dialog):

    def __init__(self, parent, principal, gestor=None):
        super().__init__(parent, title=_("Escena"), size=(640, 540),
                         name="DialogoEscena")
        self._principal = principal
        self._propio = gestor is None
        self._gestor = gestor or GestorPanelObs()
        self._restablecimiento = RegistroRestablecimiento()
        self._asegurar = obs_lanzador.asegurar_obs
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo,
            self._tras_operacion)
        self._crear_controles()
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelEscena")
        caja = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(panel, name="PestanasEscena")
        self._pagina_escena = PaginaEscena(
            self.nb, self._gestor, self._operaciones, self._elegir_escena)
        self._pagina_fuentes = PaginaFuentes(
            self.nb, self, self._gestor, self._operaciones,
            self._restablecimiento, self._escena_elegida)
        self._pagina_agregar = PaginaAgregar(
            self.nb, self, self._gestor, self._operaciones,
            self._escena_elegida, self._recargar_escena)
        self._pagina_audio = PaginaAudio(
            self.nb, self._principal, self._gestor, self._operaciones)
        self.nb.AddPage(self._pagina_escena, _("Escena"))
        self.nb.AddPage(self._pagina_fuentes, _("Fuentes"))
        self.nb.AddPage(self._pagina_agregar, _("Agregar"))
        self.nb.AddPage(self._pagina_audio, _("Audio"))
        caja.Add(self.nb, 1, wx.EXPAND | wx.ALL, 10)
        self.btn_ayuda = boton(
            panel, _("A&yuda"), nombre_de_etiqueta(_("A&yuda")))
        self.btn_cerrar = boton(panel, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.btn_ayuda, 0, wx.RIGHT, 8)
        fila.AddStretchSpacer(1)
        fila.Add(self.btn_cerrar, 0)
        caja.Add(fila, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(caja)
        self._acciones = (
            *self._pagina_escena.acciones, *self._pagina_fuentes.acciones,
            *self._pagina_agregar.acciones, *self._pagina_audio.acciones,
            self.btn_ayuda, self.btn_cerrar)
        self._enlazar_eventos()
        self.SetMinSize((600, -1))
        self.Centre()
        paleta.pintar_ventana(self)

    def _enlazar_eventos(self):
        self.btn_ayuda.Bind(wx.EVT_BUTTON, self._ayuda)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    def _preferido(self):
        return gui_microfono.microfono_preferido(self._principal)

    def _cargar_inicial(self):
        self._asegurar(
            lambda: self._gestor.conectar(),
            al_anunciar=lambda frase: wx.CallAfter(anunciar, frase))
        if not self._gestor.conectado:
            self._gestor.conectar()
        escenas = self._gestor.escenas()
        al_aire = self._gestor.escena_al_aire()
        escena = al_aire if al_aire in escenas else (escenas[0] if escenas else "")
        leida = consultas_transmision.leer_escena(self._gestor, escena)
        estado = consultas_transmision.leer_estado(
            self._gestor, "", self._preferido())
        return escenas, escena, leida, estado

    def _inicial_cargada(self, datos):
        escenas, escena, leida, estado = datos
        self._pagina_escena.cargar(escenas, escena, leida.descripcion)
        self._pagina_fuentes.cargar(leida.fuentes, leida.fuente, leida.snap)
        self._pagina_agregar.cargar_ventanas(leida.opciones, leida.actual)
        self._pagina_audio.fijar(estado.silenciado)
        if leida.descripcion:
            anunciar(leida.descripcion)
        self._pagina_escena.cho_escena.SetFocus()

    def _escena_elegida(self):
        return self._pagina_escena.escena()

    def _elegir_escena(self, escena):
        if self._operaciones.en_vuelo:
            return
        self._en_hilo(
            lambda: consultas_transmision.leer_escena(self._gestor, escena),
            self._escena_leida)

    def _escena_leida(self, leida):
        self._pagina_escena.mostrar_descripcion(leida.descripcion)
        self._pagina_fuentes.cargar(leida.fuentes, leida.fuente, leida.snap)
        self._pagina_agregar.cargar_ventanas(leida.opciones, leida.actual)
        if leida.fuentes:
            self._pagina_fuentes.anunciar_snap(leida.snap)

    def _recargar_escena(self):
        if self._operaciones.en_vuelo:
            return
        self._elegir_escena(self._escena_elegida())

    def _activar(self, activo):
        for control in self._acciones:
            control.Enable(activo)

    def _tras_operacion(self, resultado):
        if isinstance(resultado, obs_disposicion.SnapshotPanel):
            self._pagina_fuentes.mostrar_snap(resultado)

    def _escribir_fallo(self, mensaje):
        self._pagina_escena.mostrar_fallo(mensaje)

    def _enfocar_tras_fallo(self):
        self.btn_cerrar.SetFocus()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _ayuda(self, event):
        wx.MessageBox(_(TEXTO_AYUDA_ESCENA), _("Ayuda de Escena"),
                      wx.OK | wx.ICON_INFORMATION, self)

    def _al_tecla(self, evento):
        if evento.GetKeyCode() == wx.WXK_ESCAPE:
            if self._pagina_fuentes.en_ajuste:
                evento.Skip()
                return
            self._cerrar(evento)
            return
        evento.Skip()

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._operaciones.cerrar()
        if self._propio:
            diagnostico.crear_hilo(
                self._cerrar_gestor, "CerrarEscenaOBS").start()
        self.EndModal(wx.ID_CANCEL)

    def _cerrar_gestor(self):
        try:
            self._gestor.cerrar()
        except Exception as error:
            logger.debug("no se pudo cerrar el gestor de OBS: %s", error)


def abrir_escena(padre, principal, gestor=None):
    dialogo = VentanaEscena(padre, principal, gestor)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
