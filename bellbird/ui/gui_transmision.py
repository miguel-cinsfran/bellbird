"""Diálogo accesible para colocar el panel de chat en OBS."""

from __future__ import annotations

import wx

from bellbird.obs import consultas_transmision
from bellbird.obs import obs_cliente
from bellbird.obs import obs_destinos
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_estado
from bellbird.obs import obs_lanzador
from bellbird.obs import transmision_directa
from bellbird.obs.obs_destinos import DESTINOS
from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.obs import overlay_servidor
from bellbird.ui.accesibilidad import anunciar, nombre_accesible
from bellbird.ui.confirmar_transmision import _ETIQUETA_TRANSMITIR, confirmar_transmision
from bellbird.ui.gui import caja_de_grupo
from bellbird.ui.gui_organizar_escena import OrganizarEscenaDialog
from bellbird.ui.operaciones_obs import OperacionesObs
from bellbird.ui import paleta
from bellbird.ui.preferencias_comun import boton, fila_botones, fila_campo
from bellbird.obs.obs_panel import GestorPanelObs, NOMBRE_FUENTE
from bellbird.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


_PUERTO_PANEL_DEFECTO = 8730
_RUTA_PANEL_CHAT = "/chat"

_ETIQUETA_DETENER_TRANSMISION = N_("Detener la &transmisión")
_ETIQUETA_GRABAR = N_("&Grabar")
_ETIQUETA_DETENER_GRABACION = N_("Detener la &grabación")


class TransmisionDialog(wx.Dialog):

    _transmitiendo = False

    def __init__(self, parent, gestor=None, alternar_panel=None,
                 supervisar=None, guardar_usuario=None, usuario_tiktok="",
                 asegurar=None, guardar_destino=None):
        super().__init__(parent, title=_("Transmisión"), size=(680, 680),
                          name="DialogoTransmision")
        self._gestor = gestor or GestorPanelObs()
        self._asegurar = asegurar if asegurar is not None else obs_lanzador.asegurar_obs
        self._alternar_panel = alternar_panel
        self._supervisar = supervisar
        self._guardar_usuario = guardar_usuario
        self._guardar_destino = guardar_destino
        self._usuario_tiktok = usuario_tiktok or ""
        self._operaciones = OperacionesObs(
            self, self._activar, self._escribir_fallo, self._enfocar_tras_fallo)
        self._crear_controles()
        self.Centre()
        paleta.pintar_ventana(self)
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelTransmision")
        caja = wx.BoxSizer(wx.VERTICAL)
        # Contenido desplazable (solo vertical): el foco (Tab) desplaza solo
        # hasta el control.
        zona = wx.ScrolledWindow(panel, name="ZonaTransmision",
                                 style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        zona.SetScrollRate(0, 20)
        self._zona_desplazable = zona
        contenido = wx.BoxSizer(wx.VERTICAL)
        self._crear_seccion_transmitir(zona, contenido)
        self._crear_seccion_escena(zona, contenido)
        self._crear_seccion_panel(zona, contenido)
        ancho_rotulo = max(rotulo.GetBestSize().GetWidth()
                           for rotulo in self._rotulos_transmision)
        for rotulo in self._rotulos_transmision:
            rotulo.SetMinSize((ancho_rotulo, -1))
        zona.SetSizer(contenido)
        caja.Add(zona, 1, wx.EXPAND)
        self.btn_cerrar = boton(panel, _("Cerrar"), "CerrarTransmision", wx.ID_CANCEL)
        caja.Add(self.btn_cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(caja)
        self._acciones = (self.cho_destino, self.txt_usuario_tiktok, self.btn_destino,
                          self.btn_transmitir, self.btn_grabar,
                          self.btn_pausar_grabacion, self.cho_escena,
                          self.btn_poner_al_aire, self.btn_organizar,
                          self.btn_actualizar, self.chk_panel_chat,
                          self.btn_preparar)
        self._enlazar_eventos()

    def _crear_seccion_transmitir(self, zona, contenido):
        sizer_transmitir, padre_transmitir = caja_de_grupo(zona, _("Transmitir"))
        self._sizer_transmitir = sizer_transmitir
        self._rotulos_transmision = []
        rotulo_destino = self._nuevo_rotulo(padre_transmitir, _("Transmitir a:"))
        self.cho_destino = wx.Choice(padre_transmitir, choices=list(DESTINOS),
                                     name=_("Transmitir a"))
        nombre_accesible(self.cho_destino, _("Transmitir a"))
        fila_campo(sizer_transmitir, rotulo_destino, self.cho_destino)
        rotulo_usuario = self._nuevo_rotulo(padre_transmitir, _("Usuario de TikTok:"))
        self.txt_usuario_tiktok = wx.TextCtrl(
            padre_transmitir, value=self._usuario_tiktok, name=_("Usuario de TikTok"))
        nombre_accesible(self.txt_usuario_tiktok, _("Usuario de TikTok"))
        fila_campo(sizer_transmitir, rotulo_usuario, self.txt_usuario_tiktok)
        self.btn_destino = boton(padre_transmitir, _("Preparar desti&no"), _("Preparar destino"))
        self.btn_transmitir = boton(
            padre_transmitir, _(_ETIQUETA_TRANSMITIR), _("Transmitir"))
        self.btn_grabar = boton(padre_transmitir, _(_ETIQUETA_GRABAR), _("Grabar"))
        self.btn_pausar_grabacion = boton(
            padre_transmitir, _("Pausar gra&bación"), _("Pausar grabación"))
        sizer_transmitir.Add(fila_botones((self.btn_destino, self.btn_transmitir,
                                           self.btn_grabar, self.btn_pausar_grabacion)),
                             0, wx.ALL, 6)
        contenido.Add(sizer_transmitir, 0, wx.EXPAND | wx.ALL, 10)

    def _crear_seccion_escena(self, zona, contenido):
        sizer_escena, padre_escena = caja_de_grupo(zona, _("Escena"))
        rotulo_escena = self._nuevo_rotulo(padre_escena, _("Escena:"))
        self.cho_escena = wx.Choice(padre_escena, name=_("Escena"))
        nombre_accesible(self.cho_escena, _("Escena"))
        self.btn_poner_al_aire = boton(padre_escena, _("Poner al &aire"), _("Poner al aire"))
        fila_campo(sizer_escena, rotulo_escena, self.cho_escena,
                   boton=self.btn_poner_al_aire)
        self.btn_organizar = boton(
            padre_escena, _("&Organizar escena…"), _("Organizar escena…"))
        self.btn_actualizar = boton(padre_escena, _("Actualizar e&stado"), "ActualizarEstado")
        sizer_escena.Add(fila_botones((self.btn_organizar, self.btn_actualizar)),
                         0, wx.ALL, 6)
        contenido.Add(sizer_escena, 1, wx.EXPAND | wx.ALL, 10)

    def _crear_seccion_panel(self, zona, contenido):
        sizer_panel, padre_panel = caja_de_grupo(zona, _("Panel de chat, solo YouTube"))
        self.chk_panel_chat = wx.CheckBox(
            padre_panel, label=_("&Panel de chat para transmitir"),
            name=_("Panel de chat para transmitir"))
        self.chk_panel_chat.SetValue(overlay_servidor.esta_encendido())
        self.chk_panel_chat.Enable(self._alternar_panel is not None)
        sizer_panel.Add(self.chk_panel_chat, 0, wx.ALL, 6)
        self.btn_preparar = boton(padre_panel, _("Preparar pane&l"), _("Preparar panel"))
        sizer_panel.Add(self.btn_preparar, 0, wx.ALL, 6)
        rotulo_estado = self._nuevo_rotulo(padre_panel, _("Estado del panel:"))
        sizer_panel.Add(rotulo_estado, 0, wx.ALL, 6)
        self.txt_estado = wx.TextCtrl(
            padre_panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Estado del panel"))
        nombre_accesible(self.txt_estado, _("Estado del panel"))
        self.txt_estado.SetMinSize((-1, 110))
        sizer_panel.Add(self.txt_estado, 1, wx.EXPAND | wx.ALL, 6)
        contenido.Add(sizer_panel, 0, wx.EXPAND | wx.ALL, 10)

    def _enlazar_eventos(self):
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)
        self.btn_preparar.Bind(wx.EVT_BUTTON, self._preparar)
        self.chk_panel_chat.Bind(wx.EVT_CHECKBOX, self._alternar_panel_chat)
        self.btn_poner_al_aire.Bind(wx.EVT_BUTTON, self._poner_al_aire)
        self.btn_organizar.Bind(wx.EVT_BUTTON, self._organizar_escena)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_cambiar_destino)
        self.btn_destino.Bind(wx.EVT_BUTTON, self._preparar_destino)
        self.btn_transmitir.Bind(wx.EVT_BUTTON, self._transmitir)
        self.btn_grabar.Bind(wx.EVT_BUTTON, self._grabar)
        self.btn_pausar_grabacion.Bind(wx.EVT_BUTTON, self._pausar_grabacion)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)

    def _nuevo_rotulo(self, padre, texto):
        rotulo = wx.StaticText(padre, label=texto)
        self._rotulos_transmision.append(rotulo)
        return rotulo

    def _alternar_panel_chat(self, event):
        if self._alternar_panel is not None:
            self.chk_panel_chat.SetValue(
                self._alternar_panel(self.chk_panel_chat.GetValue()))

    def _activar(self, activo):
        pide_usuario = obs_destinos.usa_usuario_tiktok(self._destino_elegido())
        for control in self._acciones:
            if control is self.chk_panel_chat:
                control.Enable(self._alternar_panel is not None)
                continue
            control.Enable(activo and (control is not self.txt_usuario_tiktok or pide_usuario))

    def _destino_elegido(self):
        sel = self.cho_destino.GetSelection()
        return DESTINOS[sel] if sel != wx.NOT_FOUND else None

    def _escribir_fallo(self, mensaje):
        self.txt_estado.SetValue(mensaje)

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
        return consultas_transmision.cargar_inicial(self._gestor)

    def _poblar_inicial(self, datos):
        # Puebla los controles sin anunciar: la carga inicial anuncia aparte
        # y el destino preparado reusa esto para refrescar en silencio.
        self.cho_escena.Set(list(datos.escenas))
        if datos.escena:
            self.cho_escena.SetStringSelection(datos.escena)
        if datos.perfil in DESTINOS:
            self.cho_destino.SetStringSelection(datos.perfil)
        else:
            self.cho_destino.SetSelection(wx.NOT_FOUND)
        self.txt_usuario_tiktok.Enable(obs_destinos.usa_usuario_tiktok(self._destino_elegido()))
        self._mostrar_estados(datos.transmision, datos.grabacion, datos.al_aire)

    def _inicial_cargada(self, datos):
        self._poblar_inicial(datos)
        frase = obs_disposicion.describir_preparacion(
            True, overlay_servidor.esta_encendido(),
            overlay_servidor.puerto_actual(), NOMBRE_FUENTE in datos.fuentes)
        self.txt_estado.SetValue(frase)
        anunciar(frase)
        self._anunciar_estados(datos.transmision, datos.grabacion, datos.al_aire)
        self.cho_destino.SetFocus()

    def _escena(self):
        return self.cho_escena.GetStringSelection()

    def _actualizar_boton(self, boton, etiqueta, nombre):
        boton.SetLabel(etiqueta)
        boton.SetName(nombre)

    def _mostrar_transmision(self, activa):
        self._transmitiendo = activa
        self._actualizar_boton(
            self.btn_transmitir,
            _(_ETIQUETA_DETENER_TRANSMISION) if activa else _(_ETIQUETA_TRANSMITIR),
            _("Detener la transmisión") if activa else _("Transmitir"))

    def _mostrar_estados(self, transmision, grabacion, al_aire):
        self._mostrar_transmision(bool(transmision.get("outputActive", False)))
        grabando = bool(grabacion.get("outputActive", False))
        self._actualizar_boton(
            self.btn_grabar,
            _(_ETIQUETA_DETENER_GRABACION) if grabando else _(_ETIQUETA_GRABAR),
            _("Detener la grabación") if grabando else _("Grabar"))
        self.btn_pausar_grabacion.Enable(grabando)

    @staticmethod
    def _frase_escena_al_aire(escena):
        return obs_estado.frase_escena_al_aire(escena)

    def _anunciar_estados(self, transmision, grabacion, al_aire):
        anunciar(obs_estado.frase_transmision(
            transmision.get("outputActive", False), transmision.get("outputDuration", 0),
            transmision.get("outputSkippedFrames", 0), transmision.get("outputTotalFrames", 0)))
        anunciar(obs_estado.frase_grabacion(
            grabacion.get("outputActive", False), grabacion.get("outputPaused", False),
            grabacion.get("outputTimecode", "")))
        anunciar(self._frase_escena_al_aire(al_aire))

    def _actualizar(self, event):
        self._en_hilo(self._leer_estados, self._estados_leidos)

    def _leer_estados(self):
        return (self._gestor.escena_al_aire(), self._gestor.estado_transmision(),
                self._gestor.estado_grabacion())

    def _estados_leidos(self, datos):
        al_aire, transmision, grabacion = datos
        self._mostrar_estados(transmision, grabacion, al_aire)
        self._anunciar_estados(transmision, grabacion, al_aire)

    def _poner_al_aire(self, event):
        escena = self._escena()
        self._en_hilo(lambda: self._gestor.poner_escena_al_aire(escena),
                      self._escena_puesta_al_aire)

    def _escena_puesta_al_aire(self, escena):
        anunciar(self._frase_escena_al_aire(escena))

    def _transmitir(self, event):
        def _preguntar(accion):
            try:
                return bool(self._supervisar(accion))
            except Exception:
                return False
        recordado = {}
        def _usuario():
            if "valor" not in recordado:
                from bellbird.capture import tiktok_vivo
                recordado["valor"] = tiktok_vivo.usuario_tiktok(
                    self.txt_usuario_tiktok.GetValue())
            return recordado["valor"]
        destino = self.cho_destino.GetStringSelection()
        decision = transmision_directa.decidir_transmision(hay_supervisor=self._supervisar is not None,
            deteniendo=lambda: _preguntar("deteniendo"), con_supervisor=lambda: _preguntar("activo"),
            transmitiendo=self._transmitiendo,
            destino=destino, usuario_tiktok=_usuario)
        if decision == transmision_directa.ALTERNAR:
            self._en_hilo(self._gestor.alternar_transmision, self._transmision_alternada)
            return
        if decision == transmision_directa.ESPERAR_DETENCION:
            anunciar(_("Deteniendo la transmisión. "
                      "Esperando a que OBS confirme."))
            return
        if decision == transmision_directa.DETENER_SUPERVISADA:
            try:
                self._supervisar("detener")
            except Exception as error:
                logger.debug("no se pudo detener la supervisión: %s", error)
            self._mostrar_transmision(False)
            return
        if decision == transmision_directa.FALTA_DESTINO:
            anunciar(_("Elige primero a dónde transmitir, en Transmitir a."))
            return
        if decision == transmision_directa.FALTA_USUARIO:
            anunciar(_("Escribe tu usuario de TikTok en Usuario de TikTok."))
            self.txt_usuario_tiktok.SetFocus()
            return
        usuario = _usuario() if destino == "TikTok" else ""
        if destino == "TikTok" and usuario != self._usuario_tiktok and self._guardar_usuario is not None:
            try:
                self._guardar_usuario(usuario)
            except Exception as error:
                logger.warning("no se pudo guardar el usuario de TikTok: %s", error)
            self._usuario_tiktok = usuario
        self._en_hilo(lambda: self._revisar_prevuelo(destino),
                      lambda revision: self._revision_lista(revision, destino, usuario))

    def _revisar_prevuelo(self, destino):
        # El destino viaja como argumento: los hilos no leen controles de wx.
        return self._gestor.revisar(destino)

    def _recordar_destino(self, destino):
        if self._guardar_destino is not None:
            try:
                self._guardar_destino(destino)
            except Exception as error:
                logger.warning("no se pudo guardar el destino de transmisión: %s", error)

    def _revision_lista(self, revision, destino, usuario):
        if not confirmar_transmision(self, revision):
            anunciar(_("No se transmitió."))
            return
        self._recordar_destino(destino)
        try:
            self._supervisar("iniciar", destino, usuario)
        except Exception as error:
            self._fallo(obs_cliente.mensaje_de_fallo_obs(error))
            return
        self._mostrar_transmision(True)

    def _transmision_alternada(self, activa):
        self._mostrar_transmision(activa)
        accion = "transmision_iniciada" if activa else "transmision_detenida"
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))

    def _grabar(self, event):
        self._en_hilo(self._gestor.alternar_grabacion, self._grabacion_alternada)

    def _grabacion_alternada(self, activa):
        self._actualizar_boton(
            self.btn_grabar,
            _(_ETIQUETA_DETENER_GRABACION) if activa else _(_ETIQUETA_GRABAR),
            _("Detener la grabación") if activa else _("Grabar"))
        self.btn_pausar_grabacion.Enable(activa)
        accion = "grabacion_iniciada" if activa else "grabacion_detenida"
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))

    def _pausar_grabacion(self, event):
        self._en_hilo(self._gestor.alternar_pausa_grabacion, self._pausa_grabacion_alternada)

    def _pausa_grabacion_alternada(self, en_pausa):
        accion = "grabacion_en_pausa" if en_pausa else "grabacion_reanudada"
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))

    def _al_cambiar_destino(self, event):
        # Solo guarda lo elegido, sin anunciar ni preparar: recorrerlo
        # con flechas dispara EVT_CHOICE y preparar ahí saldría al aire.
        self._recordar_destino(self.cho_destino.GetStringSelection())
        self.txt_usuario_tiktok.Enable(obs_destinos.usa_usuario_tiktok(self._destino_elegido()))
        event.Skip()

    def _preparar_destino(self, event):
        # Como en _al_cambiar_destino: recorrerlo dispara EVT_CHOICE.
        destino = self.cho_destino.GetStringSelection()
        if not destino:
            anunciar(_("Elige primero a dónde transmitir, en Transmitir a."))
            return
        anunciar(_("Preparando OBS para {destino}. Puede tardar unos segundos.").format(destino=destino))
        self._en_hilo(lambda: self._preparar_destino_en_hilo(destino), self._destino_preparado)

    def _preparar_destino_en_hilo(self, destino):
        # El destino se captura en el hilo principal y viaja como argumento;
        # los hilos de trabajo no leen controles de wx.
        resultado = self._gestor.preparar_destino(destino)
        return resultado, self._cargar_inicial(), destino

    def _destino_preparado(self, datos):
        resultado, inicial, destino = datos
        self._poblar_inicial(inicial)
        self._recordar_destino(destino)
        anunciar(obs_destinos.frase_destino_listo(resultado))
        self.btn_transmitir.SetFocus()

    def _preparar(self, event):
        escena = self._escena()
        self._en_hilo(lambda: self._preparar_panel(escena), self._panel_preparado)

    def _preparar_panel(self, escena):
        puerto = overlay_servidor.puerto_actual() or _PUERTO_PANEL_DEFECTO
        if not overlay_servidor.esta_encendido():
            try:
                overlay_servidor.encender(puerto)
            except overlay_servidor.OverlayPuertoOcupadoError:
                return _("No se pudo encender el panel, el puerto {puerto} está ocupado").format(puerto=puerto)
        puerto = overlay_servidor.puerto_actual() or puerto
        fuentes = self._gestor.fuentes(escena)
        if NOMBRE_FUENTE not in fuentes:
            url = f"http://127.0.0.1:{puerto}{_RUTA_PANEL_CHAT}"
            self._gestor.asegurar_fuente(escena, url, 460, 620)
            fuentes = self._gestor.fuentes(escena)
        return obs_disposicion.describir_preparacion(
            True, overlay_servidor.esta_encendido(), puerto,
            NOMBRE_FUENTE in fuentes)

    def _panel_preparado(self, frase):
        self.txt_estado.SetValue(frase)
        anunciar(frase)

    def _organizar_escena(self, event):
        escena = self._escena()
        dialogo = OrganizarEscenaDialog(self, self._gestor, escena)
        try:
            dialogo.ShowModal()
        finally:
            dialogo.Destroy()
            self.btn_organizar.SetFocus()

    def _cerrar(self, event):
        if self._operaciones.cerrando:
            return
        self._operaciones.cerrar()
        diagnostico.crear_hilo(self._cerrar_gestor, "CerrarTransmisionOBS").start()
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
