"""Sección de la clave de IA de la página Inteligencia artificial.

Dueña de su estado y de sus controles: la página solo la crea, le avisa
cuándo cambió el proveedor y le pide la clave para probar. La clave vive
en el Administrador de credenciales y nunca se muestra entera.
"""

from __future__ import annotations

import wx

from ytchat.ai import claves
from ytchat.ai import opciones_ia
from ytchat.core import diagnostico
from ytchat.ui.gui import anunciar
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


class SeccionClaveIA:
    """Clave del proveedor elegido: guardada, nueva o por escribir."""

    def __init__(self, proveedor_actual, al_cambiar_clave):
        self._proveedor_actual = proveedor_actual
        self._al_cambiar_clave = al_cambiar_clave
        self._panel = None
        self._escribiendo = False

    def construir(self, panel, sizer):
        from ytchat.ui.gui_preferencias import _T
        self._panel = panel
        etiqueta = wx.StaticText(panel, label="Cla&ve")
        etiqueta.SetForegroundColour(_T.accent)
        sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_estado = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name="EstadoClaveIA")
        sizer.Add(self.txt_estado, 0,
                  wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.txt_clave = wx.TextCtrl(
            panel, style=wx.TE_PASSWORD, name="ClaveIA")
        sizer.Add(self.txt_clave, 0,
                  wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._crear_botones(panel, sizer)
        self.actualizar()

    def _crear_botones(self, panel, sizer):
        self.btn_guardar = wx.Button(
            panel, label="G&uardar clave", name="GuardarClaveIA")
        sizer.Add(self.btn_guardar, 0,
                  wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_guardar.Bind(wx.EVT_BUTTON, self._on_guardar)
        self.btn_nueva = wx.Button(
            panel, label="Escribir una clave &nueva", name="NuevaClaveIA")
        sizer.Add(self.btn_nueva, 0,
                  wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_nueva.Bind(wx.EVT_BUTTON, self._on_nueva)
        self.btn_borrar = wx.Button(
            panel, label="&Borrar la clave guardada", name="BorrarClaveIA")
        sizer.Add(self.btn_borrar, 0,
                  wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_borrar.Bind(wx.EVT_BUTTON, self._on_borrar)

    def actualizar(self):
        """Vuelve al estado que corresponde al proveedor elegido."""
        self._escribiendo = False
        self.txt_clave.SetValue("")
        self._mostrar()

    def clave_para_probar(self):
        """La escrita si se está escribiendo, si no la guardada, si no ""."""
        return self.clave_escrita() or self._guardada()

    def clave_escrita(self):
        """La escrita sin bordes si se está escribiendo, si no ""."""
        if self.txt_clave.IsShown():
            return self.txt_clave.GetValue().strip()
        return ""

    def revisar_para_probar(self, clave):
        """Valida la escrita y anuncia el problema, si lo hay.

        La guardada ya está guardada: no se valida. Devuelve True cuando
        se puede probar.
        """
        escrita = self.clave_escrita()
        if escrita:
            problema = opciones_ia.problema_de_clave(
                self._proveedor_actual(), escrita)
            if problema:
                _snd.reproducir("ia_error")
                anunciar(problema)
                return False
        if not clave:
            anunciar(opciones_ia.TEXTO_FALTA_CLAVE)
            return False
        return True

    def _guardada(self):
        try:
            return claves.leer(self._proveedor_actual().id) or ""
        except Exception as exc:
            logger.warning("IA: sin clave guardada: %s", exc)
            return ""

    def _mostrar(self):
        guardada = self._guardada()
        hay = bool(guardada)
        escribiendo = hay and self._escribiendo
        self.txt_estado.SetValue(opciones_ia.estado_de_clave(guardada))
        self.txt_estado.Show(hay and not escribiendo)
        self.txt_clave.Show(not hay or escribiendo)
        self.btn_guardar.Show(not hay or escribiendo)
        self.btn_nueva.Show(hay and not escribiendo)
        self.btn_borrar.Show(hay)
        if self._panel is not None:
            self._panel.Layout()

    def _on_nueva(self, event):
        self._escribiendo = True
        self._mostrar()
        self.txt_clave.SetFocus()

    def _on_guardar(self, event):
        clave = self.txt_clave.GetValue().strip()
        problema = opciones_ia.problema_de_clave(
            self._proveedor_actual(), clave)
        if problema:
            _snd.reproducir("ia_error")
            anunciar(problema)
            self.txt_clave.SetFocus()
            return
        proveedor = self._proveedor_actual()
        try:
            claves.guardar(proveedor.id, clave)
        except Exception as exc:
            logger.warning("IA: no se pudo guardar la clave: %s", exc)
            _snd.reproducir("ia_error")
            anunciar(opciones_ia.TEXTO_CLAVE_NO_GUARDADA)
            return
        self.txt_clave.SetValue("")
        self._escribiendo = False
        self._mostrar()
        self.txt_estado.SetFocus()
        anunciar(opciones_ia.TEXTO_CLAVE_GUARDADA)
        self._al_cambiar_clave()

    def _on_borrar(self, event):
        proveedor = self._proveedor_actual()
        mensaje = opciones_ia.TEXTO_CONFIRMAR_BORRADO.format(
            proveedor=proveedor.nombre)
        respuesta = wx.MessageBox(
            mensaje, "Borrar la clave",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self._panel)
        if respuesta != wx.YES:
            self.btn_borrar.SetFocus()
            return
        try:
            claves.borrar(proveedor.id)
        except Exception as exc:
            logger.warning("IA: no se pudo borrar la clave: %s", exc)
            _snd.reproducir("ia_error")
            anunciar(opciones_ia.TEXTO_CLAVE_NO_BORRADA)
            return
        self.txt_clave.SetValue("")
        self._escribiendo = False
        self._mostrar()
        self.txt_clave.SetFocus()
        anunciar(opciones_ia.TEXTO_CLAVE_BORRADA)
        self._al_cambiar_clave()
