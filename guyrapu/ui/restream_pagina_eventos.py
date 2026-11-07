"""Pestaña Eventos: los próximos, los que están en directo y el historial.

Lee la lista con lo que la ventana le inyecta, muestra el detalle del evento
elegido, copia sus enlaces y pide sus estadísticas. Las llamadas de red van
en un hilo aparte, como las de Destinos.
"""

from __future__ import annotations

import webbrowser
from types import SimpleNamespace

import wx

from guyrapu.core import diagnostico, sonidos_eventos
from guyrapu.core.idioma import _
from guyrapu.restream import eventos as eventos_restream
from guyrapu.restream.api import ErrorApi
from guyrapu.ui import restream_menus
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.busqueda_teclado import instalar_busqueda_tipo
from guyrapu.ui.gui import copiar_al_portapapeles
from guyrapu.ui.preferencias_comun import CampoEstado, fila_horizontal
from guyrapu.voice import sound_player as _snd

abrir_navegador = webbrowser.open

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
        self.lista.Bind(wx.EVT_CONTEXT_MENU, self._menu_contextual)
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
        self.btn_actualizar = wx.Button(
            self, label=_("A&ctualizar"), name=_("Actualizar"))
        nombre_accesible(self.btn_actualizar,
                         self.btn_actualizar.GetName())
        self.btn_actualizar.Bind(
            wx.EVT_BUTTON, lambda evento: self.actualizar())
        vs.Add(fila_horizontal((self.btn_actualizar,)), 0, wx.ALL, 10)

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

    def copiar_informacion(self):
        evento = self.seleccionado()
        if evento is None:
            anunciar(_("Sin selección"))
            return
        copiar_al_portapapeles(self.detalle.GetValue())
        _snd.reproducir("copiar")
        anunciar(_("Información copiada."))

    def abrir_directo(self):
        evento = self.seleccionado()
        if evento is None:
            anunciar(_("Sin selección"))
            return
        enlaces = self._enlaces_nombrados(evento)
        if not enlaces:
            anunciar(_("Este evento no tiene enlaces todavía."))
            return
        abrir_navegador(enlaces[0][1])

    def abrir_url(self, url):
        abrir_navegador(url)

    def _enlaces_nombrados(self, evento):
        nombres = self._nombres()
        enlaces = []
        for destino in evento.destinos:
            if not destino.enlace:
                continue
            nombre = (nombres.get(destino.canal_id)
                      or nombres.get(destino.id)
                      or _("Plataforma {id}").format(
                          id=destino.plataforma_id))
            enlaces.append((nombre, destino.enlace))
        return enlaces

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

    def _menu_contextual(self, evento):
        evento_actual = self.seleccionado()
        if evento_actual is None:
            anunciar(_("Sin selección"))
            return
        acciones = SimpleNamespace(
            copiar=self.copiar_enlaces,
            copiar_informacion=self.copiar_informacion,
            abrir=self.abrir_directo,
            abrir_url=self.abrir_url,
            estadisticas=self.estadisticas)
        menu = restream_menus.menu_evento(
            acciones, self._enlaces_nombrados(evento_actual))
        self.lista.PopupMenu(menu)
        menu.Destroy()
        evento.Skip()

    def _al_tecla(self, evento):
        lista = evento.GetEventObject()
        try:
            seleccion, total = lista.GetSelection(), lista.GetCount()
        except Exception:
            seleccion, total = -1, 0
        tecla = evento.GetKeyCode()
        if sonidos_eventos.es_orilla(tecla, seleccion, total):
            _snd.reproducir("orilla")
        if tecla == wx.WXK_F5:
            self.actualizar()
        elif tecla in (ord("C"), ord("c")) and evento.ControlDown():
            self.copiar_enlaces()
        elif tecla in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.estadisticas()
        elif (tecla == wx.WXK_WINDOWS_MENU
              or (tecla == wx.WXK_F10 and evento.ShiftDown())):
            self._menu_contextual(evento)
        else:
            evento.Skip()

    def _en_principal(self, funcion, *args):
        def _envoltura():
            if self._vivo:
                funcion(*args)

        wx.CallAfter(_envoltura)

    def Destroy(self):
        self._vivo = False
        return super().Destroy()
