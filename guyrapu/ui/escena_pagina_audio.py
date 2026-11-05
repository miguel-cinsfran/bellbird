"""Pestaña Audio de la ventana Escena: silenciar, elegir y probar el micrófono."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import _
from guyrapu.obs import (
    filtros_microfono, nivel_microfono, obs_entradas_audio, prueba_microfono)
from guyrapu.ui import escena_escucha, escena_filtros, gui_microfono
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.preferencias_comun import boton, nombre_de_etiqueta
from guyrapu.voice import sound_player


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
        self.chk_silenciar = self._crear_casilla(_("Si&lenciar micrófono"))
        self._crear_botones()
        self.chk_escuchar = self._crear_casilla(_("&Escuchar micrófono"))
        caja.Add(self._crear_fila(), 0, wx.ALL, 8)
        self.SetSizer(caja)
        self.acciones = (
            self.chk_silenciar, self.btn_microfono, self.btn_probar,
            self.btn_filtros, self.chk_escuchar)
        self._escucha = escena_escucha.ControlEscucha(
            self.chk_escuchar, self._gestor, self._operaciones,
            lambda: gui_microfono.microfono_preferido(self._principal))

    def _crear_botones(self):
        etiquetas = (_("Elegir &micrófono…"), _("&Probar micrófono"),
                     _("&Filtros del micrófono…"))
        self.btn_microfono, self.btn_probar, self.btn_filtros = (
            boton(self, etiqueta, nombre_de_etiqueta(etiqueta))
            for etiqueta in etiquetas)

    def _crear_casilla(self, etiqueta):
        return wx.CheckBox(
            self, label=etiqueta, name=nombre_de_etiqueta(etiqueta))

    def _crear_fila(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.chk_silenciar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        fila.Add(self.btn_microfono, 0, wx.ALL, 6)
        fila.Add(self.btn_probar, 0, wx.ALL, 6)
        fila.Add(self.btn_filtros, 0, wx.ALL, 6)
        fila.Add(self.chk_escuchar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        return fila

    def _enlazar_eventos(self):
        self.btn_microfono.Bind(
            wx.EVT_BUTTON,
            lambda evento: gui_microfono.abrir_microfono_obs(
                self._principal, al_cerrar=self.btn_microfono.SetFocus))
        self.btn_probar.Bind(wx.EVT_BUTTON, self._al_probar)
        self.btn_filtros.Bind(wx.EVT_BUTTON, self._al_filtros)
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

    def _al_filtros(self, evento=None):
        preferido = gui_microfono.microfono_preferido(self._principal)
        def preparar():
            fuente, _s, _n = prueba_microfono.preparar(self._gestor, preferido)
            return fuente, filtros_microfono.leer(fuente) if fuente else None
        self._operaciones.en_hilo(preparar, self._filtros_listos)

    def _filtros_listos(self, resultado):
        fuente, estado = resultado
        if not fuente:
            anunciar(_(obs_entradas_audio.AVISO_SIN_MICROFONO))
            return
        elegido = escena_filtros.pedir_filtros(self, fuente, estado)
        self.btn_filtros.SetFocus()
        if elegido is not None:
            self._operaciones.en_hilo(
                lambda: filtros_microfono.aplicar(fuente, elegido),
                lambda _resultado: anunciar(
                    filtros_microfono.resumen(elegido)))

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
        self._escucha.al_cerrar()
        evento.Skip()
