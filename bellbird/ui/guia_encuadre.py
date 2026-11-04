"""La guía de encuadre con pitidos, en marcha.

Su única razón para cambiar: la guía en marcha, con su hilo, sus
pitidos, su fin y la pausa de la lectura. `encuadre_camara` la arranca y
la detiene por la API pública (`Guia` con `iniciar`, `detener` y
`en_marcha`), pasándole el marco, la fuente, si invierte, el timbre y una
función al terminar; ninguna lee privados de la otra.
"""

from __future__ import annotations

import threading
import time
import weakref

import wx

from bellbird.camera import guia, tono_guia
from bellbird.camera.detector_rostros import DetectorRostros, disponible
from bellbird.core import diagnostico, paths
from bellbird.core.idioma import N_, _
from bellbird.obs import obs_activacion, obs_camara, obs_cliente
from bellbird.obs.obs_camara import CamaraNoEncontrada
from bellbird.obs.obs_captura_ia import CapturaFallida
from bellbird.ui import ia_agregar_captura
from bellbird.ui.accesibilidad import anunciar
from bellbird.voice import sonido_memoria
from bellbird.voice.sound_player import reproducir_archivo


logger = diagnostico.obtener_logger(__name__)

# Traductores: anuncio al empezar la guía de encuadre con pitidos.
TEXTO_GUIA_INICIO = N_("Guía de encuadre. Sigue los pitidos.")
# Traductores: anuncio al terminar la guía de encuadre.
TEXTO_GUIA_DETENIDA = N_("Guía de encuadre detenida.")
# Traductores: aviso cuando el detector de rostros no está instalado.
TEXTO_GUIA_SIN_DETECTOR = N_("El detector de rostros no está instalado.")

# Ritmo de cuadros de la guía y duración máxima antes de detenerse sola.
INTERVALO_GUIA = 0.05
DURACION_MAXIMA_GUIA = 60.0


class Guia:
    """Una guía de encuadre en marcha: hilo, pitidos, fin y pausa."""

    def __init__(self):
        self._hilo = None
        self._parada = None
        self._marcha = None
        self._pausa_tomada = False
        self._al_terminar = None
        self._marco = lambda: None
        self._timbre = "normal"
        self._centro_sonando = False
        self._dueno_centro = None

    def en_marcha(self) -> bool:
        """¿La guía está sonando en su hilo?"""
        hilo = self._hilo
        return hilo is not None and hilo.is_alive()

    def iniciar(self, marco, fuente: str, invertir: bool, timbre: str,
                al_terminar) -> bool:
        """Anuncia el inicio, pausa la lectura y lanza el hilo."""
        if self.en_marcha():
            return False
        if marco is None:
            return False
        if not disponible():
            anunciar(_(TEXTO_GUIA_SIN_DETECTOR))
            return False
        if not obs_activacion.obs_esta_en_ejecucion():
            anunciar(_(ia_agregar_captura.TEXTO_OBS_CERRADO))
            return False
        anunciar(_(TEXTO_GUIA_INICIO))
        self._tomar_pausa(marco)
        try:
            self._marco = weakref.ref(marco)
        except TypeError:
            self._marco = lambda: marco
        self._al_terminar = al_terminar
        self._timbre = tono_guia.normalizar_timbre(timbre)
        self._centro_sonando = False
        self._dueno_centro = None
        parada = threading.Event()
        self._parada = parada
        self._hilo = diagnostico.crear_hilo(
            lambda: self._bucle(fuente, invertir, parada), "GuiaEncuadre")
        self._hilo.start()
        return True

    def _tomar_pausa(self, marco) -> None:
        """Pausa la lectura si no lo estaba y recuerda si hay que devolverla."""
        try:
            pausada = marco._worker.esta_pausado()
            if not pausada:
                marco._worker.toggle_pausa()
            self._pausa_tomada = not pausada
        except Exception as fallo:
            logger.warning("GuiaEncuadre: sin pausa: %s", fallo)
            self._pausa_tomada = False

    def detener(self, mensaje) -> None:
        """Cierra la guía: corta el tono, devuelve la pausa, avisa y dice el final."""
        sonido_memoria.detener()
        self._centro_sonando = False
        self._dueno_centro = None
        parada, self._parada = self._parada, None
        self._hilo = None
        if parada is not None:
            parada.set()
        marco = self._marco()
        tomada, self._pausa_tomada = self._pausa_tomada, False
        if tomada and marco is not None:
            try:
                marco._worker.toggle_pausa()
            except Exception as fallo:
                logger.warning("GuiaEncuadre: sin reanudar: %s", fallo)
        terminar, self._al_terminar = self._al_terminar, None
        if terminar is not None:
            try:
                terminar()
            except Exception as fallo:
                logger.warning("GuiaEncuadre: sin cerrar: %s", fallo)
        if mensaje is not None and marco is not None:
            anunciar(mensaje)

    def _bucle(self, fuente: str, invertir: bool, parada=None) -> None:
        """Pitidos hacia el centro hasta 1,5 s seguidos, 60 s o un fallo."""
        if parada is None:
            parada = self._parada
        if self._marco() is None:
            wx.CallAfter(self.detener, None)
            return
        try:
            cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
            cliente.conectar()
            camara = obs_camara.buscar_camara(cliente, fuente)
        except Exception as fallo:
            wx.CallAfter(self.detener, _texto_fallo(fallo))
            return
        self._centro_sonando = False
        self._dueno_centro = None
        marcha = guia.Marcha(
            inicio=time.monotonic(), cliente=cliente, camara=camara,
            detector=DetectorRostros(),
            espejo=camara.espejo != invertir)
        self._marcha = marcha
        try:
            while parada is not None and not parada.is_set():
                if not self._paso(time.monotonic(), parada):
                    return
                parada.wait(INTERVALO_GUIA)
        finally:
            self._soltar(marcha, parada)

    def _soltar(self, marcha, parada) -> None:
        """Al salir del bucle: corta el tono propio y cierra OBS."""
        if parada is not None and parada.is_set() and \
                self._dueno_centro is threading.current_thread():
            sonido_memoria.detener()
            self._centro_sonando = False
            self._dueno_centro = None
        if self._marcha is marcha:
            self._marcha = None
        try:
            marcha.cliente.cerrar()
        except Exception as fallo:
            logger.warning("GuiaEncuadre: no se pudo cerrar OBS: %s", fallo)

    def _paso(self, ahora: float, parada=None) -> bool:
        """Un cuadro de la guía: pitido o final. False si ya terminó."""
        marcha = self._marcha
        if ahora - marcha.inicio >= DURACION_MAXIMA_GUIA:
            wx.CallAfter(self.detener, _(TEXTO_GUIA_DETENIDA))
            return False
        try:
            bmp = obs_camara.capturar_cuadro(marcha.cliente, marcha.camara)
            cuadro = marcha.detector.analizar(bmp)
        except Exception as fallo:
            wx.CallAfter(self.detener, _texto_fallo(fallo))
            return False
        accion, tono, frase_final = guia.cuadro(
            marcha, cuadro.rostros, cuadro.ancho, cuadro.alto,
            cuadro.luz_rostro, cuadro.luz_fondo, ahora)
        if accion == "lista":
            self._terminar_lista(frase_final)
            return False
        self._sonar(accion, tono, parada)
        return True

    def _sonar(self, accion, tono, parada=None) -> None:
        """El tono del centro, un pitido o el aviso sin rostro."""
        if parada is not None and parada.is_set():
            return
        if accion == "centro":
            if not self._centro_sonando:
                self._centro_sonando = sonido_memoria.reproducir(
                    tono_guia.tono_centro(self._timbre), bucle=True)
                if self._centro_sonando:
                    self._dueno_centro = threading.current_thread()
            return
        if self._centro_sonando:
            sonido_memoria.detener()
            self._centro_sonando = False
            self._dueno_centro = None
        if accion == "pitido":
            sonido_memoria.reproducir(
                tono_guia.pitido(tono.paneo, tono.frecuencia, self._timbre))
        elif accion == "sin_rostro":
            reproducir_archivo(paths.carpeta_guia() / "sin_rostro.wav")

    def _terminar_lista(self, frase_final) -> None:
        """Confirma el encuadre y cierra la guía."""
        sonido_memoria.detener()
        self._centro_sonando = False
        self._dueno_centro = None
        reproducir_archivo(paths.carpeta_guia() / "listo.wav")
        wx.CallAfter(self.detener, frase_final)


def _texto_fallo(fallo) -> str:
    """El texto del fallo de OBS o cámara para cerrar la guía."""
    if isinstance(fallo, (CamaraNoEncontrada, CapturaFallida)):
        return str(fallo)
    return obs_cliente.mensaje_de_fallo_obs(fallo)
