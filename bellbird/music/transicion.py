"""Movimiento de volúmenes y vigilancia del final durante un cambio de tema.

Un hilo daemon da un paso cada 50 ms: mueve las ganancias de un fundido
cruzado y vigila el tiempo del tema que suena para avisar dónde termina su
sonido real. Mide los bordes con ffmpeg en otro hilo y los guarda en memoria
por archivo. Nunca llama al adaptador ni al coordinador con su lock tomado.
"""

from __future__ import annotations

import os
import threading
import time

from bellbird.core import diagnostico
from bellbird.music import bordes, cruce, sonoridad

logger = diagnostico.obtener_logger(__name__)

PASO_S = 0.05


class Transiciones:
    """Fundidos cruzados y aviso del final real del tema actual."""

    def __init__(self, cruce_de, medir=None, ruta_ffmpeg_de=None):
        self._cruce_de = cruce_de
        self._medir = medir if medir is not None else bordes.medir_bordes
        self._ruta_ffmpeg_de = ruta_ffmpeg_de
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._cache = {}
        self._vigilancia = None
        self._cruce = None
        self._token = 0
        self._hilo = threading.Thread(
            target=self._bucle, name="musica-transicion", daemon=True)
        self._hilo.start()

    def _segundos(self):
        try:
            return float(self._cruce_de() or 0)
        except Exception:
            logger.debug("No se pudo leer la duración del fundido")
            return 0.0

    def vigilar(self, reproductor, ficha, ruta, al_por_terminar):
        """Vigila el final del sonido real del tema que suena ahora.

        Con el fundido en 0, o si la ruta no es un archivo local, no hace
        nada. Si no, mide los bordes en un hilo daemon y saltea el silencio
        inicial cuando llega a `SALTO_MINIMO_MS`.
        """
        segundos = self._segundos()
        if segundos <= 0 or not ruta or not os.path.isfile(ruta):
            return
        with self._lock:
            self._token += 1
            token = self._token
            self._vigilancia = {
                "reproductor": reproductor,
                "ficha": ficha,
                "ruta": ruta,
                "al_por_terminar": al_por_terminar,
                "bordes": None,
                "listo": False,
                "avisado": False,
                "token": token,
                "cruce_ms": int(segundos * 1000),
            }
        threading.Thread(
            target=self._medir_bordes, args=(token, ruta),
            name="musica-bordes", daemon=True).start()

    def _ruta_ffmpeg(self):
        if self._ruta_ffmpeg_de is not None:
            return self._ruta_ffmpeg_de()
        from bellbird.downloads import ffmpeg_bin
        return ffmpeg_bin.ruta_ffmpeg()

    def _medir_archivo(self, ruta):
        try:
            return self._medir(self._ruta_ffmpeg(), ruta)
        except Exception as exc:
            logger.warning("No se pudieron medir los bordes de %s: %s",
                           ruta, exc)
            return None

    def _medir_bordes(self, token, ruta):
        clave = None
        try:
            estado = os.stat(ruta)
            clave = (ruta, estado.st_mtime_ns, estado.st_size)
        except OSError as exc:
            logger.debug("No se pudo consultar %s: %s", ruta, exc)
        medidos = None
        cacheado = False
        if clave is not None:
            with self._lock:
                if clave in self._cache:
                    medidos = self._cache[clave]
                    cacheado = True
        if not cacheado:
            medidos = self._medir_archivo(ruta)
            if clave is not None:
                with self._lock:
                    self._cache[clave] = medidos
        with self._lock:
            estado = self._vigilancia
            if estado is None or estado["token"] != token:
                return
            estado["bordes"] = medidos
            estado["listo"] = True
            reproductor = estado["reproductor"]
        salto = cruce.salto_inicial_ms(medidos)
        if salto > 0:
            self._saltar(reproductor, salto)

    def _saltar(self, reproductor, salto):
        with self._lock:
            estado = self._vigilancia
            if estado is None or estado["reproductor"] is not reproductor:
                return
            try:
                tiempo = reproductor.get_time()
            except Exception as exc:
                logger.debug("No se pudo leer la posición para el salto: %s", exc)
                return
            if tiempo is not None and tiempo >= salto:
                return
            try:
                reproductor.set_time(salto)
            except Exception as exc:
                logger.debug("No se pudo saltear el silencio inicial: %s", exc)

    def cruzar(self, sale, volumen_sale, entra, volumen_entra,
               duracion_ms, al_soltar):
        """Cruza una canción que sale con otra que entra."""
        with self._lock:
            self._cruce = {
                "sale": sale,
                "volumen_sale": volumen_sale,
                "entra": entra,
                "volumen_entra": volumen_entra,
                "duracion_ms": max(1, int(duracion_ms or 0)),
                "al_soltar": al_soltar,
                "inicio": None,
                "soltado": False,
            }

    def en_fundido(self, reproductor):
        """Verdadero si ese reproductor participa de un cruce en curso."""
        with self._lock:
            estado = self._cruce
            return (estado is not None
                    and (reproductor is estado["sale"]
                         or reproductor is estado["entra"]))

    def duracion_cruce(self, reproductor, cruce_ms):
        """La duración que le corresponde a ese reproductor, o None."""
        with self._lock:
            estado = self._vigilancia
            if (estado is None or estado["reproductor"] is not reproductor
                    or not estado["listo"]):
                return None
            medidos = estado["bordes"]
            try:
                largo = reproductor.get_length()
            except Exception:
                return None
        punto = cruce.punto_de_cruce(largo, medidos, cruce_ms)
        return punto[1] if punto is not None else None

    def olvidar(self, reproductor):
        """Deja de tocar un reproductor que se va a cerrar."""
        with self._lock:
            estado = self._vigilancia
            if estado is not None and estado["reproductor"] is reproductor:
                self._vigilancia = None
                self._token += 1
            estado = self._cruce
            if estado is not None and (estado["sale"] is reproductor
                                       or estado["entra"] is reproductor):
                self._cruce = None

    def terminar_ya(self):
        """Termina el cruce en curso en el acto, si hay uno."""
        with self._lock:
            estado = self._cruce
            if estado is None:
                return
            self._cruce = None
            self._poner_volumen(estado["entra"], estado["volumen_entra"])
        self._llamar(estado["al_soltar"], estado["sale"])

    def cerrar(self):
        """Termina el cruce y el hilo. Repetirlo no falla."""
        self.terminar_ya()
        self._parar.set()
        with self._lock:
            self._vigilancia = None
            self._token += 1
            hilo = self._hilo
        if hilo is not None and hilo is not threading.current_thread():
            hilo.join(timeout=2.0)

    def _bucle(self):
        while not self._parar.wait(PASO_S):
            try:
                self._paso_cruce()
                self._paso_vigilancia()
            except Exception:
                logger.exception("Falló un paso del fundido entre canciones")

    def _paso_cruce(self):
        soltar = None
        with self._lock:
            estado = self._cruce
            if estado is None:
                return
            ahora = time.monotonic()
            if estado["inicio"] is None:
                estado["inicio"] = ahora
            transcurrido = (ahora - estado["inicio"]) * 1000.0
            if transcurrido >= estado["duracion_ms"]:
                self._poner_volumen(estado["entra"], estado["volumen_entra"])
                self._cruce = None
                soltar = (estado["al_soltar"], estado["sale"])
            else:
                avance = transcurrido / estado["duracion_ms"]
                sale_db, entra_db = cruce.ganancias_db(avance)
                self._poner_volumen(
                    estado["sale"],
                    sonoridad.volumen_efectivo(
                        estado["volumen_sale"], sale_db))
                self._poner_volumen(
                    estado["entra"],
                    sonoridad.volumen_efectivo(
                        estado["volumen_entra"], entra_db))
        if soltar is not None:
            self._llamar(*soltar)

    def _paso_vigilancia(self):
        aviso = None
        with self._lock:
            estado = self._vigilancia
            if estado is None or estado["avisado"] or not estado["listo"]:
                return
            reproductor = estado["reproductor"]
            medidos = estado["bordes"]
            cruce_ms = estado["cruce_ms"]
            try:
                largo = reproductor.get_length()
            except Exception:
                return
            if not largo or largo <= 0:
                return
            punto = cruce.punto_de_cruce(largo, medidos, cruce_ms)
            if punto is None:
                return
            try:
                tiempo = reproductor.get_time()
            except Exception:
                return
            if tiempo is None or tiempo < punto[0]:
                return
            estado["avisado"] = True
            aviso = (estado["al_por_terminar"], estado["ficha"])
        self._llamar(*aviso)

    def _poner_volumen(self, reproductor, valor):
        try:
            reproductor.audio_set_volume(valor)
        except Exception as exc:
            logger.debug("No se pudo mover el volumen del cruce: %s", exc)

    def _llamar(self, funcion, argumento):
        try:
            funcion(argumento)
        except Exception:
            logger.exception("Falló un aviso del fundido entre canciones")
