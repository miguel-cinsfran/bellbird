"""Pestaña Audio de la ventana Escena: silenciar, elegir y probar el micrófono."""

from __future__ import annotations

import wx

from bellbird.core.idioma import _
from bellbird.obs import nivel_microfono, obs_entradas_audio, prueba_microfono
from bellbird.ui import gui_microfono
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.preferencias_comun import boton, nombre_de_etiqueta
from bellbird.voice import sound_player


class PaginaAudio(wx.Panel):

    def __init__(self, parent, principal, gestor, operaciones):
        super().__init__(parent, name="PaginaAudio")
        self._principal = principal
        self._gestor = gestor
        self._operaciones = operaciones
        self._prueba = None
        self._viva = True
        self._crear_controles()
        self._silencio = gui_microfono.ControlSilencio(
            gestor, self.chk_silenciar, operaciones,
            lambda: gui_microfono.microfono_preferido(principal),
            lambda: None)
        self._enlazar_eventos()

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self.chk_silenciar = self._crear_casilla()
        self.btn_microfono = boton(
            self, _("Elegir &micrófono…"),
            nombre_de_etiqueta(_("Elegir &micrófono…")))
        self.btn_probar = boton(
            self, _("&Probar micrófono"),
            nombre_de_etiqueta(_("&Probar micrófono")))
        caja.Add(self._crear_fila(), 0, wx.ALL, 8)
        self.SetSizer(caja)
        self.acciones = (
            self.chk_silenciar, self.btn_microfono, self.btn_probar)

    def _crear_casilla(self):
        etiqueta = _("Si&lenciar micrófono")
        return wx.CheckBox(
            self, label=etiqueta, name=nombre_de_etiqueta(etiqueta))

    def _crear_fila(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.chk_silenciar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        fila.Add(self.btn_microfono, 0, wx.ALL, 6)
        fila.Add(self.btn_probar, 0, wx.ALL, 6)
        return fila

    def _enlazar_eventos(self):
        self.btn_microfono.Bind(
            wx.EVT_BUTTON,
            lambda evento: gui_microfono.abrir_microfono_obs(
                self._principal, al_cerrar=self.btn_microfono.SetFocus))
        self.btn_probar.Bind(wx.EVT_BUTTON, self._al_probar)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

    def fijar(self, silenciado):
        self._silencio.fijar(silenciado)

    def _al_probar(self, evento=None):
        if self._prueba is not None:
            self._prueba.detener()
            return
        preferido = gui_microfono.microfono_preferido(self._principal)
        self._operaciones.en_hilo(
            lambda: prueba_microfono.preparar(self._gestor, preferido),
            self._preparada)

    def _preparada(self, resultado):
        fuente, silenciado, nombre = resultado
        if not self._puede_empezar(fuente, silenciado):
            return
        anunciar(prueba_microfono.frase_de_inicio(nombre))
        self._cambiar_rotulo(_("&Detener prueba"))
        self._prueba = prueba_microfono.PruebaMicrofono(
            fuente,
            lambda nivel: wx.CallAfter(self._anunciar_tramo, nivel),
            lambda motivo: wx.CallAfter(self._terminada, motivo))
        self._prueba.iniciar()

    def _puede_empezar(self, fuente, silenciado):
        if not fuente:
            anunciar(_(obs_entradas_audio.AVISO_SIN_MICROFONO))
            return False
        if silenciado:
            anunciar(_("El micrófono está silenciado en OBS. Desmarca "
                       "Silenciar micrófono y vuelve a probar."))
            return False
        return True

    def _anunciar_tramo(self, nivel):
        if not self._viva:
            return
        sound_player.reproducir(nivel_microfono.sonido_de_tramo(nivel))
        anunciar(nivel_microfono.frase_de_tramo(nivel), False)

    def _terminada(self, motivo):
        self._prueba = None
        if self._viva:
            self._cambiar_rotulo(_("&Probar micrófono"))
        if motivo == prueba_microfono.MOTIVO_FALLO:
            anunciar(_("No se pudo medir el micrófono en OBS. "
                       "Prueba detenida."))
        else:
            anunciar(_("Prueba del micrófono detenida."))

    def _cambiar_rotulo(self, texto):
        self.btn_probar.SetLabel(texto)
        self.btn_probar.SetName(nombre_de_etiqueta(texto))

    def _al_destruir(self, evento):
        self._viva = False
        if self._prueba is not None:
            self._prueba.detener()
        evento.Skip()
