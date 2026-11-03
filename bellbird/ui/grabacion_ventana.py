"""Ventana Grabación: grabar en OBS sin pasar por el panel de transmisión."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import consultas_transmision
from bellbird.obs import obs_lanzador
from bellbird.obs.estado_grabacion import resumir
from bellbird.obs.estado_panel import EstadoPanel
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.ui import gui_microfono, gui_transmitir, paleta
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.control_grabacion import ControlGrabacion
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui.preferencias_comun import (
    CampoEstado, boton, fila_horizontal)

logger = diagnostico.obtener_logger(__name__)


class VentanaGrabacion(wx.Dialog):

    def __init__(self, parent, principal, gestor=None):
        super().__init__(parent, title=_("Grabación"),
                         name="DialogoGrabacion")
        self._principal = principal
        self._propio = gestor is None
        self._gestor = gestor or GestorPanelObs()
        self._asegurar = obs_lanzador.asegurar_obs
        self._estado_actual = EstadoPanel("", "listo", ())
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo)
        self._crear_controles()
        self._enlazar_eventos()
        self.SetDefaultItem(None)
        self.Centre()
        paleta.pintar_ventana(self)
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelGrabacion")
        caja = wx.BoxSizer(wx.VERTICAL)
        rotulo = wx.StaticText(panel, label=_("&Estado:"))
        self.txt_estado = CampoEstado(panel, _("Estado"))
        caja.Add(rotulo, 0, wx.ALL, 6)
        caja.Add(self.txt_estado, 0, wx.EXPAND | wx.LEFT | wx.RIGHT
                 | wx.BOTTOM, 6)
        self._grabacion = ControlGrabacion(
            panel, self._operaciones, self._gestor, self._refrescar_estado,
            self)
        self.btn_grabar = self._grabacion.boton
        self.btn_pausar = self._grabacion.pausar
        self.btn_grabaciones = self._grabacion.grabaciones
        caja.Add(fila_horizontal((self.btn_grabar, self.btn_pausar,
                                  self.btn_grabaciones)), 0, wx.ALL, 6)
        self.chk_grabar = wx.CheckBox(
            panel, label=_("Grabar ta&mbién al transmitir"),
            name=_("Grabar también al transmitir"))
        self.chk_grabar.SetValue(
            bool(self._principal._config.get("grabar_al_transmitir", False)))
        caja.Add(self.chk_grabar, 0, wx.ALL, 10)
        self.btn_escena = boton(panel, _("Esce&na…"), _("Escena…"))
        self.btn_actualizar = boton(
            panel, _("Ac&tualizar estado"), _("Actualizar estado"))
        self.btn_cerrar = boton(
            panel, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        caja.Add(fila_horizontal((self.btn_escena, self.btn_actualizar,
                                  self.btn_cerrar)), 0, wx.ALL, 10)
        panel.SetSizer(caja)
        self._acciones = (
            self.btn_grabar, self.btn_pausar, self.btn_grabaciones,
            self.chk_grabar, self.btn_escena, self.btn_actualizar,
            self.btn_cerrar)
        self.SetMinSize((500, -1))

    def _enlazar_eventos(self):
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)
        self.btn_escena.Bind(wx.EVT_BUTTON, self._abrir_escena)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.chk_grabar.Bind(wx.EVT_CHECKBOX, self._alternar_casilla)
        self.Bind(wx.EVT_CLOSE, self._cerrar)

    def _activar(self, activo):
        for control in self._acciones:
            control.Enable(activo)

    def _microfono_preferido(self):
        try:
            return gui_microfono.microfono_preferido(self._principal)
        except Exception:
            return ""

    def _cargar_inicial(self):
        self._asegurar(
            lambda: self._gestor.conectar(),
            al_anunciar=lambda frase: wx.CallAfter(anunciar, frase))
        if not self._gestor.conectado:
            self._gestor.conectar()
        return consultas_transmision.leer_estado(
            self._gestor, "", self._microfono_preferido())

    def _inicial_cargada(self, datos):
        self._aplicar_datos(datos)
        anunciar(self._estado_actual.titular)
        self._grabacion.boton.SetFocus()

    def _mostrar_estado(self, estado):
        self._estado_actual = estado
        self.txt_estado.mostrar(estado)

    def _escribir_fallo(self, mensaje):
        self._mostrar_estado(EstadoPanel(mensaje, "aviso", ()))

    def _enfocar_tras_fallo(self):
        self.btn_actualizar.Enable(True)
        self.btn_actualizar.SetFocus()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _refrescar_estado(self, anunciar_cuadro=False):
        preferido = self._microfono_preferido()
        self._en_hilo(
            lambda: consultas_transmision.leer_estado(
                self._gestor, "", preferido),
            lambda datos: self._estado_leido(datos, anunciar_cuadro))

    def _estado_leido(self, datos, anunciar_cuadro=False):
        self._aplicar_datos(datos)
        if anunciar_cuadro:
            anunciar(self.txt_estado.GetValue())

    def _actualizar(self, event):
        self._refrescar_estado(anunciar_cuadro=True)

    def _aplicar_datos(self, datos):
        self._grabacion.fijar(
            bool(datos.grabacion.get("outputActive", False)),
            bool(datos.grabacion.get("outputPaused", False)))
        self._mostrar_estado(resumir(
            datos.grabacion, datos.transmision, datos.escena,
            datos.microfono, datos.silenciado))

    def _alternar_casilla(self, event):
        gui_transmitir.alternar_grabar_al_transmitir(self._principal)
        event.Skip()

    def _abrir_escena(self, event):
        from bellbird.ui import escena_ventana
        escena_ventana.abrir_escena(
            self, self._principal, gestor=self._gestor)
        self._refrescar_estado()

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._operaciones.cerrar()
        if self._propio:
            diagnostico.crear_hilo(
                self._cerrar_gestor, "CerrarGrabacionOBS").start()
        self.EndModal(wx.ID_CANCEL)

    def _cerrar_gestor(self):
        try:
            self._gestor.cerrar()
        except Exception as error:
            logger.debug("no se pudo cerrar el gestor de OBS: %s", error)


def abrir_grabacion(padre, principal, gestor=None):
    dialogo = VentanaGrabacion(padre, principal, gestor)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
