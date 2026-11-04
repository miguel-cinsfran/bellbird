"""Pestaña Eventos: los próximos, los que están en directo y el historial.

Lee la lista con lo que la ventana le inyecta, muestra el detalle del evento
elegido, copia sus enlaces y pide sus estadísticas. Las llamadas de red van
en un hilo aparte, como las de Destinos.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico, sonidos_eventos
from bellbird.core.idioma import _
from bellbird.restream import eventos as eventos_restream
from bellbird.restream.api import ErrorApi
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.busqueda_teclado import instalar_busqueda_tipo
from bellbird.ui.gui import copiar_al_portapapeles
from bellbird.ui.preferencias_comun import CampoEstado, fila_horizontal
from bellbird.voice import sound_player as _snd

TIPOS_POR_INDICE = (
    eventos_restream.TIPO_PROXIMOS,
    eventos_restream.TIPO_EN_DIRECTO,
    eventos_restream.TIPO_HISTORIAL,
)


class PaginaEventos(wx.Panel):

    def __init__(self, parent, leer_eventos, leer_estadisticas,
                 obtener_nombres, conectada):
        super().__init__(parent, name="PaginaEventosRestream")
        self._leer_eventos = leer_eventos
        self._leer_estadisticas = leer_estadisticas
        self._obtener_nombres = obtener_nombres
        self._esta_conectada = conectada
        self._eventos = []
        self._tipo = eventos_restream.TIPO_PROXIMOS
        self._primera_vez = True
        self._vivo = True
        self._crear_ui()

    def _crear_ui(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self._crear_mostrar(vs)
        self._crear_lista(vs)
        self._crear_detalle(vs)
        self._crear_botones(vs)
        self.SetSizer(vs)

    def _crear_mostrar(self, vs):
        self.lbl_mostrar = wx.StaticText(self, label=_("&Mostrar:"))
        self.cho_mostrar = wx.Choice(
            self, choices=[_("Próximos"), _("En directo"), _("Historial")],
            name=_("Mostrar"))
        nombre_accesible(self.cho_mostrar, self.cho_mostrar.GetName())
        self.cho_mostrar.SetSelection(0)
        self.cho_mostrar.Bind(wx.EVT_CHOICE, self._al_cambiar_mostrar)
        fila_mostrar = wx.BoxSizer(wx.HORIZONTAL)
        fila_mostrar.Add(self.lbl_mostrar, 0,
                         wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_mostrar.Add(self.cho_mostrar, 0, wx.ALIGN_CENTER_VERTICAL)
        vs.Add(fila_mostrar, 0, wx.ALL, 8)

    def _crear_lista(self, vs):
        self.lista = wx.ListBox(
            self, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=_("Eventos"))
        nombre_accesible(self.lista, _("Eventos"))
        instalar_busqueda_tipo(
            self.lista,
            lambda: [self.lista.GetString(i) for i
                     in range(self.lista.GetCount())])
        self.lista.Bind(wx.EVT_LISTBOX, self._al_elegir)
        self.lista.Bind(wx.EVT_KEY_DOWN, self._al_tecla)
        vs.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

    def _crear_detalle(self, vs):
        self.lbl_detalle = wx.StaticText(
            self, label=_("&Detalle del evento:"))
        self.detalle = CampoEstado(
            self, _("Detalle del evento"), lineas=6)
        nombre_accesible(self.detalle, self.detalle.GetName())
        vs.Add(self.lbl_detalle, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        vs.Add(self.detalle, 0, wx.EXPAND | wx.ALL, 8)

    def _crear_botones(self, vs):
        self.btn_copiar = wx.Button(
            self, label=_("Copiar &enlaces"), name=_("Copiar enlaces"))
        self.btn_estadisticas = wx.Button(
            self, label=_("E&stadísticas"), name=_("Estadísticas"))
        self.btn_actualizar = wx.Button(
            self, label=_("&Actualizar"), name=_("Actualizar"))
        for boton in (self.btn_copiar, self.btn_estadisticas,
                      self.btn_actualizar):
            nombre_accesible(boton, boton.GetName())
        self.btn_copiar.Bind(
            wx.EVT_BUTTON, lambda evento: self.copiar_enlaces())
        self.btn_estadisticas.Bind(
            wx.EVT_BUTTON, lambda evento: self.estadisticas())
        self.btn_actualizar.Bind(
            wx.EVT_BUTTON, lambda evento: self.actualizar())
        vs.Add(fila_horizontal((self.btn_copiar, self.btn_estadisticas,
                                self.btn_actualizar)), 0, wx.ALL, 10)

    def al_mostrarse(self):
        """La primera vez que se muestra la pestaña, lee la lista."""
        if self._primera_vez:
            self._primera_vez = False
            self._leer()

    def reiniciar(self):
        """Olvida lo leído y deja la pestaña lista para volver a leer."""
        self._primera_vez = True
        self._eventos = []
        self.lista.Set([])
        if self._conectada():
            self.detalle.SetValue("")
        else:
            self._sin_cuenta()

    def actualizar_nombres(self):
        """Vuelve a mostrar el detalle con los nombres de Destinos al día."""
        evento = self.seleccionado()
        if evento is not None:
            self._mostrar_detalle(evento)

    def seleccionado(self):
        indice = self.lista.GetSelection()
        if 0 <= indice < len(self._eventos):
            return self._eventos[indice]
        return None

    def copiar_enlaces(self):
        evento = self.seleccionado()
        if evento is None:
            anunciar(_("Sin selección"))
            return
        enlaces = eventos_restream.enlaces(evento)
        if not enlaces:
            _snd.reproducir("error")
            anunciar(_("Este evento no tiene enlaces todavía."))
            return
        copiar_al_portapapeles("\n".join(enlaces))
        _snd.reproducir("copiar")
        anunciar(_("Enlaces copiados."))

    def estadisticas(self):
        evento = self.seleccionado()
        if evento is None:
            anunciar(_("Sin selección"))
            return
        if self._tipo == eventos_restream.TIPO_PROXIMOS:
            _snd.reproducir("error")
            anunciar(_("Un evento que no empezó no tiene estadísticas."))
            return
        if self._leer_estadisticas is None:
            return
        identificador = evento.id

        def _correr():
            try:
                leidas = self._leer_estadisticas(identificador)
            except Exception as exc:
                self._en_principal(self._fallo_estadisticas, exc)
            else:
                self._en_principal(
                    self._estadisticas_listas, identificador, leidas)

        diagnostico.crear_hilo(_correr, "RestreamEstadisticas").start()

    def actualizar(self):
        self._leer()

    def _conectada(self):
        try:
            return bool(self._esta_conectada())
        except Exception:
            return False

    def _leer(self):
        if not self._conectada():
            self._sin_cuenta()
            return
        if self._leer_eventos is None:
            return
        tipo = self._tipo

        def _correr():
            try:
                leidos = self._leer_eventos(tipo)
            except Exception as exc:
                self._en_principal(self._fallo_lectura, exc)
            else:
                self._en_principal(self._eventos_listos, leidos, tipo)

        diagnostico.crear_hilo(_correr, "RestreamEventos").start()

    def _sin_cuenta(self):
        self._eventos = []
        self.lista.Set([])
        self.detalle.SetValue(_(
            "Conecta una cuenta de Restream en la pestaña Cuenta."))

    def _eventos_listos(self, leidos, tipo):
        if tipo != self._tipo:
            return
        self._eventos = list(leidos or ())
        self.lista.Set([eventos_restream.fila(evento, tipo)
                        for evento in self._eventos])
        self._mostrar_detalle(None)

    def _fallo_lectura(self, error):
        if isinstance(error, ErrorApi):
            texto = str(error).strip()
        else:
            texto = _("No se pudieron leer los eventos de Restream. "
                      "Vuelve a intentarlo.")
        self._eventos = []
        self.lista.Set([])
        self.detalle.SetValue(texto)
        _snd.reproducir("error")
        anunciar(texto)

    def _estadisticas_listas(self, identificador, leidas):
        evento = self.seleccionado()
        if evento is None or evento.id != identificador:
            return
        frase = eventos_restream.frase_estadisticas(leidas)
        texto = self.detalle.GetValue()
        if texto:
            texto += "\n"
        self.detalle.SetValue(texto + frase)
        anunciar(frase)

    def _fallo_estadisticas(self, error):
        if isinstance(error, ErrorApi):
            texto = str(error).strip()
        else:
            texto = _("No se pudieron leer las estadísticas del evento. "
                      "Vuelve a intentarlo.")
        _snd.reproducir("error")
        anunciar(texto)

    def _al_cambiar_mostrar(self, _evento):
        indice = self.cho_mostrar.GetSelection()
        if 0 <= indice < len(TIPOS_POR_INDICE):
            self._tipo = TIPOS_POR_INDICE[indice]
        self._leer()

    def _al_elegir(self, evento):
        self._mostrar_detalle(self.seleccionado())
        evento.Skip()

    def _mostrar_detalle(self, evento):
        if evento is None:
            self.detalle.SetValue("")
            return
        self.detalle.SetValue(eventos_restream.detalle(
            evento, self._nombres()))

    def _nombres(self):
        if self._obtener_nombres is None:
            return {}
        try:
            return dict(self._obtener_nombres())
        except Exception:
            return {}

    def _al_tecla(self, evento):
        lista = evento.GetEventObject()
        try:
            seleccion, total = lista.GetSelection(), lista.GetCount()
        except Exception:
            seleccion, total = -1, 0
        if sonidos_eventos.es_orilla(evento.GetKeyCode(), seleccion, total):
            _snd.reproducir("orilla")
        evento.Skip()

    def _en_principal(self, funcion, *args):
        def _envoltura():
            if self._vivo:
                funcion(*args)

        wx.CallAfter(_envoltura)

    def Destroy(self):
        self._vivo = False
        return super().Destroy()
