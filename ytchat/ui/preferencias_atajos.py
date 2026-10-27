"""Página Atajos del diálogo de Preferencias.

Dueña de sus botones, de la captura de combinaciones y de su guardado
propio. El diálogo la construye por composición.
"""

from __future__ import annotations

import wx

from ytchat.core import config as cfg
from ytchat.core.config import APP_NAME
from ytchat.ui import atajos_captura
from ytchat.ui.atajos_captura import etiqueta_de_accion
from ytchat.ui.gui import _T, anunciar, caja_de_grupo
from ytchat.ui.preferencias_comun import ANCHO_NOTA, crear_panel


_AREA_AYUDA = atajos_captura._AREA_AYUDA


class PaginaAtajos:
    """Página Atajos: captura y guardado de las combinaciones de teclas."""

    def __init__(self, ventana, config):
        self._ventana = ventana
        self._config = config
        self._capturando_atajo = None

    def construir(self, parent):
        p = crear_panel(parent, "PagAtajos")
        vs = wx.BoxSizer(wx.VERTICAL)

        nota = wx.StaticText(
            p, label=atajos_captura.NOTA_PAGINA, name="NotaAtajos")
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(ANCHO_NOTA)
        vs.Add(nota, 0, wx.ALL, 10)

        # Valores normalizados en memoria (lo que se edita y se guarda).
        raw = self._config.get("atajos_raw", {})
        self._valores_atajo: dict[str, str] = {}
        self._botones_atajo: dict[str, wx.Button] = {}
        for accion, default in cfg.todos_los_atajos_default().items():
            crudo = raw.get(accion, default)
            self._valores_atajo[accion] = (
                default if accion in cfg.ATAJOS_FIJOS
                else cfg._normalizar_atajo(crudo) or "")

        self._crear_grupos(p, vs)

        btn_restablecer = wx.Button(
            p, label="&Restablecer los atajos a los valores de fábrica",
            name="RestablecerAtajos")
        btn_restablecer.SetBackgroundColour(_T.btn)
        btn_restablecer.SetForegroundColour(_T.btn_t)
        btn_restablecer.Bind(wx.EVT_BUTTON, self._restablecer_atajos)
        vs.Add(btn_restablecer, 0, wx.ALL, 10)

        p.Bind(wx.EVT_CHAR_HOOK, self._on_tecla_captura)
        p.SetSizer(vs)
        return p

    def _crear_grupos(self, p, vs):
        for titulo, acciones in cfg.ATAJOS_GRUPOS:
            box, padre = caja_de_grupo(p, titulo)
            for accion in acciones:
                etiqueta = etiqueta_de_accion(accion)
                fija = accion in cfg.ATAJOS_FIJOS
                valor = self._valores_atajo.get(accion, "")
                sufijo = " (fija)" if fija else ""
                btn = wx.Button(
                    padre, name=f"Atajo_{accion}",
                    label=atajos_captura.etiqueta_boton(etiqueta, valor) + sufijo)
                btn.SetBackgroundColour(_T.btn); btn.SetForegroundColour(_T.btn_t)
                if fija:
                    btn.Disable()
                else:
                    btn.SetToolTip("Pulsa para capturar una nueva combinación.")
                    btn.Bind(wx.EVT_BUTTON,
                             lambda e, a=accion, et=etiqueta: self._capturar_atajo(a, et))
                    btn.Bind(wx.EVT_KILL_FOCUS, self._atajo_perdio_foco)
                self._botones_atajo[accion] = btn
                box.Add(btn, 0, wx.EXPAND | wx.ALL, 4)
            vs.Add(box, 0, wx.EXPAND | wx.ALL, 8)

    def _capturar_atajo(self, accion, etiqueta):
        self._capturando_atajo = (accion, etiqueta)
        boton = self._botones_atajo[accion]
        boton.SetLabel(f"{etiqueta}: pulsa la combinación")
        anunciar(atajos_captura.texto_de_espera(
            etiqueta, _AREA_AYUDA.get(cfg.ATAJOS_AREA.get(accion), "")))

    def _restaurar_etiqueta_atajo(self, accion, etiqueta):
        valor = self._valores_atajo.get(accion, "")
        sufijo = " (fija)" if accion in cfg.ATAJOS_FIJOS else ""
        self._botones_atajo[accion].SetLabel(
            atajos_captura.etiqueta_boton(etiqueta, valor) + sufijo)

    def _salir_captura_atajo(self, anunciar_cambio=False):
        if self._capturando_atajo is None:
            return
        accion, etiqueta = self._capturando_atajo
        self._capturando_atajo = None
        self._restaurar_etiqueta_atajo(accion, etiqueta)
        if anunciar_cambio:
            anunciar("Sin cambios")

    def _restablecer_atajos(self, event):
        from ytchat.core import config_predeterminada as _pred
        for accion, valor in _pred.seccion("atajos").items():
            if accion in cfg.ATAJOS_FIJOS:
                continue
            self._valores_atajo[accion] = valor
            self._restaurar_etiqueta_atajo(accion, etiqueta_de_accion(accion))
        anunciar("Atajos restablecidos a los valores de fábrica. Se aplican al pulsar Guardar.")

    def _atajo_perdio_foco(self, event):
        self._salir_captura_atajo()
        event.Skip()

    def _on_tecla_captura(self, event):
        if self._capturando_atajo is None:
            event.Skip()
            return
        k = event.GetKeyCode()
        mods = event.GetModifiers()
        if k == wx.WXK_ESCAPE:
            self._salir_captura_atajo(True)
            return
        if k in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_RAW_CONTROL):
            return
        if k == wx.WXK_TAB and mods == wx.MOD_NONE:
            self._salir_captura_atajo()
            event.Skip()
            return
        accion, etiqueta = self._capturando_atajo
        if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and mods == wx.MOD_NONE:
            estado, valor, texto = atajos_captura.resolver(
                accion, None, self._valores_atajo)
        else:
            combo = atajos_captura.combo_a_texto(mods, k)
            estado, valor, texto = atajos_captura.resolver(
                accion, combo, self._valores_atajo)
        anunciar(texto)
        if estado == "rechazado":
            wx.MessageBox(texto, APP_NAME, wx.OK | wx.ICON_ERROR, self._ventana)
            boton = self._botones_atajo[accion]
            boton.SetFocus()
            self._capturar_atajo(accion, etiqueta)
            return
        self._valores_atajo[accion] = valor
        self._capturando_atajo = None
        self._restaurar_etiqueta_atajo(accion, etiqueta)

    def guardar(self, fijar, en_memoria):
        # Los valores ya vienen validados desde la captura (área y conflicto).
        raw = en_memoria.setdefault("atajos_raw", {})
        for accion, valor in self._valores_atajo.items():
            if accion in cfg.ATAJOS_FIJOS:
                continue
            fijar("atajos", accion, valor)
            raw[accion] = valor
