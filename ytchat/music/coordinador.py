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
    REINICIADO,
    SIN_TEMA,
    TEMA_FALLIDO,
    VOLUMEN_INVALIDO,
    EstadoMusica,
    Resultado,
    Tema,
)


logger = obtener_logger(__name__)

UMBRAL_REINICIO_MS = 3000

_SIN_DESDE = object()


class Adaptador(Protocol):
    """Contrato del motor de audio que maneja el coordinador.

    El motor corre en el mismo proceso y responde en el acto. Debe implementar:

    - ``cargar(tema, ficha)``: deja de sonar lo anterior y empieza a sonar
      ``tema``. Lanza una excepción si no puede ni empezar.
    - ``pausar()``, ``reanudar()``, ``detener()``, ``volumen(valor)``.
    - ``tiempo_ms()``: posición del tema actual en milisegundos, o ``None``.
    - ``ir_a(ms)``: salta a una posición del tema actual.

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

    def tiempo_ms(self) -> int | None: ...

    def ir_a(self, ms: int) -> None: ...


class Coordinador:
    """Maneja orden, aleatorio, avance, pausa y volumen contra un adaptador.

    ``_cola`` es la lista visible, en el orden en que el usuario la armó, y
    nunca se reordena sola. El orden en que suena vive en ``_orden``, una
    lista de índices de ``_cola``, y ``_cursor`` marca el que suena dentro de
    ella. Con aleatorio apagado, ``_orden`` es el orden natural.
    """

    def __init__(self, adaptador, mezclar=random.shuffle, al_cambiar=None, volumen=100):
        self._adaptador = adaptador
        self._mezclar = mezclar
        self._al_cambiar = al_cambiar
        # Lock simple: las llamadas al adaptador van con el lock tomado porque
        # son instantáneas, y al_cambiar va siempre con el lock suelto.
        self._lock = threading.Lock()
        self._cola: tuple[Tema, ...] = ()
        self._orden: list[int] = []
        self._cursor: int | None = None
        self._posicion: int | None = None
        self._pausado = False
        self._terminado = False
        self._a_continuacion = 0
        self._volumen = volumen
        self._aleatorio = False
        self._repetir = "no"
        self._ficha = 0

    def reproducir_lista(self, temas, en_orden: bool = False,
                         desde=_SIN_DESDE) -> Resultado:
        """Pone la lista como cola y empieza a sonar por `desde`.

        La lista visible no se mezcla nunca. Con aleatorio activo y sin
        `en_orden`, empieza por un tema al azar. Si `desde` llega explícito,
        empieza por ese índice. Un índice fuera de rango deja la cola como
        estaba y devuelve "sin_tema", igual que `reproducir_desde`.
        """
        with self._lock:
            cola = tuple(temas)
            if not cola:
                return Resultado(False, COLA_VACIA, self._estado())
            if self._aleatorio and not en_orden:
                if desde is _SIN_DESDE:
                    inicio = None
                elif not _indice_valido(desde, len(cola)):
                    return Resultado(False, SIN_TEMA, self._estado())
                else:
                    inicio = desde
                mezclar_resto = True
            else:
                if desde is _SIN_DESDE:
                    inicio = 0
                    mezclar_resto = self._aleatorio
                elif not _indice_valido(desde, len(cola)):
                    return Resultado(False, SIN_TEMA, self._estado())
                else:
                    inicio = desde
                    mezclar_resto = self._aleatorio
            return self._iniciar_cola(cola, inicio, mezclar_resto)

    def reproducir_tema(self, tema: Tema) -> Resultado:
        return self.reproducir_lista((tema,))

    def reproducir_desde(self, indice) -> Resultado:
        """Pone a sonar el tema de la cola actual que ocupa `indice`.

        Sin cola devuelve "cola_vacia"; con el índice fuera de rango,
        "sin_tema". Si el motor no puede cargar ese tema, es "error_motor"
        con el tema y la cola queda terminada, igual que al moverla.
        """
        with self._lock:
            if not self._cola:
                return Resultado(False, COLA_VACIA, self._estado())
            if not _indice_valido(indice, len(self._cola)):
                return Resultado(False, SIN_TEMA, self._estado())
            if self._aleatorio:
                resto = [i for i in range(len(self._cola)) if i != indice]
                self._mezclar_lista(resto)
                self._orden = [indice] + resto
                self._cursor = 0
            else:
                self._orden = list(range(len(self._cola)))
                self._cursor = indice
            self._posicion = indice
            self._a_continuacion = 0
            try:
                self._cargar(self._cola[indice])
            except Exception:
                self._detener_motor()
                self._pausado = False
                self._terminado = True
                return Resultado(False, ERROR_MOTOR, self._estado(),
                                 tema=self._cola[indice])
            self._pausado = False
            self._terminado = False
            return Resultado(True, OK, self._estado())

    def agregar(self, temas) -> Resultado:
        with self._lock:
            return self._agregar(tuple(temas))

    def reproducir_ahora(self, temas) -> Resultado:
        """Mete los temas detrás del que suena y salta al primero de ellos.

        Conserva el resto de la cola y no corta nada más que el tema actual.
        Sin nada activo se comporta como `agregar`.
        """
        with self._lock:
            nuevos = tuple(temas)
            if not nuevos:
                return Resultado(False, COLA_VACIA, self._estado())
            if self._posicion is None or self._terminado:
                return self._agregar(nuevos)
            posicion = self._posicion
            self._insertar_ahora(posicion, nuevos)
            indice = posicion + 1
            self._cursor = self._orden.index(indice)
            self._posicion = indice
            self._pausado = False
            self._a_continuacion = 0
            try:
                self._cargar(self._cola[indice])
            except Exception:
                self._detener_motor()
                self._terminado = True
                return Resultado(False, ERROR_MOTOR, self._estado(),
                                 tema=self._cola[indice])
            self._terminado = False
            return Resultado(True, OK, self._estado())

    def a_continuacion(self, temas) -> Resultado:
        """Mete los temas justo detrás del que suena, sin cortar nada.

        Sin temas es cola_vacia. Sin nada activo (cola vacía, detenida o
        terminada) se comporta como `agregar`: suma al final y empieza por
        el primero nuevo, con su mismo manejo de error_motor. Con un tema
        activo (sonando o en pausa) inserta detrás de la posición actual,
        en orden de llegada, sin llamar al adaptador ni tocar ficha, pausa,
        posición o aleatorio. Devuelve ok con el estado nuevo.
        """
        with self._lock:
            nuevos = tuple(temas)
            if not nuevos:
                return Resultado(False, COLA_VACIA, self._estado())
            if self._posicion is None or self._terminado:
                return self._agregar(nuevos)
            self._insertar_continuacion(self._posicion, nuevos)
            return Resultado(True, OK, self._estado())

    def quitar(self, indice) -> Resultado:
        """Quita un tema de la cola. Si suena, pasa al siguiente del orden."""
        with self._lock:
            if not _indice_valido(indice, len(self._cola)):
                return Resultado(False, SIN_TEMA, self._estado())
            activo = self._posicion is not None and not self._terminado
            if not activo or indice != self._posicion:
                return self._quitar_sin_cortar(indice)
            return self._quitar_el_actual(indice)

    def mover(self, indice, paso) -> Resultado:
        """Intercambia un tema con su vecino en la lista visible."""
        with self._lock:
            if (not _indice_valido(indice, len(self._cola))
                    or paso not in (-1, 1)):
                return Resultado(False, SIN_TEMA, self._estado())
            destino = indice + paso
            if not 0 <= destino < len(self._cola):
                return Resultado(False, SIN_TEMA, self._estado())
            cola = list(self._cola)
            cola[indice], cola[destino] = cola[destino], cola[indice]
            self._cola = tuple(cola)
            self._orden = [
                destino if valor == indice
                else indice if valor == destino
                else valor
                for valor in self._orden
            ]
            if self._posicion == indice:
                self._posicion = destino
            elif self._posicion == destino:
                self._posicion = indice
            if self._posicion is not None:
                self._cursor = self._orden.index(self._posicion)
            self._a_continuacion = 0
            return Resultado(True, OK, self._estado())

    def vaciar(self) -> Resultado:
        """Deja solo el tema activo en la cola, o la vacía si no hay ninguno."""
        with self._lock:
            if self._posicion is not None and not self._terminado:
                actual = self._cola[self._posicion]
                self._cola = (actual,)
                self._orden = [0]
                self._cursor = 0
                self._posicion = 0
            else:
                self._cola = ()
                self._orden = []
                self._cursor = None
                self._posicion = None
                self._pausado = False
                self._terminado = False
            self._a_continuacion = 0
            return Resultado(True, OK, self._estado())

    def mezclar_cola(self) -> Resultado:
        """Reordena la lista visible al azar, dejando el actual primero."""
        with self._lock:
            activo = self._posicion is not None and not self._terminado
            if activo:
                actual = self._cola[self._posicion]
                resto = [i for i in range(len(self._cola))
                         if i != self._posicion]
                self._mezclar_lista(resto)
                self._cola = (actual,) + tuple(self._cola[i] for i in resto)
                self._cursor = 0
                self._posicion = 0
            else:
                indices = list(range(len(self._cola)))
                self._mezclar_lista(indices)
                self._cola = tuple(self._cola[i] for i in indices)
                self._cursor = None
                self._posicion = None
                self._pausado = False
                self._terminado = False
            self._orden = list(range(len(self._cola)))
            self._a_continuacion = 0
            return Resultado(True, OK, self._estado())

    def _insertar_continuacion(self, posicion: int,
                               nuevos: tuple[Tema, ...]) -> None:
        """Inserta en la lista visible y en el orden, detrás de lo pendiente."""
        cantidad = len(nuevos)
        insercion = posicion + 1 + self._a_continuacion
        self._orden = [valor + cantidad if valor >= insercion else valor
                       for valor in self._orden]
        self._cola = (self._cola[:insercion] + nuevos
                      + self._cola[insercion:])
        indices = list(range(insercion, insercion + cantidad))
        en_orden = self._cursor + 1 + self._a_continuacion
        self._orden = (self._orden[:en_orden] + indices
                       + self._orden[en_orden:])
        self._a_continuacion += cantidad

    def _insertar_ahora(self, posicion: int,
                        nuevos: tuple[Tema, ...]) -> None:
        """Inserta los temas justo detrás del actual y antes de todo lo demás."""
        cantidad = len(nuevos)
        insercion = posicion + 1
        self._orden = [valor + cantidad if valor >= insercion else valor
                       for valor in self._orden]
        self._cola = (self._cola[:insercion] + nuevos
                      + self._cola[insercion:])
        indices = list(range(insercion, insercion + cantidad))
        en_orden = self._cursor + 1
        self._orden = (self._orden[:en_orden] + indices
                       + self._orden[en_orden:])

    def _quitar_sin_cortar(self, indice: int) -> Resultado:
        posicion = self._posicion
        if (posicion is not None and indice > posicion
                and indice <= posicion + self._a_continuacion):
            self._a_continuacion -= 1
        self._cola = self._cola[:indice] + self._cola[indice + 1:]
        self._orden = [valor if valor < indice else valor - 1
                       for valor in self._orden if valor != indice]
        if posicion is not None:
            if indice < posicion:
                posicion -= 1
            elif indice == posicion:
                posicion = None
            self._posicion = posicion
            if posicion is None:
                self._cursor = None
            else:
                self._cursor = self._orden.index(posicion)
        if not self._cola:
            self._terminado = False
        return Resultado(True, OK, self._estado())

    def _quitar_el_actual(self, indice: int) -> Resultado:
        pausado = self._pausado
        siguiente = None
        if self._cursor is not None and self._cursor + 1 < len(self._orden):
            siguiente = self._orden[self._cursor + 1]
        self._cola = self._cola[:indice] + self._cola[indice + 1:]
        self._orden = [valor if valor < indice else valor - 1
                       for valor in self._orden if valor != indice]
        if siguiente is None:
            self._detener_motor()
            self._cursor = None
            self._posicion = None
            self._pausado = False
            self._terminado = True
            self._a_continuacion = 0
            return Resultado(False, FIN_LISTA, self._estado())
        nuevo = siguiente if siguiente < indice else siguiente - 1
        self._posicion = nuevo
        self._cursor = self._orden.index(nuevo)
        if self._a_continuacion > 0:
            self._a_continuacion -= 1
        else:
            self._a_continuacion = 0
        try:
            self._cargar(self._cola[nuevo])
            if pausado:
                self._adaptador.pausar()
        except Exception:
            self._detener_motor()
            self._pausado = False
            self._terminado = True
            return Resultado(False, ERROR_MOTOR, self._estado(),
                             tema=self._cola[nuevo])
        self._pausado = pausado
        self._terminado = False
        return Resultado(True, OK, self._estado())

    def _agregar(self, nuevos: tuple[Tema, ...]) -> Resultado:
        if not nuevos:
            return Resultado(False, COLA_VACIA, self._estado())
        activo = self._posicion is not None and not self._terminado
        inicio = len(self._cola)
        self._cola = self._cola + nuevos
        indices = list(range(inicio, inicio + len(nuevos)))
        if activo:
            if self._aleatorio and self._cursor is not None:
                corte = self._cursor + 1 + self._a_continuacion
                bloque = self._orden[self._cursor + 1:corte]
                resto = self._orden[corte:]
                combinado = resto + indices
                self._mezclar_lista(combinado)
                self._orden = self._orden[:self._cursor + 1] + bloque + combinado
            else:
                self._orden = self._orden + indices
            return Resultado(True, OK, self._estado())
        self._preparar_inicio(indices[0])
        try:
            self._cargar(nuevos[0])
        except Exception:
            self._detener_motor()
            self._pausado = False
            self._terminado = True
            return Resultado(False, ERROR_MOTOR, self._estado(), tema=nuevos[0])
        self._pausado = False
        self._terminado = False
        return Resultado(True, OK, self._estado())

    def _preparar_inicio(self, inicio: int) -> None:
        """Arma el orden de reproducción para empezar por `inicio`."""
        self._a_continuacion = 0
        if self._aleatorio:
            resto = [i for i in range(len(self._cola)) if i != inicio]
            self._mezclar_lista(resto)
            self._orden = [inicio] + resto
        else:
            self._orden = list(range(len(self._cola)))
        self._cursor = self._orden.index(inicio)
        self._posicion = inicio

    def actualizar_temas(self, mapa) -> int:
        """Reemplaza en la cola los temas cuyo `origen` está en `mapa`.

        Solo cambia el nombre: ni la posición, ni la pausa, ni la ficha, ni
        el aleatorio, ni el orden. No llama al adaptador ni a `al_cambiar`.
        Es lo que usa el hilo de etiquetas para poner al día lo que suena.
        Devuelve cuántos reemplazó.
        """
        with self._lock:
            if not mapa or not self._cola:
                return 0
            nueva = tuple(mapa.get(tema.origen, tema) for tema in self._cola)
            puestos = sum(1 for viejo, nuevo in zip(self._cola, nueva)
                          if nuevo is not viejo)
            self._cola = nueva
        return puestos

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
        with self._lock:
            return self._mover(1)

    def anterior(self) -> Resultado:
        with self._lock:
            if self._posicion is None or self._cursor is None:
                return Resultado(False, SIN_TEMA, self._estado())
            tiempo = self._tiempo_actual()
            if tiempo is not None and tiempo > UMBRAL_REINICIO_MS:
                try:
                    self._adaptador.ir_a(0)
                except Exception:
                    return Resultado(False, ERROR_MOTOR, self._estado())
                return Resultado(True, REINICIADO, self._estado())
            return self._mover(-1)

    def detener(self) -> Resultado:
        with self._lock:
            try:
                self._adaptador.detener()
            except Exception:
                return Resultado(False, ERROR_MOTOR, self._estado())
            self._cursor = None
            self._posicion = None
            self._pausado = False
            self._terminado = False
            self._a_continuacion = 0
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
            nuevo = bool(activo)
            if nuevo == self._aleatorio:
                return Resultado(True, OK, self._estado())
            activo_ahora = (self._posicion is not None
                            and not self._terminado)
            if activo_ahora and self._cursor is not None:
                if nuevo:
                    corte = self._cursor + 1 + self._a_continuacion
                    bloque = self._orden[self._cursor + 1:corte]
                    resto = self._orden[corte:]
                    self._mezclar_lista(resto)
                    self._orden = self._orden[:self._cursor + 1] + bloque + resto
                else:
                    self._orden = list(range(len(self._cola)))
                    self._cursor = self._posicion
            elif self._repetir == "no" and not self._orden:
                self._orden = list(range(len(self._cola)))
            self._aleatorio = nuevo
            return Resultado(True, OK, self._estado())

    def fijar_repetir(self, modo) -> Resultado:
        with self._lock:
            if modo is True:
                modo = "todo"
            elif modo is False:
                modo = "no"
            if modo not in ("no", "todo", "tema"):
                return Resultado(False, SIN_TEMA, self._estado())
            self._repetir = modo
            return Resultado(True, OK, self._estado())

    @property
    def repetir(self) -> str:
        """Modo de repetición: "no", "todo" o "tema". Solo lectura."""
        return self._repetir

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
            avisos.extend(self._avanzar_tras_fin(fallo))
        for aviso in avisos:
            self._avisar(aviso)

    def _iniciar_cola(self, cola: tuple[Tema, ...], inicio: int | None,
                      mezclar_resto: bool) -> Resultado:
        self._cola = cola
        self._a_continuacion = 0
        if self._aleatorio:
            if inicio is None:
                orden = list(range(len(cola)))
                self._mezclar_lista(orden)
                inicio = orden[0]
                self._orden = orden
            else:
                resto = [i for i in range(len(cola)) if i != inicio]
                if mezclar_resto:
                    self._mezclar_lista(resto)
                self._orden = [inicio] + resto
        else:
            self._orden = list(range(len(cola)))
            if inicio is None:
                inicio = 0
        self._cursor = self._orden.index(inicio)
        self._posicion = inicio
        try:
            self._cargar(cola[inicio])
        except Exception:
            self._detener_motor()
            self._pausado = False
            self._terminado = True
            return Resultado(False, ERROR_MOTOR, self._estado(),
                             tema=cola[inicio])
        self._pausado = False
        self._terminado = False
        return Resultado(True, OK, self._estado())

    def _mover(self, paso: int) -> Resultado:
        """Avanza o retrocede en el orden. El llamador tiene el lock tomado."""
        if self._posicion is None or self._cursor is None:
            return Resultado(False, SIN_TEMA, self._estado())
        destino = self._cursor + paso
        if destino >= len(self._orden):
            if self._repetir == "no":
                self._detener_motor()
                self._a_continuacion = 0
                self._pausado = False
                self._terminado = True
                return Resultado(False, FIN_LISTA, self._estado())
            if self._aleatorio:
                self._nuevo_ciclo(self._posicion)
            destino = 0
            self._a_continuacion = 0
        elif destino < 0:
            if self._repetir == "no":
                return Resultado(False, INICIO_LISTA, self._estado())
            destino = len(self._orden) - 1
            self._a_continuacion = 0
        else:
            self._consumir_continuacion(destino)
        indice = self._orden[destino]
        self._cursor = destino
        self._posicion = indice
        try:
            self._cargar(self._cola[indice])
        except Exception:
            self._detener_motor()
            self._pausado = False
            self._terminado = True
            return Resultado(False, ERROR_MOTOR, self._estado(),
                             tema=self._cola[indice])
        # Al cambiar de tema con el teclado se espera oírlo: queda sonando.
        self._pausado = False
        self._terminado = False
        return Resultado(True, OK, self._estado())

    def _avanzar_tras_fin(self, fallo: bool = False) -> list[Resultado]:
        """Avanza tras el fin de un tema, respetando el modo de repetición.

        Con "tema" vuelve a cargar el mismo. Con "todo", al acabarse el orden
        arranca un ciclo nuevo, que se vuelve a mezclar si el aleatorio está
        activo. Cada tema se prueba una sola vez por avance: si todos fallan,
        termina en fin_lista y nunca en un bucle.
        """
        avisos = []
        total = len(self._cola)
        if self._repetir == "tema" and self._posicion is not None:
            if fallo:
                # Repetir un tema que el motor acaba de rechazar sería un
                # bucle: se detiene en vez de volver a probarlo.
                self._detener_motor()
                self._pausado = False
                self._terminado = True
                self._a_continuacion = 0
                avisos.append(Resultado(True, FIN_LISTA, self._estado()))
                return avisos
            actual = self._cola[self._posicion]
            try:
                self._cargar(actual)
            except Exception:
                self._detener_motor()
                self._pausado = False
                self._terminado = True
                avisos.append(Resultado(False, TEMA_FALLIDO, self._estado(),
                                        tema=actual))
                avisos.append(Resultado(True, FIN_LISTA, self._estado()))
                return avisos
            self._pausado = False
            self._terminado = False
            return [Resultado(True, AVANZO, self._estado())]

        intentados = set()
        ultimo = None
        while len(intentados) < total:
            if self._cursor is None:
                break
            destino = self._cursor + 1
            if destino >= len(self._orden):
                if self._repetir == "no":
                    break
                if self._aleatorio:
                    self._nuevo_ciclo(self._posicion)
                destino = 0
                self._a_continuacion = 0
            indice = self._orden[destino]
            if indice in intentados:
                self._cursor = destino
                self._posicion = indice
                continue
            intentados.add(indice)
            ultimo = indice
            anterior = self._cursor
            try:
                self._cargar(self._cola[indice])
            except Exception:
                if (self._a_continuacion > 0
                        and destino == anterior + 1):
                    self._a_continuacion -= 1
                else:
                    self._a_continuacion = 0
                self._cursor = destino
                self._posicion = indice
                avisos.append(Resultado(False, TEMA_FALLIDO, self._estado(),
                                        tema=self._cola[indice]))
                continue
            if (self._a_continuacion > 0 and destino == anterior + 1):
                self._a_continuacion -= 1
            else:
                self._a_continuacion = 0
            self._cursor = destino
            self._posicion = indice
            self._pausado = False
            self._terminado = False
            avisos.append(Resultado(True, AVANZO, self._estado()))
            return avisos
        self._detener_motor()
        if ultimo is not None:
            self._posicion = ultimo
            self._cursor = self._orden.index(ultimo)
        elif total:
            self._posicion = total - 1
            self._cursor = self._orden.index(self._posicion)
        self._pausado = False
        self._terminado = True
        self._a_continuacion = 0
        avisos.append(Resultado(True, FIN_LISTA, self._estado()))
        return avisos

    def _nuevo_ciclo(self, excluir: int | None = None) -> None:
        """Mezcla un ciclo nuevo y evita que empiece por el último anterior."""
        orden = list(range(len(self._cola)))
        self._mezclar_lista(orden)
        if (excluir is not None and len(orden) > 1
                and orden[0] == excluir):
            orden[0], orden[1] = orden[1], orden[0]
        self._orden = orden
        self._cursor = 0

    def _consumir_continuacion(self, destino: int) -> None:
        """Descuenta un pendiente de "a continuación" al avanzar de a uno."""
        if (self._a_continuacion > 0 and self._cursor is not None
                and destino == self._cursor + 1):
            self._a_continuacion -= 1
        else:
            self._a_continuacion = 0

    def _tiempo_actual(self) -> int | None:
        metodo = getattr(self._adaptador, "tiempo_ms", None)
        if not callable(metodo):
            return None
        try:
            return metodo()
        except Exception:
            return None

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
            self._repetir,
        )

    def _mezclar_lista(self, lista: list) -> None:
        devuelto = self._mezclar(lista)
        if devuelto is not None:
            lista[:] = list(devuelto)

    def _avisar(self, resultado: Resultado) -> None:
        if self._al_cambiar is None:
            return
        try:
            self._al_cambiar(resultado)
        except Exception:
            logger.exception("Falló al_cambiar del coordinador de música")


def _indice_valido(indice, total: int) -> bool:
    return (not isinstance(indice, bool) and isinstance(indice, int)
            and 0 <= indice < total)
