"""Ventana única de música: Biblioteca, Cola y acciones con foco.

La Biblioteca se elige con «Mostrar» (la carpeta o una lista propia) y la
Cola es lo único que suena. Cada tecla actúa sobre la lista que tiene el
foco y cada operación la hace `ControlMusica`, que es quien anuncia.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import anuncios, vista
from ytchat.ui import gui_musica, musica_menus
from ytchat.ui.gui import _T, _pintar, anunciar, nombre_accesible
from ytchat.ui.musica_ventana_acciones import AccionesVentanaMusica

logger = diagnostico.obtener_logger(__name__)
TITULO = "Música"
TEXTO_CARGANDO = "Cargando la carpeta…"
TEXTO_SIN_CARPETA = "No hay carpeta de música"


class VentanaMusica(AccionesVentanaMusica, wx.Dialog):

    def __init__(self, parent, control, abrir_listas=False):
        super().__init__(parent, title=TITULO, size=(640, 700),
                         name="VentanaMusica")
        self._control = control
        self._abrir_listas = bool(abrir_listas)
        self._biblioteca = None
        self._fuente = None
        self._nombres_listas = []
        self._temas_fuente = ()
        self._temas_filtrados = ()
        self._generacion = 0
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
        vs = wx.BoxSizer(wx.VERTICAL)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(wx.StaticText(panel, label="&Buscar:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        self.txt_buscar = self._campo(panel, "Buscar en la música")
        fila.Add(self.txt_buscar, 1, wx.EXPAND | wx.ALL, 6)
        vs.Add(fila, 0, wx.EXPAND)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(wx.StaticText(panel, label="&Mostrar:"), 0,
                 wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        self.cho_mostrar = wx.Choice(panel, name="Qué mostrar")
        _pintar(self.cho_mostrar, _T.field, _T.text)
        fila.Add(self.cho_mostrar, 1, wx.EXPAND | wx.ALL, 6)
        vs.Add(fila, 0, wx.EXPAND)
        vs.Add(wx.StaticText(panel, label="&Temas:"), 0, wx.ALL, 6)
        self.lb_temas = self._lista(panel, "Biblioteca", 190)
        vs.Add(self.lb_temas, 1, wx.EXPAND | wx.ALL, 6)
        vs.Add(wx.StaticText(panel, label="C&ola:"), 0, wx.ALL, 6)
        self.lb_cola = self._lista(panel, "Cola de reproducción", 150)
        vs.Add(self.lb_cola, 1, wx.EXPAND | wx.ALL, 6)
        botones = wx.WrapSizer(wx.HORIZONTAL, flags=0)
        self.btn_enlace = self._boton(panel, "Abrir &enlace…", "Abrir enlace")
        self.btn_nueva = self._boton(panel, "&Nueva lista…", "Nueva lista")
        self.btn_carpeta = self._boton(
            panel, "Cambiar car&peta…", "Cambiar carpeta")
        self.btn_cerrar = wx.Button(panel, wx.ID_CANCEL, "&Cerrar",
                                    name="Cerrar")
        _pintar(self.btn_cerrar, _T.btn, _T.btn_t)
        for boton in (self.btn_enlace, self.btn_nueva, self.btn_carpeta,
                      self.btn_cerrar):
            botones.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(botones, 0, wx.ALL, 6)
        panel.SetSizer(vs)
        self._conectar()
        self._reload_mostrar()

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
        lista.SetMinSize((-1, alto))
        return lista

    @staticmethod
    def _boton(panel, etiqueta, nombre):
        boton = wx.Button(panel, wx.ID_ANY, etiqueta, name=nombre)
        _pintar(boton, _T.btn, _T.btn_t)
        return boton

    def _conectar(self):
        self.txt_buscar.Bind(wx.EVT_TEXT, self._al_filtrar)
        self.txt_buscar.Bind(wx.EVT_KEY_DOWN, self._tecla_buscar)
        self.cho_mostrar.Bind(wx.EVT_CHOICE, self._cambiar_mostrar)
        self.lb_temas.Bind(wx.EVT_KEY_DOWN, self._tecla_temas)
        self.lb_temas.Bind(wx.EVT_CONTEXT_MENU, lambda e: self._menu_temas())
        self.lb_cola.Bind(wx.EVT_KEY_DOWN, self._tecla_cola)
        self.lb_cola.Bind(wx.EVT_CONTEXT_MENU, lambda e: self._menu_cola())
        self.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._accion_biblioteca(
            musica_menus.ACCION_AHORA) if e.GetEventObject() is self.lb_temas
            else self._accion_cola(musica_menus.ACCION_REPRODUCIR))
        self.btn_enlace.Bind(wx.EVT_BUTTON, lambda e: self._abrir_enlace())
        self.btn_nueva.Bind(wx.EVT_BUTTON, lambda e: self._nueva_lista())
        self.btn_carpeta.Bind(
            wx.EVT_BUTTON, lambda e: self._cambiar_carpeta())
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

    def enfocar_primer_control(self):
        if self._abrir_listas:
            self.cho_mostrar.SetFocus()
        else:
            self.txt_buscar.SetFocus()

    def _inicio(self):
        estado = self._control.estado()
        posicion = None
        if estado is not None and not estado.terminado:
            posicion = estado.posicion
        self.refrescar_cola(seleccion=posicion)
        if self._abrir_listas and self._nombres_listas:
            self.cho_mostrar.SetSelection(1)
            self._fuente = self._nombres_listas[0]
            self._cargar_lista()
        else:
            self.cho_mostrar.SetSelection(0)
            self._fuente = None
            self._cargar_carpeta()
        self.enfocar_primer_control()

    def _reload_mostrar(self, preferir=None):
        nombres = self._leer_nombres()
        self._nombres_listas = nombres
        self.cho_mostrar.Set(vista.etiquetas_mostrar(nombres))
        indice = 0
        if preferir:
            buscado = str(preferir).casefold()
            for posicion, nombre in enumerate(nombres, start=1):
                if nombre.casefold() == buscado:
                    indice = posicion
                    break
        self.cho_mostrar.SetSelection(indice)

    def _fuente_elegida(self):
        indice = self.cho_mostrar.GetSelection()
        if indice <= 0 or indice > len(self._nombres_listas):
            return None
        return self._nombres_listas[indice - 1]

    def _cambiar_mostrar(self, evento):
        self._cargar_fuente()
        evento.Skip()

    def _cargar_fuente(self):
        self._generacion += 1
        self.txt_buscar.ChangeValue("")
        self._cancelar_temporizador()
        self._fuente = self._fuente_elegida()
        if self._fuente is None:
            self._cargar_carpeta()
        else:
            self._biblioteca = None
            self._cargar_lista()

    def _cargar_carpeta(self):
        self._biblioteca = None
        self._primera_carga = True
        self.txt_buscar.ChangeValue("")
        self._cambiar_estado(TEXTO_CARGANDO)
        generacion = self._generacion
        self._control.biblioteca(
            lambda biblioteca: self._al_biblioteca(biblioteca, generacion))

    def _cargar_lista(self, seleccion=None):
        nombre = self._fuente
        generacion = self._generacion
        if seleccion is None:
            seleccion = self.lb_temas.GetSelection()
        self._cambiar_estado(TEXTO_CARGANDO)
        temas = tuple(self._control.temas_de_lista(nombre) or ())
        if generacion != self._generacion or self._fuente != nombre:
            return
        self._temas_fuente = temas
        self._cargando = False
        self._aplicar_filtro()
        self._estado_listo()
        indice = vista.indice_seleccion_tras_refrescar(
            seleccion, len(self._temas_filtrados))
        if indice >= 0:
            self.lb_temas.SetSelection(indice)

    def _al_biblioteca(self, biblioteca, generacion):
        if not self or generacion != self._generacion \
                or self._fuente is not None:
            return
        if biblioteca is None:
            self._temas_fuente = ()
            self._temas_filtrados = ()
            self._cambiar_estado(TEXTO_SIN_CARPETA)
            self.btn_carpeta.Enable(True)
            return
        self._biblioteca = biblioteca
        self._temas_fuente = tuple(biblioteca.temas())
        self._cargando = False
        self._aplicar_filtro()
        self._estado_listo()
        if self._primera_carga:
            self._primera_carga = False
            anunciar(vista.texto_resumen(
                len(self._temas_fuente), len(self._temas_filtrados), False))

    def _aplicar_filtro(self):
        if self._cargando or (self._fuente is None
                              and self._biblioteca is None):
            return
        texto = self.txt_buscar.GetValue()
        biblioteca = self._biblioteca if self._fuente is None else None
        self._temas_filtrados = vista.filtrar_fuente(
            self._temas_fuente, texto, biblioteca)
        anterior = self.lb_temas.GetSelection()
        self.lb_temas.Set(vista.filas_temas(
            self._temas_filtrados, self._con_artista()))
        if self._temas_filtrados:
            indice = vista.indice_seleccion_tras_refrescar(
                anterior, len(self._temas_filtrados))
            self.lb_temas.SetSelection(0 if indice < 0 else indice)
        else:
            self.lb_temas.SetSelection(wx.NOT_FOUND)

    def _cambiar_estado(self, texto):
        self._cargando = texto == TEXTO_CARGANDO
        if texto == TEXTO_CARGANDO:
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

    def _avisar_coincidencias(self):
        if self and self.txt_buscar.GetValue().strip():
            anunciar(vista.texto_coincidencias(len(self._temas_filtrados)))

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
                anunciar(anuncios.TEXTO_BUSQUEDA_BORRADA)
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
            if foco is self.lb_temas:
                return self._tecla_temas(evento)
            if foco is self.lb_cola:
                return self._tecla_cola(evento)
        if evento.GetKeyCode() == wx.WXK_F1:
            ayuda = self._ayuda_de_foco()
            if ayuda:
                anunciar(ayuda)
                return
        if gui_musica.manejar_atajo_de_tecla(
                self._control, self._combos, evento):
            self.refrescar_cola()
            return
        evento.Skip()

    def _ayuda_de_foco(self):
        foco = wx.Window.FindFocus()
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
        control.olvidar_ventana()
        ventana.Destroy()
