"""Botón directo de transmisión en la ventana principal, con wx.

Crea el botón en el panel que le pasan y concentra la lógica de wx
(visibilidad, etiqueta, nombre accesible, foco y repintado). El trabajo
de fondo (preparar OBS, confirmar, supervisar, finalizar) usa
`transmision_directa`, sin decidir nada en el marco: este solo crea el
botón, lo mete en la fila y le pide `actualizar`.
"""

from __future__ import annotations

import wx

from ytchat.core import diagnostico
from ytchat.obs import obs_cliente
from ytchat.obs import obs_lanzador
from ytchat.obs import transmision_directa
from ytchat.obs.obs_panel import GestorPanelObs
from ytchat.ui.gui import _T, _pintar, anunciar
from ytchat.voice import sound_player as _snd


class BotonDirecto:
    """Botón «Transmitir en directo» / «Finalizar directo»."""

    def __init__(self, panel, btn_conectar, marco):
        etiqueta, nombre = transmision_directa.etiqueta(False)
        self._marco = marco
        self._conectar = btn_conectar
        self._transmitiendo = False
        self.boton = wx.Button(panel, label=etiqueta, name=nombre)
        _pintar(self.boton, _T.primary, _T.primary_t)
        self.boton.SetFont(self.boton.GetFont().Bold())
        self.boton.Bind(wx.EVT_BUTTON, self._al_pulsar)

    def actualizar(self, conectado, conectando, propio, transmitiendo):
        """Aplica visibilidad, etiqueta y nombre; repinta la fila.

        Oculto sale del orden de Tab; si tenía el foco, este vuelve a
        Conectar para no quedar en un control invisible.
        """
        self._transmitiendo = bool(transmitiendo)
        etiqueta, nombre = transmision_directa.etiqueta(transmitiendo)
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
        if self._transmitiendo:
            self._finalizar()
        else:
            self._transmitir()

    def _transmitir(self):
        marco = self._marco
        from ytchat.ui.gui_elegir_destino import pedir_destino
        destino_guardado = marco._config.get("transmision_destino", "") or ""
        usuario_guardado = marco._config.get("tiktok_usuario", "") or ""
        elegido = pedir_destino(marco, destino_guardado, usuario_guardado)
        if elegido is None:
            anunciar("No se transmitió.")
            return
        destino, usuario = elegido
        try:
            marco._guardar_destino_transmision(destino)
        except Exception:
            pass
        if destino == "TikTok":
            try:
                usuario = marco._guardar_usuario_tiktok(usuario)
            except Exception:
                pass
        _snd.reproducir("conectando")
        anunciar("Revisando OBS antes de transmitir.")
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
            anunciar("OBS ya está transmitiendo. Con este mismo botón "
                      "puedes finalizar el directo.")
            marco._actualizar_boton_directo()
            return
        if destino == "YouTube":
            marco._supervisar_transmision(
                "iniciar", destino, usuario,
                revision=preparacion.revision)
            marco._actualizar_boton_directo()
            return
        from ytchat.ui.gui_transmision import confirmar_transmision
        if not confirmar_transmision(marco, preparacion.revision):
            anunciar("No se transmitió.")
            return
        marco._supervisar_transmision("iniciar", destino, usuario)
        marco._actualizar_boton_directo()

    def _finalizar(self):
        marco = self._marco
        dialogo = wx.MessageDialog(
            marco,
            "¿Finalizar el directo? Quienes te están viendo dejarán de verte.",
            "Finalizar directo", wx.YES_NO | wx.NO_DEFAULT)
        try:
            dialogo.SetYesNoLabels("&Finalizar directo",
                                   "&Seguir transmitiendo")
            seguir = dialogo.ShowModal() != wx.ID_YES
        finally:
            dialogo.Destroy()
        if seguir:
            anunciar("Sigues transmitiendo.")
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
            from ytchat.youtube import credenciales, emision, youtube_api
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
                    except Exception:
                        pass

        return _cerrar

    def _finalizada(self):
        marco = self._marco
        if not marco._alive:
            return
        marco._obs_transmitiendo = False
        _snd.reproducir("desconectado")
        anunciar("Transmisión detenida.")
        marco._actualizar_boton_directo()

    def _finalizada_con_error(self, error):
        if not self._marco._alive:
            return
        if isinstance(error, transmision_directa.FalloCierreYoutube):
            _snd.reproducir("error")
            anunciar(str(error))
            try:
                diagnostico.obtener_logger(__name__).warning(
                    "cierre en YouTube sin supervisor: %s",
                    error.__cause__ or error)
            except Exception:
                pass
            return
        _snd.reproducir("error")
        anunciar(obs_cliente.mensaje_de_fallo_obs(error))
