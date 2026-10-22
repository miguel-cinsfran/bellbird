"""Ventana Preguntar a la IA: conversación sobre capturas de OBS.

Modal con la lista de mensajes, el campo para escribir y sus botones.
La conversación vive lo que vive la ventana: al cerrarla se pierde.
"""

from __future__ import annotations

from datetime import datetime

import wx

from ytchat.ai import ajustes_ia
from ytchat.ai import catalogo
from ytchat.ai import claves
from ytchat.ai import consulta
from ytchat.ai import conversacion
from ytchat.ai import envio_ia
from ytchat.ai import proveedores
from ytchat.ai import ventana_ia
from ytchat.core import diagnostico
from ytchat.core import paths
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui import ia_privacidad
from ytchat.ui.gui import anunciar, nombre_accesible
from ytchat.ui.ia_agregar_captura import pedir_captura
from ytchat.voice.sound_player import reproducir

logger = diagnostico.obtener_logger(__name__)

TITULO = "Preguntar a la IA"
INTERVALO_AVISO_MS = 5000
INTERVALO_MELODIA_MS = 2000


class DialogoMensaje(wx.Dialog):
    def __init__(self, padre, texto):
        super().__init__(padre, title="Mensaje", name="DialogoMensaje")
        vs = wx.BoxSizer(wx.VERTICAL)
        self.txt = wx.TextCtrl(
            self, value=texto,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Mensaje completo")
        vs.Add(self.txt, 1, wx.EXPAND | wx.ALL, 10)
        self.btn = wx.Button(self, wx.ID_OK, "&Cerrar", name="Cerrar")
        vs.Add(self.btn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(vs)
        self.btn.Bind(wx.EVT_BUTTON, self._al_cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.txt.SetFocus()

    def _al_cerrar(self, _event) -> None:
        self.EndModal(wx.ID_OK)

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        event.Skip()


class VentanaIA(wx.Dialog):
    def __init__(self, padre, charla=None, descripcion=""):
        super().__init__(padre, title=TITULO, name="VentanaIA")
        self._charla = charla if charla is not None else conversacion.Conversacion()
        self._descripcion = descripcion or ""
        self._n_consulta = 0
        self._en_curso = False
        self._cerrada = False
        self._decir_analizando = True
        self._crear_controles()
        self._temporizador_melodia = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._al_temporizador_melodia,
                  self._temporizador_melodia)
        self._rehacer_lista()
        self.txt_mensaje.SetFocus()

    def _crear_controles(self) -> None:
        vs = wx.BoxSizer(wx.VERTICAL)
        self.rotulo_conv = wx.StaticText(self, label="Con&versación:")
        vs.Add(self.rotulo_conv, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.lst_conversacion = wx.ListBox(
            self, style=wx.LB_SINGLE, name="Conversación")
        nombre_accesible(self.lst_conversacion, "Conversación")
        vs.Add(self.lst_conversacion, 1, wx.EXPAND | wx.ALL, 10)
        self.rotulo_msg = wx.StaticText(self, label="&Mensaje:")
        vs.Add(self.rotulo_msg, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.txt_mensaje = wx.TextCtrl(
            self, name="Mensaje", style=wx.TE_PROCESS_ENTER)
        nombre_accesible(self.txt_mensaje, "Mensaje")
        vs.Add(self.txt_mensaje, 0, wx.EXPAND | wx.ALL, 10)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_enviar = wx.Button(self, wx.ID_ANY, "&Enviar",
                                    name="Enviar")
        self.btn_captura = wx.Button(self, wx.ID_ANY, "Agregar &captura",
                                     name="Agregar captura")
        self.btn_copiar = wx.Button(self, wx.ID_ANY, "C&opiar respuesta",
                                    name="Copiar respuesta")
        self.btn_nueva = wx.Button(self, wx.ID_ANY, "&Nueva conversación",
                                   name="Nueva conversación")
        self.btn_cerrar = wx.Button(self, wx.ID_CLOSE, "Ce&rrar",
                                    name="Cerrar")
        for boton in (self.btn_enviar, self.btn_captura, self.btn_copiar,
                      self.btn_nueva, self.btn_cerrar):
            fila.Add(boton, 0, wx.RIGHT, 6)
        vs.Add(fila, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(vs)
        self._temporizador = wx.Timer(self)
        self.lst_conversacion.Bind(wx.EVT_LISTBOX_DCLICK, self._al_doble_clic)
        self.lst_conversacion.Bind(wx.EVT_KEY_DOWN, self._al_tecla_lista)
        self.txt_mensaje.Bind(wx.EVT_TEXT_ENTER, self._al_enviar)
        self.btn_enviar.Bind(wx.EVT_BUTTON, self._al_enviar)
        self.btn_captura.Bind(wx.EVT_BUTTON, self._al_captura)
        self.btn_copiar.Bind(wx.EVT_BUTTON, self._al_copiar)
        self.btn_nueva.Bind(wx.EVT_BUTTON, self._al_nueva)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._al_cerrar)
        self.Bind(wx.EVT_TIMER, self._al_temporizador, self._temporizador)
        self.Bind(wx.EVT_CHAR_HOOK, self._al_tecla)
        self.Bind(wx.EVT_CLOSE, self._al_cerrar)

    def _rehacer_lista(self) -> None:
        visibles = ventana_ia.filas_visibles(self._charla.filas)
        self.lst_conversacion.Set(visibles)
        self.lst_conversacion.SetSelection(len(visibles) - 1)

    def _mostrar_mensaje(self) -> None:
        if not self._charla.filas:
            return
        indice = self.lst_conversacion.GetSelection()
        if indice == wx.NOT_FOUND:
            return
        dialogo = DialogoMensaje(
            self, self.lst_conversacion.GetString(indice))
        try:
            dialogo.ShowModal()
        finally:
            dialogo.Destroy()

    def _al_doble_clic(self, _event) -> None:
        self._mostrar_mensaje()

    def _al_tecla_lista(self, event) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._mostrar_mensaje()
            return
        event.Skip()

    def _al_enviar(self, _event=None) -> None:
        if self._en_curso or self._cerrada:
            return
        texto = self.txt_mensaje.GetValue()
        ajustes = ajustes_ia.leer(paths.config_ini())
        self._decir_analizando = ajustes.decir_analizando
        muestra = catalogo.cargar(
            paths.catalogo_ia(), paths.catalogo_ia_empaquetado())
        try:
            clave = claves.leer(ajustes.proveedor)
        except OSError as fallo:
            logger.warning("VentanaIA: sin clave: %s", fallo)
            clave = None
        try:
            preparada = consulta.preparar(
                self._charla, texto, ajustes, muestra, clave,
                self._descripcion)
        except (conversacion.SinCaptura, conversacion.SinTexto,
                consulta.FaltaConfiguracion) as fallo:
            anunciar(consulta.texto_de_error(fallo))
            reproducir("ia_error")
            self.txt_mensaje.SetFocus()
            return
        proveedor = proveedores.por_id(ajustes.proveedor)
        if proveedor is None:
            proveedor = proveedores.PROVEEDORES[0]
        if not ia_privacidad.confirmar(self, ajustes, proveedor.nombre):
            self.txt_mensaje.SetFocus()
            return
        reproducir("ia_enviada")
        self._en_curso = True
        self.btn_enviar.Disable()
        self.btn_captura.Disable()
        self._temporizador.Start(INTERVALO_AVISO_MS)
        self._temporizador_melodia.Start(INTERVALO_MELODIA_MS)
        numero = self._n_consulta
        diagnostico.crear_hilo(
            self._consultar_en_hilo, "VentanaIAConsultar",
            args=(numero, preparada, clave)).start()

    def _consultar_en_hilo(self, numero, preparada, clave) -> None:
        try:
            respuesta = envio_ia.enviar(
                preparada.pedido, clave, preparada.tiempo_espera)
        except Exception as error:
            wx.CallAfter(self._consulta_fallida, numero, error)
            return
        wx.CallAfter(self._consulta_lista, numero, preparada, clave,
                     respuesta)

    def _consulta_lista(self, numero, preparada, clave, respuesta) -> None:
        if self._cerrada or numero != self._n_consulta:
            return
        self._frenar_avisos()
        self._en_curso = False
        self.btn_enviar.Enable()
        self.btn_captura.Enable()
        try:
            texto = consulta.consultar(
                self._charla, preparada, clave,
                enviar=lambda *args: respuesta)
        except Exception as fallo:
            self._avisar_fallo(fallo)
            return
        self.txt_mensaje.ChangeValue("")
        self._rehacer_lista()
        reproducir("ia_respuesta")
        anunciar(texto)
        self.txt_mensaje.SetFocus()

    def _consulta_fallida(self, numero, error) -> None:
        if self._cerrada or numero != self._n_consulta:
            return
        self._frenar_avisos()
        self._en_curso = False
        self.btn_enviar.Enable()
        self.btn_captura.Enable()
        self._avisar_fallo(error)

    def _avisar_fallo(self, error) -> None:
        try:
            detalle = error.detalle
        except AttributeError:
            detalle = str(error)
        logger.warning("VentanaIA: falló la consulta: %s", detalle)
        reproducir("ia_error")
        anunciar(consulta.texto_de_error(error))

    def _al_temporizador(self, _event) -> None:
        if self._decir_analizando:
            anunciar(ventana_ia.TEXTO_ANALIZANDO, urgente=False)

    def _al_temporizador_melodia(self, _event) -> None:
        reproducir("ia_analizando")

    def _frenar_avisos(self) -> None:
        try:
            self._temporizador.Stop()
        except Exception as fallo:
            logger.warning("VentanaIA: no se pudo frenar el aviso: %s",
                           fallo)
        try:
            self._temporizador_melodia.Stop()
        except Exception as fallo:
            logger.warning("VentanaIA: no se pudo frenar la melodía: %s",
                           fallo)

    def _cancelar(self) -> None:
        self._n_consulta += 1
        self._en_curso = False
        self._frenar_avisos()
        try:
            self.btn_enviar.Enable()
            self.btn_captura.Enable()
        except Exception as fallo:
            logger.warning("VentanaIA: no se pudo habilitar: %s", fallo)

    def _cerrar(self) -> None:
        self._cancelar()
        self._cerrada = True
        self.EndModal(wx.ID_CLOSE)

    def _al_cerrar(self, event) -> None:
        if self._cerrada:
            event.Skip()
            return
        self._cerrar()

    def _al_tecla(self, event) -> None:
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            if self._en_curso:
                self._cancelar()
                reproducir("ia_cancelada")
                anunciar(ventana_ia.TEXTO_CANCELADA)
                return
            self._cerrar()
            return
        event.Skip()

    def _al_captura(self, _event=None) -> None:
        pedir_captura(self, self._captura_lista)

    def _captura_lista(self, resultado) -> None:
        if self._cerrada or resultado is None:
            return
        fuente, captura = resultado
        self._charla.agregar_captura(
            captura.jpeg, fuente, ventana_ia.hora_de(datetime.now()))
        self._rehacer_lista()
        reproducir("ia_captura")
        anunciar(ventana_ia.texto_captura_agregada(fuente))
        self.txt_mensaje.SetFocus()
        diagnostico.crear_hilo(
            self._pedir_descripcion_en_hilo,
            "VentanaIADescripcion").start()

    def _pedir_descripcion_en_hilo(self) -> None:
        gestor = GestorPanelObs()
        try:
            try:
                gestor.conectar()
                descripcion = gestor.descripcion_escena()
            except Exception as fallo:
                logger.warning("VentanaIA: sin descripción: %s", fallo)
                descripcion = ""
            finally:
                try:
                    gestor.cerrar()
                except Exception as fallo:
                    logger.warning("VentanaIA: no se pudo cerrar: %s",
                                   fallo)
        except Exception as fallo:
            logger.warning("VentanaIA: falló la descripción: %s", fallo)
            descripcion = ""
        wx.CallAfter(self._descripcion_lista, descripcion)

    def _descripcion_lista(self, descripcion) -> None:
        if self._cerrada:
            return
        self._descripcion = descripcion or ""

    def _al_copiar(self, _event=None) -> None:
        texto = ventana_ia.ultima_respuesta(self._charla)
        if texto is None:
            anunciar(ventana_ia.TEXTO_SIN_RESPUESTA)
            return
        try:
            if not wx.TheClipboard.Open():
                reproducir("ia_error")
                anunciar(ventana_ia.TEXTO_NO_COPIADA)
                return
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(texto))
                wx.TheClipboard.Flush()
            finally:
                wx.TheClipboard.Close()
        except Exception as fallo:
            logger.warning("VentanaIA: no se pudo copiar: %s", fallo)
            reproducir("ia_error")
            anunciar(ventana_ia.TEXTO_NO_COPIADA)
            return
        reproducir("copiar")
        anunciar(ventana_ia.TEXTO_COPIADA)

    def _al_nueva(self, _event=None) -> None:
        self._cancelar()
        if self._cerrada:
            return
        self._charla.nueva()
        self._descripcion = ""
        self._rehacer_lista()
        anunciar(ventana_ia.TEXTO_NUEVA)
        self.txt_mensaje.SetFocus()


def abrir_ventana(padre):
    from ytchat.ui import ia_consulta_rapida
    tomada = ia_consulta_rapida.tomar_conversacion(padre)
    if tomada is None:
        ventana = VentanaIA(padre)
    else:
        charla, descripcion = tomada
        ventana = VentanaIA(padre, charla, descripcion)
    try:
        ventana.ShowModal()
    finally:
        ventana._cancelar()
        try:
            ventana._frenar_avisos()
        except Exception as fallo:
            logger.warning("VentanaIA: no se pudo frenar el aviso: %s",
                           fallo)
        ventana.Destroy()
