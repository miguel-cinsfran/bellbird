"""Adaptador de música sobre la instancia compartida de libVLC.

Cumple el contrato ``Adaptador`` del coordinador usando el libVLC que YTChat
ya trae, más la lectura de etiquetas para la biblioteca. Sin ``wx``. Los
enlaces de YouTube no se resuelven acá: un hilo daemon pide la dirección del
audio y arranca el reproductor cuando llega, sin bloquear al coordinador.
"""

from __future__ import annotations

import os
import queue
import threading

from ytchat.core import diagnostico
from ytchat.music import enlaces, modelo
from ytchat.player import motor_vlc


logger = diagnostico.obtener_logger(__name__)

_FIN = "fin"
_ERROR = "error"
_SONANDO = "sonando"
_CERRAR = "cerrar"


class MotorNoDisponible(RuntimeError):
    """No hay instancia de libVLC para reproducir música."""


class AdaptadorVlc:
    """Motor de música sobre libVLC, con un reproductor por tema.

    Los callbacks de VLC solo encolan un aviso: llamar a libVLC dentro de su
    propio aviso lo cuelga, así que el trabajo lo hace un hilo aparte.
    """

    def __init__(self, salida_audio=None, volumen=100, dispositivo=None):
        instancia = motor_vlc.instancia()
        if instancia is None:
            raise MotorNoDisponible("No hay motor de música libVLC disponible")
        self._instancia = instancia
        self._vlc = motor_vlc.modulo()
        self._salida_audio = salida_audio
        self._dispositivo = dispositivo or None
        self._volumen = volumen
        self._aviso = None
        self._actual = None
        self._pedida = None
        self._pendiente = None
        self._pausa_pendiente = False
        self._iniciado = False
        self._ficha_actual = None
        self._lock = threading.RLock()
        self._callbacks = {}
        self._cola = queue.Queue()
        self._cerrado = False
        self._hilo = diagnostico.crear_hilo(self._consumir, "musica-vlc")
        self._hilo.start()

    def asignar_aviso(self, funcion):
        """Guarda a quién avisar el fin de un tema. Sin aviso, se descartan."""
        self._aviso = funcion

    def fijar_dispositivo(self, identificador):
        """Elige el dispositivo de salida para el próximo tema, sin cortar el
        que suena. None o "" usan el predeterminado del sistema."""
        self._dispositivo = identificador or None

    def cargar(self, tema, ficha):
        """Empieza a sonar el tema con un reproductor nuevo y cierra el anterior.

        Un enlace de YouTube no bloquea: anota la ficha pedida, cierra en el
        acto lo que estuviera sonando y resuelve el audio en un hilo daemon.
        Si al volver ya se pidió otro tema, lo descarta; si la resolución
        falla, avisa el fallo desde ese hilo.
        """
        with self._lock:
            self._pedida = ficha
            self._pausa_pendiente = False
            if tema.es_enlace:
                self._pendiente = ficha
                anterior = self._actual
                self._actual = None
                self._iniciado = False
                self._ficha_actual = None
                if anterior is not None:
                    self._cola.put((_CERRAR, None, anterior))
                diagnostico.crear_hilo(
                    self._resolver_enlace, "musica-enlace",
                    args=(tema, ficha)).start()
                return
            self._pendiente = None
            if not os.path.isfile(tema.origen):
                raise FileNotFoundError(tema.origen)
            reproductor = self._instancia.media_player_new()
            if reproductor is None:
                raise RuntimeError("VLC no pudo crear un reproductor")
            if self._salida_audio is not None:
                reproductor.audio_output_set(self._salida_audio)
            if self._dispositivo:
                reproductor.audio_output_device_set(None, self._dispositivo)
            try:
                media = self._instancia.media_new(tema.origen)
                reproductor.set_media(media)
            except Exception as exc:
                self._cola.put((_CERRAR, None, reproductor))
                raise RuntimeError("VLC no pudo preparar el tema") from exc
            reproductor.audio_set_volume(self._volumen)
            self._enganchar(reproductor, ficha)
            if reproductor.play() == -1:
                # El nuevo no arranca: se cierra y el anterior sigue sonando igual.
                self._cola.put((_CERRAR, None, reproductor))
                raise RuntimeError("VLC no pudo iniciar el tema")
            anterior = self._actual
            self._actual = reproductor
            self._iniciado = True
            self._ficha_actual = ficha
            if anterior is not None:
                # Un reproductor por tema: el fin tardío del viejo sale por su
                # propio gestor con su ficha vieja, y el coordinador lo ignora.
                self._cola.put((_CERRAR, None, anterior))

    def _resolver_enlace(self, tema, ficha):
        """Resuelve el audio del enlace y arranca el reproductor. Corre en su
        propio hilo: nunca usa libVLC desde un callback."""
        try:
            url = enlaces.url_audio(tema.origen)
        except Exception:
            logger.debug("No se pudo resolver el audio del enlace: %s", tema.origen)
            with self._lock:
                if self._pendiente == ficha:
                    self._pendiente = None
                if ficha == self._pedida:
                    # El aviso sale por el hilo consumidor: acá se puede tener
                    # el candado del coordinador y llamarlo acá lo colgaría.
                    self._cola.put((_ERROR, ficha, None))
            return
        with self._lock:
            if self._pendiente == ficha:
                self._pendiente = None
            # La ficha guardada es la pedida: si el usuario ya pidió otro tema,
            # el resultado que llegó tarde se descarta y no toca al que suena.
            if self._cerrado or ficha != self._pedida:
                return
            self._abrir_enlace(url, ficha)

    def _abrir_enlace(self, url, ficha):
        reproductor = self._instancia.media_player_new()
        if reproductor is None:
            self._cola.put((_ERROR, ficha, None))
            return
        if self._salida_audio is not None:
            reproductor.audio_output_set(self._salida_audio)
        if self._dispositivo:
            reproductor.audio_output_device_set(None, self._dispositivo)
        try:
            media = self._instancia.media_new(url)
            for opcion in _opciones_enlace():
                media.add_option(opcion)
            reproductor.set_media(media)
        except Exception as exc:
            logger.debug("No se pudo preparar el enlace: %s", exc)
            self._cola.put((_CERRAR, None, reproductor))
            self._cola.put((_ERROR, ficha, None))
            return
        reproductor.audio_set_volume(self._volumen)
        self._enganchar(reproductor, ficha)
        preparado_en_pausa = self._pausa_pendiente
        self._pausa_pendiente = False
        if not preparado_en_pausa and reproductor.play() == -1:
            self._cola.put((_CERRAR, None, reproductor))
            self._cola.put((_ERROR, ficha, None))
            return
        anterior = self._actual
        self._actual = reproductor
        self._iniciado = not preparado_en_pausa
        self._ficha_actual = ficha
        if anterior is not None:
            self._cola.put((_CERRAR, None, anterior))

    def pausar(self):
        with self._lock:
            if self._actual is not None:
                if self._iniciado:
                    self._actual.set_pause(1)
                return
            if self._pendiente is not None:
                self._pausa_pendiente = True

    def reanudar(self):
        with self._lock:
            self._pausa_pendiente = False
            if self._actual is None:
                return
            if self._iniciado:
                self._actual.set_pause(0)
                return
            self._iniciar_actual()

    def _iniciar_actual(self):
        """Arranca el reproductor preparado que esperaba una pausa pendiente."""
        reproductor = self._actual
        if reproductor is None:
            return
        if reproductor.play() == -1:
            ficha = self._ficha_actual
            self._actual = None
            self._iniciado = False
            self._ficha_actual = None
            self._cola.put((_CERRAR, None, reproductor))
            if ficha is not None and ficha == self._pedida:
                # Nunca directo: `reanudar` puede venir con el candado del
                # coordinador tomado y el aviso lo vuelve a pedir.
                self._cola.put((_ERROR, ficha, None))
            return
        self._iniciado = True

    def detener(self):
        with self._lock:
            # Invalidar la ficha pendiente evita que un enlace que termina de
            # resolverse después de detener arranque a sonar igual.
            self._pedida = None
            self._pendiente = None
            self._pausa_pendiente = False
            self._iniciado = False
            self._ficha_actual = None
            anterior = self._actual
            self._actual = None
            if anterior is not None:
                self._cola.put((_CERRAR, None, anterior))

    def volumen(self, valor):
        with self._lock:
            self._volumen = valor
            if self._actual is not None:
                self._actual.audio_set_volume(valor)

    def tiempo_ms(self):
        """Posición del tema actual en milisegundos, o None si no se sabe."""
        with self._lock:
            if self._actual is None:
                return None
            try:
                valor = self._actual.get_time()
            except Exception:
                return None
            if valor is None or valor < 0:
                return None
            return int(valor)

    def ir_a(self, ms):
        """Salta a una posición del tema actual. Sin tema no hace nada."""
        with self._lock:
            if self._actual is None:
                return
            try:
                self._actual.set_time(int(ms))
            except Exception:
                logger.debug("No se pudo saltar a %s ms en el tema actual", ms)

    def cerrar(self, plazo=2.0):
        """Cierra el reproductor actual y termina el hilo. Repetirlo no falla."""
        with self._lock:
            if self._cerrado:
                return
            self._cerrado = True
            self._pedida = None
            self._pendiente = None
            self._pausa_pendiente = False
            self._iniciado = False
            self._ficha_actual = None
            anterior = self._actual
            self._actual = None
            if anterior is not None:
                self._cola.put((_CERRAR, None, anterior))
            self._cola.put(None)
        if self._hilo is not None:
            self._hilo.join(timeout=plazo)

    def _enganchar(self, reproductor, ficha):
        vlc = self._vlc
        if vlc is None or not hasattr(vlc, "EventType"):
            self._callbacks[reproductor] = ()
            return
        cola = self._cola

        def al_fin(_evento):
            cola.put((_FIN, ficha, reproductor))

        def al_error(_evento):
            cola.put((_ERROR, ficha, reproductor))

        def al_sonar(_evento):
            cola.put((_SONANDO, ficha, reproductor))

        callbacks = (
            (vlc.EventType.MediaPlayerEndReached, al_fin),
            (vlc.EventType.MediaPlayerEncounteredError, al_error),
            (vlc.EventType.MediaPlayerPlaying, al_sonar),
        )
        try:
            gestor = reproductor.event_manager()
            for tipo, callback in callbacks:
                gestor.event_attach(tipo, callback)
        except Exception as exc:
            logger.debug("No se pudieron enganchar los eventos de música: %s", exc)
        self._callbacks[reproductor] = callbacks

    def _consumir(self):
        while True:
            elemento = self._cola.get()
            if elemento is None:
                return
            tipo, ficha, reproductor = elemento
            if tipo == _CERRAR:
                self._cerrar_reproductor(reproductor)
            elif tipo == _SONANDO:
                if reproductor is self._actual:
                    try:
                        reproductor.audio_set_volume(self._volumen)
                    except Exception:
                        pass
            else:
                self._avisar_fin(ficha, tipo == _ERROR)

    def _avisar_fin(self, ficha, fallo):
        aviso = self._aviso
        if aviso is None:
            return
        try:
            aviso(ficha, fallo)
        except Exception:
            logger.exception("Falló el aviso de fin de tema")

    def _cerrar_reproductor(self, reproductor):
        try:
            reproductor.stop()
        except Exception:
            pass
        try:
            reproductor.release()
        except Exception:
            pass
        # Mientras libVLC pueda llamar, el gestor conserva vivos sus callbacks.
        self._callbacks.pop(reproductor, None)


def _opciones_enlace() -> tuple[str, ...]:
    """Opciones de red del reproductor de vídeo para flujos de YouTube.

    Salen de ``reproductor.opciones_medio``, que es pública, importada al
    momento para no arrastrar la interfaz al cargar este módulo. Si no se
    puede importar, ninguna: el medio igual suena.
    """
    try:
        from ytchat.player.reproductor import opciones_medio
    except Exception:
        return ()
    return opciones_medio(False, solo_audio=True)


def salidas_audio() -> list[tuple[str, str]]:
    """Dispositivos de salida de libVLC como pares (identificador, descripción).

    Usa un reproductor temporal de la instancia compartida y libera la lista y
    el reproductor. Nunca lanza: sin motor o ante un error devuelve lista
    vacía. Es bloqueante, la interfaz la llama desde un hilo aparte.
    """
    instancia = motor_vlc.instancia()
    vlc = motor_vlc.modulo()
    if instancia is None or vlc is None:
        return []
    reproductor = None
    lista = None
    try:
        reproductor = instancia.media_player_new()
        if reproductor is None:
            return []
        lista = reproductor.audio_output_device_enum()
        salidas = []
        nodo = lista
        while nodo:
            datos = nodo.contents
            salidas.append((_texto(datos.device), _texto(datos.description)))
            nodo = datos.next
        return salidas
    except Exception as exc:
        logger.debug("No se pudieron listar las salidas de audio: %s", exc)
        return []
    finally:
        if lista is not None:
            try:
                vlc.libvlc_audio_output_device_list_release(lista)
            except Exception:
                pass
        if reproductor is not None:
            try:
                reproductor.release()
            except Exception:
                pass


def _texto(valor) -> str:
    """Campo de texto de libVLC, que puede llegar en bytes o None."""
    if isinstance(valor, bytes):
        return valor.decode("utf-8", "replace")
    return valor or ""


def leer_etiquetas_vlc(ruta, plazo_ms=1500) -> dict:
    """Lee título, artista, álbum y duración de un archivo con libVLC.

    Nunca lanza: devuelve ``{}`` sin motor, si falla o al vencer el plazo. Se
    llama desde el hilo que indexa, nunca desde un callback de VLC.
    """
    instancia, vlc = motor_vlc.instancia(), motor_vlc.modulo()
    if instancia is None or vlc is None:
        return {}
    try:
        media = instancia.media_new(ruta)
    except Exception:
        return {}
    if media is None:
        return {}
    try:
        listo = threading.Event()

        def al_parsear(_evento):
            listo.set()
        try:
            gestor = media.event_manager()
            gestor.event_attach(vlc.EventType.MediaParsedChanged, al_parsear)
        except Exception:
            pass
        if media.parse_with_options(vlc.MediaParseFlag.local, plazo_ms) == -1:
            return {}
        if not listo.wait(plazo_ms / 1000):
            return {}
        titulo = media.get_meta(vlc.Meta.Title)
        artista = media.get_meta(vlc.Meta.Artist)
        album = media.get_meta(vlc.Meta.Album)
        duracion = modelo.normalizar_duracion(media.get_duration())
    except Exception:
        return {}
    finally:
        try:
            media.release()
        except Exception:
            pass
    return {
        "titulo": _titulo_real(titulo, ruta),
        "artista": artista or "",
        "album": album or "",
        "duracion_ms": duracion,
    }


def _titulo_real(titulo, ruta):
    """Descarta el título cuando libVLC repite el nombre del archivo."""
    if not titulo:
        return ""
    nombre = os.path.basename(ruta)
    raiz = os.path.splitext(nombre)[0]
    if titulo.casefold() in (nombre.casefold(), raiz.casefold()):
        return ""
    return titulo
