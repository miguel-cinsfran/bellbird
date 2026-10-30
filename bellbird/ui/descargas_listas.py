"""Pestañas Cola e Historial del administrador de descargas.

Cómo se muestran y se manejan las descargas en sus listas: la cola con su
progreso y cancelación por ítem, y el historial con las terminadas.
"""
from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.downloads import historial_descargas
from bellbird.ui.gui import anunciar, nombre_accesible, _T
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

_ESTADOS_FINALES = ("completado", "parcial", "cancelado", "error")
_ETIQUETAS_ESTADO = {"en_cola": N_("en cola"), "descargando": N_("descargando"),
                     "completado": N_("completado"), "parcial": N_("con errores"),
                     "cancelado": N_("cancelado"), "error": N_("error")}


def _texto_estado(estado: str, mensaje: str) -> str:
    """Celda «Estado» de la cola: el motivo acompaña a los estados finales."""
    texto = _(_ETIQUETAS_ESTADO.get(estado, estado)) if estado else ""
    if mensaje and estado in ("error", "cancelado", "completado", "parcial"):
        return _("{estado}: {mensaje}").format(estado=texto, mensaje=mensaje[:80])[:200]
    return texto[:200]


def _formatear_velocidad(velocidad) -> str:
    """«850 KB/s» o «3 MB/s», sin decimales porque el lector los lee mal."""
    if not velocidad or velocidad <= 0:
        return ""
    if velocidad < 1024 * 1024:
        return f"{round(velocidad / 1024):.0f} KB/s"
    return f"{round(velocidad / (1024 * 1024)):.0f} MB/s"


def _formatear_tiempo(eta) -> str:
    """«quedan 2 minutos», «queda 1 minuto» o «quedan 45 segundos»."""
    if not eta:
        return ""
    segundos = max(0, int(eta))
    if segundos >= 60:
        minutos = int(round(segundos / 60))
        if minutos <= 1:
            return _("queda 1 minuto")
        return _("quedan {n} minutos").format(n=minutos)
    segundos = int(round(segundos / 5)) * 5
    if segundos <= 0:
        return ""
    return _("quedan {n} segundos").format(n=segundos)


def texto_de_item(item) -> str:
    """Celda «Estado» de un ítem: estado, vídeo de la lista, velocidad y tiempo."""
    if item.estado != "descargando":
        return _texto_estado(item.estado, item.mensaje)
    partes = [_("procesando") if item.procesando
              else _(_ETIQUETAS_ESTADO.get(item.estado, item.estado))]
    if item.total > 1:
        partes.append(_("vídeo {indice} de {total}").format(
            indice=item.indice, total=item.total))
    if not item.procesando:
        velocidad = _formatear_velocidad(item.velocidad)
        if velocidad:
            partes.append(velocidad)
        tiempo = _formatear_tiempo(item.eta)
        if tiempo:
            partes.append(tiempo)
    return ", ".join(partes)[:200]


class PaginaCola(wx.Panel):
    """Pestaña Cola: filas de descargas con su progreso y cancelación por ítem."""

    def __init__(self, parent, gestor):
        super().__init__(parent)
        self._gestor = gestor
        self._items_fila: dict[str, int] = {}   # item_id -> índice en ListCtrl
        self._fila_items: dict[int, str] = {}   # índice -> item_id
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                 name="ColaDescargas")
        nombre_accesible(self.lista, _("Cola de descargas"), msaa=False)
        self.lista.InsertColumn(0, _("Progreso"), width=100)
        self.lista.InsertColumn(1, _("Estado"), width=160)
        self.lista.InsertColumn(2, _("Nombre"), width=320)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)

        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_cancelar = wx.Button(self, label=_("C&ancelar descarga"),
                                      name="CancelarDescarga")
        self.btn_cancelar.SetBackgroundColour(_T.btn)
        self.btn_cancelar.SetForegroundColour(_T.btn_t)
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._on_cancelar)
        fila.Add(self.btn_cancelar, 0)
        vs.Add(fila, 0, wx.ALL, 6)
        self.SetSizer(vs)
        self._repoblar_lista()

    def _repoblar_lista(self) -> None:
        for item in self._gestor.lista():
            idx = self.lista.InsertItem(self.lista.GetItemCount(), f"{item.progreso:.0f} %")
            self.lista.SetItem(idx, 2, item.nombre[:300])
            self.lista.SetItem(idx, 1, texto_de_item(item))
            self._items_fila[item.id] = idx
            self._fila_items[idx] = item.id

    def refrescar(self) -> None:
        """Vuelca a cada fila el estado actual de su ítem. Solo escribe lo que
        cambió: reescribir celdas iguales hace hablar al lector sin motivo."""
        for item in self._gestor.lista():
            idx = self._items_fila.get(item.id)
            if idx is None:
                continue
            celdas = {0: f"{item.progreso:.0f} %", 1: texto_de_item(item)}
            if item.nombre:
                celdas[2] = item.nombre[:300]
            for columna, texto in celdas.items():
                if self.lista.GetItemText(idx, columna) != texto:
                    self.lista.SetItem(idx, columna, texto)

    def agregar_enlace(self, url: str) -> None:
        # Inserción optimista en la cola (estado «en_cola»); el temporizador
        # vuelca después el estado y el progreso del gestor.
        idx = self.lista.InsertItem(self.lista.GetItemCount(), "0 %")
        self.lista.SetItem(idx, 1, _("en cola"))
        self.lista.SetItem(idx, 2, url[:300])

        def _registrar_fila(item_id):
            self._items_fila[item_id] = idx
            self._fila_items[idx] = item_id

        self._gestor.encolar(url, lambda *_args: None, lambda *_args: None,
                             _registrar_fila)

    def _on_cancelar(self, _event):
        idx = self.lista.GetFirstSelected()
        if idx < 0:
            wx.MessageBox(_("Selecciona una descarga de la cola para cancelar."),
                          _("Nada seleccionado"), wx.OK | wx.ICON_INFORMATION, self)
            return
        item_id = self._fila_items.get(idx)
        if item_id is None:
            return
        item = self._gestor.obtener(item_id)
        if item is None or item.estado in _ESTADOS_FINALES:
            try:
                _snd.reproducir("error")
            except Exception as error:
                logger.debug("no se pudo reproducir el aviso de descarga terminada: %s", error)
            anunciar(_("La descarga ya terminó"))
            return
        self._gestor.cancelar(item_id)
        # El estado lo confirmará el propio hilo («cancelado»).
        anunciar(_("Cancelando descarga"))


class PaginaHistorial(wx.Panel):
    """Pestaña Historial: descargas terminadas y cómo vaciarlas."""

    def __init__(self, parent, ruta):
        super().__init__(parent)
        self._ruta = ruta
        self._historial = historial_descargas.cargar(self._ruta)
        vs = wx.BoxSizer(wx.VERTICAL)
        self.lista = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            name=_("Lista del historial de descargas"))
        nombre_accesible(self.lista, _("Lista del historial de descargas"),
                         msaa=False)
        self.lista.InsertColumn(0, _("Nombre"), width=360)
        self.lista.InsertColumn(1, _("Fecha"), width=180)
        self.lista.InsertColumn(2, _("Estado"), width=140)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)
        self.btn_vaciar = wx.Button(
            self, label=_("Vaciar &historial"),
            name=_("Vaciar historial"))
        self.btn_vaciar.SetBackgroundColour(_T.btn)
        self.btn_vaciar.SetForegroundColour(_T.btn_t)
        self.btn_vaciar.Bind(wx.EVT_BUTTON, self._on_vaciar_historial)
        vs.Add(self.btn_vaciar, 0, wx.ALL, 6)
        self.SetSizer(vs)
        self._repoblar_historial()

    def _repoblar_historial(self) -> None:
        for entrada in self._historial:
            self._agregar_fila_historial(entrada)

    def _agregar_fila_historial(self, entrada: dict) -> None:
        nombre, fecha, estado = historial_descargas.formatear(entrada)
        idx = self.lista.InsertItem(self.lista.GetItemCount(), nombre)
        self.lista.SetItem(idx, 1, fecha)
        self.lista.SetItem(idx, 2, estado)

    def mostrar_entrada(self, entrada: dict) -> None:
        """Refleja en la pestaña Historial una entrada recién persistida."""
        if not self or not self.lista:
            return
        self._historial = historial_descargas.agregar(self._historial, entrada)
        nombre, fecha, estado = historial_descargas.formatear(entrada)
        self.lista.InsertItem(0, nombre)
        self.lista.SetItem(0, 1, fecha)
        self.lista.SetItem(0, 2, estado)

    def _on_vaciar_historial(self, _event) -> None:
        cantidad = len(self._historial)
        mensaje = _("Borra los elementos del historial. No borra ningún archivo "
                    "descargado del disco, solo la lista. ¿Deseas continuar?")
        if wx.MessageBox(mensaje, _("Vaciar historial"),
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self) != wx.YES:
            return
        self._historial = []
        historial_descargas.guardar(self._ruta, self._historial)
        self.lista.DeleteAllItems()
        if cantidad == 1:
            anunciar(_("Se borró 1 elemento del historial"))
        else:
            anunciar(_("Se borraron {cantidad} elementos del historial").format(cantidad=cantidad))
