"""Diálogo «Administrador de descargas» (yt-dlp), accesible y nativo.

Diálogo modal con dos pestañas: buscar en YouTube y ver la cola con
progreso y acciones por ítem. El motor puro está en `descargas.py`
(sin wx); este módulo monta la UI y refresca la cola con un
temporizador.

Accesibilidad (regla de oro NVDA):
  - Cada control interactivo tiene `name=` accesible.
  - Los errores avisan con sonido, anuncio y texto en la columna
    Estado del `ListCtrl`. Nunca se re-lanza una excepción fuera
    del hilo de descarga.
  - Toda mutación de la GUI desde el hilo de descarga va con `wx.CallAfter`.

Apertura: `abrir(parent, url_inicial=None, abrir_en_bellbird=None, musica=None)`
desde `gui._abrir_descargas`.
"""
from __future__ import annotations

from datetime import datetime

import wx

from bellbird.core import diagnostico
from bellbird.core import config as cfg
from bellbird.core import paths
from bellbird.core.idioma import _
from bellbird.downloads.descargas import gestor
from bellbird.downloads import filas_descargas
from bellbird.downloads.motivo_error import frase_aviso_descarga
from bellbird.downloads import historial_descargas
from bellbird.downloads.opciones_formato import (
    BITRATES, FORMATOS, RESOLUCIONES, clase_de_calidad,
    etiquetas_de_calidad)
from bellbird.ui.descargas_buscador import PaginaBuscador
from bellbird.ui.descargas_listas import _ESTADOS_FINALES, PaginaDescargas
from bellbird.ui.buscador_acciones import anunciar_agregados
from bellbird.ui.gui import anunciar, nombre_accesible, _T, _tc
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


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
    "parcial": "descarga_parcial",
    "error": "descarga_fallida",
    "cancelado": "descarga_cancelada",
}
# Lo que suena mientras la descarga sigue en curso.
_SONIDO_EN_CURSO = {
    "descargando": "descarga_iniciada",
    "procesando": "descarga_procesando",
}
# Fines seguidos sin que la cola termine: con dos o más y la cola
# terminada, el aviso nombra la cola y el contador vuelve a 0.
_finales_seguidos = 0
# Cada 500 ms el diálogo abierto vuelca el estado del gestor a sus filas.
INTERVALO_REFRESCO_MS = 500

# El diálogo abierto (si lo hay) y los ítems ya llevados al historial. Viven a
# nivel de módulo porque las descargas sobreviven al diálogo: una que termina
# con el gestor cerrado también tiene que entrar en el historial.
_dialogo_activo = None
_registrados: set[str] = set()


def _ruta_historial():
    return paths.historial_descargas()


def _memoria_valida(valor, validos, defecto):
    """El valor si está entre los válidos, o el defecto."""
    return valor if valor in validos else defecto


def _pedidos_nuevos(pedidos, padre) -> list:
    """Los pedidos que entran: si alguno ya está en el historial, pregunta.

    Con No entran solo los nuevos. Sin repetidos no pregunta nada.
    """
    historial = historial_descargas.cargar(_ruta_historial())
    repetidos = [u for u in pedidos if filas_descargas.ya_descargado(u, historial)]
    if not repetidos:
        return list(pedidos)
    if len(repetidos) == 1:
        pregunta = _("Este vídeo ya está en el historial. ¿Agregar de todos modos?")
    else:
        pregunta = _("{cantidad} ya están en el historial. ¿Agregar de todos modos?").format(
            cantidad=len(repetidos))
    if wx.MessageBox(pregunta, _("Administrador de descargas"),
                     wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, padre) == wx.YES:
        return list(pedidos)
    return [u for u in pedidos if u not in repetidos]


def registrar_historial(item, estado: str, ruta=None) -> dict | None:
    """Persiste el fin de una descarga en el historial. Devuelve la entrada,
    o None si ese ítem ya estaba registrado."""
    if item is None or item.id in _registrados:
        return None
    _registrados.add(item.id)
    ruta = ruta or _ruta_historial()
    entrada = {
        "id": item.id,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "nombre": item.nombre or item.url,
        "url": item.url,
        "estado": estado,
        "carpeta": item.carpeta or cfg.obtener_opciones_descarga().get("carpeta", ""),
        "ruta": item.rutas[0] if item.rutas else "",
    }
    entradas = historial_descargas.agregar(historial_descargas.cargar(ruta), entrada)
    historial_descargas.guardar(ruta, entradas)
    return entrada


def _fin_descarga_en_gui(estado: str, mensaje: str, nombre: str, item) -> None:
    """Parte del aviso de fin que toca wx: corre en el hilo de la GUI."""
    global _finales_seguidos
    if estado in ("descargando", "procesando"):
        try:
            _snd.reproducir(_SONIDO_EN_CURSO[estado])
        except Exception as error:
            logger.debug("no se pudo reproducir el aviso en curso: %s", error)
        return
    frase = frase_aviso_descarga(estado, mensaje, nombre)
    if not frase:
        return
    sonido = _SONIDO_POR_FIN.get(estado, "descarga_cancelada")
    if estado in _ESTADOS_FINALES:
        _finales_seguidos += 1
        if filas_descargas.cola_terminada(gestor().lista()):
            if _finales_seguidos >= 2:
                if estado == "completado":
                    sonido = "cola_descargas_terminada"
                frase = _("{frase}. Cola de descargas terminada").format(frase=frase)
            _finales_seguidos = 0
    try:
        _snd.reproducir(sonido)
    except Exception as error:
        logger.debug("no se pudo reproducir el aviso de descarga: %s", error)
    anunciar(frase)
    if estado not in _ESTADOS_FINALES:
        return
    entrada = registrar_historial(item, estado)
    dialogo = _dialogo_activo
    if entrada is not None and dialogo is not None and dialogo._alive:
        dialogo.pagina_descargas.agregar_entrada(entrada)


def _avisar_fin_descarga(estado: str, mensaje: str, nombre: str, item=None) -> None:
    # Llega desde el hilo de descarga: el sonido, el anuncio y el historial
    # (que toca el ListCtrl del diálogo) van al hilo de la GUI.
    wx.CallAfter(_fin_descarga_en_gui, estado, mensaje, nombre, item)


def _suscribir_al_gestor() -> None:
    gestor().suscribir_fin(_avisar_fin_descarga)


class GestorDescargasDialog(wx.Dialog):
    """Diálogo principal del gestor de descargas."""

    def __init__(self, parent, url_inicial=None, abrir_en_bellbird=None, musica=None):
        global _dialogo_activo
        super().__init__(parent, title=_("Administrador de descargas"),
                         size=(860, 680),
                         name="DialogoGestorDescargas")
        self.SetBackgroundColour(_T.bg)
        self._alive = True
        self._abrir_en_bellbird, self._musica = abrir_en_bellbird, musica
        self._opciones = cfg.obtener_opciones_descarga()
        self._gestor = gestor()
        self._mem_resolucion = _memoria_valida(
            self._opciones.get("resolucion", 0), RESOLUCIONES, 0)
        self._mem_bitrate = _memoria_valida(
            self._opciones.get("bitrate", 192), BITRATES, 192)
        self._formato_visto = (self._opciones.get("formato") or "mp4")
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
            self.pagina_buscador.fijar_texto(url_inicial)
        wx.CallAfter(self.pagina_buscador.campo.SetFocus)
        self.Centre()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        panel = wx.Panel(self, name="PanelGestorDescargas")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        vs = wx.BoxSizer(wx.VERTICAL)

        vs.Add(self._seccion_listas(panel), 1, wx.EXPAND | wx.ALL, 10)
        vs.Add(self._seccion_opciones(panel), 0, wx.EXPAND | wx.ALL, 10)
        vs.Add(self._seccion_botones(panel), 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(vs)

    def _seccion_opciones(self, parent):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        lbl_fmt = wx.StaticText(parent, label=_("&Formato:"),
                                name="EtiquetaFormato")
        lbl_fmt.SetForegroundColour(_T.text)
        fila.Add(lbl_fmt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        etiquetas = [_(et) for et, _sin_uso in FORMATOS]
        valores = [v for _sin_uso, v in FORMATOS]
        self.cho_formato = wx.Choice(parent, choices=etiquetas,
                                     name=_("Formato"))
        _tc(self.cho_formato)
        actual = self._opciones.get("formato", "mp4")
        try:    self.cho_formato.SetSelection(valores.index(actual))
        except ValueError: self.cho_formato.SetSelection(0)
        self.cho_formato.Bind(wx.EVT_CHOICE, self._on_formato)
        fila.Add(self.cho_formato, 1, wx.EXPAND | wx.RIGHT, 12)
        lbl_cal = wx.StaticText(parent, label=_("Cali&dad:"),
                                name="EtiquetaCalidad")
        lbl_cal.SetForegroundColour(_T.text)
        fila.Add(lbl_cal, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.cho_calidad = wx.Choice(parent, choices=[], name=_("Calidad"))
        _tc(self.cho_calidad)
        fila.Add(self.cho_calidad, 1, wx.EXPAND)
        self._on_formato()   # llena la calidad y ajusta su habilitación
        return fila

    def _seccion_listas(self, parent):
        self.pestanas = wx.Notebook(parent, name="PestanasDescargas")
        self.pagina_buscador = PaginaBuscador(
            self.pestanas, self.agregar_urls, paths.busquedas_recientes(),
            self._al_abrir_en_bellbird, self._musica)
        self.pestanas.AddPage(self.pagina_buscador, _("Buscar en YouTube"))
        self.pagina_descargas = PaginaDescargas(
            self.pestanas, self._gestor, _ruta_historial(), self._preparar_opciones)
        self.pestanas.AddPage(self.pagina_descargas, _("Descargas"))
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

    def _guardar_calidad_previa(self) -> None:
        if getattr(self, "_formato_visto", None) is None:
            return
        clase = clase_de_calidad(self._formato_visto)
        sel = self.cho_calidad.GetSelection()
        if clase == "resolucion" and 0 <= sel < len(RESOLUCIONES):
            self._mem_resolucion = RESOLUCIONES[sel]
        elif clase == "bitrate" and 0 <= sel < len(BITRATES):
            self._mem_bitrate = BITRATES[sel]

    def _on_formato(self, _event=None):
        self._guardar_calidad_previa()
        idx = self.cho_formato.GetSelection()
        if idx < 0 or idx >= len(FORMATOS):
            return
        valor = FORMATOS[idx][1]
        self._formato_visto = valor
        self.cho_calidad.Clear()
        for etiqueta in etiquetas_de_calidad(valor):
            self.cho_calidad.Append(etiqueta)
        clase = clase_de_calidad(valor)
        if clase == "resolucion":
            try:    sel = RESOLUCIONES.index(self._mem_resolucion)
            except ValueError: sel = 0
        elif clase == "bitrate":
            try:    sel = BITRATES.index(self._mem_bitrate)
            except ValueError: sel = 0
        else:
            sel = -1
        if sel >= 0:
            self.cho_calidad.SetSelection(sel)
        self.cho_calidad.Enable(clase != "")

    def _opciones_actuales(self) -> dict:
        op = cfg.obtener_opciones_descarga()
        idx = self.cho_formato.GetSelection()
        formato = FORMATOS[idx][1] if 0 <= idx < len(FORMATOS) else "mp4"
        self._formato_visto = formato
        self._guardar_calidad_previa()
        op["formato"] = formato
        op["bitrate"] = self._mem_bitrate
        op["resolucion"] = self._mem_resolucion
        return op

    def _preparar_opciones(self) -> None:
        # Persistimos las opciones elegidas antes de encolar (así el Gestor
        # las ve). Si luego el usuario cambia el formato en medio, la nueva
        # descarga usará la nueva config.
        op = self._opciones_actuales()
        try:    cfg.guardar_opciones_descarga(op)
        except Exception as exc: logger.debug("guardar opciones: %s", exc)
        self._opciones = op
        self._gestor.set_opciones(op)

    def agregar_urls(self, urls, formato=None, titulo=None) -> int:
        """Encola esos enlaces, avisa lo que pasó y devuelve cuántos fueron.

        Con formato "audio" o "video" encola con ese formato sin mover
        lo elegido ni guardarlo. `titulo` es el del resultado, si es uno
        solo; el turno se mira antes de encolar.
        """
        pedidos = _pedidos_nuevos([u for u in (urls or []) if u], self)
        if not pedidos:
            return 0
        hay_turno = self._gestor.hay_turno()
        if formato in ("audio", "video"):
            elegidas = self._opciones_actuales()
            transitorias = dict(elegidas)
            transitorias["formato"] = "audio_original" if formato == "audio" else "mp4"
            self._gestor.set_opciones(transitorias)
            try:
                for url in pedidos:
                    self.pagina_descargas.agregar_enlace(url)
            finally:
                self._gestor.set_opciones(elegidas)
        else:
            self._preparar_opciones()
            for url in pedidos:
                self.pagina_descargas.agregar_enlace(url)
        anunciar_agregados(len(pedidos), titulo, hay_turno)
        return len(pedidos)

    def _al_abrir_en_bellbird(self, url: str) -> None:
        # Conectar con el modal abierto no anda: primero se cierra.
        callback = self._abrir_en_bellbird
        self._on_cerrar(None)
        if callback is not None:
            wx.CallAfter(callback, url)

    def _on_refresco(self, _event) -> None:
        if not self or not self._alive or not self.pagina_descargas.lista:
            return
        self.pagina_descargas.refrescar()

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
        try:
            self.pagina_buscador.detener_escucha()
        except Exception as error:
            logger.debug("no se pudo detener la escucha: %s", error)
        if _dialogo_activo is self:
            _dialogo_activo = None


def abrir(parent, url_inicial=None, abrir_en_bellbird=None, musica=None) -> bool:
    """Abre el gestor como modal y devuelve True si el usuario lo usó (siempre,
    salvo que falle la apertura). El diálogo persiste las opciones al cerrarse
    vía `cfg.guardar_opciones_descarga` desde los callbacks."""
    dlg = GestorDescargasDialog(parent, url_inicial=url_inicial,
                                abrir_en_bellbird=abrir_en_bellbird,
                                musica=musica)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
    return True
