"""Piezas de construcción que comparten todas las páginas de Preferencias."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.ui.accesibilidad import nombre_accesible
from bellbird.ui import tema
from bellbird.ui.tema import _T

logger = diagnostico.obtener_logger(__name__)


def nombre_de_etiqueta(etiqueta) -> str:
    """El nombre accesible de un rótulo, sin la letra de acceso ni los dos puntos."""
    return etiqueta.replace("&", "").rstrip(":")


def grilla_campos():
    """Grilla de rótulo, campo y botón con la columna central creciente."""
    grilla = wx.FlexGridSizer(0, 3, 8, 8)
    grilla.AddGrowableCol(1, 1)
    return grilla


def fila_grilla(grilla, rotulo, control, boton=None):
    """Agrega a la grilla una fila de rótulo ya creado, campo y botón opcional."""
    grilla.Add(rotulo, 0, wx.ALIGN_CENTER_VERTICAL)
    grilla.Add(control, 0, wx.EXPAND)
    if boton is None:
        grilla.AddSpacer(0)
    else:
        grilla.Add(boton, 0, wx.EXPAND)


def lista_con_nombre(padre, etiqueta, opciones=None):
    """Un wx.Choice con su nombre accesible igual al rótulo."""
    control = wx.Choice(padre, choices=opciones or [],
                        name=nombre_de_etiqueta(etiqueta))
    nombre_accesible(control, control.GetName())
    return control


class EleccionTexto(wx.Choice):
    """Lista desplegable que guarda un valor de texto en vez del índice.

    La tabla de opciones simples habla con `SetValue` y `GetValue`, igual que
    una casilla o un contador. Acá se traduce entre el valor guardado y la
    etiqueta que se lee.
    """

    def __init__(self, parent, opciones, normalizar=None, **kwargs):
        self._valores = tuple(valor for valor, _etiqueta in opciones)
        self._normalizar = normalizar or (lambda valor: str(valor))
        super().__init__(parent, choices=[etiqueta for _valor, etiqueta
                                          in opciones], **kwargs)

    def SetValue(self, valor) -> None:
        try:
            indice = self._valores.index(self._normalizar(valor))
        except ValueError:
            indice = 0
        self.SetSelection(indice)

    def GetValue(self) -> str:
        indice = self.GetSelection()
        if 0 <= indice < len(self._valores):
            return self._valores[indice]
        return self._valores[0]


# Ancho al que se parten las notas de cada página. Con 560 desbordaban el área
# visible (unos 490 px) y no hay desplazamiento horizontal.
ANCHO_NOTA = 450


def crear_panel(parent, name):
    # Página desplazable (solo vertical): la de Atajos mide más de 1200 px
    # y en un wx.Panel fijo dos tercios de sus botones quedaban fuera del
    # alcance del ratón. El foco (Tab) desplaza solo hasta el control.
    p = wx.ScrolledWindow(parent, name=name, style=wx.TAB_TRAVERSAL | wx.VSCROLL)
    p.SetScrollRate(0, 20)
    p.SetBackgroundColour(_T.bg)
    p.SetForegroundColour(_T.text)
    return p


def _rotulos_de(ventana):
    for hijo in ventana.GetChildren():
        if isinstance(hijo, wx.StaticText):
            yield hijo
        yield from _rotulos_de(hijo)


def _igualar_rotulos(zona):
    rotulos = list(_rotulos_de(zona))
    ancho = max((rotulo.GetBestSize().GetWidth() for rotulo in rotulos),
                default=0)
    for rotulo in rotulos:
        rotulo.SetMinSize((ancho, -1))


def ajustar_zona(ventana, zona, contenido):
    """Recalcula el alto mínimo de la zona según lo que está visible."""
    alto = min(contenido.CalcMin().GetHeight(),
               wx.Display(ventana).GetClientArea().GetHeight() - 120)
    zona.SetMinSize((-1, alto))


def fijar_zona(ventana, zona, contenido):
    """Fija el sizer de la zona y un alto que no tape la barra de tareas."""
    zona.SetSizer(contenido)
    _igualar_rotulos(zona)
    # Fit mide un ScrolledWindow por su mínimo, no por su contenido: sin
    # este mínimo el diálogo nace colapsado y solo se ven los botones.
    ajustar_zona(ventana, zona, contenido)


def fila_label(p, texto):
    lbl = wx.StaticText(p, label=texto)
    lbl.SetForegroundColour(_T.text)
    return lbl


def fila_botones(botones, borde=6):
    fila = wx.WrapSizer(wx.HORIZONTAL)
    for boton in botones:
        fila.Add(boton, 0, wx.RIGHT, borde)
    return fila


def fila_horizontal(controles, borde=4):
    fila = wx.BoxSizer(wx.HORIZONTAL)
    for control in controles:
        fila.Add(control, 0, wx.ALL, borde)
    return fila


def mostrar_fila(fila, visible, foco):
    for hijo in fila.GetChildren():
        ventana = hijo.GetWindow()
        if ventana is None:
            continue
        if not visible and ventana.HasFocus():
            foco.SetFocus()
        fila.Show(ventana, visible)
    fila.Layout()


def mostrar_control(control, visible, foco):
    if not visible and control.HasFocus():
        foco.SetFocus()
    control.Show(visible)
    sizer = control.GetContainingSizer()
    if sizer is not None:
        sizer.Show(control, visible)


class CampoEstado(wx.TextCtrl):
    """Cuadro de solo lectura para el estado, con su primera línea en negrita."""

    def __init__(self, padre, nombre, lineas=6):
        super().__init__(
            padre, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name=nombre)
        self.SetMinSize((-1, lineas * self.GetCharHeight() + 8))

    def mostrar(self, estado):
        texto = "\n".join((estado.titular, *estado.lineas))
        self.SetValue(texto)
        color = tema._T.red if estado.tono == "aviso" else tema._T.primary
        self.SetStyle(0, len(texto), self._atributo(None))
        self.SetStyle(0, len(estado.titular), self._atributo(color, True))

    def _atributo(self, color, negrita=False):
        atributo = wx.TextAttr()
        atributo.SetFont(self.GetFont().Bold() if negrita else self.GetFont())
        if color is not None and not tema.ALTO_CONTRASTE:
            atributo.SetTextColour(color)
        return atributo


def fila_campo(sizer, rotulo, control, proporcion=0, boton=None):
    fila = wx.BoxSizer(wx.HORIZONTAL)
    fila.Add(rotulo, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
    fila.Add(control, 1, wx.EXPAND | wx.ALL, 6)
    if boton is not None:
        fila.Add(boton, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
    sizer.Add(fila, proporcion, wx.EXPAND, 0)
    return fila


def boton(panel, etiqueta, nombre, identificador=wx.ID_ANY):
    return wx.Button(panel, identificador, etiqueta, name=nombre)


def opciones_con_elegida(automatico, elegida, encontradas) -> list:
    """El desplegable con la elegida conservada y las halladas sin repetir."""
    opciones = [automatico]
    for fuente in (elegida, *(encontradas or ())):
        if fuente and fuente not in opciones:
            opciones.append(fuente)
    return opciones


def _ancho_categorias(libro, lista):
    textos = [libro.GetPageText(i) for i in range(libro.GetPageCount())]
    if not textos:
        return 0
    medidos = [lista.GetTextExtent(t)[0] for t in textos]
    return max(medidos) + wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X) + 28


def ajustar_ancho_categorias(libro, lista):
    """La lista muestra el nombre más largo entero, medido con el texto real."""
    try:
        ancho = _ancho_categorias(libro, lista)
        if ancho:
            lista.SetColumnWidth(0, ancho)
            lista.SetMinSize((ancho, lista.GetMinSize().height))
    except Exception as exc:
        logger.debug("ancho de las categorías: %s", exc)
