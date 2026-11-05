"""Iniciar y finalizar el directo desde el panel de transmisión.

Vive aparte de la ventana por composición: recibe los controles, el gestor y
las funciones que necesita, y no lee atributos privados de la ventana. Su
única razón para cambiar es el camino del directo en este panel.
"""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import obs_estado
from guyrapu.obs import transmision_directa
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.confirmar_transmision import (
    confirmar_finalizar, confirmar_transmision)
from guyrapu.voice import sound_player

logger = diagnostico.obtener_logger(__name__)


class DirectoPanel:
    """El botón del directo del panel y su espera a que OBS se detenga."""

    def __init__(self, ventana, boton, operaciones, gestor, supervisar,
                 guardar_usuario, guardar_destino, usuario_guardado, asegurar,
                 datos_directo, al_cambiar):
        self._ventana = ventana
        self._boton = boton
        self._operaciones = operaciones
        self._gestor = gestor
        self._supervisar = supervisar
        self._guardar_usuario = guardar_usuario
        self._guardar_destino = guardar_destino
        self._usuario_guardado = usuario_guardado or ""
        self._asegurar = asegurar
        self._datos_directo = datos_directo
        self._al_cambiar = al_cambiar
        self._transmitiendo = False
        self._deteniendo = False
        self._temporizador = wx.Timer(ventana)
        ventana.Bind(wx.EVT_TIMER, self._al_temporizador, self._temporizador)
        boton.Bind(wx.EVT_BUTTON, self._al_pulsar)
        self._actualizar_boton()

    @property
    def transmitiendo(self) -> bool:
        return self._transmitiendo

    @property
    def deteniendo(self) -> bool:
        return self._deteniendo

    def sincronizar(self, transmitiendo, deteniendo=False) -> None:
        """Ajusta el estado y la etiqueta sin pedir nada a OBS."""
        self._transmitiendo = bool(transmitiendo)
        self._deteniendo = bool(deteniendo)
        self._actualizar_boton()

    def cerrar(self) -> None:
        self._temporizador.Stop()

    def _actualizar_boton(self) -> None:
        etiqueta, nombre = transmision_directa.etiqueta(
            self._transmitiendo, self._deteniendo)
        self._boton.SetLabel(etiqueta)
        self._boton.SetName(nombre)

    def _al_pulsar(self, event) -> None:
        if self._deteniendo:
            anunciar(_("Deteniendo la transmisión. "
                       "Esperando a que OBS confirme."))
            return
        if self._transmitiendo:
            self._finalizar()
        else:
            self._transmitir()

    def _normalizar_usuario(self, destino, usuario) -> str:
        if destino != "TikTok":
            return ""
        from guyrapu.capture import tiktok_vivo
        return tiktok_vivo.usuario_tiktok(usuario or "")

    def _transmitir(self) -> None:
        destino, usuario = self._datos_directo()
        usuario = self._normalizar_usuario(destino, usuario)

        def _preguntar(accion):
            try:
                return bool(self._supervisar(accion))
            except Exception:
                return False

        decision = transmision_directa.decidir_transmision(
            hay_supervisor=self._supervisar is not None,
            deteniendo=lambda: _preguntar("deteniendo"),
            con_supervisor=lambda: _preguntar("activo"),
            transmitiendo=self._transmitiendo,
            destino=destino, usuario_tiktok=lambda: usuario)
        if decision == transmision_directa.ALTERNAR:
            self._operaciones.en_hilo(
                self._gestor.alternar_transmision,
                self._transmision_alternada)
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
            self._al_cambiar("usuario")
            return
        sound_player.reproducir("conectando")
        anunciar(_("Revisando OBS antes de transmitir."))
        self._operaciones.en_hilo(
            lambda: self._preparar(destino),
            lambda preparacion: self._revision_lista(
                preparacion, destino, usuario))

    def _preparar(self, destino):
        return transmision_directa.preparar(
            self._gestor, destino, self._asegurar,
            lambda frase: wx.CallAfter(anunciar, frase), cerrar=False)

    def _guardar_usuario_tiktok(self, usuario) -> None:
        if usuario == self._usuario_guardado or self._guardar_usuario is None:
            return
        try:
            self._guardar_usuario(usuario)
        except Exception as error:
            logger.warning("no se pudo guardar el usuario de TikTok: %s", error)
        self._usuario_guardado = usuario

    def recordar_destino(self, destino) -> None:
        self._recordar_destino(destino)

    def _recordar_destino(self, destino) -> None:
        if self._guardar_destino is None:
            return
        try:
            self._guardar_destino(destino)
        except Exception as error:
            logger.warning("no se pudo guardar el destino de transmisión: %s", error)

    def _revision_lista(self, preparacion, destino, usuario) -> None:
        if preparacion.ya_transmitiendo:
            self._recordar_destino(destino)
            self._mostrar_transmision(True)
            anunciar(_("OBS ya está transmitiendo. Con este mismo botón "
                       "puedes finalizar el directo."))
            return
        if destino == "YouTube":
            self._recordar_destino(destino)
            self._supervisar("iniciar", destino, usuario,
                             revision=preparacion.revision)
            self._mostrar_transmision(True)
            return
        if not confirmar_transmision(self._ventana, preparacion.revision):
            anunciar(_("No se transmitió."))
            return
        self._guardar_usuario_tiktok(usuario)
        self._recordar_destino(destino)
        self._supervisar("iniciar", destino, usuario)
        self._mostrar_transmision(True)

    def _mostrar_transmision(self, activa) -> None:
        self._transmitiendo = bool(activa)
        self._deteniendo = False
        self._actualizar_boton()
        self._al_cambiar()

    def _transmision_alternada(self, activa) -> None:
        self._mostrar_transmision(activa)
        accion = "transmision_iniciada" if activa else "transmision_detenida"
        sound_player.reproducir(obs_estado.sonido_resultado(accion))
        anunciar(obs_estado.frase_resultado(accion))

    def _finalizar(self) -> None:
        if not confirmar_finalizar(self._ventana):
            anunciar(_("Sigues transmitiendo."))
            return
        try:
            activa = bool(self._supervisar("activo"))
        except Exception:
            activa = False
        if self._supervisar is not None and activa:
            try:
                self._supervisar("detener")
            except Exception as error:
                logger.debug("no se pudo detener la supervisión: %s", error)
            self._deteniendo = True
            self._actualizar_boton()
            self._temporizador.Start(2000)
            self._al_cambiar()
            return
        self._operaciones.en_hilo(
            lambda: transmision_directa.finalizar(self._gestor),
            self._finalizada)

    def _finalizada(self, _resultado) -> None:
        self._mostrar_transmision(False)
        sound_player.reproducir("desconectado")
        anunciar(_("Transmisión detenida."))

    def _al_temporizador(self, event) -> None:
        if not self._deteniendo:
            self._temporizador.Stop()
            return
        try:
            deteniendo = bool(self._supervisar("deteniendo"))
        except Exception:
            deteniendo = False
        if deteniendo:
            return
        self._temporizador.Stop()
        self._mostrar_transmision(False)
