"""Página Sonidos del diálogo de Preferencias.

Dueña de su estado: la lista de casillas y el conjunto inicial de
silenciados. El diálogo solo la construye y le pide `guardar()`.
Cada fila es un evento de `eventos_sonido.EVENTOS` con su nombre llano;
destildar lo calla al guardar, sin reiniciar.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import wx

from ytchat.core import archivos
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.core import config as cfg
from ytchat.core.eventos_sonido import EVENTOS, NOMBRES
from ytchat.core.sonidos_ini import con_silenciados, silenciados
from ytchat.ui.accesibilidad import nombre_accesible
from ytchat.ui.tema import _T, _pintar
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


def _leer_texto(ruta: Path) -> str:
    """Texto de sounds.ini o «» si no se puede leer."""
    try:
        return ruta.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Sonidos: no se pudo leer %s: %s", ruta, exc)
        return ""


def _ruta_evento(evento: str) -> Path:
    """Archivo que suena para el botón: el override si lo hay, si no el
    del tema activo, igual que `config.cargar_sonidos` cuando no calla."""
    ruta = paths.sounds_ini()
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(ruta, encoding="utf-8")
    except configparser.Error as exc:
        logger.warning("Sonidos: sounds.ini roto: %s", exc)
    if parser.has_option("sonidos", evento):
        try:
            crudo = (parser.get("sonidos", evento) or "").strip()
        except configparser.Error:
            crudo = ""
        if crudo:
            candidata = Path(crudo)
            if not candidata.is_absolute():
                candidata = paths.carpeta_instalacion() / candidata
            return candidata
    return (paths.carpeta_sonidos() / "themes"
            / cfg.tema_sonido_actual() / f"{evento}.wav")


class PaginaSonidos:
    """Lista de sonidos con casilla y botón para oír el elegido."""

    def __init__(self):
        self._panel = None
        self._lista = None
        self._btn_oir = None
        self._inicial = set()

    def construir(self, libro) -> wx.ScrolledWindow:
        self._panel = wx.ScrolledWindow(
            libro, name="PagSonidos",
            style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        self._panel.SetScrollRate(0, 20)
        self._panel.SetBackgroundColour(_T.bg)
        self._panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)
        vs.Add(wx.StaticText(self._panel, label="&Sonidos:"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self._crear_lista(vs)
        self._btn_oir = wx.Button(
            self._panel, label="&Oír el sonido elegido", name="OirSonido")
        self._btn_oir.SetBackgroundColour(_T.btn)
        self._btn_oir.SetForegroundColour(_T.btn_t)
        self._btn_oir.Bind(wx.EVT_BUTTON, self._on_oir)
        vs.Add(self._btn_oir, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._panel.SetSizer(vs)
        self._cargar_filas()
        return self._panel

    def _crear_lista(self, vs):
        self._lista = wx.ListCtrl(
            self._panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            name="Sonidos")
        _pintar(self._lista, _T.field, _T.text)
        nombre_accesible(self._lista, "Sonidos")
        self._lista.InsertColumn(0, "Sonido", width=420)
        self._lista.EnableCheckBoxes(True)
        self._lista.SetMinSize((460, 300))
        self._lista.Bind(wx.EVT_SIZE, self._on_tamanio_lista)
        vs.Add(self._lista, 1, wx.EXPAND | wx.ALL, 10)

    def _on_tamanio_lista(self, event):
        # La única columna ocupa todo el cliente: sin franja vacía a la
        # derecha cuando la ventana se agranda.
        self._lista.SetColumnWidth(0, self._lista.GetClientSize().width)
        event.Skip()

    def _cargar_filas(self):
        texto = _leer_texto(paths.sounds_ini())
        self._inicial = silenciados(texto)
        self._lista.DeleteAllItems()
        for evento in EVENTOS:
            indice = self._lista.InsertItem(
                self._lista.GetItemCount(), NOMBRES[evento])
            self._lista.CheckItem(indice, evento not in self._inicial)
        if self._lista.GetItemCount():
            self._lista.Select(0)
            self._lista.Focus(0)

    def _marcados(self) -> set:
        """Eventos destildados, o sea callados, según la lista."""
        callados = set()
        for indice, evento in enumerate(EVENTOS):
            if indice >= self._lista.GetItemCount():
                break
            if not self._lista.IsItemChecked(indice):
                callados.add(evento)
        return callados

    def _on_oir(self, _evento=None):
        indice = self._lista.GetFirstSelected()
        if indice < 0 or indice >= len(EVENTOS):
            return
        try:
            _snd.reproducir_archivo(_ruta_evento(EVENTOS[indice]))
        except Exception as exc:
            logger.warning("Sonidos: no se pudo oír: %s", exc)

    def guardar(self) -> bool:
        """Escribe los cambios en sounds.ini y recarga. Sin cambios no
        escribe. Un fallo de escritura se registra y devuelve False."""
        callados = self._marcados()
        if callados == self._inicial:
            return True
        ruta = paths.sounds_ini()
        try:
            texto = ruta.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Sonidos: no se pudo leer %s: %s", ruta, exc)
            return False
        try:
            archivos.escribir_texto_atomico(
                ruta, con_silenciados(texto, callados, list(EVENTOS)))
        except OSError as exc:
            logger.warning("Sonidos: no se pudo escribir %s: %s", ruta, exc)
            return False
        try:
            _snd.cargar(cfg.cargar_sonidos())
        except Exception as exc:
            logger.warning("recargar sonidos: %s", exc)
        self._inicial = callados
        return True
