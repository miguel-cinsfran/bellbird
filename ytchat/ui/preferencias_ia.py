"""Página Inteligencia artificial del diálogo de Preferencias.

Mezcla sin estado propio: `gui_preferencias` hereda de acá. La clave del
proveedor elegido vive en el Administrador de credenciales y nunca en
config.ini; los otros siete valores van a la sección [ia] por
`ajustes_ia.guardar`, que conserva `privacidad_aceptada` y
`decir_analizando`.
"""

from __future__ import annotations

import wx

from ytchat.ai import ajustes_ia
from ytchat.ai import catalogo
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import envio_ia
from ytchat.ai import opciones_ia
from ytchat.ai import proveedores
from ytchat.ai import sondeo_gratis
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.ui.gui import ContadorAccesible, anunciar
from ytchat.ui.preferencias_ia_clave import SeccionClaveIA
from ytchat.ui.preferencias_ia_lista import ActualizacionModelosIA
from ytchat.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


# (atributo del control, sección, clave): los siete pares de [ia] que
# edita esta página. `tests/test_coherencia.py` los cuenta como pares
# con control; `privacidad_aceptada` y `decir_analizando` quedan fuera.
OPCIONES_IA = (
    ("cho_ia_proveedor", "ia", "proveedor"),
    ("txt_ia_direccion", "ia", "direccion"),
    ("cho_ia_modelo", "ia", "modelo"),
    ("txt_ia_pregunta", "ia", "pregunta"),
    ("cho_ia_largo", "ia", "largo"),
    ("sp_ia_tiempo", "ia", "tiempo_espera"),
    ("chk_ia_gratis", "ia", "solo_gratis"),
)


class PaginaIA:
    """Página Inteligencia artificial: proveedor, clave, modelo, pregunta, largo y espera."""

    def _pag_ia(self, parent):
        p = self._make_panel(parent, "PagIA")
        self._pag_ia_panel = p
        vs = wx.BoxSizer(wx.VERTICAL)
        self._ia_leer_estado()
        self._ia_proveedor(p, vs)
        self._ia_clave(p, vs)
        self._ia_modelo(p, vs)
        self.ia_lista = ActualizacionModelosIA(
            self.btn_ia_actualizar, self._ia_proveedor_actual,
            self._ia_lista_recibida)
        self._ia_pregunta(p, vs)
        self._ia_largo(p, vs)
        self._ia_mostrar_condicionales()
        p.SetSizer(vs)
        return p

    def _ia_leer_estado(self):
        self._ia_ajustes = ajustes_ia.leer(self._ruta)
        self._ia_muestra = catalogo.cargar(
            paths.catalogo_ia(), paths.catalogo_ia_empaquetado())
        self._ia_modelos_ids = []

    def _ia_proveedor(self, p, vs):
        vs.Add(self._fila_label(p, "&Proveedor"),
               0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.cho_ia_proveedor = wx.Choice(
            p, choices=[pr.nombre for pr in proveedores.PROVEEDORES],
            name="ProveedorIA")
        actual = proveedores.por_id(self._ia_ajustes.proveedor)
        if actual is None:
            actual = proveedores.PROVEEDORES[0]
        self.cho_ia_proveedor.SetSelection(
            proveedores.PROVEEDORES.index(actual))
        vs.Add(self.cho_ia_proveedor, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.cho_ia_proveedor.Bind(wx.EVT_CHOICE, self._on_ia_proveedor)
        self._ia_lbl_direccion = self._fila_label(
            p, "&Dirección del servicio")
        vs.Add(self._ia_lbl_direccion, 0, wx.LEFT | wx.RIGHT, 10)
        self.txt_ia_direccion = wx.TextCtrl(
            p, value=self._ia_ajustes.direccion, name="DireccionIA")
        vs.Add(self.txt_ia_direccion, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self._ia_leer_marcas()

    def _ia_leer_marcas(self):
        self._ia_marcas = sondeo_gratis.leer(
            paths.gratis_ia(), self._ia_proveedor_actual().id)

    def _ia_clave(self, p, vs):
        self.ia_clave = SeccionClaveIA(
            self._ia_proveedor_actual, self._ia_clave_cambiada)
        self.ia_clave.construir(p, vs)
        self.btn_ia_probar_clave = wx.Button(
            p, label="P&robar la clave", name="ProbarClaveIA")
        vs.Add(self.btn_ia_probar_clave, 0,
               wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_ia_probar_clave.Bind(
            wx.EVT_BUTTON, self._on_ia_probar_clave)

    def _ia_modelo(self, p, vs):
        vs.Add(self._fila_label(p, "&Modelo"), 0, wx.LEFT | wx.RIGHT, 10)
        self.cho_ia_modelo = wx.Choice(p, choices=[], name="ModeloIA")
        vs.Add(self.cho_ia_modelo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.cho_ia_modelo.Bind(wx.EVT_CHOICE, self._on_ia_modelo)
        self.chk_ia_gratis = wx.CheckBox(
            p, label="Solo gra&tuitos", name="SoloGratuitosIA")
        self.chk_ia_gratis.SetValue(bool(self._ia_ajustes.solo_gratis))
        vs.Add(self.chk_ia_gratis, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.chk_ia_gratis.Bind(wx.EVT_CHECKBOX, self._on_ia_gratis)
        self.btn_ia_actualizar = wx.Button(
            p, label="&Actualizar la lista de modelos",
            name="ActualizarModelosIA")
        vs.Add(self.btn_ia_actualizar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        vs.Add(self._fila_label(p, "&Otro modelo"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.txt_ia_otro = wx.TextCtrl(p, value="", name="OtroModeloIA")
        vs.Add(self.txt_ia_otro, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.txt_ia_otro.Bind(wx.EVT_TEXT, self._on_ia_otro)
        self.lbl_ia_aviso = wx.StaticText(p, label="", name="AvisoModeloIA")
        vs.Add(self.lbl_ia_aviso, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        filas = self._ia_filas()
        id_lista, texto_otro = opciones_ia.separar_modelo_guardado(
            self._ia_ajustes.modelo, filas)
        self.txt_ia_otro.ChangeValue(texto_otro)
        self._ia_mostrar_filas(filas, id_lista)
        self._ia_actualizar_aviso()

    def _ia_pregunta(self, p, vs):
        vs.Add(self._fila_label(p, "&Instrucción para las capturas"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.txt_ia_pregunta = wx.TextCtrl(
            p, value=self._ia_ajustes.pregunta, style=wx.TE_MULTILINE,
            name="PreguntaIA")
        vs.Add(self.txt_ia_pregunta, 0,
               wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_ia_restaurar = wx.Button(
            p, label="R&estaurar la instrucción", name="RestaurarPreguntaIA")
        vs.Add(self.btn_ia_restaurar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.btn_ia_restaurar.Bind(wx.EVT_BUTTON, self._on_ia_restaurar)

    def _ia_largo(self, p, vs):
        # Definido en gui_preferencias: se importa acá para evitar un import circular.
        from ytchat.ui.gui_preferencias import EleccionTexto
        vs.Add(self._fila_label(p, "&Largo de la respuesta"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.cho_ia_largo = EleccionTexto(
            p, (("corta", "Corta"), ("media", "Media"), ("larga", "Larga")),
            normalizar=lambda v: v if v in ajustes_ia.LARGOS else "media",
            name="LargoIA")
        self.cho_ia_largo.SetValue(self._ia_ajustes.largo)
        vs.Add(self.cho_ia_largo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        vs.Add(self._fila_label(p, "Tiempo de e&spera en segundos"),
               0, wx.LEFT | wx.RIGHT, 10)
        self.sp_ia_tiempo = ContadorAccesible(
            p, min=ajustes_ia.TIEMPO_MINIMO, max=ajustes_ia.TIEMPO_MAXIMO,
            name="TiempoIA")
        self.sp_ia_tiempo.SetValue(self._ia_ajustes.tiempo_espera)
        vs.Add(self.sp_ia_tiempo, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

    def _ia_proveedor_actual(self):
        i = self.cho_ia_proveedor.GetSelection()
        if 0 <= i < len(proveedores.PROVEEDORES):
            return proveedores.PROVEEDORES[i]
        return proveedores.PROVEEDORES[0]

    def _ia_id_en_lista(self):
        i = self.cho_ia_modelo.GetSelection()
        if 0 <= i < len(self._ia_modelos_ids):
            return self._ia_modelos_ids[i]
        return ""

    def _ia_filas(self):
        return opciones_ia.filas_modelos(
            self._ia_muestra, self._ia_proveedor_actual(),
            self.chk_ia_gratis.GetValue(), self._ia_marcas)

    def _ia_mostrar_filas(self, filas, elegir):
        self._ia_modelos_ids = [ident for ident, _et in filas]
        if filas:
            self.cho_ia_modelo.Set([et for _ident, et in filas])
        else:
            # Habilitado a propósito: uno deshabilitado sale del Tab y el
            # lector no lo dice. No es un modelo: `modelo_elegido` lo ignora.
            self.cho_ia_modelo.Set([opciones_ia.TEXTO_SIN_MODELOS])
        if elegir in self._ia_modelos_ids:
            self.cho_ia_modelo.SetSelection(
                self._ia_modelos_ids.index(elegir))
        elif filas:
            self.cho_ia_modelo.SetSelection(wx.NOT_FOUND)
        else:
            self.cho_ia_modelo.SetSelection(0)

    def _ia_refrescar_modelos(self):
        self._ia_mostrar_filas(self._ia_filas(), self._ia_id_en_lista())

    def _ia_modelo_actual(self):
        proveedor = self._ia_proveedor_actual()
        if proveedor.id_catalogo is None:
            return None
        elegido = (self.txt_ia_otro.GetValue() or "").strip()
        if not elegido:
            elegido = self._ia_id_en_lista()
        if not elegido:
            return None
        for modelo in catalogo.modelos(
                self._ia_muestra, proveedor.id_catalogo):
            if modelo.id == elegido:
                return modelo
        return None

    def _ia_actualizar_aviso(self):
        texto = opciones_ia.aviso_de_modelo(self._ia_modelo_actual())
        self.lbl_ia_aviso.SetLabel(texto)

    def _ia_mostrar_condicionales(self):
        proveedor = self._ia_proveedor_actual()
        self._ia_lbl_direccion.Show(proveedor.pide_direccion)
        self.txt_ia_direccion.Show(proveedor.pide_direccion)
        self.chk_ia_gratis.Show(
            not proveedor.gratis_por_clave or bool(self._ia_marcas))
        panel = getattr(self, "_pag_ia_panel", None)
        if panel is not None:
            panel.Layout()

    def _on_ia_proveedor(self, event):
        # Sin anunciar: el lector ya lee el valor del combinado.
        self._ia_leer_marcas()
        self._ia_mostrar_condicionales()
        self._ia_refrescar_modelos()
        self._ia_actualizar_aviso()
        self.ia_clave.actualizar()

    def _ia_clave_cambiada(self):
        proveedor = self._ia_proveedor_actual()
        try:
            sondeo_gratis.olvidar(paths.gratis_ia(), proveedor.id)
        except OSError as exc:
            logger.warning("IA: no se pudo olvidar el sondeo: %s", exc)
        self._ia_leer_marcas()
        self._ia_mostrar_condicionales()
        self._ia_refrescar_modelos()
        self._ia_actualizar_aviso()

    def _on_ia_modelo(self, event):
        self.txt_ia_otro.ChangeValue("")
        self._ia_actualizar_aviso()

    def _on_ia_otro(self, event):
        self._ia_actualizar_aviso()

    def _on_ia_gratis(self, event):
        # Sin anunciar: el lector ya lee la casilla.
        self._ia_refrescar_modelos()
        self._ia_actualizar_aviso()

    def _on_ia_restaurar(self, event):
        self.txt_ia_pregunta.SetValue(conversacion.PREGUNTA_INICIAL)
        anunciar(opciones_ia.TEXTO_INSTRUCCION_RESTAURADA)

    def _on_ia_probar_clave(self, event):
        clave = self.ia_clave.clave_para_probar()
        if not self.ia_clave.revisar_para_probar(clave):
            return
        self.btn_ia_probar_clave.Disable()
        anunciar(opciones_ia.TEXTO_PROBANDO)
        ajustes = self._ia_ajustes_de_controles()
        muestra = self._ia_muestra
        diagnostico.crear_hilo(
            lambda: self._ia_probar_en_hilo(ajustes, muestra, clave),
            "ProbarClaveIA").start()

    def _ia_probar_en_hilo(self, ajustes, muestra, clave):
        # La red nunca corre en el hilo de la interfaz.
        try:
            pedido = opciones_ia.pedido_de_prueba(ajustes, muestra, clave)
            respuesta = envio_ia.enviar(pedido, clave, ajustes.tiempo_espera)
        except Exception as exc:
            logger.warning("IA: falló la prueba con %s: %s",
                           ajustes.modelo, exc)
            wx.CallAfter(self._ia_prueba_lista, False,
                         consulta.texto_de_error(exc))
            return
        wx.CallAfter(self._ia_prueba_lista, True,
                     opciones_ia.TEXTO_PRUEBA_BIEN.format(
                         modelo=ajustes.modelo))

    def _ia_prueba_lista(self, bien, texto):
        if not self:   # el diálogo pudo cerrarse mientras se probaba
            return
        self.btn_ia_probar_clave.Enable()
        _snd.reproducir("ia_respuesta" if bien else "ia_error")
        anunciar(texto)

    def _ia_lista_recibida(self, muestra, marcas, proveedor):
        if not self:   # el diálogo pudo cerrarse mientras se descargaba
            return None
        self._ia_muestra = muestra
        if self._ia_proveedor_actual().id == proveedor.id:
            self._ia_marcas = marcas
        else:
            self._ia_leer_marcas()
        self._ia_mostrar_condicionales()
        self._ia_refrescar_modelos()
        self._ia_actualizar_aviso()
        return len(self._ia_filas())

    def _ia_ajustes_de_controles(self):
        actuales = ajustes_ia.leer(self._ruta)
        actuales.proveedor = self._ia_proveedor_actual().id
        actuales.direccion = self.txt_ia_direccion.GetValue().strip()
        actuales.modelo = opciones_ia.modelo_elegido(
            self._ia_id_en_lista(), self.txt_ia_otro.GetValue())
        actuales.tiempo_espera = int(self.sp_ia_tiempo.GetValue())
        return actuales

    def _guardar_ia(self):
        actuales = self._ia_ajustes_de_controles()
        actuales.pregunta = self.txt_ia_pregunta.GetValue()
        actuales.largo = self.cho_ia_largo.GetValue()
        actuales.solo_gratis = bool(self.chk_ia_gratis.GetValue())
        if not ajustes_ia.guardar(self._ruta, actuales):
            self._fallo_guardado = True
