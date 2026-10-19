"""Ventana modal de listas de música propias.

Crea, renombra, borra y reproduce listas guardadas en `.m3u8`, y deja quitar
y reordenar sus temas. La cola que suena se puede guardar como lista. El
trabajo de archivo lo hace `ytchat.music.listas`, que es puro; acá solo se
pide, se anuncia y se vuelve a mostrar.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import anuncios, listas, vista
from ytchat.ui import gui_musica
from ytchat.ui.gui import _T, _pintar, anunciar, nombre_accesible
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

TITULO = "Listas de música"
TEXTO_SIN_LISTAS = "No hay listas"
TEXTO_MENSAJE_NOMBRE = "Nombre de la lista:"
TITULO_NUEVA = "Nueva lista"
TITULO_RENOMBRAR = "Renombrar lista"


class VentanaListas(wx.Dialog):
    """Listas guardadas y sus temas, con crear, renombrar, borrar y reproducir."""

    def __init__(self, parent, control):
        super().__init__(parent, title=TITULO, size=(620, 620),
                         name="VentanaListas")
        self._control = control
        self._nombres: list[str] = []
        self._combos = control.combos_atajo()
        self.SetBackgroundColour(_T.bg)
        self._crear_controles()
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla_atajo)
        self.Centre()
        self.refrescar_listas()

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelListas")
        self._panel = panel
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(wx.StaticText(panel, label="&Listas:"), 0, wx.ALL, 6)
        self.lb_listas = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name="Listas guardadas")
        _pintar(self.lb_listas, _T.field, _T.text)
        nombre_accesible(self.lb_listas, "Listas guardadas")
        self.lb_listas.SetMinSize((-1, 130))
        vs.Add(self.lb_listas, 1, wx.EXPAND | wx.ALL, 6)

        botones = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_reproducir = self._boton(
            panel, "&Reproducir la lista", "Reproducir la lista")
        self.btn_nueva = self._boton(panel, "&Nueva lista…", "Nueva lista")
        self.btn_renombrar = self._boton(panel, "R&enombrar…", "Renombrar")
        self.btn_borrar = self._boton(panel, "&Borrar…", "Borrar")
        for boton in (self.btn_reproducir, self.btn_nueva, self.btn_renombrar,
                      self.btn_borrar):
            botones.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(botones, 0, wx.ALL, 6)

        vs.Add(wx.StaticText(panel, label="&Temas de la lista:"), 0, wx.ALL, 6)
        self.lb_temas = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name="Temas de la lista")
        _pintar(self.lb_temas, _T.field, _T.text)
        nombre_accesible(self.lb_temas, "Temas de la lista")
        self.lb_temas.SetMinSize((-1, 150))
        vs.Add(self.lb_temas, 1, wx.EXPAND | wx.ALL, 6)

        pie = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_guardar = self._boton(
            panel, "&Guardar la cola como lista…", "Guardar la cola como lista")
        self.btn_cerrar = wx.Button(panel, wx.ID_CANCEL, "&Cerrar", name="Cerrar")
        _pintar(self.btn_cerrar, _T.btn, _T.btn_t)
        pie.Add(self.btn_guardar, 0, wx.RIGHT, 6)
        pie.AddStretchSpacer()
        pie.Add(self.btn_cerrar, 0, 0, 0)
        vs.Add(pie, 0, wx.EXPAND | wx.ALL, 6)

        panel.SetSizer(vs)

        self.lb_listas.Bind(wx.EVT_LISTBOX, self._al_elegir_lista)
        self.lb_listas.Bind(wx.EVT_KEY_DOWN, self._tecla_listas)
        self.lb_listas.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._reproducir())
        self.lb_temas.Bind(wx.EVT_KEY_DOWN, self._tecla_temas)
        self.btn_reproducir.Bind(wx.EVT_BUTTON, lambda e: self._reproducir())
        self.btn_nueva.Bind(wx.EVT_BUTTON, lambda e: self._nueva())
        self.btn_renombrar.Bind(wx.EVT_BUTTON, lambda e: self._renombrar())
        self.btn_borrar.Bind(wx.EVT_BUTTON, lambda e: self._borrar())
        self.btn_guardar.Bind(wx.EVT_BUTTON, lambda e: self._guardar_cola())
        self.btn_cerrar.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.lb_listas.SetFocus()
        self._ajustar_minimo()

    @staticmethod
    def _boton(panel, etiqueta, nombre):
        boton = wx.Button(panel, wx.ID_ANY, etiqueta, name=nombre)
        _pintar(boton, _T.btn, _T.btn_t)
        return boton

    def _ajustar_minimo(self):
        """La ventana no baja nunca del tamaño que piden sus controles.

        La fila de botones es un `WrapSizer`: si no entra a lo ancho, baja
        de renglón en vez de aplastarse. Del sizer sale el mínimo y no se
        achican los 620 x 620 de fábrica.
        """
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
            logger.debug("mínimo de la ventana de listas: %s", exc)

    def enfocar_primer_control(self):
        """Deja el foco en el primer control, para cuando la traen al frente."""
        self.lb_listas.SetFocus()

    # ── Listas guardadas y sus temas ────────────────────────────────────────

    def _carpeta(self):
        return self._control.carpeta_listas()

    def refrescar_listas(self, seleccionar=None):
        """Vuelve a leer las listas y muestra la elegida, si la hay."""
        try:
            self._nombres = list(listas.nombres(self._carpeta()))
        except listas.ErrorListas as exc:
            self._error(exc)
            self._nombres = []
        if not self._nombres:
            self.lb_listas.Set([TEXTO_SIN_LISTAS])
            self.lb_temas.Set([])
            self._acciones()
            return
        self.lb_listas.Set(self._nombres)
        indice = 0
        if seleccionar in self._nombres:
            indice = self._nombres.index(seleccionar)
        self.lb_listas.SetSelection(indice)
        self._cargar_temas(self._nombres[indice])
        self._acciones()

    def _acciones(self):
        hay = bool(self._nombres)
        self.btn_reproducir.Enable(hay)
        self.btn_renombrar.Enable(hay)
        self.btn_borrar.Enable(hay)

    def _lista_elegida(self):
        indice = self.lb_listas.GetSelection()
        if not self._nombres or indice == wx.NOT_FOUND \
                or indice >= len(self._nombres):
            return None
        return self._nombres[indice]

    def _cargar_temas(self, nombre):
        try:
            temas, _saltadas = listas.cargar(self._carpeta(), nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            self.lb_temas.Set([])
            return
        self._poner_temas(temas)

    def _poner_temas(self, temas, seleccion=0):
        self.lb_temas.Set(vista.filas_temas(temas, self._con_artista()))
        if temas:
            self.lb_temas.SetSelection(min(seleccion, len(temas) - 1))

    def _al_elegir_lista(self, event):
        nombre = self._lista_elegida()
        if nombre is not None:
            self._cargar_temas(nombre)
        event.Skip()

    # ── Acciones sobre las listas ───────────────────────────────────────────

    def _reproducir(self):
        nombre = self._lista_elegida()
        if nombre is None:
            return
        self._control.reproducir_lista_guardada(nombre)

    def _nueva(self):
        nombre = self._pedir_nombre(TITULO_NUEVA)
        if nombre is None:
            return
        try:
            limpio = listas.crear(self._carpeta(), nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._avisar(anuncios.aviso_lista_creada(limpio))
        self.refrescar_listas(seleccionar=limpio)

    def _renombrar(self):
        viejo = self._lista_elegida()
        if viejo is None:
            return
        nombre = self._pedir_nombre(TITULO_RENOMBRAR, viejo)
        if nombre is None:
            return
        try:
            limpio = listas.renombrar(self._carpeta(), viejo, nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._avisar(anuncios.aviso_lista_renombrada(limpio))
        self.refrescar_listas(seleccionar=limpio)

    def _borrar(self):
        nombre = self._lista_elegida()
        if nombre is None:
            return
        pregunta = f"¿Borrar la lista {nombre}?"
        if wx.MessageBox(pregunta, TITULO, wx.YES_NO | wx.ICON_QUESTION,
                         self) != wx.YES:
            return
        try:
            listas.borrar(self._carpeta(), nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._avisar(anuncios.aviso_lista_borrada(nombre))
        self.refrescar_listas()

    def _guardar_cola(self):
        cola = tuple(self._control.cola_actual() or ())
        if not cola:
            self._avisar(anuncios.aviso_sin_cola())
            return
        nombre = self._pedir_nombre(TITULO_NUEVA)
        if nombre is None:
            return
        try:
            limpio = listas.guardar(self._carpeta(), nombre, cola)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._avisar(anuncios.aviso_lista_guardada(limpio))
        self.refrescar_listas(seleccionar=limpio)

    # ── Acciones sobre los temas ────────────────────────────────────────────

    def _mover(self, paso):
        nombre = self._lista_elegida()
        indice = self.lb_temas.GetSelection()
        if nombre is None or indice == wx.NOT_FOUND:
            return
        try:
            nuevo = listas.mover(self._carpeta(), nombre, indice, paso)
            temas, _saltadas = listas.cargar(self._carpeta(), nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._poner_temas(temas, seleccion=nuevo)
        self._avisar(anuncios.aviso_tema_movido(nuevo + 1, len(temas)))

    def _quitar_tema(self):
        nombre = self._lista_elegida()
        indice = self.lb_temas.GetSelection()
        if nombre is None or indice == wx.NOT_FOUND:
            return
        try:
            listas.quitar(self._carpeta(), nombre, indice)
            temas, _saltadas = listas.cargar(self._carpeta(), nombre)
        except listas.ErrorListas as exc:
            self._error(exc)
            return
        self._poner_temas(temas, seleccion=indice)
        self._avisar(anuncios.aviso_tema_quitado())

    # ── Teclas ──────────────────────────────────────────────────────────────

    def _tecla_listas(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._reproducir()
            return
        event.Skip()

    def _tecla_temas(self, event):
        codigo = event.GetKeyCode()
        if codigo == wx.WXK_UP and (event.GetModifiers() & wx.MOD_ALT):
            self._mover(-1)
            return
        if codigo == wx.WXK_DOWN and (event.GetModifiers() & wx.MOD_ALT):
            self._mover(1)
            return
        if codigo in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self._quitar_tema()
            return
        event.Skip()

    def _tecla_atajo(self, event):
        if gui_musica.manejar_atajo_de_tecla(self._control, self._combos, event):
            return
        event.Skip()

    # ── Interno ─────────────────────────────────────────────────────────────

    def _pedir_nombre(self, titulo, valor=""):
        with wx.TextEntryDialog(
                self, TEXTO_MENSAJE_NOMBRE, titulo, valor) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.GetValue()

    def _con_artista(self):
        try:
            return bool(self._control.incluir_artista())
        except Exception:
            return False

    def _error(self, exc):
        self._avisar(anuncios.aviso_error_listas(str(exc)))

    def _avisar(self, aviso):
        if aviso is None:
            return
        if aviso.sonido:
            try:
                _snd.reproducir(aviso.sonido)
            except Exception:
                logger.debug("No se pudo reproducir el sonido %s", aviso.sonido)
        if aviso.texto:
            anunciar(aviso.texto)


def abrir_ventana(control) -> None:
    """Abre la ventana modal y la destruye al cerrarse."""
    parent = getattr(control, "_frame", None)
    ventana = VentanaListas(parent, control)
    control.registrar_ventana(ventana, "listas")
    try:
        ventana.ShowModal()
    finally:
        control.olvidar_ventana("listas")
        ventana.Destroy()
