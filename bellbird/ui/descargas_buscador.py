"""Pestaña de búsqueda en YouTube: un campo que busca o encola.

La búsqueda corre en un hilo y una nueva descarta la anterior.
"""

from __future__ import annotations

import time

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.downloads import busqueda_youtube
from bellbird.downloads.busqueda_youtube import (
    CANTIDAD_DEFECTO, Filtros, clasificar_entrada, ordenar, texto_detalles,
    texto_duracion, texto_fecha, texto_vistas)
from bellbird.downloads import busquedas_recientes
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.tema import _T, _tc
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)

_TIPOS = ((N_("Vídeos"), "videos"), (N_("Listas"), "listas"),
          (N_("Canales"), "canales"), (N_("En directo"), "directo"))
_DURACIONES = ((N_("Cualquiera"), ""), (N_("Menos de 4 minutos"), "corta"),
               (N_("De 4 a 20 minutos"), "media"),
               (N_("Más de 20 minutos"), "larga"))
_FECHAS = ((N_("Cualquiera"), ""), (N_("Hoy"), "hoy"),
           (N_("Esta semana"), "semana"), (N_("Este mes"), "mes"),
           (N_("Este año"), "anio"))
_ORDENES = ((N_("Relevancia"), "relevancia"), (N_("Fecha"), "fecha"),
            (N_("Vistas"), "vistas"), (N_("Duración"), "duracion"))
_CANTIDADES = tuple(str(n) for n in busqueda_youtube.CANTIDADES)


def _sonar_error() -> None:
    try:
        _snd.reproducir("error")
    except Exception as error:
        logger.debug("sin sonido de error: %s", error)


class PaginaBuscador(wx.Panel):
    """La pestaña de búsqueda, con su estado."""

    def __init__(self, parent, agregar_url, ruta_recientes):
        super().__init__(parent)
        self._agregar_url = agregar_url
        self._ruta = ruta_recientes
        self._recientes = busquedas_recientes.cargar(ruta_recientes)
        self._resultados = []
        self._texto = ""
        self._filtros = Filtros()
        self._cantidad = CANTIDAD_DEFECTO
        self._inicio = 1
        self._hay_mas = False
        self._generacion = 0
        self._crear_controles()
        self._cargar_opciones()

    def _crear_controles(self):
        vs = wx.BoxSizer(wx.VERTICAL)
        self._crear_campo(vs)
        self._crear_filtros(vs)
        self._crear_lista(vs)
        self._crear_pie(vs)
        self.SetSizer(vs)

    def _crear_campo(self, vs):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(self, label=_("B&uscar o pegar enlace:"))
        lbl.SetForegroundColour(_T.text)
        fila.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.campo = wx.ComboBox(
            self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER,
            name=_("Buscar o pegar enlace"))
        _tc(self.campo)
        self.campo.Bind(wx.EVT_TEXT_ENTER, self._on_buscar)
        fila.Add(self.campo, 1, wx.EXPAND)
        self.btn_buscar = wx.Button(self, label=_("&Buscar"), name="BuscarYoutube")
        self.btn_buscar.SetBackgroundColour(_T.btn)
        self.btn_buscar.SetForegroundColour(_T.btn_t)
        self.btn_buscar.Bind(wx.EVT_BUTTON, self._on_buscar)
        fila.Add(self.btn_buscar, 0, wx.LEFT, 6)
        vs.Add(fila, 0, wx.EXPAND | wx.ALL, 6)
        self.chk_filtros = wx.CheckBox(self, label=_("Mostrar fi&ltros"),
                                       name=_("Mostrar filtros"))
        self.chk_filtros.SetForegroundColour(_T.text)
        self.chk_filtros.Bind(wx.EVT_CHECKBOX, self._on_filtros)
        vs.Add(self.chk_filtros, 0, wx.ALL, 6)

    def _crear_filtros(self, vs):
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self._controles_filtros = []
        pares = (
            (_("Ti&po:"), _("Tipo"), _TIPOS),
            (_("Du&ración:"), _("Duración"), _DURACIONES),
            (_("Fec&ha:"), _("Fecha"), _FECHAS),
            (_("&Orden:"), _("Orden"), _ORDENES),
        )
        elecciones = []
        for texto, nombre, _opciones in pares:
            lbl = wx.StaticText(self, label=texto)
            lbl.SetForegroundColour(_T.text)
            fila.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            cho = wx.Choice(self, name=nombre)
            _tc(cho)
            fila.Add(cho, 1, wx.EXPAND | wx.RIGHT, 6)
            self._controles_filtros.extend((lbl, cho))
            elecciones.append(cho)
        (self.cho_tipo, self.cho_duracion,
         self.cho_fecha, self.cho_orden) = elecciones
        self.cho_orden.Bind(wx.EVT_CHOICE, self._on_orden)
        for control in self._controles_filtros:
            control.Show(False)
        vs.Add(fila, 0, wx.EXPAND | wx.ALL, 6)
        fila_cantidad = wx.BoxSizer(wx.HORIZONTAL)
        lbl_cantidad = wx.StaticText(self, label=_("Ca&ntidad:"))
        lbl_cantidad.SetForegroundColour(_T.text)
        fila_cantidad.Add(lbl_cantidad, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.cho_cantidad = wx.Choice(self, choices=list(_CANTIDADES),
                                     name=_("Cantidad"))
        _tc(self.cho_cantidad)
        fila_cantidad.Add(self.cho_cantidad, 0)
        vs.Add(fila_cantidad, 0, wx.ALL, 6)

    def _crear_lista(self, vs):
        self.lista = wx.ListCtrl(self, style=wx.LC_REPORT,
                                 name="ListaResultados")
        nombre_accesible(self.lista, _("Resultados de la búsqueda"), msaa=False)
        self.lista.InsertColumn(0, _("Título"), width=280)
        self.lista.InsertColumn(1, _("Canal"), width=160)
        self.lista.InsertColumn(2, _("Duración"), width=80)
        self.lista.InsertColumn(3, _("Vistas"), width=110)
        self.lista.InsertColumn(4, _("Fecha"), width=110)
        self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_elegir)
        self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_agregar)
        vs.Add(self.lista, 1, wx.EXPAND | wx.ALL, 6)

    def _crear_pie(self, vs):
        lbl = wx.StaticText(self, label=_("D&etalles:"))
        lbl.SetForegroundColour(_T.text)
        vs.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.txt_detalles = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Detalles"))
        _tc(self.txt_detalles)
        self.txt_detalles.SetMinSize((-1, 90))
        vs.Add(self.txt_detalles, 0, wx.EXPAND | wx.ALL, 6)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_agregar = wx.Button(self, label=_("&Agregar a la cola"), name="AgregarACola")
        self.btn_agregar.SetBackgroundColour(_T.btn)
        self.btn_agregar.SetForegroundColour(_T.btn_t)
        self.btn_agregar.Bind(wx.EVT_BUTTON, self._on_agregar)
        fila.Add(self.btn_agregar, 0, wx.RIGHT, 6)
        self.btn_mas = wx.Button(self, label=_("Mostrar &más"), name="MostrarMas")
        self.btn_mas.SetBackgroundColour(_T.btn)
        self.btn_mas.SetForegroundColour(_T.btn_t)
        self.btn_mas.Bind(wx.EVT_BUTTON, self._on_mas)
        self.btn_mas.Disable()
        fila.Add(self.btn_mas, 0)
        vs.Add(fila, 0, wx.ALL, 6)

    def _cargar_opciones(self):
        self.campo.Set(self._recientes)
        self.campo.SetValue("")
        for cho, opciones in ((self.cho_tipo, _TIPOS),
                             (self.cho_duracion, _DURACIONES),
                             (self.cho_fecha, _FECHAS),
                             (self.cho_orden, _ORDENES)):
            cho.Set([_(etiqueta) for etiqueta, _valor in opciones])
            cho.SetSelection(0)
        try:
            inicial = _CANTIDADES.index(str(self._cantidad))
        except ValueError:
            inicial = _CANTIDADES.index(str(CANTIDAD_DEFECTO))
        self.cho_cantidad.SetSelection(inicial)

    def _filtros_actuales(self) -> Filtros:
        if not self.chk_filtros.GetValue():
            return Filtros()

        def _elegido(cho, opciones):
            idx = cho.GetSelection()
            if 0 <= idx < len(opciones):
                return opciones[idx][1]
            return opciones[0][1]
        return Filtros(
            tipo=_elegido(self.cho_tipo, _TIPOS),
            duracion=_elegido(self.cho_duracion, _DURACIONES),
            fecha=_elegido(self.cho_fecha, _FECHAS),
            orden=_elegido(self.cho_orden, _ORDENES))

    def _cantidad_actual(self) -> int:
        idx = self.cho_cantidad.GetSelection()
        if 0 <= idx < len(_CANTIDADES):
            return int(_CANTIDADES[idx])
        return CANTIDAD_DEFECTO

    def _on_buscar(self, _event):
        texto = self.campo.GetValue()
        clase, valor = clasificar_entrada(texto)
        if clase == "vacio":
            _sonar_error()
            anunciar(_("Escribe una búsqueda o un enlace."))
            return
        if clase == "enlace":
            self._agregar_url(valor)
            self.campo.SetValue("")
            anunciar(_("Agregado a la cola"))
            return
        self._recientes = busquedas_recientes.agregar(self._recientes, valor)
        busquedas_recientes.guardar(self._ruta, self._recientes)
        self.campo.Set(self._recientes)
        self.campo.SetValue(valor)
        self._texto = valor
        self._filtros = self._filtros_actuales()
        self._cantidad = self._cantidad_actual()
        self._lanzar(mas=False)
        anunciar(_("Buscando"))

    def _lanzar(self, mas: bool) -> None:
        inicio = self._inicio if mas else 1
        if not mas:
            self._inicio = 1
            self._resultados = []
            self.lista.DeleteAllItems()
            self.txt_detalles.SetValue("")
            self.btn_mas.Disable()
        self._generacion += 1
        hilo = diagnostico.crear_hilo(
            self._buscar_en_hilo,
            "BusquedaYoutube",
            args=(self._generacion, self._texto, self._filtros,
                  inicio, self._cantidad, mas))
        hilo.start()

    def _buscar_en_hilo(self, generacion, texto, filtros, inicio, cantidad, mas):
        respuesta = busqueda_youtube.buscar(texto, filtros, inicio, cantidad)
        wx.CallAfter(self._al_volver, generacion, respuesta, mas)

    def _al_volver(self, generacion, respuesta, mas):
        if not self:
            return
        if generacion != self._generacion:
            return
        foco_en_mas = wx.Window.FindFocus() is self.btn_mas
        if respuesta.error:
            self._hay_mas = self._hay_mas and mas
            self.btn_mas.Enable(self._hay_mas)
            self.txt_detalles.SetValue(respuesta.error)
            _sonar_error()
            anunciar(respuesta.error)
            if foco_en_mas:
                self.lista.SetFocus()
            return
        vistos = {r.id for r in self._resultados}
        nuevos = [r for r in respuesta.resultados if r.id not in vistos]
        self._hay_mas = bool(respuesta.hay_mas)
        self.btn_mas.Enable(self._hay_mas)
        if mas:
            self._volver_mas(nuevos, foco_en_mas)
        else:
            self._volver_primera(nuevos, foco_en_mas)

    def _volver_primera(self, nuevos, foco_en_mas):
        self._resultados = ordenar(list(nuevos), self._filtros.orden)
        self._inicio = 1 + self._cantidad
        if not nuevos:
            self.txt_detalles.SetValue(_("Sin resultados"))
            anunciar(_("Sin resultados"))
            return
        self._agregar_filas(self._resultados)
        self._elegir(0)
        self._anunciar_cantidad(len(nuevos), mas=False)
        if foco_en_mas or wx.Window.FindFocus() in (self.campo, self.btn_buscar):
            self.lista.SetFocus()

    def _volver_mas(self, nuevos, foco_en_mas):
        self._inicio += self._cantidad
        if not nuevos:
            anunciar(_("No hay más resultados"))
            if foco_en_mas:
                self.lista.SetFocus()
            return
        for sel in self._seleccionados():
            self.lista.Select(sel, False)
        self._resultados.extend(nuevos)
        if self._filtros.orden == "relevancia":
            self._agregar_filas(nuevos)
            self._elegir(len(self._resultados) - len(nuevos))
        else:
            self._resultados = ordenar(self._resultados, self._filtros.orden)
            self.lista.DeleteAllItems()
            self._agregar_filas(self._resultados)
            self._elegir([r.id for r in self._resultados].index(nuevos[0].id))
        if foco_en_mas:
            self.lista.SetFocus()
        self._anunciar_cantidad(len(nuevos), mas=True)

    def _elegir(self, indice):
        self.lista.Select(indice)
        self.lista.Focus(indice)
        self.lista.EnsureVisible(indice)

    def _anunciar_cantidad(self, cuantos: int, mas: bool) -> None:
        if cuantos == 1:
            anunciar(_("1 resultado más") if mas else _("1 resultado"))
        elif mas:
            anunciar(_("{cantidad} resultados más").format(cantidad=cuantos))
        else:
            anunciar(_("{cantidad} resultados").format(cantidad=cuantos))

    def _on_mas(self, _event):
        if self._texto:
            self._lanzar(mas=True)

    def _on_orden(self, _event):
        idx = self.cho_orden.GetSelection()
        orden = _ORDENES[idx][1] if 0 <= idx < len(_ORDENES) else "relevancia"
        sel = self.lista.GetFirstSelected()
        elegido = self._resultados[sel].id if 0 <= sel < len(self._resultados) else None
        self._filtros = Filtros(
            self._filtros.tipo, self._filtros.duracion,
            self._filtros.fecha, orden)
        self._resultados = ordenar(self._resultados, orden)
        self.lista.DeleteAllItems()
        self._agregar_filas(self._resultados)
        if elegido is not None:
            for i, resultado in enumerate(self._resultados):
                if resultado.id == elegido:
                    self._elegir(i)
                    break

    def _on_filtros(self, _event):
        mostrar = self.chk_filtros.GetValue()
        for control in self._controles_filtros:
            control.Show(mostrar)
        self.Layout()

    def _on_elegir(self, _event):
        sel = self.lista.GetFirstSelected()
        if 0 <= sel < len(self._resultados):
            self.txt_detalles.SetValue(
                texto_detalles(self._resultados[sel], time.time()))

    def _on_agregar(self, _event):
        indices = self._seleccionados()
        if not indices:
            _sonar_error()
            anunciar(_("Selecciona un resultado."))
            return
        enlaces, rechazos = [], []
        for idx in indices:
            if 0 <= idx < len(self._resultados):
                resultado = self._resultados[idx]
                if resultado.tipo == "canal":
                    rechazos.append(_("Un canal no se puede agregar a la cola."))
                elif resultado.en_directo:
                    rechazos.append(_("Un directo en curso no se puede descargar."))
                elif resultado.programado:
                    rechazos.append(_("Este directo todavía no empezó."))
                else:
                    enlaces.append(resultado.url)
        for mensaje in dict.fromkeys(rechazos):
            _sonar_error()
            anunciar(mensaje)
        for enlace in enlaces:
            self._agregar_url(enlace)
        if len(enlaces) == 1:
            anunciar(_("Agregado a la cola"))
        elif enlaces:
            anunciar(_("{cantidad} agregados a la cola").format(
                cantidad=len(enlaces)))

    def _seleccionados(self) -> list:
        indices = []
        idx = self.lista.GetFirstSelected()
        while idx != -1:
            indices.append(idx)
            idx = self.lista.GetNextSelected(idx)
        return indices

    def _agregar_filas(self, nuevos) -> None:
        ahora = time.time()
        for resultado in nuevos:
            i = self.lista.InsertItem(self.lista.GetItemCount(),
                                      resultado.titulo)
            self.lista.SetItem(i, 1, resultado.canal)
            self.lista.SetItem(i, 2, texto_duracion(resultado.duracion))
            self.lista.SetItem(i, 3, texto_vistas(resultado.vistas))
            self.lista.SetItem(i, 4, texto_fecha(resultado.marca_tiempo, ahora))

    def fijar_texto(self, url: str | None) -> None:
        self.campo.SetValue(url or "")
