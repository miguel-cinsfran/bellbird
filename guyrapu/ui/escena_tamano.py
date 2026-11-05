"""Cuadro Posición y tamaño de la fuente del Panel de OBS.

No habla con OBS: devuelve los porcentajes y el lugar elegidos, y la
pestaña Escena los convierte a píxeles antes de aplicarlos.
"""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import obs_disposicion, tamano_relativo
from guyrapu.ui import paleta
from guyrapu.ui.accesibilidad import ContadorAccesible
from guyrapu.ui.preferencias_comun import (
    fila_campo, lista_con_nombre, mostrar_control, nombre_de_etiqueta)


class TamanoFuenteDialog(wx.Dialog):
    """Pide el tamaño y el lugar de una fuente, con el foco en Tamaño."""

    def __init__(self, padre, porcentaje_ancho, porcentaje_alto):
        super().__init__(padre, title=_("Posición y tamaño de la fuente"),
                         name="DialogoTamanoFuente")
        self._elegido = None
        self._anclaje = ""
        self._crear_controles(porcentaje_ancho, porcentaje_alto)
        paleta.pintar_ventana(self)
        self.Centre()
        self.cho_tamano.SetFocus()

    def _crear_controles(self, porcentaje_ancho, porcentaje_alto):
        vertical = wx.BoxSizer(wx.VERTICAL)
        self._crear_campos(vertical, porcentaje_ancho, porcentaje_alto)
        self._crear_botones(vertical)
        self.SetSizerAndFit(vertical)
        self._elegir_comun(porcentaje_ancho)
        self._actualizar_visibilidad()
        self._enlazar_eventos()

    def _crear_campos(self, vertical, porcentaje_ancho, porcentaje_alto):
        self._crear_posicion(vertical)
        self._crear_tamano(vertical)
        self._crear_ancho(vertical, porcentaje_ancho)
        self._crear_proporcion(vertical)
        self._crear_alto(vertical, porcentaje_ancho, porcentaje_alto)

    def _crear_posicion(self, vertical):
        self.rotulo_posicion = wx.StaticText(self, label=_("&Posición:"))
        self.cho_posicion = lista_con_nombre(
            self, _("&Posición:"),
            [_("Donde está ahora")]
            + [_(obs_disposicion.etiqueta_anclaje(nombre))
               for nombre in obs_disposicion.ANCLAJES])
        self.cho_posicion.SetSelection(0)
        fila_campo(vertical, self.rotulo_posicion, self.cho_posicion)

    def _crear_tamano(self, vertical):
        opciones = [_(nombre) for _clave, nombre, _fraccion
                    in tamano_relativo.COMUNES]
        opciones.append(_("Personalizado"))
        self.rotulo_tamano = wx.StaticText(self, label=_("&Tamaño:"))
        self.cho_tamano = lista_con_nombre(self, _("&Tamaño:"), opciones)
        fila_campo(vertical, self.rotulo_tamano, self.cho_tamano)

    def _crear_ancho(self, vertical, porcentaje_ancho):
        self.rotulo_ancho = wx.StaticText(self, label=_("A&ncho:"))
        self.sp_ancho = ContadorAccesible(
            self, min=5, max=100, initial=self._en_rango(porcentaje_ancho),
            name=_("Ancho en porcentaje del vídeo"))
        self._fila_ancho = fila_campo(
            vertical, self.rotulo_ancho, self.sp_ancho)

    def _crear_proporcion(self, vertical):
        self.chk_proporcion = wx.CheckBox(
            self, label=_("&Mantener proporción"),
            name=nombre_de_etiqueta(_("&Mantener proporción")))
        self.chk_proporcion.SetValue(True)
        vertical.Add(self.chk_proporcion, 0, wx.ALL, 6)

    def _crear_alto(self, vertical, porcentaje_ancho, porcentaje_alto):
        self.rotulo_alto = wx.StaticText(self, label=_("A&lto:"))
        self.sp_alto = ContadorAccesible(
            self, min=5, max=100,
            initial=self._en_rango(porcentaje_alto
                                   if porcentaje_alto is not None
                                   else porcentaje_ancho),
            name=_("Alto en porcentaje del vídeo"))
        self._fila_alto = fila_campo(vertical, self.rotulo_alto, self.sp_alto)

    def _crear_botones(self, vertical):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aceptar = wx.Button(self, wx.ID_OK, _("&Aceptar"))
        self.btn_aceptar.SetDefault()
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
        fila.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        fila.Add(self.btn_cancelar, 0)
        vertical.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_aceptar.Bind(wx.EVT_BUTTON, self._al_aceptar)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._al_cancelar)
        self.cho_tamano.Bind(wx.EVT_CHOICE, self._al_cambiar_tamano)
        self.chk_proporcion.Bind(wx.EVT_CHECKBOX,
                                 self._al_cambiar_proporcion)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)

    @staticmethod
    def _en_rango(porcentaje):
        return max(5, min(100, int(round(porcentaje))))

    def _elegir_comun(self, porcentaje_ancho):
        comun = tamano_relativo.comun_de(porcentaje_ancho)
        if comun is None:
            self.cho_tamano.SetStringSelection(_("Personalizado"))
            return
        for clave, nombre, _fraccion in tamano_relativo.COMUNES:
            if clave == comun:
                self.cho_tamano.SetStringSelection(_(nombre))
                return

    def _al_cambiar_tamano(self, _event):
        indice = self.cho_tamano.GetSelection()
        if 0 <= indice < len(tamano_relativo.COMUNES):
            fraccion = tamano_relativo.COMUNES[indice][2]
            self.sp_ancho.SetValue(int(round(fraccion * 100)))
        self._actualizar_visibilidad()

    def _al_cambiar_proporcion(self, _event):
        self._actualizar_visibilidad()

    def _actualizar_visibilidad(self):
        personalizado = (
            self.cho_tamano.GetStringSelection() == _("Personalizado"))
        self._mostrar_fila(self._fila_ancho, self.rotulo_ancho,
                           self.sp_ancho, personalizado)
        self._mostrar_fila(self._fila_alto, self.rotulo_alto, self.sp_alto,
                           not self.chk_proporcion.GetValue())
        self.Layout()
        self.Fit()

    def _mostrar_fila(self, fila, rotulo, control, visible):
        mostrar_control(rotulo, visible, self.chk_proporcion)
        mostrar_control(control, visible, self.chk_proporcion)
        fila.Show(rotulo, visible)
        fila.Show(control, visible)

    def tamano_elegido(self):
        return self._elegido

    def anclaje_elegido(self):
        return self._anclaje

    def _al_aceptar(self, _event):
        self._elegido = (self._porcentaje_ancho(), self._porcentaje_alto())
        self._anclaje = self._lugar_elegido()
        self.EndModal(wx.ID_OK)

    def _porcentaje_ancho(self):
        indice = self.cho_tamano.GetSelection()
        if 0 <= indice < len(tamano_relativo.COMUNES):
            return int(round(tamano_relativo.COMUNES[indice][2] * 100))
        return self.sp_ancho.GetValue()

    def _porcentaje_alto(self):
        return (None if self.chk_proporcion.GetValue()
                else self.sp_alto.GetValue())

    def _lugar_elegido(self):
        lugar = self.cho_posicion.GetSelection()
        return tuple(obs_disposicion.ANCLAJES)[lugar - 1] if lugar > 0 else ""

    def _al_cancelar(self, _event):
        self.EndModal(wx.ID_CANCEL)

    def _al_tecla(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


def pedir_tamano(padre, porcentaje_ancho, porcentaje_alto):
    """Abre el cuadro y devuelve porcentajes y lugar, o None si se cancela."""
    dialogo = TamanoFuenteDialog(padre, porcentaje_ancho, porcentaje_alto)
    try:
        if dialogo.ShowModal() == wx.ID_OK:
            return (*dialogo.tamano_elegido(), dialogo.anclaje_elegido())
        return None
    finally:
        dialogo.Destroy()
