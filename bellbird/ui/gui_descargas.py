"""Diálogo «Administrador de descargas» (yt-dlp), accesible y nativo.

Diálogo modal que deja al usuario pegar enlaces de YouTube, elegir
formato, bitrate, carpeta y numeración, y ver la cola con progreso y
botón de cancelación por ítem. El motor puro está en `descargas.py`
(sin wx); este módulo monta la UI y refresca la cola con un
temporizador.

Accesibilidad (regla de oro NVDA):
  - Cada control interactivo tiene `name=` accesible.
  - Los errores avisan con sonido, anuncio y texto en la columna
    Estado del `ListCtrl`. Nunca se re-lanza una excepción fuera
    del hilo de descarga.
  - Toda mutación de la GUI desde el hilo de descarga va con `wx.CallAfter`.

Apertura: `abrir(parent, url_inicial=None)` desde `gui._abrir_descargas`.
"""
from __future__ import annotations

from datetime import datetime

import wx

from bellbird.core import diagnostico
from bellbird.core import config as cfg
from bellbird.core import paths
from bellbird.core.idioma import N_, _
from bellbird.downloads.descargas import frase_aviso_descarga, gestor, recortar_url_registro
from bellbird.downloads import historial_descargas
from bellbird.ui.descargas_listas import (
    _ESTADOS_FINALES, PaginaCola, PaginaHistorial)
from bellbird.ui.gui import anunciar, nombre_accesible, caja_de_grupo, _T, _tc
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


# Etiquetas legibles para el Choice de formato. mp3/m4a abren el bitrate.
_FORMATOS_OPCIONES = [
    (N_("Vídeo MP4"), "mp4"),
    (N_("Vídeo WebM"),        "webm"),
    (N_("Audio MP3"),         "mp3"),
    (N_("Audio M4A"),         "m4a"),
]
_BITRATE_OPCIONES = [192, 256, 320]


def _es_formato_audio(formato: str) -> bool:
    return (formato or "").lower() in ("mp3", "m4a")


def nombrar_selector_carpeta(selector) -> None:
    if hasattr(selector, "GetTextCtrl"):
        nombre_accesible(selector.GetTextCtrl(), _("Carpeta de destino de las descargas"))
    if hasattr(selector, "GetPickerCtrl"):
        boton_carpeta = selector.GetPickerCtrl()
        boton_carpeta.SetLabel(_("Examinar…"))
        nombre_accesible(boton_carpeta, _("Examinar…"))


# Cada fin de descarga avisa con su sonido propio.
_SONIDO_POR_FIN = {
    "completado": "descarga_completada",
    "error": "descarga_fallida",
    "cancelado": "descarga_cancelada",
}
# Cada 500 ms el diálogo abierto vuelca el estado del gestor a sus filas.
INTERVALO_REFRESCO_MS = 500

# El diálogo abierto (si lo hay) y los ítems ya llevados al historial. Viven a
# nivel de módulo porque las descargas sobreviven al diálogo: una que termina
# con el gestor cerrado también tiene que entrar en el historial.
_dialogo_activo = None
_registrados: set[str] = set()


def _ruta_historial():
    return paths.historial_descargas()


def registrar_historial(item, estado: str, ruta=None) -> dict | None:
    """Persiste el fin de una descarga en el historial. Devuelve la entrada,
    o None si ese ítem ya estaba registrado."""
    if item is None or item.id in _registrados:
        return None
    _registrados.add(item.id)
    ruta = ruta or _ruta_historial()
    entrada = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "nombre": item.nombre or item.url,
        "url": recortar_url_registro(item.url),
        "estado": estado,
        "carpeta": item.carpeta or cfg.obtener_opciones_descarga().get("carpeta", ""),
    }
    entradas = historial_descargas.agregar(historial_descargas.cargar(ruta), entrada)
    historial_descargas.guardar(ruta, entradas)
    return entrada


def _fin_descarga_en_gui(estado: str, mensaje: str, nombre: str, item) -> None:
    """Parte del aviso de fin que toca wx: corre en el hilo de la GUI."""
    if estado == "descargando":
        try:
            _snd.reproducir("descarga_iniciada")
        except Exception as error:
            logger.debug("no se pudo reproducir el inicio de descarga: %s", error)
        return
    frase = frase_aviso_descarga(estado, mensaje, nombre)
    if not frase:
        return
    try:
        _snd.reproducir(_SONIDO_POR_FIN.get(estado, "descarga_cancelada"))
    except Exception as error:
        logger.debug("no se pudo reproducir el aviso de descarga: %s", error)
    anunciar(frase)
    if estado not in _ESTADOS_FINALES:
        return
    entrada = registrar_historial(item, estado)
    dialogo = _dialogo_activo
    if entrada is not None and dialogo is not None and dialogo._alive:
        dialogo.pagina_historial.mostrar_entrada(entrada)


def _avisar_fin_descarga(estado: str, mensaje: str, nombre: str, item=None) -> None:
    # Llega desde el hilo de descarga: el sonido, el anuncio y el historial
    # (que toca el ListCtrl del diálogo) van al hilo de la GUI.
    wx.CallAfter(_fin_descarga_en_gui, estado, mensaje, nombre, item)


def _suscribir_al_gestor() -> None:
    gestor().suscribir_fin(_avisar_fin_descarga)


class GestorDescargasDialog(wx.Dialog):
    """Diálogo principal del gestor de descargas."""

    def __init__(self, parent, url_inicial: str | None = None):
        global _dialogo_activo
        super().__init__(parent, title=_("Administrador de descargas"),
                         size=(720, 560),
                         name="DialogoGestorDescargas")
        self.SetBackgroundColour(_T.bg)
        self._alive = True
        self._opciones = cfg.obtener_opciones_descarga()
        self._gestor = gestor()
        _suscribir_al_gestor()
        self._build_ui()
        self.Bind(wx.EVT_CLOSE, self._on_cerrar)
        # Las filas repobladas al reabrir no tienen callbacks (eran cierres del
        # diálogo anterior): un temporizador vuelca el estado del gestor.
        self._temporizador = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_refresco, self._temporizador)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
        self._temporizador.Start(INTERVALO_REFRESCO_MS)
        _dialogo_activo = self
        if url_inicial:
            self.txt_url.SetValue(url_inicial)
        self.Centre()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        panel = wx.Panel(self, name="PanelGestorDescargas")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._seccion_opciones(panel), 0, wx.EXPAND | wx.ALL, 10)
        vs.Add(self._seccion_anadir(panel), 0, wx.EXPAND | wx.ALL, 10)
        vs.Add(self._seccion_listas(panel), 1, wx.EXPAND | wx.ALL, 10)
        vs.Add(self._seccion_botones(panel), 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(vs)

    def _seccion_opciones(self, parent):
        box, padre = caja_de_grupo(parent, _("Opciones de descarga"))
        # Formato (Choice, no RadioBox: menos carga cognitiva y mejor con NVDA).
        fila_fmt = wx.BoxSizer(wx.HORIZONTAL)
        lbl_fmt = wx.StaticText(padre, label=_("&Formato:"), name="EtiquetaFormato")
        lbl_fmt.SetForegroundColour(_T.text)
        fila_fmt.Add(lbl_fmt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        etiquetas = [_(et) for et, _sin_uso in _FORMATOS_OPCIONES]
        valores = [v for _sin_uso, v in _FORMATOS_OPCIONES]
        self.cho_formato = wx.Choice(padre, choices=etiquetas, name=_("Formato"))
        _tc(self.cho_formato)
        actual = self._opciones.get("formato", "mp4")
        try:    self.cho_formato.SetSelection(valores.index(actual))
        except ValueError: self.cho_formato.SetSelection(0)
        self.cho_formato.Bind(wx.EVT_CHOICE, self._on_formato)
        fila_fmt.Add(self.cho_formato, 1, wx.EXPAND)
        box.Add(fila_fmt, 0, wx.EXPAND | wx.ALL, 6)

        # Bitrate (solo se habilita si formato es audio).
        fila_bit = wx.BoxSizer(wx.HORIZONTAL)
        lbl_bit = wx.StaticText(padre, label=_("&Velocidad de bits (kbps):"), name="EtiquetaBitrate")
        lbl_bit.SetForegroundColour(_T.text)
        fila_bit.Add(lbl_bit, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.cho_bitrate = wx.Choice(padre,
                                     choices=[str(b) for b in _BITRATE_OPCIONES],
                                      name=_("Velocidad de bits"))
        _tc(self.cho_bitrate)
        try:    self.cho_bitrate.SetSelection(
                    _BITRATE_OPCIONES.index(int(self._opciones.get("bitrate", 192))))
        except ValueError: self.cho_bitrate.SetSelection(0)
        fila_bit.Add(self.cho_bitrate, 1, wx.EXPAND)
        box.Add(fila_bit, 0, wx.EXPAND | wx.ALL, 6)

        fila_carp = wx.BoxSizer(wx.HORIZONTAL)
        lbl_carp = wx.StaticText(padre, label=_("Carpeta de &destino:"), name="EtiquetaCarpeta")
        lbl_carp.SetForegroundColour(_T.text)
        fila_carp.Add(lbl_carp, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.dir_carpeta = wx.DirPickerCtrl(
            padre, path=self._opciones.get("carpeta") or str(paths.descargas_por_defecto()),
            name=_("Carpeta de destino"), message=_("Elige la carpeta de descargas"))
        _tc(self.dir_carpeta)
        nombrar_selector_carpeta(self.dir_carpeta)
        fila_carp.Add(self.dir_carpeta, 1, wx.EXPAND)
        box.Add(fila_carp, 0, wx.EXPAND | wx.ALL, 6)

        # Enumerar playlist (casilla, sin color).
        self.chk_enumerar = wx.CheckBox(
            padre, name="EnumerarPlaylist",
            label=_("&Numerar archivos de listas"))
        self.chk_enumerar.SetValue(bool(self._opciones.get("enumerar", False)))
        box.Add(self.chk_enumerar, 0, wx.ALL, 6)

        self._on_formato()   # ajusta habilitación del bitrate
        return box

    def _seccion_anadir(self, parent):
        box, padre = caja_de_grupo(parent, _("Agregar enlace"))
        fila = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(padre, label=_("En&lace del vídeo o lista de reproducción:"),
                            name="EtiquetaURL")
        lbl.SetForegroundColour(_T.text)
        fila.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.txt_url = wx.TextCtrl(padre, value="",
                                   style=wx.TE_PROCESS_ENTER,
                                   name=_("Enlace del vídeo o lista de reproducción"))
        _tc(self.txt_url)
        self.txt_url.SetToolTip(_("Pega un enlace de YouTube (vídeo o lista de reproducción)."))
        self.txt_url.Bind(wx.EVT_TEXT_ENTER, lambda e: self._on_anadir(None))
        fila.Add(self.txt_url, 1, wx.EXPAND)
        self.btn_anadir = wx.Button(padre, label=_("A&gregar"), name="AnadirURL")
        self.btn_anadir.SetBackgroundColour(_T.btn)
        self.btn_anadir.SetForegroundColour(_T.btn_t)
        self.btn_anadir.Bind(wx.EVT_BUTTON, self._on_anadir)
        fila.Add(self.btn_anadir, 0, wx.LEFT, 6)
        box.Add(fila, 0, wx.EXPAND | wx.ALL, 6)
        return box

    def _seccion_listas(self, parent):
        self.pestanas = wx.Notebook(parent, name="PestanasDescargas")
        self.pagina_cola = PaginaCola(self.pestanas, self._gestor)
        self.pagina_historial = PaginaHistorial(self.pestanas, _ruta_historial())
        self.pestanas.AddPage(self.pagina_cola, _("Cola"))
        self.pestanas.AddPage(self.pagina_historial, _("Historial"))
        return self.pestanas

    def _seccion_botones(self, parent):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_cerrar = wx.Button(parent, wx.ID_CANCEL, _("&Cerrar"),
                                    name="CerrarGestorDescargas")
        self.btn_cerrar.SetBackgroundColour(_T.btn)
        self.btn_cerrar.SetForegroundColour(_T.btn_t)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._on_cerrar)
        fila.Add(self.btn_cerrar, 0, wx.RIGHT, 6)
        return fila

    # ── Callbacks de UI ──────────────────────────────────────────────────────

    def _on_formato(self, _event=None):
        idx = self.cho_formato.GetSelection()
        if idx < 0 or idx >= len(_FORMATOS_OPCIONES):
            return
        _sin_uso, valor = _FORMATOS_OPCIONES[idx]
        es_audio = _es_formato_audio(valor)
        self.cho_bitrate.Enable(es_audio)
        # Si pasó de audio a vídeo, no escondemos el valor: el usuario lo
        # verá gris. Si era vídeo y pasa a audio, ya está en 192/256/320.

    def _opciones_actuales(self) -> dict:
        idx = self.cho_formato.GetSelection()
        formato = _FORMATOS_OPCIONES[idx][1] if 0 <= idx < len(_FORMATOS_OPCIONES) else "mp4"
        try:    bitrate = _BITRATE_OPCIONES[self.cho_bitrate.GetSelection()]
        except Exception: bitrate = 192
        carpeta = self.dir_carpeta.GetPath() or str(paths.descargas_por_defecto())
        enumerar = bool(self.chk_enumerar.GetValue())
        return {"formato": formato, "bitrate": bitrate, "carpeta": carpeta, "enumerar": enumerar}

    def _on_anadir(self, _event):
        url = self.txt_url.GetValue().strip()
        if not url:
            wx.MessageBox(_("Pega un enlace de YouTube (vídeo o lista de reproducción) antes de agregar."),
                          _("Falta el enlace"), wx.OK | wx.ICON_INFORMATION, self)
            return
        # Persistimos las opciones elegidas antes de encolar (así el Gestor
        # las ve). Si luego el usuario cambia el formato en medio, la nueva
        # descarga usará la nueva config.
        op = self._opciones_actuales()
        try:    cfg.guardar_opciones_descarga(op)
        except Exception as exc: logger.debug("guardar opciones: %s", exc)
        self._opciones = op
        self._gestor.set_opciones(op)

        self.pagina_cola.agregar_enlace(url)
        self.txt_url.SetValue("")
        anunciar(_("Agregado a la cola"))

    def _on_refresco(self, _event) -> None:
        if not self or not self._alive or not self.pagina_cola.lista:
            return
        self.pagina_cola.refrescar()

    def _on_cerrar(self, _event):
        self._alive = False
        self._soltar()
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            self.Destroy()

    def _al_destruir(self, event):
        if event.GetEventObject() is self:
            self._alive = False
            self._soltar()
        event.Skip()

    def _soltar(self) -> None:
        global _dialogo_activo
        try:
            self._temporizador.Stop()
        except Exception as error:
            logger.debug("no se pudo detener el temporizador: %s", error)
        if _dialogo_activo is self:
            _dialogo_activo = None


def abrir(parent, url_inicial: str | None = None) -> bool:
    """Abre el gestor como modal y devuelve True si el usuario lo usó (siempre,
    salvo que falle la apertura). El diálogo persiste las opciones al cerrarse
    vía `cfg.guardar_opciones_descarga` desde los callbacks."""
    dlg = GestorDescargasDialog(parent, url_inicial=url_inicial)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
    return True
