"""Pestaña Transmisión del Panel de OBS: preparar y manejar el directo."""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _, pgettext
from guyrapu.obs import (chat_en_video, consultas_transmision, obs_lanzador,
                          obs_panel_recarga, overlay_servidor,
                          transmision_directa)
from guyrapu.obs.estado_panel import resumir
from guyrapu.restream import ganchos, transmitir
from guyrapu.ui import gui_microfono, menu_transmision, tema
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.directo_panel import DirectoPanel
from guyrapu.ui.gui import caja_de_grupo
from guyrapu.ui.gui_elegir_destino import pedir_destino
from guyrapu.ui.preferencias_comun import boton
from guyrapu.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


class PaginaTransmision(wx.Panel):
    """Lo que hace la pestaña Transmisión: el directo y sus acciones."""

    def __init__(self, parent, principal, gestor, operaciones, al_terminar=None):
        super().__init__(parent, name="PaginaTransmision")
        self._principal = principal
        self._gestor = gestor
        self._operaciones = operaciones
        self._al_terminar = al_terminar
        self._puerto_ocupado_avisado = False
        self._supervisar = getattr(
            principal, "_supervisar_transmision", None)
        self._guardar_usuario = getattr(
            principal, "_guardar_usuario_tiktok", None)
        self._guardar_destino = getattr(
            principal, "_guardar_destino_transmision", None)
        self._leer_config()
        self._escena_al_aire = ""
        self._crear_controles()
        self._directo = DirectoPanel(
            self, self.btn_directo, operaciones, gestor,
            self._supervisar, self._guardar_usuario, self._guardar_destino,
            self._usuario_tiktok, obs_lanzador.asegurar_obs,
            self._datos_directo, self._al_cambiar_directo)
        self._enlazar_eventos()

    def _leer_config(self):
        config = getattr(self._principal, "_config", None) or {}
        self._usuario_tiktok = config.get("tiktok_usuario", "") or ""
        self._destino_guardado = config.get("transmision_destino", "") or ""

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self._crear_grupo_directo(caja)
        self.btn_restream = boton(
            self, pgettext("pestaña Transmisión", "Re&stream…"),
            _("Restream…"))
        caja.Add(self.btn_restream, 0, wx.ALL, 10)
        self.SetSizer(caja)
        self.acciones = (self.btn_directo, self.btn_restream)

    def _crear_grupo_directo(self, contenido):
        sizer, padre = caja_de_grupo(self, _("Directo"))
        etiqueta, nombre = transmision_directa.etiqueta(False)
        self.btn_directo = boton(padre, etiqueta, nombre)
        tema.boton_principal(self.btn_directo)
        sizer.Add(self.btn_directo, 0, wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_restream.Bind(wx.EVT_BUTTON, self._abrir_restream)

    def destino_actual(self):
        perfiles = ganchos.cargar_perfiles()
        return transmitir.destino_obs(self._destino_guardado, perfiles) or ""

    def _datos_directo(self):
        elegido = pedir_destino(
            self, self._destino_guardado, self._usuario_tiktok)
        if elegido is None:
            return None
        opcion, usuario = elegido
        if self._guardar_destino is not None:
            try:
                self._guardar_destino(opcion)
            except Exception as error:
                logger.warning(
                    "no se pudo guardar el destino de transmisión: %s", error)
        self._destino_guardado = opcion
        if opcion == "TikTok":
            if self._guardar_usuario is not None:
                try:
                    self._guardar_usuario(usuario)
                except Exception as error:
                    logger.warning(
                        "no se pudo guardar el usuario de TikTok: %s", error)
            self._usuario_tiktok = usuario
        return (opcion, self.destino_actual(), usuario)

    def _microfono_preferido(self):
        try:
            return gui_microfono.microfono_preferido(self._principal)
        except Exception:
            return ""

    def _al_cambiar_directo(self, foco=None):
        self._aplicar_visibilidad()
        self._refrescar_estado()

    def _aplicar_visibilidad(self):
        self.Layout()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def cargar(self, datos):
        """Pone el estado inicial que leyó la ventana."""
        self._aplicar_datos(datos)

    def enfocar_inicial(self):
        self.btn_directo.SetFocus()

    def cerrar_directo(self):
        self._directo.cerrar()

    def _refrescar_estado(self, anunciar_titular=False):
        destino = self.destino_actual()
        preferido = self._microfono_preferido()
        self._en_hilo(
            lambda: consultas_transmision.leer_estado(
                self._gestor, destino, preferido),
            lambda datos: self._estado_leido(datos, anunciar_titular))

    def _estado_leido(self, datos, anunciar_titular=False):
        self._aplicar_datos(datos)
        if anunciar_titular:
            anunciar(self._resumen(datos).titular)
        if self._al_terminar is not None:
            self._al_terminar()

    def _resumen(self, datos):
        escena = getattr(datos, "al_aire", "") or getattr(datos, "escena", "")
        return resumir(
            self.destino_actual(), datos.transmision, datos.grabacion,
            escena, datos.microfono, datos.silenciado, datos.problemas)

    def _aplicar_datos(self, datos):
        if not self._directo.deteniendo:
            self._directo.sincronizar(
                bool(datos.transmision.get("outputActive", False)))
        escena = getattr(datos, "al_aire", "") or getattr(datos, "escena", "")
        self._escena_al_aire = escena
        self._aplicar_visibilidad()
        self.sincronizar_chat(datos)

    def sincronizar_chat(self, datos):
        """Enciende o apaga el servicio según lo que OBS tenga en ese momento.

        Lo llaman todas las lecturas de estado del panel. Encender o apagar
        solo no anuncia nada y no mueve el foco.
        """
        accion = chat_en_video.decidir(
            bool(getattr(datos, "tiene_chat", False)),
            overlay_servidor.esta_encendido(),
            bool(getattr(self._gestor, "conectado", False)))
        if accion == chat_en_video.ENCENDER:
            self._encender_chat()
        elif accion == chat_en_video.APAGAR:
            self._apagar_chat()

    def _encender_chat(self):
        config = getattr(self._principal, "_config", None) or {}
        puerto = chat_en_video.puerto_del_panel(config)
        try:
            overlay_servidor.encender(puerto)
        except overlay_servidor.OverlayPuertoOcupadoError:
            self._avisar_puerto_ocupado(puerto)
            return
        self._guardar_chat_activo(True)
        diagnostico.crear_hilo(
            obs_panel_recarga.recargar_fuente_panel, "RecargarPanelObs").start()

    def _apagar_chat(self):
        overlay_servidor.apagar()
        self._guardar_chat_activo(False)

    def _guardar_chat_activo(self, activo):
        config = getattr(self._principal, "_config", None)
        if config is not None:
            config["overlay_activo"] = bool(activo)
        from guyrapu.ui import gui as _gui
        _gui.guardar_opcion(_gui.RUTA_CONFIG, "overlay", "activo",
                            "true" if activo else "false")

    def _avisar_puerto_ocupado(self, puerto):
        if self._puerto_ocupado_avisado:
            return
        self._puerto_ocupado_avisado = True
        sound_player.reproducir("error")
        anunciar(_("No se pudo activar el chat en el vídeo: el puerto {puerto} "
                   "está en uso. Cámbialo en Preferencias, categoría "
                   "OBS.").format(puerto=puerto))

    def _abrir_restream(self, event):
        menu_transmision.abrir_restream(self._principal)
