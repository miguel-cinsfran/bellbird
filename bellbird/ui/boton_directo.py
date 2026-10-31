"""Botón directo de transmisión en la ventana principal, con wx.

Crea el botón en el panel que le pasan y concentra la lógica de wx
(visibilidad, etiqueta, nombre accesible, foco y repintado). El trabajo
de fondo (preparar OBS, confirmar, supervisar, finalizar) usa
`transmision_directa`, sin decidir nada en el marco: este solo crea el
botón, lo mete en la fila y le pide `actualizar`.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_cliente
from bellbird.obs import obs_lanzador
from bellbird.obs import transmision_directa
from bellbird.obs.obs_panel import GestorPanelObs
from bellbird.ui.accesibilidad import anunciar
from bellbird.ui.tema import _T, _pintar
from bellbird.voice import sound_player as _snd

logger = diagnostico.obtener_logger(__name__)


class BotonDirecto:
    """Botón «Transmitir en directo» / «Finalizar directo»."""

    def __init__(self, panel, btn_conectar, marco):
        etiqueta, nombre = transmision_directa.etiqueta(False)
        self._marco = marco
        self._conectar = btn_conectar
        self._transmitiendo = False
        self._deteniendo = False
        self.boton = wx.Button(panel, label=etiqueta, name=nombre)
        _pintar(self.boton, _T.btn, _T.btn_t)
        self.boton.SetFont(self.boton.GetFont().Bold())
        self.boton.Bind(wx.EVT_BUTTON, self._al_pulsar)

    def actualizar(self, conectado, conectando, propio, transmitiendo,
                   deteniendo=False):
        """Aplica visibilidad, etiqueta y nombre; repinta la fila.

        Oculto sale del orden de Tab; si tenía el foco, este vuelve a
        Conectar para no quedar en un control invisible. Mientras se
        detiene sigue visible y habilitado, solo cambia lo que dice.
        """
        self._transmitiendo = bool(transmitiendo)
        self._deteniendo = bool(deteniendo)
        etiqueta, nombre = transmision_directa.etiqueta(transmitiendo,
                                                         deteniendo)
        self.boton.SetLabel(etiqueta)
        self.boton.SetName(nombre)
        if transmision_directa.boton_visible(conectado, conectando, propio,
                                             transmitiendo):
            self.boton.Show()
        else:
            if self.boton.HasFocus():
                self._conectar.SetFocus()
            self.boton.Hide()
        self.boton.GetParent().Layout()

    def _al_pulsar(self, event):
        if self._deteniendo:
            anunciar(_("Deteniendo la transmisión. Esperando a que OBS confirme."))
            return
        if self._transmitiendo:
            self._finalizar()
        else:
            self._transmitir()

    def _transmitir(self):
        marco = self._marco
        from bellbird.ui.gui_elegir_destino import pedir_destino
        destino_guardado = marco._config.get("transmision_destino", "") or ""
        usuario_guardado = marco._config.get("tiktok_usuario", "") or ""
        elegido = pedir_destino(marco, destino_guardado, usuario_guardado)
        if elegido is None:
            anunciar(_("No se transmitió."))
            return
        destino, usuario = elegido
        try:
            marco._guardar_destino_transmision(destino)
        except Exception as error:
            logger.warning("no se pudo guardar el destino de transmisión: %s", error)
        if destino == "TikTok":
            try:
                usuario = marco._guardar_usuario_tiktok(usuario)
            except Exception as error:
                logger.warning("no se pudo guardar el usuario de TikTok: %s", error)
        _snd.reproducir("conectando")
        anunciar(_("Revisando OBS antes de transmitir."))
        self.boton.Disable()

        def _revisar():
            try:
                preparacion = transmision_directa.preparar(
                    GestorPanelObs(), destino, obs_lanzador.asegurar_obs,
                    lambda frase: wx.CallAfter(anunciar, frase))
            except Exception as error:
                wx.CallAfter(self._revision_fallida, error)
            else:
                wx.CallAfter(self._revision_lista, preparacion, destino,
                             usuario)

        diagnostico.crear_hilo(_revisar, "BotonDirectoRevisar").start()

    def _revision_fallida(self, error):
        if not self._marco._alive:
            return
        self.boton.Enable()
        _snd.reproducir("error")
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))

    def _revision_lista(self, preparacion, destino, usuario):
        marco = self._marco
        if not marco._alive:
            return
        self.boton.Enable()
        if preparacion.ya_transmitiendo:
            marco._obs_transmitiendo = True
            anunciar(_("OBS ya está transmitiendo. Con este mismo botón "
                      "puedes finalizar el directo."))
            marco._actualizar_boton_directo()
            return
        if destino == "YouTube":
            marco._supervisar_transmision(
                "iniciar", destino, usuario,
                revision=preparacion.revision)
            marco._actualizar_boton_directo()
            return
        from bellbird.ui.gui_transmision import confirmar_transmision
        if not confirmar_transmision(marco, preparacion.revision):
            anunciar(_("No se transmitió."))
            return
        marco._supervisar_transmision("iniciar", destino, usuario)
        marco._actualizar_boton_directo()

    def _finalizar(self):
        marco = self._marco
        dialogo = wx.MessageDialog(
            marco,
            _("¿Finalizar el directo? Quienes te están viendo dejarán de verte."),
            _("Finalizar directo"), wx.YES_NO | wx.NO_DEFAULT)
        try:
            dialogo.SetYesNoLabels(_("&Finalizar directo"),
                                   _("&Seguir transmitiendo"))
            seguir = dialogo.ShowModal() != wx.ID_YES
        finally:
            dialogo.Destroy()
        if seguir:
            anunciar(_("Sigues transmitiendo."))
            return
        if marco._supervisar_transmision("activo"):
            marco._supervisar_transmision("detener")
            marco._actualizar_boton_directo()
            return

        finalizar_youtube = self._cierre_en_youtube()

        def _detener():
            try:
                transmision_directa.finalizar(
                    GestorPanelObs(),
                    finalizar_youtube=finalizar_youtube)
            except Exception as error:
                wx.CallAfter(self._finalizada_con_error, error)
            else:
                wx.CallAfter(self._finalizada)

        diagnostico.crear_hilo(_detener, "BotonDirectoFinalizar").start()

    def _cierre_en_youtube(self):
        """Callable sin argumentos que cierra el directo en YouTube.

        Solo con sesión iniciada, con las mismas credenciales que arma
        `gui.py` al supervisar: busca las emisiones activas atadas al
        flujo reutilizable de la cuenta y las finaliza. Sin sesión
        devuelve None y OBS se detiene como hoy.
        """
        try:
            from bellbird.youtube import credenciales, emision, youtube_api
        except Exception:
            return None
        try:
            datos = credenciales.cargar()
        except Exception:
            return None
        if not credenciales.hay_sesion(datos):
            return None
        try:
            cliente = youtube_api.ClienteYouTube(
                credenciales.efectivas(datos))
        except Exception:
            return None

        def _cerrar():
            try:
                flujo = cliente.flujo_reutilizable()
                id_flujo = flujo[0] if flujo else ""
                if not id_flujo:
                    return
                for id_video, atado, _titulo in cliente.emisiones_activas():
                    if atado == id_flujo:
                        emision.finalizar_en_youtube(cliente, id_video)
            finally:
                try:
                    nuevo = cliente.token_actualizado()
                except Exception:
                    nuevo = None
                if nuevo:
                    try:
                        credenciales.guardar_campo("token", nuevo)
                    except Exception as error:
                        logger.warning("no se pudo guardar el token actualizado: %s", error)

        return _cerrar

    def _finalizada(self):
        marco = self._marco
        if not marco._alive:
            return
        marco._obs_transmitiendo = False
        _snd.reproducir("desconectado")
        anunciar(_("Transmisión detenida."))
        marco._actualizar_boton_directo()

    def _finalizada_con_error(self, error):
        if not self._marco._alive:
            return
        if isinstance(error, transmision_directa.FalloCierreYoutube):
            _snd.reproducir("error")
            anunciar(str(error))
            logger.warning(
                "cierre en YouTube sin supervisor: %s",
                error.__cause__ or error)
            return
        _snd.reproducir("error")
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))
