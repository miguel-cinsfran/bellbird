"""Ventana única de música: Colecciones, Cola y acciones con foco.

Las Colecciones eligen lo que muestra la lista de temas: «Biblioteca» es
la carpeta y debajo va una fila por lista propia. La Cola se muestra y se
oculta con un botón y es lo único que suena. Cada tecla actúa sobre la
lista que tiene el foco y cada operación la hace `ControlMusica`, que es
quien anuncia.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.core.idioma import N_, _
from ytchat.music import anuncios, vista
from ytchat.ui import musica_filtros, musica_menus, musica_teclas
from ytchat.ui.accesibilidad import anunciar, nombre_accesible
from ytchat.ui.busqueda_teclado import instalar_busqueda_tipo
from ytchat.ui.tema import _T, _pintar
from ytchat.ui.musica_colecciones import (
    TEXTO_CARGANDO, TEXTO_SIN_CARPETA, ColeccionesVentanaMusica)
from ytchat.ui.musica_ventana_acciones import AccionesVentanaMusica
from ytchat.ui.musica_ventana_igualando import IgualandoVentanaMusica

logger = diagnostico.obtener_logger(__name__)
# Traductores: título de la ventana de música; una sola palabra.
TITULO = N_("Música")


class VentanaMusica(ColeccionesVentanaMusica, AccionesVentanaMusica,
                     IgualandoVentanaMusica, wx.Dialog):

    def __init__(self, parent, control, abrir_listas=False):
        super().__init__(parent, title=_(TITULO), size=(820, 620),
                         name="VentanaMusica")
        self._control = control
        self._abrir_listas = bool(abrir_listas)
        self._biblioteca = None
        self._fuente = None
        self._nombres_listas = []
        self._temas_fuente = ()
        self._temas_filtrados = ()
        self._generacion = 0
        self._examinando = False
        self._cargando = False
        self._primera_carga = True
        self._temporizador = None
        self._combos = control.combos_atajo() or {}
        self.SetBackgroundColour(_T.bg)
        self._crear_controles()
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla_atajo)
        self.Centre()
        self._inicio()
        self._ajustar_minimo()

    def _crear_controles(self):
        self._panel = panel = wx.Panel(self, name="PanelMusica")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        # Traductores: nombre accesible de la lista de colecciones; una palabra.
        self.lb_colecciones = self._lista(panel, _("Colecciones"), 190)
        self.lb_colecciones.SetMinSize((220, 190))
        _pintar(self.lb_colecciones, _T.field, _T.text)
        self.txt_buscar = self._campo(panel, _("Buscar en la música"))
        self.filtros = musica_filtros.FiltrosMusica(
            panel, *self._control.filtros_guardados(),
            al_cambiar=self._aplicar_filtro,
            programar_aviso=self._programar_aviso_coincidencias,
            recordar=self._recordar_filtros, avisar=anunciar)
        # Traductores: nombre accesible de la lista de canciones; una palabra.
        self.lb_temas = self._lista(panel, _("Canciones"), 190)
        self.btn_cola = self._boton(
            panel, _("Mostrar la c&ola"), _("Mostrar la cola"))
        self.lb_cola = self._lista(panel, _("Cola de reproducción"), 160)
        self._crear_igualando(panel)
        self._crear_pie(panel)
        self._disponer(panel)
        self._conectar()
        self._reload_colecciones()
        self._aplicar_cola_guardada()

    def _disponer(self, panel):
        arriba = wx.BoxSizer(wx.HORIZONTAL)
        izquierda = wx.BoxSizer(wx.VERTICAL)
        izquierda.Add(wx.StaticText(panel, label=_("Co&lecciones:")),
                      0, wx.BOTTOM, 8)
        izquierda.Add(self.lb_colecciones, 1, wx.EXPAND)
        derecha = wx.BoxSizer(wx.VERTICAL)
        fila_buscar = wx.BoxSizer(wx.HORIZONTAL)
        fila_buscar.Add(wx.StaticText(panel, label=_("&Buscar:")), 0,
                        wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        fila_buscar.Add(self.txt_buscar, 1, wx.EXPAND)
        derecha.Add(fila_buscar, 0, wx.EXPAND | wx.BOTTOM, 8)
        derecha.Add(self.filtros.sizer, 0, wx.EXPAND | wx.BOTTOM, 8)
        derecha.Add(wx.StaticText(panel, label=_("C&anciones:")), 0, wx.BOTTOM, 8)
        derecha.Add(self.lb_temas, 1, wx.EXPAND)
        arriba.Add(izquierda, 0, wx.EXPAND | wx.RIGHT, 8)
        arriba.Add(derecha, 1, wx.EXPAND)
        vs = wx.BoxSizer(wx.VERTICAL)
        vs.Add(arriba, 1, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 12)
        vs.Add(self.btn_cola, 0, wx.TOP | wx.LEFT | wx.RIGHT, 12)
        vs.Add(self.lb_cola, 1, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 12)
        vs.Add(self._fila_igualando(panel), 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 12)
        vs.Add(wx.StaticLine(panel), 0,
               wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 12)
        vs.Add(self._fila_pie(panel), 0, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(vs)

    @staticmethod
    def _campo(panel, nombre):
        campo = wx.TextCtrl(panel, name=nombre)
        _pintar(campo, _T.field, _T.text)
        nombre_accesible(campo, nombre)
        return campo

    @staticmethod
    def _lista(panel, nombre, alto):
        lista = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_HSCROLL, name=nombre)
        _pintar(lista, _T.field, _T.text)
        nombre_accesible(lista, nombre)
        instalar_busqueda_tipo(
            lista,
            lambda: [lista.GetString(i) for i in range(lista.GetCount())])
        lista.SetMinSize((-1, alto))
        return lista

    @staticmethod
    def _boton(panel, etiqueta, nombre):
        boton = wx.Button(panel, wx.ID_ANY, etiqueta, name=nombre)
        _pintar(boton, _T.btn, _T.btn_t)
        return boton

    def _crear_pie(self, panel):
        """Los botones al pie, en orden de Tab."""
        # Traductores: abre el diálogo del enlace; segunda, su nombre accesible.
        self.btn_enlace = self._boton(panel, _("Abrir &enlace…"), _("Abrir enlace"))
        # Traductores: crea una lista nueva; segunda, su nombre accesible.
        self.btn_nueva = self._boton(panel, _("&Nueva lista…"), _("Nueva lista"))
        # Traductores: cambia la carpeta de música; segunda, su nombre accesible.
        self.btn_carpeta = self._boton(
            panel, _("Cambiar car&peta…"), _("Cambiar carpeta"))
        # Traductores: mide e iguala el volumen; segunda, su nombre accesible.
        self.btn_igualar = self._boton(
            panel, _("&Igualar el volumen"), _("Igualar el volumen"))
        # Traductores: vuelve a examinar la carpeta; segunda, su nombre accesible.
        self.btn_examinar = self._boton(
            panel, _("E&xaminar la carpeta"), _("Examinar la carpeta"))
        # Traductores: cierra la ventana; segunda, su nombre accesible.
        self.btn_cerrar = wx.Button(panel, wx.ID_CANCEL, _("&Cerrar"),
                                    name=_("Cerrar"))
        _pintar(self.btn_cerrar, _T.btn, _T.btn_t)

    def _conectar(self):
        self.txt_buscar.Bind(wx.EVT_TEXT, self._al_filtrar)
        self.txt_buscar.Bind(wx.EVT_KEY_DOWN, self._tecla_buscar)
        self.lb_colecciones.Bind(wx.EVT_LISTBOX, self._cambiar_coleccion)
        self.lb_colecciones.Bind(wx.EVT_KEY_DOWN, self._tecla_colecciones)
        self.lb_colecciones.Bind(
            wx.EVT_CONTEXT_MENU, lambda e: self._menu_colecciones())
        self.lb_temas.Bind(wx.EVT_KEY_DOWN, self._tecla_temas)
        self.lb_temas.Bind(wx.EVT_CONTEXT_MENU, lambda e: self._menu_temas())
        self.lb_cola.Bind(wx.EVT_KEY_DOWN, self._tecla_cola)
        self.lb_cola.Bind(wx.EVT_CONTEXT_MENU, lambda e: self._menu_cola())
        self.Bind(wx.EVT_LISTBOX_DCLICK, self._doble_clic_lista)
        self.btn_cola.Bind(wx.EVT_BUTTON, lambda e: self._alternar_cola())
        self.btn_enlace.Bind(wx.EVT_BUTTON, lambda e: self._abrir_enlace())
        self.btn_nueva.Bind(wx.EVT_BUTTON, lambda e: self._nueva_lista())
        self.btn_carpeta.Bind(
            wx.EVT_BUTTON, lambda e: self._cambiar_carpeta())
        self.btn_igualar.Bind(
            wx.EVT_BUTTON, lambda e: self.alternar_igualacion())
        self.btn_examinar.Bind(
            wx.EVT_BUTTON, lambda e: self.examinar_carpeta())
        self.btn_cerrar.Bind(wx.EVT_BUTTON, lambda e: self._cerrar())

    def _ajustar_minimo(self):
        try:
            self._panel.Layout()
            minimo = self._panel.GetSizer().GetMinSize()
            actual = self.GetSize()
            ancho = max(actual.width, minimo.width)
            alto = max(actual.height, minimo.height)
            self.SetMinSize((ancho, alto))
            if actual.width < ancho or actual.height < alto:
                self.SetSize((ancho, alto))
        except Exception as exc:
            logger.debug("mínimo de la ventana de música: %s", exc)

    def _doble_clic_lista(self, evento):
        foco = evento.GetEventObject()
        if foco is self.lb_colecciones:
            self._reproducir_coleccion()
        elif foco is self.lb_temas:
            self._accion_biblioteca(musica_menus.ACCION_AHORA)
        else:
            self._accion_cola(musica_menus.ACCION_REPRODUCIR)

    def _cola_guardada_visible(self):
        lee = getattr(self._control, "cola_visible", None)
        return bool(lee()) if callable(lee) else False

    def _aplicar_cola_guardada(self):
        visible = self._cola_guardada_visible()
        self._rotular_boton_cola(visible)
        if visible:
            self.lb_cola.Show()
        else:
            self.lb_cola.Hide()

    def _rotular_boton_cola(self, visible):
        if visible:
            self.btn_cola.SetLabel(_("Ocultar la c&ola"))
            nombre_accesible(self.btn_cola, _("Ocultar la cola"))
        else:
            self.btn_cola.SetLabel(_("Mostrar la c&ola"))
            nombre_accesible(self.btn_cola, _("Mostrar la cola"))

    def _alternar_cola(self):
        visible = not self.lb_cola.IsShown()
        self._rotular_boton_cola(visible)
        if visible:
            self.lb_cola.Show()
        else:
            self.lb_cola.Hide()
        self._panel.Layout()
        try:
            self._control.recordar_cola_visible(visible)
        except Exception as exc:
            logger.debug("No se pudo recordar la Cola visible: %s", exc)
        if visible:
            self.lb_cola.SetFocus()
            anunciar(vista.texto_cola_visible(
                len(self._control.cola_actual() or ())))
        else:
            self.btn_cola.SetFocus()
            anunciar(_(vista.TEXTO_COLA_OCULTA))

    def _aplicar_filtro(self):
        if self._cargando or (self._fuente is None
                              and self._biblioteca is None):
            return
        texto = self.txt_buscar.GetValue()
        biblioteca = self._biblioteca if self._fuente is None else None
        self._temas_filtrados = vista.filtrar_fuente(
            self._temas_fuente, texto, biblioteca)
        self._temas_filtrados = self.filtros.aplicar(self._temas_filtrados)
        anterior = self.lb_temas.GetSelection()
        self.lb_temas.Set(vista.filas_temas(self._temas_filtrados))
        if self._temas_filtrados:
            indice = vista.indice_seleccion_tras_refrescar(
                anterior, len(self._temas_filtrados))
            self.lb_temas.SetSelection(0 if indice < 0 else indice)
        else:
            self.lb_temas.SetSelection(wx.NOT_FOUND)

    def _cambiar_estado(self, texto):
        self._cargando = texto == _(TEXTO_CARGANDO)
        if texto == _(TEXTO_CARGANDO):
            self._temas_filtrados = ()
        self.lb_temas.Set([texto])
        self.btn_carpeta.Enable(not self._cargando)

    def _estado_listo(self):
        self._cargando = False
        self.btn_carpeta.Enable(True)

    def _con_tema(self):
        if self._cargando:
            return None, -1
        indice = self.lb_temas.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._temas_filtrados):
            return None, -1
        return self._temas_filtrados[indice], indice

    def _al_filtrar(self, evento):
        self._aplicar_filtro()
        self._cancelar_temporizador()
        self._temporizador = wx.CallLater(700, self._avisar_coincidencias)
        evento.Skip()

    def _avisar_coincidencias(self, siempre=False):
        if self and (siempre or self.txt_buscar.GetValue().strip()):
            anunciar(vista.texto_coincidencias(len(self._temas_filtrados)))

    def _programar_aviso_coincidencias(self):
        self._cancelar_temporizador()
        self._temporizador = wx.CallLater(700, self._avisar_coincidencias, True)

    def _recordar_filtros(self, visibles, artista, orden):
        self._control.recordar_filtros(visibles, artista, orden)

    def _cancelar_temporizador(self):
        if self._temporizador is not None:
            try:
                self._temporizador.Stop()
            except Exception as exc:
                logger.debug("No se pudo parar el aviso de coincidencias: %s",
                             exc)
            self._temporizador = None

    def _tecla_buscar(self, evento):
        codigo = evento.GetKeyCode()
        if codigo == wx.WXK_ESCAPE:
            if self.txt_buscar.GetValue():
                self.txt_buscar.ChangeValue("")
                self._aplicar_filtro()
                self._cancelar_temporizador()
                anunciar(_(anuncios.TEXTO_BUSQUEDA_BORRADA))
            else:
                self._cerrar()
            return
        if codigo == wx.WXK_DOWN:
            self.lb_temas.SetFocus()
            if self.lb_temas.GetCount() and \
                    self.lb_temas.GetSelection() == wx.NOT_FOUND:
                self.lb_temas.SetSelection(0)
            return
        evento.Skip()

    def _tecla_temas(self, evento):
        codigo = evento.GetKeyCode()
        modificadores = evento.GetModifiers()
        if codigo in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if modificadores & wx.MOD_SHIFT:
                self._accion_biblioteca(musica_menus.ACCION_CONTINUACION)
            elif modificadores & wx.MOD_CONTROL:
                self._accion_biblioteca(musica_menus.ACCION_AGREGAR)
            else:
                self._accion_biblioteca(musica_menus.ACCION_AHORA)
            return
        if codigo in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            if self._fuente is not None:
                tema, _indice = self._con_tema()
                if tema is not None:
                    self._quitar_lista(tema)
            return
        if codigo == wx.WXK_WINDOWS_MENU or (
                codigo == wx.WXK_F10 and modificadores & wx.MOD_SHIFT):
            self._menu_temas()
            return
        evento.Skip()

    def _tecla_cola(self, evento):
        codigo = evento.GetKeyCode()
        modificadores = evento.GetModifiers()
        if codigo in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._accion_cola(musica_menus.ACCION_REPRODUCIR)
            return
        if codigo in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self._accion_cola(musica_menus.ACCION_QUITAR)
            return
        if codigo == wx.WXK_UP and modificadores & wx.MOD_ALT:
            self._accion_cola(musica_menus.ACCION_SUBIR)
            return
        if codigo == wx.WXK_DOWN and modificadores & wx.MOD_ALT:
            self._accion_cola(musica_menus.ACCION_BAJAR)
            return
        if codigo == wx.WXK_WINDOWS_MENU or (
                codigo == wx.WXK_F10 and modificadores & wx.MOD_SHIFT):
            self._menu_cola()
            return
        evento.Skip()

    def _tecla_atajo(self, evento):
        if evento.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            foco = wx.Window.FindFocus()
            if foco is self.lb_colecciones:
                return self._tecla_colecciones(evento)
            if foco is self.lb_temas:
                return self._tecla_temas(evento)
            if foco is self.lb_cola:
                return self._tecla_cola(evento)
        if evento.GetKeyCode() == wx.WXK_F1:
            ayuda = self._ayuda_de_foco()
            if ayuda:
                anunciar(ayuda)
                return
        if musica_teclas.manejar_atajo_de_tecla(
                self._control, self._combos, evento):
            self.refrescar_cola()
            return
        evento.Skip()

    def _ayuda_de_foco(self):
        foco = wx.Window.FindFocus()
        if foco is self.lb_colecciones:
            return vista.ayuda_colecciones()
        if foco is self.txt_buscar:
            return vista.ayuda_buscar()
        if foco is self.lb_temas:
            return vista.ayuda_biblioteca(self._fuente is not None)
        if foco is self.lb_cola:
            return vista.ayuda_cola()
        return ""


def abrir_ventana(control, abrir_listas=False):
    parent = getattr(control, "_frame", None)
    ventana = VentanaMusica(parent, control, abrir_listas=abrir_listas)
    control.registrar_ventana(ventana)
    try:
        ventana.ShowModal()
    finally:
        ventana._cancelar_temporizador()
        ventana._parar_igualando()
        control.olvidar_ventana()
        ventana.Destroy()
