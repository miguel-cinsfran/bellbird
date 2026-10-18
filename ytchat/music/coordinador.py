"""Cola de reproducción de música sobre un adaptador de motor de audio."""

from __future__ import annotations

import random
import threading
from typing import Protocol

from ytchat.core.diagnostico import obtener_logger
from ytchat.music.modelo import (
    AVANZO,
    COLA_VACIA,
    ERROR_MOTOR,
    FIN_LISTA,
    INICIO_LISTA,
    OK,
    SIN_TEMA,
    TEMA_FALLIDO,
    VOLUMEN_INVALIDO,
    EstadoMusica,
    Resultado,
    Tema,
)


logger = obtener_logger(__name__)


class Adaptador(Protocol):
    """Contrato del motor de audio que maneja el coordinador.

    El motor corre en el mismo proceso y responde en el acto. Debe implementar:

    - ``cargar(tema, ficha)``: deja de sonar lo anterior y empieza a sonar
      ``tema``. Lanza una excepción si no puede ni empezar.
    - ``pausar()``, ``reanudar()``, ``detener()``, ``volumen(valor)``.

    El adaptador avisa el fin de un tema llamando
    ``coordinador.tema_terminado(ficha, fallo)`` con la misma ``ficha`` que
    recibió en ``cargar``, y ``fallo=True`` si el motor no pudo
    reproducirlo. Ese aviso llega desde OTRO hilo y NUNCA desde dentro de una
    llamada del coordinador al adaptador, porque libVLC se cuelga si se lo
    llama desde su propio aviso.
    """

    def cargar(self, tema: Tema, ficha: int) -> None: ...

    def pausar(self) -> None: ...

    def reanudar(self) -> None: ...

    def detener(self) -> None: ...

    def volumen(self, valor: int) -> None: ...


class Coordinador:
    """Maneja orden, aleatorio, avance, pausa y volumen contra un adaptador."""

    def __init__(self, adaptador, mezclar=random.shuffle, al_cambiar=None, volumen=100):
        self._adaptador = adaptador
        self._mezclar = mezclar
        self._al_cambiar = al_cambiar
        # Lock simple: las llamadas al adaptador van con el lock tomado porque
        # son instantáneas, y al_cambiar va siempre con el lock suelto.
        self._lock = threading.Lock()
        self._cola: tuple[Tema, ...] = ()
        self._posicion: int | None = None
        self._pausado = False
        self._terminado = False
        self._volumen = volumen
        self._aleatorio = False
        self._ficha = 0

    def reproducir_lista(self, temas) -> Resultado:
        with self._lock:
            cola = tuple(temas)
            if not cola:
                return Resultado(False, COLA_VACIA, self._estado())
            if self._aleatorio:
                cola = self._mezclado(cola)
            return self._iniciar_cola(cola)

    def reproducir_tema(self, tema: Tema) -> Resultado:
        return self.reproducir_lista((tema,))

    def agregar(self, temas) -> Resultado:
        with self._lock:
            nuevos = tuple(temas)
            if not nuevos:
                return Resultado(False, COLA_VACIA, self._estado())
            inicio = len(self._cola)
            self._cola = self._cola + nuevos
            if self._posicion is not None and not self._terminado:
                return Resultado(True, OK, self._estado())
            try:
                self._cargar(nuevos[0])
            except Exception:
                self._detener_motor()
                self._posicion = inicio
                self._pausado = False
                self._terminado = True
                return Resultado(False, ERROR_MOTOR, self._estado(), tema=nuevos[0])
            self._posicion = inicio
            self._pausado = False
            self._terminado = False
            return Resultado(True, OK, self._estado())

    def alternar_pausa(self) -> Resultado:
        with self._lock:
            if self._posicion is None or self._terminado:
                return Resultado(False, SIN_TEMA, self._estado())
            try:
                if self._pausado:
                    self._adaptador.reanudar()
                else:
                    self._adaptador.pausar()
            except Exception:
                return Resultado(False, ERROR_MOTOR, self._estado())
            self._pausado = not self._pausado
            return Resultado(True, OK, self._estado())

    def siguiente(self) -> Resultado:
        return self._mover(1)

    def anterior(self) -> Resultado:
        return self._mover(-1)

    def detener(self) -> Resultado:
        with self._lock:
            try:
                self._adaptador.detener()
            except Exception:
                return Resultado(False, ERROR_MOTOR, self._estado())
            self._posicion = None
            self._pausado = False
            self._terminado = False
            return Resultado(True, OK, self._estado())

    def fijar_volumen(self, valor) -> Resultado:
        with self._lock:
            if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= 100:
                return Resultado(False, VOLUMEN_INVALIDO, self._estado())
            try:
                self._adaptador.volumen(valor)
            except Exception:
                return Resultado(False, ERROR_MOTOR, self._estado())
            self._volumen = valor
            return Resultado(True, OK, self._estado())

    def fijar_aleatorio(self, activo: bool) -> Resultado:
        with self._lock:
            self._aleatorio = bool(activo)
            return Resultado(True, OK, self._estado())

    def estado(self) -> EstadoMusica:
        with self._lock:
            return self._estado()

    def tema_terminado(self, ficha, fallo: bool) -> None:
        """Aviso del adaptador, llegado desde otro hilo."""
        avisos = []
        with self._lock:
            # Una ficha vieja se ignora en silencio: un fin tardío del tema
            # anterior nunca hace avanzar al nuevo, aun con el mismo archivo
            # repetido en la cola.
            if ficha != self._ficha:
                return
            if self._pausado or self._terminado or self._posicion is None:
                return
            if fallo:
                avisos.append(Resultado(False, TEMA_FALLIDO, self._estado(),
                                        tema=self._cola[self._posicion]))
            avisos.extend(self._avanzar_tras_fin())
        for aviso in avisos:
            self._avisar(aviso)

    def _iniciar_cola(self, cola: tuple[Tema, ...]) -> Resultado:
        self._cola = cola
        try:
            self._cargar(cola[0])
        except Exception:
            self._detener_motor()
            self._posicion = 0
            self._pausado = False
            self._terminado = True
            return Resultado(False, ERROR_MOTOR, self._estado(), tema=cola[0])
        self._posicion = 0
        self._pausado = False
        self._terminado = False
        return Resultado(True, OK, self._estado())

    def _mover(self, paso: int) -> Resultado:
        with self._lock:
            if self._posicion is None:
                return Resultado(False, SIN_TEMA, self._estado())
            destino = self._posicion + paso
            if destino >= len(self._cola):
                self._detener_motor()
                self._terminado = True
                return Resultado(False, FIN_LISTA, self._estado())
            if destino < 0:
                return Resultado(False, INICIO_LISTA, self._estado())
            try:
                self._cargar(self._cola[destino])
            except Exception:
                self._detener_motor()
                self._posicion = destino
                self._terminado = True
                return Resultado(False, ERROR_MOTOR, self._estado(), tema=self._cola[destino])
            self._posicion = destino
            # Al cambiar de tema con el teclado se espera oírlo: queda sonando.
            self._pausado = False
            self._terminado = False
            return Resultado(True, OK, self._estado())

    def _avanzar_tras_fin(self) -> list[Resultado]:
        """Avanza tras el fin de un tema. Cada tema se prueba una sola vez."""
        avisos = []
        destino = self._posicion + 1
        while destino < len(self._cola):
            try:
                self._cargar(self._cola[destino])
            except Exception:
                self._posicion = destino
                avisos.append(Resultado(False, TEMA_FALLIDO, self._estado(),
                                        tema=self._cola[destino]))
                destino += 1
                continue
            self._posicion = destino
            self._pausado = False
            self._terminado = False
            avisos.append(Resultado(True, AVANZO, self._estado()))
            return avisos
        self._detener_motor()
        self._posicion = len(self._cola) - 1
        self._pausado = False
        self._terminado = True
        avisos.append(Resultado(True, FIN_LISTA, self._estado()))
        return avisos

    def _cargar(self, tema: Tema) -> None:
        self._ficha += 1
        self._adaptador.cargar(tema, self._ficha)

    def _detener_motor(self) -> None:
        try:
            self._adaptador.detener()
        except Exception:
            logger.exception("No se pudo detener el motor de música")

    def _estado(self) -> EstadoMusica:
        return EstadoMusica(
            self._cola, self._posicion, self._pausado,
            self._terminado, self._volumen, self._aleatorio,
        )

    def _mezclado(self, cola: tuple[Tema, ...]) -> tuple[Tema, ...]:
        lista = list(cola)
        devuelto = self._mezclar(lista)
        if devuelto is not None:
            lista = list(devuelto)
        return tuple(lista)

    def _avisar(self, resultado: Resultado) -> None:
        if self._al_cambiar is None:
            return
        try:
            self._al_cambiar(resultado)
        except Exception:
            logger.exception("Falló al_cambiar del coordinador de música")
