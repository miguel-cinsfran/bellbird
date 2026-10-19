"""Ventana modal para elegir qué música suena.

Se busca en la carpeta, se elige un tema o uno de los resultados, se ve la
cola y se salta a un tema, y se cambia la carpeta. Cerrarla no corta la
música: el motor vive en `ControlMusica`, no acá.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.music import anuncios, enlaces, listas
from ytchat.music import vista
from ytchat.ui.gui import _T, _pintar, anunciar, nombre_accesible
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

TITULO = "Música"
TEXTO_CARGANDO = "Cargando la carpeta…"
TEXTO_SIN_CARPETA = "No hay carpeta de música"
TITULO_AGREGAR = "Agregar a una lista"
TITULO_NUEVA_LISTA = "Nueva lista"
TITULO_AGREGAR_ENLACE = "Agregar enlace"
TEXTO_DIRECCION_ENLACE = "Dirección de un vídeo o una lista de YouTube:"


class VentanaMusica(wx.Dialog):
    """Lista de temas, búsqueda, cola y cambio de carpeta, en una sola ventana."""

    def __init__(self, parent, control):
        super().__init__(parent, title=TITULO, size=(560, 660),
                         name="VentanaMusica")
        self._control = control
        self._biblioteca = None
        self._temas_filtrados = ()
        self._primera_carga = True
        self._cargando = False
        self._combos = control.combos_atajo()
        self.SetBackgroundColour(_T.bg)
        self._crear_controles()
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla_atajo)
        self.Centre()
        self.refrescar_cola()
        self._cargar_biblioteca()

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelMusica")
        self._panel = panel
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        rotulo_buscar = wx.StaticText(panel, label="&Buscar:")
        self.txt_buscar = wx.TextCtrl(panel, name="Buscar en la música")
        _pintar(self.txt_buscar, _T.field, _T.text)
        nombre_accesible(self.txt_buscar, "Buscar en la música")
        fila.Add(rotulo_buscar, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
        fila.Add(self.txt_buscar, 1, wx.EXPAND | wx.ALL, 6)
        vs.Add(fila, 0, wx.EXPAND, 0)

        vs.Add(wx.StaticText(panel, label="&Temas:"), 0, wx.ALL, 6)
        self.lb_temas = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name="Temas de la carpeta")
        _pintar(self.lb_temas, _T.field, _T.text)
        nombre_accesible(self.lb_temas, "Temas de la carpeta")
        self.lb_temas.SetMinSize((-1, 180))
        vs.Add(self.lb_temas, 1, wx.EXPAND | wx.ALL, 6)

        self.lbl_resumen = wx.StaticText(
            panel, name="Resumen de la música", label="")
        _pintar(self.lbl_resumen, fg=_T.dim)
        vs.Add(self.lbl_resumen, 0, wx.ALL, 6)

        botones = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_reproducir = self._boton(panel, "&Reproducir este", "Reproducir este")
        self.btn_todo = self._boton(panel, "Reproducir to&do", "Reproducir todo")
        self.btn_agregar = self._boton(panel, "&Agregar a la cola", "Agregar a la cola")
        self.btn_a_continuacion = self._boton(
            panel, "Reproducir a co&ntinuación", "Reproducir a continuación")
        self.btn_agregar_lista = self._boton(
            panel, "Agregar a una li&sta…", "Agregar a una lista")
        self.btn_agregar_enlace = self._boton(
            panel, "Agregar &enlace…", "Agregar enlace")
        for boton in (self.btn_reproducir, self.btn_todo, self.btn_agregar,
                      self.btn_a_continuacion, self.btn_agregar_lista,
                      self.btn_agregar_enlace):
            botones.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(botones, 0, wx.ALL, 6)

        vs.Add(wx.StaticText(panel, label="C&ola:"), 0, wx.ALL, 6)
        self.lb_cola = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_HSCROLL,
            name="Cola de reproducción")
        _pintar(self.lb_cola, _T.field, _T.text)
        nombre_accesible(self.lb_cola, "Cola de reproducción")
        self.lb_cola.SetMinSize((-1, 140))
        vs.Add(self.lb_cola, 1, wx.EXPAND | wx.ALL, 6)

        pie = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_carpeta = self._boton(panel, "Cambiar car&peta…", "Cambiar carpeta")
        self.btn_cerrar = wx.Button(panel, wx.ID_CANCEL, "&Cerrar", name="Cerrar")
        _pintar(self.btn_cerrar, _T.btn, _T.btn_t)
        pie.Add(self.btn_carpeta, 0, wx.RIGHT, 6)
        pie.AddStretchSpacer()
        pie.Add(self.btn_cerrar, 0, 0, 0)
        vs.Add(pie, 0, wx.EXPAND | wx.ALL, 6)

        panel.SetSizer(vs)

        self.txt_buscar.Bind(wx.EVT_TEXT, self._al_filtrar)
        self.lb_temas.Bind(wx.EVT_KEY_DOWN, self._tecla_temas)
        self.lb_temas.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._reproducir_este())
        self.lb_cola.Bind(wx.EVT_KEY_DOWN, self._tecla_cola)
        self.lb_cola.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._reproducir_de_cola())
        self.btn_reproducir.Bind(wx.EVT_BUTTON, lambda e: self._reproducir_este())
        self.btn_todo.Bind(wx.EVT_BUTTON, lambda e: self._reproducir_todo())
        self.btn_agregar.Bind(wx.EVT_BUTTON, lambda e: self._agregar())
        self.btn_a_continuacion.Bind(
            wx.EVT_BUTTON, lambda e: self._a_continuacion())
        self.btn_agregar_lista.Bind(wx.EVT_BUTTON, lambda e: self._agregar_a_lista())
        self.btn_agregar_enlace.Bind(wx.EVT_BUTTON, lambda e: self._agregar_enlace())
        self.btn_carpeta.Bind(wx.EVT_BUTTON, lambda e: self._cambiar_carpeta())
        self.btn_cerrar.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.txt_buscar.SetFocus()
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
        achican los 560 x 660 de fábrica.
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
            logger.debug("mínimo de la ventana de música: %s", exc)

    def enfocar_primer_control(self):
        """Deja el foco en el primer control, para cuando la traen al frente."""
        self.txt_buscar.SetFocus()

    # ── Carga de la biblioteca ──────────────────────────────────────────────

    def _cargar_biblioteca(self):
        self._biblioteca = None
        self._temas_filtrados = ()
        self.txt_buscar.ChangeValue("")
        self._primera_carga = True
        self._estado_cargando()
        self._control.biblioteca(self._al_lista)

    def _al_lista(self, biblioteca):
        if not self:
            return
        if biblioteca is None:
            self._estado_sin_carpeta()
            return
        self._biblioteca = biblioteca
        self._aplicar_filtro()
        self._estado_listo()
        if self._primera_carga:
            self._primera_carga = False
            total = len(biblioteca.temas())
            anunciar(vista.texto_resumen(total, total, False))

    def _al_filtrar(self, event):
        self._aplicar_filtro()
        event.Skip()

    def _aplicar_filtro(self):
        if self._biblioteca is None:
            return
        texto = self.txt_buscar.GetValue()
        todos = self._biblioteca.temas()
        buscando = bool(texto.strip())
        if buscando:
            self._temas_filtrados = tuple(self._biblioteca.buscar(texto))
        else:
            self._temas_filtrados = tuple(todos)
        self.lb_temas.Set(
            vista.filas_temas(self._temas_filtrados, self._con_artista()))
        if self._temas_filtrados:
            self.lb_temas.SetSelection(0)
        self.lbl_resumen.SetLabel(vista.texto_resumen(
            len(todos), len(self._temas_filtrados), buscando))

    # ── Estados de la lista de temas ────────────────────────────────────────

    def _estado_cargando(self):
        self._cargando = True
        self.lb_temas.Set([TEXTO_CARGANDO])
        self.lbl_resumen.SetLabel("")
        self._acciones(False, carpeta=False)

    def _estado_sin_carpeta(self):
        self._cargando = False
        self.lb_temas.Set([TEXTO_SIN_CARPETA])
        self.lbl_resumen.SetLabel("")
        self._acciones(False, carpeta=True)

    def _estado_listo(self):
        self._cargando = False
        self._acciones(True, carpeta=True)

    def _acciones(self, activo, carpeta):
        self.btn_reproducir.Enable(activo)
        self.btn_todo.Enable(activo)
        self.btn_agregar.Enable(activo)
        self.btn_a_continuacion.Enable(activo)
        self.btn_agregar_lista.Enable(activo)
        # Un enlace no necesita carpeta: se resuelve por la red.
        self.btn_agregar_enlace.Enable(True)
        self.btn_carpeta.Enable(carpeta)

    # ── Acciones ────────────────────────────────────────────────────────────

    def _tema_elegido(self):
        indice = self.lb_temas.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._temas_filtrados):
            return None, -1
        return self._temas_filtrados[indice], indice

    def _reproducir_este(self):
        _tema, indice = self._tema_elegido()
        if indice < 0:
            return
        self._control.reproducir_temas_desde(self._temas_filtrados, indice)
        self.refrescar_cola()

    def _reproducir_todo(self):
        if not self._temas_filtrados:
            return
        self._control.reproducir_temas(self._temas_filtrados)
        self.refrescar_cola()

    def _agregar(self):
        tema, _indice = self._tema_elegido()
        if tema is None:
            return
        self._control.agregar_temas([tema])
        self.refrescar_cola()

    def _a_continuacion(self):
        tema, _indice = self._tema_elegido()
        if tema is None:
            return
        self._control.reproducir_a_continuacion(tema)
        self.refrescar_cola()

    def _agregar_a_lista(self):
        """Suma el tema elegido a una lista propia, nueva si no hay ninguna."""
        tema, _indice = self._tema_elegido()
        if tema is None:
            return
        try:
            carpeta = self._control.carpeta_listas()
            nombres = listas.nombres(carpeta)
        except Exception as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        if nombres:
            nombre = self._elegir_lista(nombres)
            if nombre is None:
                return
        else:
            nombre = self._pedir_nombre_nueva()
            if nombre is None:
                return
            try:
                nombre = listas.crear(carpeta, nombre)
            except listas.ErrorListas as exc:
                self._avisar(anuncios.aviso_error_listas(str(exc)))
                return
        try:
            listas.agregar(carpeta, nombre, (tema,))
        except listas.ErrorListas as exc:
            self._avisar(anuncios.aviso_error_listas(str(exc)))
            return
        self._avisar(anuncios.aviso_agregado_a_lista(nombre))

    def _agregar_enlace(self):
        """Pide una dirección de YouTube y la manda a expandir al control."""
        with wx.TextEntryDialog(
                self, TEXTO_DIRECCION_ENLACE, TITULO_AGREGAR_ENLACE) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            url = dialogo.GetValue().strip()
        if not enlaces.es_enlace_youtube(url):
            self._avisar(anuncios.aviso_enlace_no_youtube())
            return
        self._avisar(anuncios.aviso_leyendo_enlace())
        self._control.agregar_enlace(url)

    def _elegir_lista(self, nombres):
        with wx.SingleChoiceDialog(
                self, "Lista:", TITULO_AGREGAR, list(nombres)) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.GetStringSelection()

    def _pedir_nombre_nueva(self):
        with wx.TextEntryDialog(
                self, "Nombre de la lista:", TITULO_NUEVA_LISTA) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return None
            return dialogo.GetValue()

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

    def _reproducir_de_cola(self):
        indice = self.lb_cola.GetSelection()
        if indice == wx.NOT_FOUND:
            return
        self._control.reproducir_desde(indice)
        self.refrescar_cola()

    def _cambiar_carpeta(self):
        with wx.DirDialog(
                self, "Elige la carpeta de música",
                defaultPath=self._control._carpeta()) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            ruta = dialogo.GetPath()
        self._control.cambiar_carpeta(ruta)
        self._cargar_biblioteca()

    def refrescar_cola(self):
        """Pone al día la lista de la cola. La llama el control."""
        if not self:
            return
        estado = self._control.estado()
        if estado is None:
            filas = []
        else:
            filas = vista.filas_cola(estado, self._con_artista())
        self.lb_cola.Set(filas)

    def actualizar_nombres(self, mapa) -> None:
        """Pone al día las filas con etiquetas recién leídas, sin mover nada.

        Reemplaza en lo filtrado los temas con origen en el mapa y cambia
        SOLO el texto de las filas afectadas, con `SetString`: la selección
        y el foco quedan donde estaban. El resumen y el filtro no se
        recalculan. Para la cola, lo mismo fila por fila; si su cantidad
        cambió a mitad, se refresca entera como siempre.
        """
        if not self:
            return
        if not mapa:
            return
        con_artista = self._con_artista()
        filtrados = tuple(
            mapa.get(tema.origen, tema) for tema in self._temas_filtrados)
        self._temas_filtrados = filtrados
        filas = vista.filas_temas(filtrados, con_artista)
        try:
            cantidad = self.lb_temas.GetCount()
        except Exception:
            logger.debug("No se pudo actualizar la lista de temas")
            return
        for indice, tema in enumerate(filtrados):
            if tema.origen in mapa and indice < cantidad:
                try:
                    self.lb_temas.SetString(indice, filas[indice])
                except Exception:
                    logger.debug("No se pudo actualizar la fila de un tema")
        try:
            estado = self._control.estado()
        except Exception:
            return
        if estado is None:
            return
        filas_cola = vista.filas_cola(estado, con_artista)
        try:
            cantidad_cola = self.lb_cola.GetCount()
        except Exception:
            logger.debug("No se pudo actualizar la cola")
            return
        if cantidad_cola != len(filas_cola):
            self.refrescar_cola()
            return
        for indice, tema in enumerate(estado.cola):
            if tema.origen in mapa:
                try:
                    self.lb_cola.SetString(indice, filas_cola[indice])
                except Exception:
                    logger.debug("No se pudo actualizar la fila de la cola")

    # ── Teclas ──────────────────────────────────────────────────────────────

    def _tecla_temas(self, event):
        if event.GetKeyCode() == wx.WXK_RETURN:
            self._reproducir_este()
            return
        event.Skip()

    def _tecla_cola(self, event):
        if event.GetKeyCode() == wx.WXK_RETURN:
            self._reproducir_de_cola()
            return
        event.Skip()

    def _tecla_atajo(self, event):
        combo = (event.GetModifiers(), event.GetKeyCode())
        accion = self._combos.get(combo)
        if accion is None:
            event.Skip()
            return
        self._control.ejecutar_atajo(accion)
        self.refrescar_cola()

    # ── Interno ─────────────────────────────────────────────────────────────

    def _con_artista(self):
        try:
            return bool(self._control.incluir_artista())
        except Exception:
            return False


def abrir_ventana(control) -> None:
    """Abre la ventana modal y la destruye al cerrarse."""
    parent = getattr(control, "_frame", None)
    ventana = VentanaMusica(parent, control)
    control.registrar_ventana(ventana)
    try:
        ventana.ShowModal()
    finally:
        control.olvidar_ventana()
        ventana.Destroy()
