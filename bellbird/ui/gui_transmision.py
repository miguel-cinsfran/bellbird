"""Panel accesible para preparar y manejar la transmisión en OBS."""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import (consultas_transmision, obs_estado, obs_lanzador,
                          overlay_servidor, transmision_directa)
from bellbird.obs.estado_panel import EstadoPanel, resumir
from bellbird.obs.obs_destinos import DESTINOS
from bellbird.obs.obs_panel import GestorPanelObs, NOMBRE_FUENTE
from bellbird.ui import gui_microfono, menu_transmision, paleta, tema
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.control_grabacion import ControlGrabacion
from bellbird.ui.directo_panel import DirectoPanel
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.gui_organizar_escena import OrganizarEscenaDialog
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui.preferencias_comun import (
    CampoEstado, ajustar_zona, boton, fijar_zona, fila_campo,
    fila_horizontal, mostrar_control, mostrar_fila)

logger = diagnostico.obtener_logger(__name__)

_PUERTO_PANEL_DEFECTO = 8730
_RUTA_PANEL_CHAT = "/chat"

_ETIQUETA_CHAT = N_("Mostrar &chat en el vídeo")
_ETIQUETA_SILENCIAR = N_("Si&lenciar")


class TransmisionDialog(wx.Dialog):

    def __init__(self, parent, gestor=None, alternar_panel=None,
                 supervisar=None, guardar_usuario=None, usuario_tiktok="",
                 asegurar=None, guardar_destino=None):
        super().__init__(parent, title=_("Panel de transmisión"),
                         name="DialogoTransmision")
        self._gestor = gestor or GestorPanelObs()
        self._asegurar = asegurar if asegurar is not None else obs_lanzador.asegurar_obs
        self._alternar_panel = alternar_panel
        self._supervisar = supervisar
        self._guardar_usuario = guardar_usuario
        self._guardar_destino = guardar_destino
        self._usuario_tiktok = usuario_tiktok or ""
        self._estado_actual = EstadoPanel("", "listo", ())
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo)
        self._crear_controles()
        self._silencio = gui_microfono.ControlSilencio(
            self._gestor, self.chk_silenciar, self._operaciones,
            self._microfono_preferido, self._refrescar_estado)
        self._directo = DirectoPanel(
            self, self.btn_directo, self._operaciones, self._gestor,
            self._supervisar, self._guardar_usuario, self._guardar_destino,
            self._usuario_tiktok, self._asegurar, self._datos_directo,
            self._al_cambiar_directo)
        self._enlazar_eventos()
        self.SetDefaultItem(None)
        self.Centre()
        paleta.pintar_ventana(self)
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelTransmision")
        caja = wx.BoxSizer(wx.VERTICAL)
        zona = wx.ScrolledWindow(panel, name="ZonaTransmision",
                                 style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        zona.SetScrollRate(0, 20)
        self._zona_desplazable = zona
        contenido = wx.BoxSizer(wx.VERTICAL)
        self._filas = {}
        self._crear_estado(zona, contenido)
        self._crear_grupo_directo(zona, contenido)
        self._crear_grupo_grabacion(zona, contenido)
        self._crear_grupo_microfono(zona, contenido)
        self._crear_grupo_escena(zona, contenido)
        fijar_zona(self, zona, contenido)
        caja.Add(zona, 1, wx.EXPAND)
        self.btn_organizar = boton(
            panel, _("&Organizar escena…"), _("Organizar escena…"))
        self.btn_mostrar_obs = boton(
            panel, _("Mostrar O&BS"), _("Mostrar OBS"))
        self.btn_actualizar = boton(
            panel, _("Ac&tualizar estado"), _("Actualizar estado"))
        self.btn_cerrar = boton(
            panel, _("Cerrar"), _("Cerrar"), wx.ID_CANCEL)
        caja.Add(fila_horizontal((self.btn_organizar, self.btn_mostrar_obs,
                                  self.btn_actualizar, self.btn_cerrar)),
                 0, wx.ALL, 10)
        panel.SetSizer(caja)
        self._acciones = (
            self.cho_destino, self.txt_usuario_tiktok, self.btn_directo,
            self.chk_chat, self.btn_grabar, self.btn_pausar,
            self.chk_silenciar, self.btn_microfono, self.cho_escena,
            self.btn_cambiar_escena, self.btn_organizar, self.btn_mostrar_obs,
            self.btn_actualizar, self.btn_cerrar)
        self.SetMinSize((600, -1))
        self._acomodar()

    def _crear_estado(self, zona, contenido):
        rotulo = wx.StaticText(zona, label=_("&Estado:"))
        self.txt_estado = CampoEstado(zona, _("Estado"))
        contenido.Add(rotulo, 0, wx.ALL, 6)
        contenido.Add(self.txt_estado, 0, wx.EXPAND | wx.LEFT | wx.RIGHT
                      | wx.BOTTOM, 6)

    def _crear_grupo_directo(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Directo"))
        rotulo_destino = wx.StaticText(padre, label=_("Transmitir &a:"))
        self.cho_destino = wx.Choice(padre, choices=list(DESTINOS),
                                     name=_("Transmitir a"))
        nombre_accesible(self.cho_destino, _("Transmitir a"))
        self._filas["destino"] = fila_campo(
            sizer, rotulo_destino, self.cho_destino)
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

    def _crear_grupo_grabacion(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Grabación"))
        self._grabacion = ControlGrabacion(
            padre, self._operaciones, self._gestor, self._refrescar_estado,
            self.btn_directo)
        self.btn_grabar = self._grabacion.boton
        self.btn_pausar = self._grabacion.pausar
        sizer.Add(fila_horizontal((self.btn_grabar, self.btn_pausar)),
                  0, wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _crear_grupo_microfono(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Micrófono"))
        self.chk_silenciar = wx.CheckBox(
            padre, label=_(_ETIQUETA_SILENCIAR),
            name=_("Silenciar micrófono"))
        self.btn_microfono = boton(
            padre, _("Elegir &micrófono…"), _("Elegir micrófono…"))
        sizer.Add(fila_horizontal((self.chk_silenciar, self.btn_microfono)),
                  0, wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _crear_grupo_escena(self, zona, contenido):
        sizer, padre = caja_de_grupo(zona, _("Escena"))
        rotulo_escena = wx.StaticText(padre, label=_("Esce&na:"))
        self.cho_escena = wx.Choice(padre, name=_("Escena"))
        nombre_accesible(self.cho_escena, _("Escena"))
        self._filas["escena"] = fila_campo(
            sizer, rotulo_escena, self.cho_escena)
        self.btn_cambiar_escena = boton(
            padre, _("Cambiar e&scena"), _("Cambiar escena"))
        sizer.Add(self.btn_cambiar_escena, 0, wx.ALL, 6)
        contenido.Add(sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)
        self.btn_cambiar_escena.Bind(wx.EVT_BUTTON, self._cambiar_escena)
        self.chk_chat.Bind(wx.EVT_CHECKBOX, self._alternar_chat)
        self.btn_microfono.Bind(
            wx.EVT_BUTTON,
            lambda evento: gui_microfono.abrir_microfono_obs(
                self.GetParent(), al_cerrar=self.btn_microfono.SetFocus))
        self.btn_organizar.Bind(wx.EVT_BUTTON, self._organizar_escena)
        self.btn_mostrar_obs.Bind(
            wx.EVT_BUTTON, lambda evento: menu_transmision.mostrar_obs())
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_cambiar_destino)
        self.Bind(wx.EVT_CLOSE, self._cerrar)

    def _activar(self, activo):
        for control in self._acciones:
            control.Enable(activo)
        self._aplicar_visibilidad()

    def _destino_elegido(self):
        seleccion = self.cho_destino.GetSelection()
        return DESTINOS[seleccion] if seleccion != wx.NOT_FOUND else None

    def _datos_directo(self):
        return (self._destino_elegido() or "",
                self.txt_usuario_tiktok.GetValue())

    def _microfono_preferido(self):
        try:
            return gui_microfono.microfono_preferido(self.GetParent())
        except Exception:
            return ""

    def _al_cambiar_destino(self, event):
        self._directo.recordar_destino(self._destino_elegido() or "")
        self._aplicar_visibilidad()
        self._refrescar_estado()
        event.Skip()

    def _al_cambiar_directo(self, foco=None):
        self._aplicar_visibilidad()
        if foco == "usuario" and self.txt_usuario_tiktok.IsShown():
            self.txt_usuario_tiktok.SetFocus()
        self._refrescar_estado()

    def _aplicar_visibilidad(self):
        destino = self._destino_elegido()
        transmitiendo = self._directo.transmitiendo
        mostrar_fila(self._filas["destino"], not transmitiendo,
                     self.btn_directo)
        mostrar_fila(self._filas["usuario"],
                     destino == "TikTok" and not transmitiendo,
                     self.btn_directo)
        mostrar_control(
            self.chk_chat,
            destino == "YouTube" and self._alternar_panel is not None,
            self.btn_directo)
        ajustar_zona(self, self._zona_desplazable,
                     self._zona_desplazable.GetSizer())
        self._acomodar()

    def _acomodar(self):
        self.Layout()
        self.Fit()
        self.SetSize((max(600, self.GetSize().GetWidth()),
                      self.GetSize().GetHeight()))

    def _mostrar_estado(self, estado):
        self._estado_actual = estado
        self.txt_estado.mostrar(estado)

    def _escribir_fallo(self, mensaje):
        self._mostrar_estado(EstadoPanel(mensaje, "aviso", ()))

    def _enfocar_tras_fallo(self):
        self.btn_actualizar.Enable(True)
        self.btn_actualizar.SetFocus()

    def _en_hilo(self, funcion, al_terminar=None):
        self._operaciones.en_hilo(funcion, al_terminar)

    def _fallo(self, mensaje):
        self._operaciones.fallo(mensaje)

    def _cargar_inicial(self):
        self._asegurar(lambda: self._gestor.conectar(),
                       al_anunciar=lambda frase: wx.CallAfter(anunciar, frase))
        return consultas_transmision.cargar_inicial(
            self._gestor, self._microfono_preferido())

    def _poblar_inicial(self, datos):
        self.cho_escena.Set(list(datos.escenas))
        if datos.escena:
            self.cho_escena.SetStringSelection(datos.escena)
        if datos.perfil in DESTINOS:
            self.cho_destino.SetStringSelection(datos.perfil)
        else:
            self.cho_destino.SetSelection(wx.NOT_FOUND)
        self.chk_chat.SetValue(overlay_servidor.esta_encendido())
        self._aplicar_datos(datos)

    def _inicial_cargada(self, datos):
        self._poblar_inicial(datos)
        anunciar(self._estado_actual.titular)
        if self.cho_destino.IsShown():
            self.cho_destino.SetFocus()
        else:
            self.btn_directo.SetFocus()

    def _escena(self):
        return self.cho_escena.GetStringSelection()

    def _refrescar_estado(self, anunciar_cuadro=False):
        destino = self._destino_elegido() or ""
        preferido = self._microfono_preferido()
        self._en_hilo(
            lambda: consultas_transmision.leer_estado(
                self._gestor, destino, preferido),
            lambda datos: self._estado_leido(datos, anunciar_cuadro))

    def _estado_leido(self, datos, anunciar_cuadro=False):
        self._aplicar_datos(datos)
        if anunciar_cuadro:
            anunciar(self.txt_estado.GetValue())

    def _actualizar(self, event):
        self._refrescar_estado(anunciar_cuadro=True)

    def _aplicar_datos(self, datos):
        self._grabacion.fijar(
            bool(datos.grabacion.get("outputActive", False)),
            bool(datos.grabacion.get("outputPaused", False)))
        self._silencio.fijar(datos.silenciado)
        if not self._directo.deteniendo:
            self._directo.sincronizar(
                bool(datos.transmision.get("outputActive", False)))
        escena = getattr(datos, "al_aire", "") or getattr(datos, "escena", "")
        self._mostrar_estado(resumir(
            self._destino_elegido() or "", datos.transmision, datos.grabacion,
            escena, datos.microfono, datos.silenciado, datos.problemas))
        self._aplicar_visibilidad()

    def _cambiar_escena(self, event):
        escena = self._escena()
        self._en_hilo(lambda: self._gestor.poner_escena_al_aire(escena),
                      self._escena_cambiada)

    def _escena_cambiada(self, escena):
        anunciar(obs_estado.frase_escena_al_aire(escena))
        self._refrescar_estado()

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

    def _organizar_escena(self, event):
        dialogo = OrganizarEscenaDialog(self, self._gestor, self._escena())
        try:
            dialogo.ShowModal()
        finally:
            dialogo.Destroy()
            self.btn_organizar.SetFocus()

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._directo.cerrar()
        self._operaciones.cerrar()
        diagnostico.crear_hilo(self._cerrar_gestor,
                               "CerrarTransmisionOBS").start()
        self.EndModal(wx.ID_CANCEL)

    def _cerrar_gestor(self):
        try:
            self._gestor.cerrar()
        except Exception as error:
            logger.debug("no se pudo cerrar el gestor de OBS: %s", error)


def abrir_transmision(parent, alternar_panel=None, supervisar=None,
                      guardar_usuario=None, usuario_tiktok="",
                      guardar_destino=None) -> None:
    dialogo = TransmisionDialog(
        parent, alternar_panel=alternar_panel, supervisar=supervisar,
        guardar_usuario=guardar_usuario, usuario_tiktok=usuario_tiktok,
        guardar_destino=guardar_destino)
    try:
        dialogo.ShowModal()
    finally:
        dialogo.Destroy()
