"""Pestaña Transmisión del Panel de OBS: preparar y manejar el directo."""

from __future__ import annotations

import wx

from guyrapu.core.idioma import N_, _, pgettext
from guyrapu.obs import (consultas_transmision, obs_lanzador,
                          overlay_servidor, transmision_directa)
from guyrapu.obs.estado_panel import resumir
from guyrapu.obs.obs_panel import NOMBRE_FUENTE
from guyrapu.restream import ganchos, transmitir
from guyrapu.ui import gui_microfono, menu_transmision, tema
from guyrapu.ui.accesibilidad import anunciar, nombre_accesible
from guyrapu.ui.directo_panel import DirectoPanel
from guyrapu.ui.gui import caja_de_grupo
from guyrapu.ui.preferencias_comun import (
    boton, fila_campo, mostrar_control, mostrar_fila)

_PUERTO_PANEL_DEFECTO = 8730
_RUTA_PANEL_CHAT = "/chat"

_ETIQUETA_CHAT = N_("Mostrar &chat en el vídeo")


class PaginaTransmision(wx.Panel):
    """Lo que hace la pestaña Transmisión: el directo y sus acciones."""

    def __init__(self, parent, principal, gestor, operaciones, al_terminar=None):
        super().__init__(parent, name="PaginaTransmision")
        self._principal = principal
        self._gestor = gestor
        self._operaciones = operaciones
        self._al_terminar = al_terminar
        self._alternar_panel = getattr(principal, "_cambiar_overlay", None)
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
        self._perfiles = ganchos.cargar_perfiles()
        self._opciones = transmitir.opciones(self._perfiles)

    def _crear_controles(self):
        caja = wx.BoxSizer(wx.VERTICAL)
        self._filas = {}
        self._crear_grupo_directo(caja)
        self.btn_restream = boton(
            self, pgettext("pestaña Transmisión", "Re&stream…"),
            _("Restream…"))
        caja.Add(self.btn_restream, 0, wx.ALL, 10)
        self.SetSizer(caja)
        self.acciones = (
            self.cho_destino, self.txt_usuario_tiktok, self.btn_directo,
            self.chk_chat, self.btn_restream)

    def _crear_selector_destino(self, sizer, padre):
        rotulo_destino = wx.StaticText(padre, label=_("Transmitir &a:"))
        self.cho_destino = wx.Choice(
            padre,
            choices=[transmitir.texto(opcion) for opcion in self._opciones],
            name=_("Transmitir a"))
        nombre_accesible(self.cho_destino, _("Transmitir a"))
        self._filas["destino"] = fila_campo(
            sizer, rotulo_destino, self.cho_destino)

    def _crear_grupo_directo(self, contenido):
        sizer, padre = caja_de_grupo(self, _("Directo"))
        self._crear_selector_destino(sizer, padre)
        rotulo_usuario = wx.StaticText(padre, label=_("&Usuario de TikTok:"))
        self.txt_usuario_tiktok = wx.TextCtrl(
            padre, value=self._usuario_tiktok, name=_("Usuario de TikTok"))
        nombre_accesible(self.txt_usuario_tiktok, _("Usuario de TikTok"))
        self._filas["usuario"] = fila_campo(
            sizer, rotulo_usuario, self.txt_usuario_tiktok)
        etiqueta, nombre = transmision_directa.etiqueta(False)
        self.btn_directo = boton(padre, etiqueta, nombre)
        tema.boton_principal(self.btn_directo)
        sizer.Add(self.btn_directo, 0, wx.ALL, 6)
        self.chk_chat = wx.CheckBox(
            padre, label=_(_ETIQUETA_CHAT),
            name=_("Mostrar chat en el vídeo"))
        self.chk_chat.SetValue(overlay_servidor.esta_encendido())
        sizer.Add(self.chk_chat, 0, wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_restream.Bind(wx.EVT_BUTTON, self._abrir_restream)
        self.chk_chat.Bind(wx.EVT_CHECKBOX, self._alternar_chat)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_cambiar_destino)
        self.cho_destino.Bind(wx.EVT_SET_FOCUS, self._al_foco_destino)

    def _destino_elegido(self):
        """La opción elegida: un destino de OBS o «restream:<nombre>»."""
        seleccion = self.cho_destino.GetSelection()
        if seleccion == wx.NOT_FOUND or seleccion >= len(self._opciones):
            return None
        return self._opciones[seleccion]

    def destino_actual(self):
        return (transmitir.destino_obs(
            self._destino_elegido() or "", self._perfiles) or "")

    def _datos_directo(self):
        return (self._destino_elegido() or "",
                self.destino_actual(),
                self.txt_usuario_tiktok.GetValue())

    def _microfono_preferido(self):
        try:
            return gui_microfono.microfono_preferido(self._principal)
        except Exception:
            return ""

    def _al_cambiar_destino(self, event):
        self._directo.recordar_destino(self._destino_elegido() or "")
        self._aplicar_visibilidad()
        self._refrescar_estado(anunciar_titular=True)
        event.Skip()

    def _al_foco_destino(self, event):
        self._releer_perfiles()
        self._aplicar_visibilidad()
        event.Skip()

    def _releer_perfiles(self):
        """Relee los perfiles y cambia la lista solo si cambiaron.

        Conserva la opción elegida si sigue existiendo y no mueve el foco.
        """
        perfiles = ganchos.cargar_perfiles()
        opciones = transmitir.opciones(perfiles)
        if opciones == self._opciones:
            return
        elegida = self._destino_elegido()
        self._perfiles = perfiles
        self._opciones = opciones
        self._poner_opciones()
        self._seleccionar_opcion(elegida)

    def _poner_opciones(self):
        self.cho_destino.Set(
            [transmitir.texto(opcion) for opcion in self._opciones])

    def _seleccionar_opcion(self, opcion):
        if opcion in self._opciones:
            self.cho_destino.SetSelection(self._opciones.index(opcion))
        else:
            self.cho_destino.SetSelection(wx.NOT_FOUND)

    def _al_cambiar_directo(self, foco=None):
        self._aplicar_visibilidad()
        if foco == "usuario" and self.txt_usuario_tiktok.IsShown():
            self.txt_usuario_tiktok.SetFocus()
        self._refrescar_estado()

    def _aplicar_visibilidad(self):
        opcion = self._destino_elegido()
        transmitiendo = self._directo.transmitiendo
        mostrar_fila(self._filas["destino"], not transmitiendo,
                     self.btn_directo)
        mostrar_fila(self._filas["usuario"],
                     opcion == "TikTok" and not transmitiendo,
                     self.btn_directo)
        mostrar_control(
            self.chk_chat,
            opcion == "YouTube" and self._alternar_panel is not None,
            self.btn_directo)
        self.Layout()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _escena(self):
        return self._escena_al_aire

    def cargar(self, datos):
        """Pone el estado y el destino iniciales que leyó la ventana."""
        self._releer_perfiles()
        if self._destino_guardado in self._opciones:
            self._seleccionar_opcion(self._destino_guardado)
        elif datos.perfil in self._opciones:
            self._seleccionar_opcion(datos.perfil)
        else:
            self.cho_destino.SetSelection(wx.NOT_FOUND)
        self.chk_chat.SetValue(overlay_servidor.esta_encendido())
        self._aplicar_datos(datos)

    def enfocar_inicial(self):
        if self.cho_destino.IsShown():
            self.cho_destino.SetFocus()
        else:
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

    def _alternar_chat(self, event):
        if self._alternar_panel is None:
            return
        encender = self.chk_chat.GetValue()
        resultado = self._alternar_panel(encender)
        if not encender or not resultado:
            self.chk_chat.SetValue(bool(resultado) if not encender else False)
            return
        escena = self._escena()
        self._en_hilo(lambda: self._agregar_chat(escena),
                      self._chat_agregado)

    def _agregar_chat(self, escena):
        puerto = overlay_servidor.puerto_actual() or _PUERTO_PANEL_DEFECTO
        if NOMBRE_FUENTE in self._gestor.fuentes(escena):
            return False, escena
        url = f"http://127.0.0.1:{puerto}{_RUTA_PANEL_CHAT}"
        self._gestor.asegurar_fuente(escena, url, 460, 620)
        return True, escena

    def _chat_agregado(self, resultado):
        agregado, escena = resultado
        if agregado:
            anunciar(_("Chat en el vídeo agregado a la escena {escena}.")
                     .format(escena=escena))
        self._refrescar_estado()

    def _abrir_restream(self, event):
        menu_transmision.abrir_restream(self._principal)
