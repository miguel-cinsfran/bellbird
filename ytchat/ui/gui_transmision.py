"""Diálogo accesible para colocar el panel de chat en OBS."""

from __future__ import annotations

import threading

import wx

from ytchat.obs import ajuste_fino
from ytchat.obs import consultas_transmision
from ytchat.obs import obs_cliente
from ytchat.obs import obs_destinos
from ytchat.obs import obs_disposicion
from ytchat.obs import obs_estado
from ytchat.obs import obs_lanzador
from ytchat.obs import transmision_directa
from ytchat.obs.obs_destinos import DESTINOS
from ytchat.core import diagnostico
from ytchat.core.idioma import N_, _
from ytchat.obs import overlay_servidor
from ytchat.ui.accesibilidad import ContadorAccesible, anunciar, nombre_accesible
from ytchat.ui.gui import caja_de_grupo
from ytchat.ui.tema import _T
from ytchat.obs.obs_panel import GestorPanelObs, NOMBRE_FUENTE
from ytchat.obs.restablecimiento import RegistroRestablecimiento
from ytchat.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


def confirmar_transmision(padre, revision) -> bool:
    """Pide confirmar el inicio del directo con la revisión a la vista.

    Mismo texto, título, etiquetas y regla de cancelación por defecto
    que la ventana Transmisión: si la revisión trae problemas, el foco
    arranca en Cancelar.
    """
    from ytchat.obs import obs_prevuelo
    frase = obs_prevuelo.frase_revision(revision)
    problemas = bool(getattr(revision, "problemas", ()))
    estilo = wx.OK | wx.CANCEL
    if problemas:
        estilo |= wx.CANCEL_DEFAULT
    dialogo = wx.MessageDialog(padre, frase, _("Antes de transmitir"), estilo)
    try:
        dialogo.SetOKCancelLabels(_(_ETIQUETA_TRANSMITIR), _("&Cancelar"))
        return dialogo.ShowModal() == wx.ID_OK
    finally:
        dialogo.Destroy()


_TEXTO_LIENZO = N_(
    "El programa de emisión compone lo que ven los espectadores sobre un\n"
    "rectángulo de tamaño fijo, llamado lienzo. No es la pantalla del equipo\n"
    "ni la ventana del juego.\n\n"
    "Lo que queda dentro del lienzo se emite. Lo que sobresale del borde se\n"
    "recorta, sin ningún aviso.\n\n"
    "Que dos fuentes se superpongan no es necesariamente un problema. El\n"
    "fondo de este panel es transparente: solo se ven las tarjetas de los\n"
    "mensajes, y solo tapan lo que hay justo debajo de ellas.")

_TEXTO_COMO_SE_COLOCA = N_(
    "Este diálogo no crea escenas ni agrega otras fuentes, salvo la captura de ventana desde la sección Escena. Hace una sola\n"
    "cosa: pone el panel de chat de esta aplicación dentro de una escena de OBS\n"
    "y lo coloca donde quieras.\n\n"
    "El orden es este.\n\n"
    "Uno. Pulsa Preparar panel. Eso enciende el servidor del panel y crea la\n"
    "fuente dentro de la escena elegida, si todavía no estaba.\n\n"
    "Dos. Elige la escena en el desplegable Escena. Recorrerlo no cambia lo que\n"
    "ven los espectadores: para eso está el botón Poner al aire.\n\n"
    "Tres. Elige qué fuente vas a mover en el desplegable Fuente. Normalmente es\n"
    "el panel de chat, pero puedes mover cualquier fuente que ya exista en la\n"
    "escena. Este diálogo solo agrega el panel y la captura de ventana: lo demás se hace\n"
    "desde OBS.\n\n"
    "Cuatro. Coloca la fuente. Tienes dos formas. El desplegable Posición más su\n"
    "botón la lleva a una de nueve posiciones fijas. El Ajuste fino la mueve de\n"
    "a poco con las flechas, y confirma con Intro.\n\n"
    "Cinco. El tamaño se cambia con Ancho y Alto y se aplica con su botón.\n\n"
    "El cuadro Estado del panel describe en todo momento dónde está la\n"
    "fuente, de qué tamaño es, si se sale del lienzo y si tapa a otras. Se\n"
    "actualiza solo con cada cambio.\n\n"
    "Restablecer deshace todo lo que hiciste desde que abriste esta ventana.")

_PUERTO_PANEL_DEFECTO = 8730
_RUTA_PANEL_CHAT = "/chat"

_ETIQUETA_TRANSMITIR = N_("&Transmitir")
_ETIQUETA_DETENER_TRANSMISION = N_("Detener la &transmisión")
_ETIQUETA_GRABAR = N_("&Grabar")
_ETIQUETA_DETENER_GRABACION = N_("Detener la &grabación")
_ETIQUETAS_POSICION = {
    "superior-izquierda": N_("Superior izquierda"), "superior-centro": N_("Superior centro"),
    "superior-derecha": N_("Superior derecha"), "centro-izquierda": N_("Centro izquierda"),
    "centro": N_("Centro"), "centro-derecha": N_("Centro derecha"),
    "inferior-izquierda": N_("Inferior izquierda"), "inferior-centro": N_("Inferior centro"),
    "inferior-derecha": N_("Inferior derecha"),
}


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
        self._restablecimiento = RegistroRestablecimiento()
        self._valores_ventana = []
        self._ajuste = ajuste_fino.EstadoAjuste()
        self._cerrando = False
        self._operacion_en_vuelo = False
        self.SetBackgroundColour(_T.bg)
        self._crear_controles()
        self._temporizador_consulta = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._anunciar_consulta, self._temporizador_consulta)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
        self.Centre()
        self._en_hilo(self._cargar_inicial, self._inicial_cargada)

    def _crear_controles(self):
        panel = wx.Panel(self, name="PanelTransmision")
        panel.SetBackgroundColour(_T.bg)
        panel.SetForegroundColour(_T.text)
        caja = wx.BoxSizer(wx.VERTICAL)
        # Contenido desplazable (solo vertical): necesita 1121 px de alto y el
        # diálogo mide 680, así que la mitad quedaba fuera del alcance del
        # ratón. El foco (Tab) desplaza solo hasta el control.
        zona = wx.ScrolledWindow(panel, name="ZonaTransmision",
                                 style=wx.TAB_TRAVERSAL | wx.VSCROLL)
        zona.SetScrollRate(0, 20)
        zona.SetBackgroundColour(_T.bg)
        zona.SetForegroundColour(_T.text)
        self._zona_desplazable = zona
        contenido = wx.BoxSizer(wx.VERTICAL)
        nota = wx.StaticText(zona, name="NotaTransmision", label=obs_estado.NOTA_TRANSMISION)
        nota.SetForegroundColour(_T.dim)
        nota.Wrap(560)
        contenido.Add(nota, 0, wx.ALL, 10)

        sizer_transmitir, padre_transmitir = caja_de_grupo(zona, _("Transmitir"))
        self._sizer_transmitir = sizer_transmitir
        self._rotulos_transmision = []

        def nuevo_rotulo(padre, texto):
            rotulo = wx.StaticText(padre, label=texto)
            rotulo.SetForegroundColour(_T.text)
            self._rotulos_transmision.append(rotulo)
            return rotulo

        def fila_campo(sizer, rotulo, control, proporcion=0):
            fila = wx.BoxSizer(wx.HORIZONTAL)
            fila.Add(rotulo, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 6)
            fila.Add(control, 1, wx.EXPAND | wx.ALL, 6)
            sizer.Add(fila, proporcion, wx.EXPAND, 0)

        rotulo_destino = nuevo_rotulo(padre_transmitir, _("Transmitir a:"))
        self.cho_destino = wx.Choice(padre_transmitir, choices=list(DESTINOS),
                                     name=_("Transmitir a"))
        nombre_accesible(self.cho_destino, _("Transmitir a"))
        fila_campo(sizer_transmitir, rotulo_destino, self.cho_destino)
        rotulo_usuario = nuevo_rotulo(padre_transmitir, _("Tu usuario de TikTok:"))
        self.txt_usuario_tiktok = wx.TextCtrl(
            padre_transmitir, value=self._usuario_tiktok, name=_("Tu usuario de TikTok"))
        nombre_accesible(self.txt_usuario_tiktok, _("Tu usuario de TikTok"))
        fila_campo(sizer_transmitir, rotulo_usuario, self.txt_usuario_tiktok)
        self.btn_destino = self._boton(padre_transmitir, _("Preparar desti&no"), _("Preparar destino"))
        sizer_transmitir.Add(self.btn_destino, 0, wx.ALL, 6)
        self.btn_transmitir = self._boton(
            padre_transmitir, _(_ETIQUETA_TRANSMITIR), _("Transmitir"))
        sizer_transmitir.Add(self.btn_transmitir, 0, wx.ALL, 6)
        self.btn_grabar = self._boton(padre_transmitir, _(_ETIQUETA_GRABAR), _("Grabar"))
        sizer_transmitir.Add(self.btn_grabar, 0, wx.ALL, 6)
        self.btn_pausar_grabacion = self._boton(
            padre_transmitir, _("Pausar gra&bación"), _("Pausar grabación"))
        sizer_transmitir.Add(self.btn_pausar_grabacion, 0, wx.ALL, 6)
        contenido.Add(sizer_transmitir, 0, wx.EXPAND | wx.ALL, 10)

        sizer_escena, padre_escena = caja_de_grupo(zona, _("Escena"))
        rotulo_escena = nuevo_rotulo(padre_escena, _("Escena:"))
        self.cho_escena = wx.Choice(padre_escena, name=_("Escena"))
        nombre_accesible(self.cho_escena, _("Escena"))
        fila_campo(sizer_escena, rotulo_escena, self.cho_escena)
        self.btn_poner_al_aire = self._boton(padre_escena, _("Poner al &aire"), _("Poner al aire"))
        sizer_escena.Add(self.btn_poner_al_aire, 0, wx.ALL, 6)
        rotulo_ventana = nuevo_rotulo(padre_escena, _("Ventana que se captura:"))
        self.cho_ventana = wx.Choice(padre_escena, name=_("Ventana que se captura"))
        nombre_accesible(self.cho_ventana, _("Ventana que se captura"))
        fila_campo(sizer_escena, rotulo_ventana, self.cho_ventana)
        self.btn_usar_ventana = self._boton(padre_escena, _("Usar esa &ventana"), _("Usar esa ventana"))
        sizer_escena.Add(self.btn_usar_ventana, 0, wx.ALL, 6)
        self.btn_captura = self._boton(
            padre_escena, _("Guardar una capt&ura de la escena…"), "GuardarCaptura")
        sizer_escena.Add(self.btn_captura, 0, wx.ALL, 6)
        self.btn_actualizar = self._boton(padre_escena, _("Actualizar e&stado"), "ActualizarEstado")
        sizer_escena.Add(self.btn_actualizar, 0, wx.ALL, 6)
        contenido.Add(sizer_escena, 1, wx.EXPAND | wx.ALL, 10)

        sizer_vista, padre_vista = caja_de_grupo(zona, _("Cómo se ve la escena"))
        self.txt_vista_escena = wx.TextCtrl(
            padre_vista, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Cómo se ve la escena"))
        self.txt_vista_escena.SetBackgroundColour(_T.field)
        self.txt_vista_escena.SetForegroundColour(_T.text)
        nombre_accesible(self.txt_vista_escena, _("Cómo se ve la escena"))
        self.txt_vista_escena.SetMinSize((-1, 110))
        sizer_vista.Add(self.txt_vista_escena, 1, wx.EXPAND | wx.ALL, 6)
        contenido.Add(sizer_vista, 0, wx.EXPAND | wx.ALL, 10)

        sizer_panel, padre_panel = caja_de_grupo(zona, _("Panel de chat, solo YouTube"))
        self.chk_panel_chat = wx.CheckBox(
            padre_panel, label=_("&Panel de chat para transmitir"),
            name=_("Panel de chat para transmitir"))
        self.chk_panel_chat.SetValue(overlay_servidor.esta_encendido())
        self.chk_panel_chat.Enable(self._alternar_panel is not None)
        sizer_panel.Add(self.chk_panel_chat, 0, wx.ALL, 6)
        self.btn_preparar = self._boton(padre_panel, _("Preparar pane&l"), _("Preparar panel"))
        sizer_panel.Add(self.btn_preparar, 0, wx.ALL, 6)
        rotulo_fuente = nuevo_rotulo(padre_panel, _("Fuente:"))
        self.cho_fuente = wx.Choice(padre_panel, name=_("Fuente"))
        nombre_accesible(self.cho_fuente, _("Fuente"))
        fila_campo(sizer_panel, rotulo_fuente, self.cho_fuente)
        rotulo_estado = nuevo_rotulo(padre_panel, _("Estado del panel:"))
        sizer_panel.Add(rotulo_estado, 0, wx.ALL, 6)
        self.txt_estado = wx.TextCtrl(
            padre_panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
            name=_("Estado del panel"))
        self.txt_estado.SetBackgroundColour(_T.field)
        self.txt_estado.SetForegroundColour(_T.text)
        nombre_accesible(self.txt_estado, _("Estado del panel"))
        self.txt_estado.SetMinSize((-1, 110))
        sizer_panel.Add(self.txt_estado, 1, wx.EXPAND | wx.ALL, 6)
        rotulo_posicion = nuevo_rotulo(padre_panel, _("Posición del panel:"))
        self.cho_posicion = wx.Choice(
            padre_panel, choices=[_(_ETIQUETAS_POSICION[nombre])
                                  for nombre in obs_disposicion.ANCLAJES],
            name=_("Posición del panel"))
        nombre_accesible(self.cho_posicion, _("Posición del panel"))
        fila_campo(sizer_panel, rotulo_posicion, self.cho_posicion)
        self.btn_colocar = self._boton(
            padre_panel, _("&Colocar en esa posición"), _("Colocar en esa posición"))
        sizer_panel.Add(self.btn_colocar, 0, wx.ALL, 6)
        rotulo_ancho = nuevo_rotulo(padre_panel, _("Ancho del panel en píxeles:"))
        self.sp_ancho = ContadorAccesible(padre_panel, min=100, max=4000, initial=460,
                                          name=_("Ancho del panel en píxeles"))
        fila_campo(sizer_panel, rotulo_ancho, self.sp_ancho)
        rotulo_alto = nuevo_rotulo(padre_panel, _("Alto del panel en píxeles:"))
        self.sp_alto = ContadorAccesible(padre_panel, min=100, max=4000, initial=620,
                                         name=_("Alto del panel en píxeles"))
        fila_campo(sizer_panel, rotulo_alto, self.sp_alto)
        self.btn_tamano = self._boton(padre_panel, _("Apl&icar tamaño"), "AplicarTamano")
        sizer_panel.Add(self.btn_tamano, 0, wx.ALL, 6)
        self.chk_mostrar = wx.CheckBox(padre_panel, label=_("&Mostrar panel en la escena"),
                                       name="MostrarPanel")
        self.chk_fijar = wx.CheckBox(padre_panel, label=_("&Fijar posición del panel"),
                                     name="FijarPanel")
        sizer_panel.Add(self.chk_mostrar, 0, wx.ALL, 6)
        sizer_panel.Add(self.chk_fijar, 0, wx.ALL, 6)
        self.btn_frente = self._boton(padre_panel, _("P&oner al frente"), "PonerAlFrente")
        sizer_panel.Add(self.btn_frente, 0, wx.ALL, 6)
        self._etiqueta_ajuste = _("A&juste fino")
        self.btn_ajuste = self._boton(padre_panel, self._etiqueta_ajuste, "AjusteFino")
        sizer_panel.Add(self.btn_ajuste, 0, wx.ALL, 6)
        self.btn_como_se_coloca = self._boton(
            padre_panel, _("Cómo s&e coloca el panel"), _("Cómo se coloca el panel"))
        sizer_panel.Add(self.btn_como_se_coloca, 0, wx.ALL, 6)
        self.btn_lienzo = self._boton(padre_panel, _("&Qué es el lienzo"), "QueEsElLienzo")
        sizer_panel.Add(self.btn_lienzo, 0, wx.ALL, 6)
        self.btn_restaurar = self._boton(padre_panel, _("&Restablecer"), "RestablecerTransmision")
        sizer_panel.Add(self.btn_restaurar, 0, wx.ALL, 6)
        contenido.Add(sizer_panel, 0, wx.EXPAND | wx.ALL, 10)
        ancho_rotulo = max(rotulo.GetBestSize().GetWidth()
                           for rotulo in self._rotulos_transmision)
        for rotulo in self._rotulos_transmision:
            rotulo.SetMinSize((ancho_rotulo, -1))
        zona.SetSizer(contenido)
        caja.Add(zona, 1, wx.EXPAND)

        self.btn_cerrar = self._boton(panel, _("Cerrar"), "CerrarTransmision", wx.ID_CANCEL)
        caja.Add(self.btn_cerrar, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(caja)
        self._acciones = (self.cho_destino, self.txt_usuario_tiktok, self.btn_destino,
                          self.btn_transmitir, self.btn_grabar, self.btn_pausar_grabacion,
                          self.cho_escena, self.btn_poner_al_aire, self.cho_ventana,
                          self.btn_usar_ventana, self.btn_captura,
                          self.btn_actualizar, self.chk_panel_chat, self.btn_preparar,
                          self.cho_fuente, self.cho_posicion, self.btn_colocar,
                          self.sp_ancho, self.sp_alto, self.btn_tamano, self.chk_mostrar,
                          self.chk_fijar, self.btn_frente, self.btn_ajuste,
                          self.btn_como_se_coloca, self.btn_restaurar)
        self.btn_actualizar.Bind(wx.EVT_BUTTON, self._actualizar)
        self.btn_preparar.Bind(wx.EVT_BUTTON, self._preparar)
        self.chk_panel_chat.Bind(wx.EVT_CHECKBOX, self._alternar_panel_chat)
        self.cho_escena.Bind(wx.EVT_CHOICE, self._cambiar_escena)
        self.btn_poner_al_aire.Bind(wx.EVT_BUTTON, self._poner_al_aire)
        self.btn_usar_ventana.Bind(wx.EVT_BUTTON, self._usar_ventana)
        self.cho_fuente.Bind(wx.EVT_CHOICE, self._cambiar_fuente)
        # Recorrer con flechas dispara EVT_CHOICE y esto sale al aire.
        self.btn_colocar.Bind(wx.EVT_BUTTON, self._colocar)
        self.btn_tamano.Bind(wx.EVT_BUTTON, self._tamano)
        self.chk_mostrar.Bind(wx.EVT_CHECKBOX, self._mostrar)
        self.chk_fijar.Bind(wx.EVT_CHECKBOX, self._fijar)
        self.btn_frente.Bind(wx.EVT_BUTTON, self._frente)
        self.btn_ajuste.Bind(wx.EVT_BUTTON, self._iniciar_ajuste)
        self.btn_ajuste.Bind(wx.EVT_KILL_FOCUS, self._ajuste_perdio_foco)
        self.btn_captura.Bind(wx.EVT_BUTTON, self._captura)
        self.btn_como_se_coloca.Bind(wx.EVT_BUTTON, self._como_se_coloca)
        self.btn_lienzo.Bind(wx.EVT_BUTTON, self._lienzo)
        self.btn_restaurar.Bind(wx.EVT_BUTTON, self._restaurar)
        self.cho_destino.Bind(wx.EVT_CHOICE, self._al_cambiar_destino)
        self.btn_destino.Bind(wx.EVT_BUTTON, self._preparar_destino)
        self.btn_transmitir.Bind(wx.EVT_BUTTON, self._transmitir)
        self.btn_grabar.Bind(wx.EVT_BUTTON, self._grabar)
        self.btn_pausar_grabacion.Bind(wx.EVT_BUTTON, self._pausar_grabacion)
        self.btn_cerrar.Bind(wx.EVT_BUTTON, self._cerrar)
        self.Bind(wx.EVT_CLOSE, self._cerrar)
        self.Bind(wx.EVT_CHAR_HOOK, self._tecla_ajuste)

    @staticmethod
    def _boton(panel, etiqueta, nombre, identificador=wx.ID_ANY):
        boton = wx.Button(panel, identificador, etiqueta, name=nombre)
        boton.SetBackgroundColour(_T.btn)
        boton.SetForegroundColour(_T.btn_t)
        return boton

    def _en_hilo(self, funcion, al_terminar=None):
        self._activar(False)
        self._operacion_en_vuelo = True
        self._temporizador_consulta.StartOnce(400)
        def ejecutar():
            try:
                resultado = funcion()
            except obs_cliente.ObsError as error:
                wx.CallAfter(self._fallo, str(error))
            except Exception as error:
                # Cualquier otro fallo (la fuente ya no existe en OBS y
                # obs_panel devuelve None, falta web/chat.html…) mataba el
                # hilo sin avisar y dejaba el diálogo con todo desactivado.
                logger.warning("operación OBS: %r", error)
                wx.CallAfter(self._fallo, obs_cliente.mensaje_de_fallo_obs(error))
            else:
                wx.CallAfter(self._terminar, resultado, al_terminar)
        diagnostico.crear_hilo(ejecutar, "TransmisionOBS").start()

    def _alternar_panel_chat(self, event):
        if self._alternar_panel is not None:
            self.chk_panel_chat.SetValue(
                self._alternar_panel(self.chk_panel_chat.GetValue()))

    def _activar(self, activo):
        for control in self._acciones:
            if control is self.chk_panel_chat:
                control.Enable(self._alternar_panel is not None)
                continue
            control.Enable(activo)

    def _terminar(self, resultado, al_terminar):
        self._temporizador_consulta.Stop()
        self._operacion_en_vuelo = False
        if self._cerrando:
            return
        self._activar(True)
        if isinstance(resultado, obs_disposicion.SnapshotPanel):
            self._mostrar_snap(resultado)
        if al_terminar:
            al_terminar(resultado)

    def _fallo(self, mensaje):
        self._temporizador_consulta.Stop()
        self._operacion_en_vuelo = False
        if self._cerrando:
            return
        self._activar(False)
        self.txt_estado.SetValue(mensaje)
        sound_player.reproducir("error")
        anunciar(mensaje)
        self.btn_actualizar.Enable(True)
        self.btn_actualizar.SetFocus()

    def _anunciar_consulta(self, event):
        if self._operacion_en_vuelo and not self._cerrando:
            # Puede repetirse mientras espera la operación y no debe interrumpir.
            anunciar(_("Consultando OBS"), False)

    def _al_destruir(self, event):
        # Un hilo puede aterrizar después del Destroy; sin esta marca tocaba
        # controles ya muertos y wx levantaba RuntimeError.
        self._cerrando = True
        self._temporizador_consulta.Stop()
        event.Skip()

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
        self._cargar_fuentes(datos.fuentes, datos.fuente)
        self._cargar_ventanas(datos.opciones, datos.actual)
        self._mostrar_snap(datos.snap)
        self._mostrar_vista(datos.descripcion)
        if datos.perfil in DESTINOS:
            self.cho_destino.SetStringSelection(datos.perfil)
        else:
            self.cho_destino.SetSelection(wx.NOT_FOUND)
        self._mostrar_estados(datos.transmision, datos.grabacion, datos.al_aire)

    def _inicial_cargada(self, datos):
        self._poblar_inicial(datos)
        anunciar(obs_disposicion.describir_preparacion(
            datos.snap.conectado, overlay_servidor.esta_encendido(),
            overlay_servidor.puerto_actual(), NOMBRE_FUENTE in datos.fuentes))
        self._anunciar_estados(datos.transmision, datos.grabacion, datos.al_aire)
        self.cho_destino.SetFocus()

    def _mostrar_snap(self, snap):
        self.txt_estado.SetValue(obs_disposicion.describir_fuente(
            self._fuente(), snap, obs_disposicion.COMPONENTES, "largo"))
        anclaje = obs_disposicion.anclaje_de(
            (snap.izquierda, snap.arriba, snap.ancho, snap.alto),
            snap.lienzo_ancho, snap.lienzo_alto)
        self.cho_posicion.SetSelection(
            tuple(obs_disposicion.ANCLAJES).index(anclaje)
            if anclaje else wx.NOT_FOUND)
        if snap.ancho:
            self.sp_ancho.SetValue(snap.ancho)
        if snap.alto:
            self.sp_alto.SetValue(snap.alto)
        self.chk_mostrar.SetValue(snap.visible)
        self.chk_fijar.SetValue(snap.bloqueada)

    def _mostrar_vista(self, descripcion):
        self.txt_vista_escena.SetValue(descripcion or "")

    def _cargar_fuentes(self, fuentes, fuente=""):
        self.cho_fuente.Set(list(fuentes))
        if fuente:
            self.cho_fuente.SetStringSelection(fuente)
        if not fuentes:
            self.txt_estado.SetValue(_("La escena no tiene fuentes."))

    def _cargar_ventanas(self, opciones, actual):
        self._valores_ventana = [valor for _sin_uso, valor in opciones or ()]
        self.cho_ventana.Set([texto for texto, _sin_uso in opciones or ()])
        if actual in self._valores_ventana:
            self.cho_ventana.SetSelection(self._valores_ventana.index(actual))
        elif opciones:
            self.cho_ventana.SetSelection(wx.NOT_FOUND)

    def _valor_ventana(self):
        indice = self.cho_ventana.GetSelection()
        if indice == wx.NOT_FOUND or indice < 0 or indice >= len(self._valores_ventana):
            return ""
        return self._valores_ventana[indice]

    def _escena(self):
        return self.cho_escena.GetStringSelection()

    def _fuente(self):
        return self.cho_fuente.GetStringSelection()

    def _leer(self, escena, fuente):
        # Escena y fuente llegan como argumentos: los hilos de trabajo no deben
        # leer controles de wx, eso solo es seguro desde el hilo principal.
        return self._gestor.instantanea(escena, fuente=fuente)

    def _anunciar_snap(self, snap):
        anunciar(obs_disposicion.describir_fuente(
            self._fuente(), snap, obs_disposicion.ACTIVOS_DEFECTO))

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
    def _frase_transmision(estado):
        return obs_estado.frase_transmision(
            estado.get("outputActive", False), estado.get("outputDuration", 0),
            estado.get("outputSkippedFrames", 0), estado.get("outputTotalFrames", 0))

    @staticmethod
    def _frase_grabacion(estado):
        return obs_estado.frase_grabacion(
            estado.get("outputActive", False), estado.get("outputPaused", False),
            estado.get("outputTimecode", ""))

    @staticmethod
    def _frase_escena_al_aire(escena):
        return obs_estado.frase_escena_al_aire(escena)

    def _anunciar_estados(self, transmision, grabacion, al_aire):
        anunciar(self._frase_transmision(transmision))
        anunciar(self._frase_grabacion(grabacion))
        anunciar(self._frase_escena_al_aire(al_aire))

    def _actualizar(self, event):
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._leer_estados(escena, fuente), self._estados_leidos)

    def _leer_estados(self, escena, fuente):
        return (self._leer(escena, fuente), self._gestor.escena_al_aire(),
                self._gestor.estado_transmision(), self._gestor.estado_grabacion(),
                *self._gestor.ventanas(escena),
                self._gestor.descripcion_escena())

    def _estados_leidos(self, datos):
        snap, al_aire, transmision, grabacion, opciones, actual, descripcion = datos
        self._mostrar_snap(snap)
        self._mostrar_vista(descripcion)
        self._mostrar_estados(transmision, grabacion, al_aire)
        self._cargar_ventanas(opciones, actual)
        self._anunciar_snap(snap)
        self._anunciar_estados(transmision, grabacion, al_aire)

    def _poner_al_aire(self, event):
        escena = self._escena()
        self._en_hilo(lambda: self._gestor.poner_escena_al_aire(escena),
                      self._escena_puesta_al_aire)

    def _usar_ventana(self, event):
        escena = self._escena()
        valor = self._valor_ventana()
        if not valor:
            anunciar(_("Elige primero una ventana en Ventana que se captura."))
            return
        self._en_hilo(lambda: self._aplicar_ventana(escena, valor),
                      self._ventana_aplicada)

    def _aplicar_ventana(self, escena, valor):
        # Escena y valor viajan como argumentos: los hilos no leen controles.
        return consultas_transmision.aplicar_ventana(self._gestor, escena, valor)

    def _ventana_aplicada(self, datos):
        self._cargar_fuentes(datos.fuentes, datos.fuente)
        self._mostrar_snap(datos.snap)
        self._mostrar_estados(datos.transmision, datos.grabacion, datos.al_aire)
        self._cargar_ventanas(datos.opciones, datos.actual)
        anunciar(datos.frase)

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
                from ytchat.capture import tiktok_vivo
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
            except Exception:
                pass
            self._mostrar_transmision(False)
            return
        if decision == transmision_directa.FALTA_DESTINO:
            anunciar(_("Elige primero a dónde transmitir, en Transmitir a."))
            return
        if decision == transmision_directa.FALTA_USUARIO:
            anunciar(_("Escribe tu usuario de TikTok en Tu usuario de TikTok."))
            self.txt_usuario_tiktok.SetFocus()
            return
        usuario = _usuario() if destino == "TikTok" else ""
        if destino == "TikTok" and usuario != self._usuario_tiktok and self._guardar_usuario is not None:
            try:
                self._guardar_usuario(usuario)
            except Exception:
                pass
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
            except Exception:
                pass

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
        anunciar(obs_estado.frase_resultado(accion))

    def _pausar_grabacion(self, event):
        self._en_hilo(self._gestor.alternar_pausa_grabacion, self._pausa_grabacion_alternada)

    def _pausa_grabacion_alternada(self, en_pausa):
        accion = "grabacion_en_pausa" if en_pausa else "grabacion_reanudada"
        anunciar(obs_estado.frase_resultado(accion))

    def _al_cambiar_destino(self, event):
        # Solo guarda lo elegido, sin anunciar ni preparar: recorrerlo
        # con flechas dispara EVT_CHOICE y preparar ahí saldría al aire.
        self._recordar_destino(self.cho_destino.GetStringSelection())
        event.Skip()

    def _preparar_destino(self, event):
        # Elegir en el desplegable no prepara nada por sí solo: recorrerlo
        # con flechas dispara EVT_CHOICE y eso saldría al aire sin querer.
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
        ancho, alto = self.sp_ancho.GetValue(), self.sp_alto.GetValue()
        self._en_hilo(lambda: self._preparar_panel(escena, ancho, alto), self._panel_preparado)

    def _preparar_panel(self, escena, ancho, alto):
        puerto = overlay_servidor.puerto_actual() or _PUERTO_PANEL_DEFECTO
        if not overlay_servidor.esta_encendido():
            try:
                overlay_servidor.encender(puerto)
            except overlay_servidor.OverlayPuertoOcupadoError:
                return _("No se pudo encender el panel, el puerto {puerto} está ocupado").format(puerto=puerto), (), None
        puerto = overlay_servidor.puerto_actual() or puerto
        fuentes = self._gestor.fuentes(escena)
        if NOMBRE_FUENTE not in fuentes:
            url = f"http://127.0.0.1:{puerto}{_RUTA_PANEL_CHAT}"
            self._gestor.asegurar_fuente(escena, url, ancho, alto)
            fuentes = self._gestor.fuentes(escena)
        snap = self._gestor.instantanea(escena, fuente=NOMBRE_FUENTE)
        frase = obs_disposicion.describir_preparacion(
            snap.conectado, overlay_servidor.esta_encendido(), puerto,
            NOMBRE_FUENTE in fuentes)
        return frase, fuentes, snap

    def _panel_preparado(self, datos):
        frase, fuentes, snap = datos
        if snap is not None:
            self._cargar_fuentes(fuentes, NOMBRE_FUENTE)
            self._mostrar_snap(snap)
        anunciar(frase)

    def _cambiar_escena(self, event):
        if self._operacion_en_vuelo:
            return
        escena = self._escena()
        self._en_hilo(lambda: self._leer_escena(escena), self._escena_cambiada)
        event.Skip()

    def _leer_escena(self, escena):
        return consultas_transmision.leer_escena(self._gestor, escena)

    def _escena_cambiada(self, datos):
        self._cargar_fuentes(datos.fuentes, datos.fuente)
        self._cargar_ventanas(datos.opciones, datos.actual)
        if datos.fuentes:
            self._mostrar_snap(datos.snap)
            self._anunciar_snap(datos.snap)

    def _cambiar_fuente(self, event):
        if self._operacion_en_vuelo:
            return
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._leer(escena, fuente), self._anunciar_snap)
        event.Skip()

    def _colocar(self, event):
        anclaje = tuple(obs_disposicion.ANCLAJES)[self.cho_posicion.GetSelection()]
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._cambiar_y_leer(escena, fuente, self._gestor.colocar, anclaje),
                      self._anunciar_snap)
        event.Skip()

    def _tamano(self, event):
        escena, fuente = self._escena(), self._fuente()
        ancho, alto = self.sp_ancho.GetValue(), self.sp_alto.GetValue()
        self._en_hilo(lambda: self._aplicar_tamano(escena, fuente, ancho, alto),
                      self._tamano_aplicado)

    def _aplicar_tamano(self, escena, fuente, ancho, alto):
        self._restablecimiento.guardar(self._gestor, escena, fuente)
        if fuente == NOMBRE_FUENTE:
            self._gestor.redimensionar(escena, ancho, alto)
            return self._leer(escena, fuente), True
        if not self._gestor.escalar(escena, ancho, alto, fuente=fuente):
            return self._leer(escena, fuente), False
        return self._leer(escena, fuente), True

    def _tamano_aplicado(self, datos):
        snap, aplicado = datos
        self._mostrar_snap(snap)
        if aplicado:
            self._anunciar_snap(snap)
        else:
            anunciar(_("{fuente} todavía no informa su tamaño.").format(fuente=self._fuente()))

    def _mostrar(self, event):
        visible = self.chk_mostrar.GetValue()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._cambiar_y_leer(escena, fuente, self._gestor.mostrar, visible),
                      self._anunciar_snap)
        event.Skip()

    def _fijar(self, event):
        fijada = self.chk_fijar.GetValue()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._cambiar_y_leer(escena, fuente, self._gestor.fijar, fijada),
                      self._anunciar_snap)
        event.Skip()

    def _frente(self, event):
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._cambiar_y_leer(escena, fuente, self._gestor.al_frente),
                      self._anunciar_snap)

    def _iniciar_ajuste(self, event):
        if self._ajuste.en_curso:
            return
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._preparar_ajuste(escena, fuente), self._ajuste_iniciado)

    def _preparar_ajuste(self, escena, fuente):
        self._restablecimiento.guardar(self._gestor, escena, fuente)
        return self._gestor.transformacion(escena, fuente=fuente), self._leer(escena, fuente)

    def _ajuste_iniciado(self, datos):
        transformacion, snap = datos
        self._ajuste.entrar(transformacion)
        self.btn_ajuste.SetLabel(ajuste_fino.etiqueta_boton(True, self._etiqueta_ajuste))
        self._mostrar_snap(snap)
        anunciar(ajuste_fino.texto_de_entrada())
        self._anunciar_ajuste(snap)

    def _tecla_ajuste(self, event):
        if not self._ajuste.en_curso:
            event.Skip()
            return
        accion, dx, dy = ajuste_fino.resolver(
            event.GetKeyCode(), event.ControlDown(), event.ShiftDown())
        if accion == "mover":
            if self._ajuste.puede_mover():
                self._mover_ajuste(dx, dy)
            return
        if accion == "cancelar":
            self._salir_ajuste(False)
            return
        if accion in ("confirmar", "salir"):
            self._salir_ajuste(True)
            if accion == "salir":
                event.Skip()
            return

    def _mover_ajuste(self, dx, dy):
        self._ajuste.empezar_movimiento()
        escena = self._escena()
        fuente = self._fuente()
        def mover():
            try:
                self._gestor.mover(escena, dx, dy, fuente=fuente)
                snap = self._leer(escena, fuente)
            except obs_cliente.ObsError as error:
                wx.CallAfter(self._movimiento_fallo, str(error))
            except Exception as error:
                logger.warning("ajuste fino OBS: %r", error)
                wx.CallAfter(self._movimiento_fallo,
                             obs_cliente.mensaje_de_fallo_obs(error))
            else:
                wx.CallAfter(self._movimiento_terminado, snap)
        diagnostico.crear_hilo(mover, "AjusteFinoOBS").start()

    def _movimiento_terminado(self, snap):
        decision = self._ajuste.aterrizar()
        if self._cerrando:
            return
        if decision == ajuste_fino.DESHACER:
            self._deshacer_ajuste()
        elif decision == ajuste_fino.MOSTRAR:
            self._mostrar_snap(snap)
            self._anunciar_ajuste(snap)

    def _movimiento_fallo(self, mensaje):
        decision = self._ajuste.aterrizar()
        if self._cerrando:
            return
        if decision == ajuste_fino.DESHACER:
            self._deshacer_ajuste()
        elif decision == ajuste_fino.MOSTRAR:
            self._fallo(mensaje)

    def _anunciar_ajuste(self, snap):
        # Aquí la fuente no cambia y ya se anunció al entrar; los otros anuncios pueden cambiar de fuente y llevan nombre.
        anunciar(obs_disposicion.describir(
            snap, ("posicion", "solape", "fuera")), "ajuste")

    def _ajuste_perdio_foco(self, event):
        if self._ajuste.en_curso:
            self._salir_ajuste(True)
        event.Skip()

    def _salir_ajuste(self, confirmar):
        decision = self._ajuste.salir(confirmar)
        if decision == ajuste_fino.NADA:
            return
        self.btn_ajuste.SetLabel(ajuste_fino.etiqueta_boton(False, self._etiqueta_ajuste))
        if decision == ajuste_fino.CONFIRMADO:
            anunciar(_("Ajuste confirmado"))
        elif decision == ajuste_fino.DESHACER:
            self._deshacer_ajuste()

    def _deshacer_ajuste(self):
        transformacion = self._ajuste.tomar_para_deshacer()
        if not transformacion:
            # transformacion() devuelve {} cuando la fuente ya no está en la
            # escena; no hay a dónde volver.
            anunciar(_("No se pudo deshacer el ajuste"))
            return
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(
            lambda: self._gestor.posicionar(
                escena, transformacion["positionX"],
                transformacion["positionY"], transformacion["alignment"], fuente=fuente),
            lambda resultado: anunciar(_("Ajuste deshecho")))

    def _cambiar_y_leer(self, escena, fuente, funcion, *argumentos):
        self._restablecimiento.guardar(self._gestor, escena, fuente)
        funcion(escena, *argumentos, fuente=fuente)
        return self._leer(escena, fuente)

    def _captura(self, event):
        # Traductores: traduce solo «Imagen PNG»; no cambies «(*.png)|*.png».
        with wx.FileDialog(self, _("Guardar una captura de la escena"), wildcard=_("Imagen PNG (*.png)|*.png"),
                           defaultFile="captura-escena.png", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialogo:
            if dialogo.ShowModal() != wx.ID_OK:
                return
            ruta = dialogo.GetPath()
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._guardar_captura(escena, fuente, ruta),
                      lambda resultado: anunciar(_("Captura guardada")))

    def _guardar_captura(self, escena, fuente, ruta):
        self._gestor.captura_de_escena(escena, ruta)
        return self._leer(escena, fuente)

    def _lienzo(self, event):
        wx.MessageBox(_(_TEXTO_LIENZO), _("Qué es el lienzo"), wx.OK | wx.ICON_INFORMATION, self)

    def _como_se_coloca(self, event):
        wx.MessageBox(_(_TEXTO_COMO_SE_COLOCA), _("Cómo se coloca el panel"),
                      wx.OK | wx.ICON_INFORMATION, self)

    def _restaurar(self, event):
        escena, fuente = self._escena(), self._fuente()
        self._en_hilo(lambda: self._aplicar_restauracion(escena, fuente),
                      lambda snap: anunciar(_("Restablecido")))

    def _aplicar_restauracion(self, escena_actual, fuente_actual):
        self._restablecimiento.aplicar(self._gestor)
        return self._leer(escena_actual, fuente_actual)

    def _cerrar(self, event):
        if self._cerrando:
            return
        self._cerrando = True
        self._temporizador_consulta.Stop()
        diagnostico.crear_hilo(self._cerrar_gestor, "CerrarTransmisionOBS").start()
        self.EndModal(wx.ID_CANCEL)

    def _cerrar_gestor(self):
        try:
            self._gestor.cerrar()
        except Exception:
            pass


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
