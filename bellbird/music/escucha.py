"""Escucha previa de un resultado de búsqueda con reproductor propio.

Razón: reproducir un solo audio por URL con su propio reproductor de
libVLC, sin tocar el reproductor principal ni el coordinador de música.
Sin wx: el aviso sale desde cualquier hilo y quien escucha lo lleva a la
GUI. Los callbacks de libVLC nunca cierran nada: solo avisan y el cierre
corre en un hilo aparte.
"""

from __future__ import annotations

import threading

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.music import enlaces
from bellbird.player import motor_vlc


logger = diagnostico.obtener_logger(__name__)

TEXTO_FALLO_CARGA = N_("No se pudo cargar el audio. Comprueba la conexión e inténtalo de nuevo.")
TEXTO_SIN_MOTOR = N_("No se pudo iniciar el reproductor de audio.")


def _opciones_audio() -> tuple:
    """Opciones de red del reproductor, como las del adaptador de música.

    Se importan al momento para no arrastrar la interfaz al cargar este
    módulo. Si no se pueden importar, ninguna: el medio igual suena.
    """
    try:
        from bellbird.player.reproductor import opciones_medio
    except Exception:
        return ()
    return opciones_medio(False, solo_audio=True)


class Escucha:
    """Un solo audio por URL, con pausa, reanudación y detención.

    `aviso(evento, detalle="")` se llama desde cualquier hilo. Eventos:
    "cargando", "sonando", "pausa", "reanudada", "fin" y "fallo". Estados:
    "inactivo", "cargando", "sonando" y "en_pausa".
    """

    def __init__(self, aviso, resolver=enlaces.url_audio, dispositivo=None,
                 volumen=100, salida_audio=motor_vlc.SALIDA_AUDIO):
        self._aviso_fn = aviso
        self._resolver_fn = resolver
        self._dispositivo = dispositivo
        self._volumen = volumen
        self._salida_audio = salida_audio
        self._lock = threading.Lock()
        self._generacion = 0
        self._estado = "inactivo"
        self._url = None
        self._actual = None
        self._callbacks = ()

    @property
    def estado(self) -> str:
        """Lo que está haciendo: inactivo, cargando, sonando o en_pausa."""
        with self._lock:
            return self._estado

    @property
    def url(self):
        """La URL que está sonando, o None si no hay ninguna."""
        with self._lock:
            return self._url

    def alternar(self, url) -> None:
        """La misma URL pausa o reanuda; otra URL u otra vez empieza.

        Con la misma URL sonando se pausa y en pausa se reanuda; cargando
        no hace nada. Otra URL, o en inactivo, detiene lo anterior y
        empieza con la nueva.
        """
        with self._lock:
            if self._estado == "cargando":
                return
            if url == self._url and self._estado in ("sonando", "en_pausa"):
                reproductor = self._actual
                generacion = self._generacion
                a_pausa = self._estado == "sonando"
            else:
                reproductor = None
        if reproductor is not None:
            self._pausar_o_reanudar(reproductor, generacion, a_pausa)
            return
        self._empezar(url)

    def detener(self) -> None:
        """Detiene lo que suena, sin avisar. Repetirlo no hace nada.

        Sube la generación para que una resolución tardía o un evento
        viejo de libVLC se descarten, y cierra en un hilo aparte.
        """
        with self._lock:
            self._generacion += 1
            reproductor, callbacks = self._actual, self._callbacks
            self._actual, self._callbacks = None, ()
            self._estado, self._url = "inactivo", None
        if reproductor is not None:
            self._cerrar_en_hilo(reproductor, callbacks)

    def _pausar_o_reanudar(self, reproductor, generacion, a_pausa) -> None:
        try:
            reproductor.set_pause(1 if a_pausa else 0)
        except Exception:
            logger.debug("No se pudo pausar la escucha")
            self._fallar(generacion, _(TEXTO_FALLO_CARGA))
            return
        with self._lock:
            if generacion != self._generacion or reproductor is not self._actual:
                return
            self._estado = "en_pausa" if a_pausa else "sonando"
        self._avisar("pausa" if a_pausa else "reanudada")

    def _empezar(self, url) -> None:
        with self._lock:
            self._generacion += 1
            generacion = self._generacion
            anterior, callbacks = self._actual, self._callbacks
            self._actual, self._callbacks = None, ()
            self._estado, self._url = "cargando", url
        if anterior is not None:
            self._cerrar_en_hilo(anterior, callbacks)
        self._avisar("cargando")
        diagnostico.crear_hilo(
            self._resolver, "escucha-resolver", args=(url, generacion)).start()

    def _resolver(self, url, generacion) -> None:
        try:
            destino = self._resolver_fn(url)
        except enlaces.ErrorEnlace as exc:
            self._fallar(generacion, str(exc))
            return
        except Exception:
            logger.exception("No se pudo cargar el audio de la escucha")
            self._fallar(generacion, _(TEXTO_FALLO_CARGA))
            return
        with self._lock:
            if generacion != self._generacion:
                return
            instancia = motor_vlc.instancia()
        if instancia is None:
            # Sin instancia no falló la red: el consejo de conexión sería falso.
            self._fallar(generacion, _(TEXTO_SIN_MOTOR))
            return
        self._abrir(instancia, destino, generacion)

    def _abrir(self, instancia, destino, generacion) -> None:
        try:
            reproductor = instancia.media_player_new()
            if reproductor is None:
                raise RuntimeError("VLC no pudo crear un reproductor")
            if self._salida_audio is not None:
                motor_vlc.fijar_salida_audio(reproductor, self._salida_audio)
            if self._dispositivo:
                reproductor.audio_output_device_set(None, self._dispositivo)
            media = instancia.media_new(destino)
            for opcion in _opciones_audio():
                media.add_option(opcion)
            reproductor.set_media(media)
            reproductor.audio_set_volume(self._volumen)
            callbacks = self._enganchar(reproductor, generacion)
        except Exception:
            logger.exception("No se pudo abrir el audio de la escucha")
            self._fallar(generacion, _(TEXTO_FALLO_CARGA))
            return
        with self._lock:
            if generacion != self._generacion:
                viejo = reproductor
            else:
                self._actual = reproductor
                self._callbacks = callbacks
                viejo = None
        if viejo is not None:
            self._cerrar_en_hilo(viejo, callbacks)
            return
        if reproductor.play() == -1:
            self._fallar(generacion, _(TEXTO_FALLO_CARGA))

    def _fallar(self, generacion, motivo) -> None:
        with self._lock:
            if generacion != self._generacion:
                return
            reproductor, callbacks = self._actual, self._callbacks
            self._actual, self._callbacks = None, ()
            self._estado, self._url = "inactivo", None
        if reproductor is not None:
            self._cerrar_en_hilo(reproductor, callbacks)
        self._avisar("fallo", motivo)

    def _enganchar(self, reproductor, generacion):
        vlc = motor_vlc.modulo()
        if vlc is None or not hasattr(vlc, "EventType"):
            return ()

        def al_fin(_evento):
            self._al_terminar(generacion, reproductor, False)

        def al_error(_evento):
            self._al_terminar(generacion, reproductor, True)

        def al_sonar(_evento):
            self._al_sonar(generacion, reproductor)

        callbacks = (
            (vlc.EventType.MediaPlayerEndReached, al_fin),
            (vlc.EventType.MediaPlayerEncounteredError, al_error),
            (vlc.EventType.MediaPlayerPlaying, al_sonar),
        )
        try:
            gestor = reproductor.event_manager()
            for tipo, callback in callbacks:
                gestor.event_attach(tipo, callback)
        except Exception:
            logger.debug("No se pudieron enganchar los eventos de escucha")
        return callbacks

    def _al_sonar(self, generacion, reproductor) -> None:
        with self._lock:
            if generacion != self._generacion or reproductor is not self._actual:
                return
            if self._estado == "sonando":
                return
            self._estado = "sonando"
        self._avisar("sonando")

    def _al_terminar(self, generacion, reproductor, con_error) -> None:
        # Nunca se cierra desde el callback de libVLC: se avisa y el
        # cierre corre en un hilo aparte, encolado acá mismo.
        with self._lock:
            if generacion != self._generacion or reproductor is not self._actual:
                return
            callbacks = self._callbacks
            self._actual, self._callbacks = None, ()
            self._estado, self._url = "inactivo", None
        if con_error:
            self._avisar("fallo", _(TEXTO_FALLO_CARGA))
        else:
            self._avisar("fin")
        self._cerrar_en_hilo(reproductor, callbacks)

    def _cerrar_en_hilo(self, reproductor, callbacks) -> None:
        diagnostico.crear_hilo(
            self._cerrar, "escucha-cierre", args=(reproductor, callbacks)).start()

    @staticmethod
    def _cerrar(reproductor, callbacks) -> None:
        # `callbacks` solo conserva vivos los enganches hasta el release.
        try:
            reproductor.stop()
        except Exception as error:
            logger.debug("no se pudo detener la escucha: %s", error)
        try:
            reproductor.release()
        except Exception as error:
            logger.debug("no se pudo liberar la escucha: %s", error)

    def _avisar(self, evento, detalle="") -> None:
        try:
            self._aviso_fn(evento, detalle)
        except Exception:
            logger.exception("Falló el aviso de escucha %s", evento)
