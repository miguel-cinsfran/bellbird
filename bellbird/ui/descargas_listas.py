"""Página única de descargas del administrador.

Muestra en una sola lista lo que está en curso, lo que espera y lo
terminado, con filtro, menú contextual y acciones por fila.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core import sonidos_eventos
from bellbird.core.idioma import N_, _
from bellbird.downloads import filas_descargas
from bellbird.downloads import historial_descargas
from bellbird.ui import barra_progreso
from bellbird.ui.descargas_acciones import AccionesDescarga
from bellbird.ui.gui import nombre_accesible, _T, _tc
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

_ESTADOS_FINALES = ("completado", "parcial", "cancelado", "error")
_ETIQUETAS_ESTADO = {"en_cola": N_("en cola"), "descargando": N_("descargando"),
                     "completado": N_("completado"), "parcial": N_("con errores"),
                     "cancelado": N_("cancelado"), "error": N_("error")}


def _texto_estado(estado: str, mensaje: str) -> str:
    """Celda «Estado» de lo terminado: el motivo acompaña al estado."""
    texto = _(_ETIQUETAS_ESTADO.get(estado, estado)) if estado else ""
    if mensaje and estado in _ESTADOS_FINALES:
        texto = _("{estado}: {mensaje}").format(estado=texto, mensaje=mensaje[:80])
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
    """Celda «Estado» de un ítem activo: estado, vídeo, velocidad y tiempo."""
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


_FILTROS_ORDEN = (filas_descargas.TODAS, filas_descargas.EN_CURSO,
                 filas_descargas.EN_ESPERA, filas_descargas.COMPLETADAS,
                 filas_descargas.CON_ERRORES)


def _texto_filtro(filtro: str, cantidad: int) -> str:
    if filtro == filas_descargas.EN_CURSO:
        return _("En curso ({cantidad})").format(cantidad=cantidad)
    if filtro == filas_descargas.EN_ESPERA:
        return _("En espera ({cantidad})").format(cantidad=cantidad)
    if filtro == filas_descargas.COMPLETADAS:
        return _("Completadas ({cantidad})").format(cantidad=cantidad)
    if filtro == filas_descargas.CON_ERRORES:
        return _("Con errores ({cantidad})").format(cantidad=cantidad)
    return _("Todas ({cantidad})").format(cantidad=cantidad)


def _texto_progreso(fila) -> str:
    if fila.estado in ("descargando", "en_cola"):
        return f"{fila.progreso:.0f} %"
    if fila.estado == "completado":
        return "100 %"
    return ""


def _texto_estado_fila(fila) -> str:
    if fila.estado in ("descargando", "en_cola") and fila.item is not None:
        return texto_de_item(fila.item)
    return _texto_estado(fila.estado, fila.mensaje)


class PaginaDescargas(wx.Panel):
    """Lista única de descargas, con filtro y menú contextual."""

    def __init__(self, parent, gestor, ruta, preparar_opciones):
        super().__init__(parent)
        self._gestor = gestor
        self._ruta = ruta
        self._acciones = AccionesDescarga(
            gestor, ruta, preparar_opciones, self._tras_cambiar)
        self._historial = historial_descargas.cargar(self._ruta)
        self._filas: list = []
        self._claves: list[str] = []
        self._tramos: list[int] = []
        self._filtro = filas_descargas.TODAS
        vs = wx.BoxSizer(wx.VERTICAL)
        vs.Add(self._seccion_filtro(), 0, wx.EXPAND | wx.ALL, 8)
        vs.Add(self._seccion_lista(), 1, wx.EXPAND | wx.ALL, 8)
        vs.Add(self._seccion_botones(), 0, wx.ALL, 8)
        self.SetSizer(vs)
        self.refrescar()

    def _seccion_filtro(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(self, label=_("&Mostrar:"), name="EtiquetaMostrar")
        lbl.SetForegroundColour(_T.text)
        fila.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.cho_mostrar = wx.Choice(
            self, choices=[_texto_filtro(f, 0) for f in _FILTROS_ORDEN],
            name=_("Mostrar"))
        _tc(self.cho_mostrar)
        self.cho_mostrar.SetSelection(0)
        self.cho_mostrar.Bind(wx.EVT_CHOICE, self._on_filtro)
        fila.Add(self.cho_mostrar, 1, wx.EXPAND)
        return fila

    def _seccion_lista(self):
        self.lista = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
                                 name="ListaDescargas")
        nombre_accesible(self.lista, _("Lista de descargas"), msaa=False)
        self.lista.AssignImageList(
            barra_progreso.lista_de_imagenes(self.lista.GetBackgroundColour()),
            wx.IMAGE_LIST_SMALL)
        self.lista.InsertColumn(0, _("Progreso"), width=120)
        self.lista.InsertColumn(1, _("Estado"), width=160)
        self.lista.InsertColumn(2, _("Nombre"), width=320)
        self.lista.InsertColumn(3, _("Fecha"), width=140)
        self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_activar)
        self.lista.Bind(wx.EVT_KEY_DOWN, self._on_key)
        self.lista.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)
        return self.lista

    def _seccion_botones(self):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_cancelar = wx.Button(self, label=_("C&ancelar descarga"),
                                      name="CancelarDescarga")
        self.btn_cancelar.Bind(wx.EVT_BUTTON, self._on_cancelar)
        fila.Add(self.btn_cancelar, 0, wx.RIGHT, 8)
        self.btn_vaciar = wx.Button(self, label=_("Vaciar l&ista"),
                                    name="VaciarLista")
        self.btn_vaciar.Bind(wx.EVT_BUTTON, self._on_vaciar)
        fila.Add(self.btn_vaciar, 0)
        for boton in (self.btn_cancelar, self.btn_vaciar):
            boton.SetBackgroundColour(_T.btn)
            boton.SetForegroundColour(_T.btn_t)
        return fila

    def _on_filtro(self, _event):
        idx = self.cho_mostrar.GetSelection()
        if 0 <= idx < len(_FILTROS_ORDEN):
            self._filtro = _FILTROS_ORDEN[idx]
        self.refrescar()

    def refrescar(self) -> None:
        """Reconstruye las filas sin mover el foco ni la selección."""
        todas = filas_descargas.construir(self._gestor.lista(), self._historial)
        self._actualizar_choice(filas_descargas.cantidades(todas))
        filtradas = filas_descargas.filtrar(todas, self._filtro)
        deseadas = [f.clave for f in filtradas]
        sel = self.lista.GetFirstSelected()
        clave_sel = self._claves[sel] if 0 <= sel < len(self._claves) else None
        self._sincronizar(deseadas)
        self._filas = filtradas
        self._escribir_celdas(filtradas)
        self._restaurar(clave_sel, sel, deseadas)

    def _tras_cambiar(self) -> None:
        self._historial = historial_descargas.cargar(self._ruta)
        self.refrescar()

    def _actualizar_choice(self, cantidades: dict) -> None:
        for i, filtro in enumerate(_FILTROS_ORDEN):
            texto = _texto_filtro(filtro, cantidades.get(filtro, 0))
            if self.cho_mostrar.GetString(i) != texto:
                self.cho_mostrar.SetString(i, texto)

    def _sincronizar(self, deseadas: list) -> None:
        claves = list(self._claves)
        tramos = list(self._tramos)
        pasos = filas_descargas.pasos_para_sincronizar(claves, deseadas)
        for paso in pasos:
            if paso[0] == "borrar":
                self.lista.DeleteItem(paso[1])
                del claves[paso[1]]
                del tramos[paso[1]]
            else:
                self.lista.InsertItem(paso[1], "")
                claves.insert(paso[1], paso[2])
                tramos.insert(paso[1], -1)
        self._claves = deseadas
        self._tramos = tramos

    def _escribir_celdas(self, filtradas: list) -> None:
        for i, fila in enumerate(filtradas):
            celdas = {0: _texto_progreso(fila), 1: _texto_estado_fila(fila),
                      2: (fila.nombre or "")[:300],
                      3: filas_descargas.fecha_legible(fila.fecha)}
            for columna, texto in celdas.items():
                if self.lista.GetItemText(i, columna) != texto:
                    self.lista.SetItem(i, columna, texto)
            imagen = barra_progreso.tramo(fila.estado, fila.progreso)
            if self._tramos[i] != imagen:
                self.lista.SetItemImage(i, imagen)
                self._tramos[i] = imagen

    def _restaurar(self, clave_sel, sel: int, deseadas: list) -> None:
        if clave_sel in deseadas:
            indice = deseadas.index(clave_sel)
        elif clave_sel is not None and deseadas:
            indice = min(sel, len(deseadas) - 1)
        else:
            return
        if self.lista.GetFirstSelected() != indice:
            self.lista.Select(indice)
            self.lista.Focus(indice)

    def agregar_enlace(self, url: str) -> None:
        """Encola sin fila optimista: sale en el refresco."""
        self._gestor.encolar(url, lambda *_a: None, lambda *_a: None)
        self.refrescar()

    def agregar_entrada(self, _entrada: dict) -> None:
        """Refleja una entrada recién persistida."""
        self._historial = historial_descargas.cargar(self._ruta)
        self.refrescar()

    def _fila_elegida(self):
        idx = self.lista.GetFirstSelected()
        if idx < 0 or idx >= len(self._filas):
            return None
        return self._filas[idx]

    def abrir_archivo(self) -> None:
        self._acciones.abrir_archivo(self._fila_elegida())

    def abrir_carpeta(self) -> None:
        self._acciones.abrir_carpeta(self._fila_elegida())

    def reintentar(self) -> None:
        self._acciones.reintentar(self._fila_elegida())

    def volver_a_descargar(self) -> None:
        self._acciones.volver_a_descargar(self._fila_elegida())

    def copiar(self) -> None:
        self._acciones.copiar(self._fila_elegida())

    def cancelar(self) -> None:
        self._acciones.cancelar(self._fila_elegida())

    def eliminar(self) -> None:
        self._acciones.eliminar(self._fila_elegida())

    def cancelar_todas(self) -> None:
        self._acciones.cancelar_todas()

    def eliminar_completadas(self) -> None:
        self._acciones.eliminar_completadas()

    def _on_cancelar(self, _event):
        self._acciones.cancelar(self._fila_elegida())

    def _on_vaciar(self, _event) -> None:
        self._acciones.vaciar(self)

    def _on_activar(self, _event):
        fila = self._fila_elegida()
        if fila is not None and "abrir_archivo" in filas_descargas.acciones(fila):
            self.abrir_archivo()

    def _on_key(self, event):
        tecla = event.GetKeyCode()
        sel = self.lista.GetFirstSelected()
        total = self.lista.GetItemCount()
        if sonidos_eventos.es_orilla(tecla, sel, total):
            try:
                _snd.reproducir("orilla")
            except Exception as error:
                logger.debug("sin orilla: %s", error)
        if tecla == wx.WXK_DELETE:
            self.eliminar()
        elif tecla == wx.WXK_WINDOWS_MENU or (tecla == wx.WXK_F10 and event.ShiftDown()):
            self._mostrar_menu()
        else:
            event.Skip()

    def _on_context_menu(self, _event):
        self._mostrar_menu()

    def _mostrar_menu(self) -> None:
        fila = self._fila_elegida()
        permitidas = filas_descargas.acciones(fila) if fila is not None else ()
        menu = wx.Menu()
        self._agregar_acciones(menu, permitidas)
        if menu.GetMenuItemCount():
            menu.AppendSeparator()
        self._agregar_globales(menu)
        self.lista.PopupMenu(menu)
        menu.Destroy()

    def _agregar_acciones(self, menu, permitidas) -> None:
        textos = {"abrir_archivo": _("&Abrir archivo"),
                  "abrir_carpeta": _("Abrir car&peta"),
                  "cancelar": _("&Cancelar descarga"),
                  "reintentar": _("&Reintentar"),
                  "volver_a_descargar": _("&Volver a descargar"),
                  "copiar": _("Copiar &enlace"),
                  "eliminar": _("E&liminar de la lista")}
        llamadas = {"abrir_archivo": self.abrir_archivo,
                    "abrir_carpeta": self.abrir_carpeta,
                    "cancelar": self.cancelar,
                    "reintentar": self.reintentar,
                    "volver_a_descargar": self.volver_a_descargar,
                    "copiar": self.copiar, "eliminar": self.eliminar}
        orden = ("abrir_archivo", "abrir_carpeta", "cancelar", "reintentar",
                 "volver_a_descargar", "copiar", "eliminar")
        for clave in orden:
            if clave not in permitidas:
                continue
            ident = wx.NewIdRef()
            menu.Append(ident, textos[clave])
            menu.Bind(wx.EVT_MENU, _llamar(llamadas[clave]), id=ident)

    def _agregar_globales(self, menu) -> None:
        todas = wx.NewIdRef()
        menu.Append(todas, _("Cancelar &todas"))
        menu.Bind(wx.EVT_MENU, _llamar(self.cancelar_todas), id=todas)
        hechas = wx.NewIdRef()
        menu.Append(hechas, _("Eliminar c&ompletadas"))
        menu.Bind(wx.EVT_MENU, _llamar(self.eliminar_completadas), id=hechas)


def _llamar(funcion):
    return lambda _e: funcion()
