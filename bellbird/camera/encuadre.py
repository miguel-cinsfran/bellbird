"""Lógica pura del encuadre de cámara y del vigía de avisos.

A partir de los rostros ya detectados, en píxeles, dice qué problemas
tiene el encuadre, arma la frase que se anuncia y decide cuándo un aviso
automático tiene que sonar. Sin wx, sin OpenCV y sin OBS: la detección la
hace `detector_rostros` y la imagen llega en otros módulos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from bellbird.core.idioma import N_, _, ngettext

# Umbrales y esperas: valores de partida a ajustar con el usuario real.
UMBRAL_IZQUIERDA = 0.38
UMBRAL_DERECHA = 0.62
BORDE_CORTADO_ARRIBA = 0.01
BORDE_CORTADO_ABAJO = 0.99
OJO_ALTO = 0.25
OJO_BAJO = 0.45
TAMANO_LEJOS = 0.15
TAMANO_CERCA = 0.60
DESVIO_LADO = 0.35
ANGULO_INCLINADO = 15.0
LUZ_OSCURO = 50.0
DIFERENCIA_CONTRALUZ = 70.0
ESPERA_FUERA = 3.0
ESPERA_DENTRO = 1.5
ESPERA_REAVISO = 10.0
ESPERA_CONGELADA = 5.0

# Prioridad con la que se informan los problemas.
ORDEN_PROBLEMAS = ("cortado_arriba", "cortado_abajo", "mover_izquierda",
                   "mover_derecha", "alto", "bajo", "lejos", "cerca",
                   "girado", "inclinado", "contraluz", "oscuro")


@dataclass(frozen=True, slots=True)
class Rostro:
    """Un rostro detectado, en píxeles con el origen arriba a la izquierda.

    `ojo_izquierda` es el ojo que aparece más a la izquierda en la imagen,
    no el izquierdo de la persona.
    """

    x: float
    y: float
    ancho: float
    alto: float
    ojo_izquierda: tuple
    ojo_derecha: tuple
    nariz: tuple
    confianza: float = 0.0


@dataclass(frozen=True, slots=True)
class Encuadre:
    """Cuántos rostros hay y los problemas del principal, en prioridad."""

    cantidad: int
    problemas: tuple = ()


@dataclass(frozen=True, slots=True)
class Aviso:
    """Un aviso del vigía: `tipo` es «fuera» o «dentro», con su frase."""

    tipo: str
    frase: str


# Frase por código de problema. Se traducen al armar la frase.
_FRASE_POR_PROBLEMA = {
    # Traductores: aviso de encuadre, rostro fuera del borde superior.
    "cortado_arriba": N_("Rostro fuera del borde superior."),
    # Traductores: aviso de encuadre, rostro fuera del borde inferior.
    "cortado_abajo": N_("Rostro fuera del borde inferior."),
    # Traductores: aviso de encuadre, moverse a la propia izquierda.
    "mover_izquierda": N_("Muévete a tu izquierda."),
    # Traductores: aviso de encuadre, moverse a la propia derecha.
    "mover_derecha": N_("Muévete a tu derecha."),
    # Traductores: aviso de encuadre, rostro alto en la imagen.
    "alto": N_("Rostro alto en la imagen."),
    # Traductores: aviso de encuadre, rostro bajo en la imagen.
    "bajo": N_("Rostro bajo en la imagen."),
    # Traductores: aviso de encuadre, rostro lejos de la cámara.
    "lejos": N_("Rostro lejos: acércate a la cámara."),
    # Traductores: aviso de encuadre, rostro muy cerca de la cámara.
    "cerca": N_("Rostro muy cerca: aléjate de la cámara."),
    # Traductores: aviso de encuadre, rostro de lado.
    "girado": N_("Rostro de lado: mira a la cámara."),
    # Traductores: aviso de encuadre, cabeza inclinada.
    "inclinado": N_("Cabeza inclinada."),
    # Traductores: aviso de encuadre, contraluz detrás de la persona.
    "contraluz": N_("Contraluz: la luz está detrás de ti."),
    # Traductores: aviso de encuadre, poca luz sobre el rostro.
    "oscuro": N_("Rostro oscuro: falta luz delante."),
}


def principal(rostros):
    """El rostro de mayor área; a igual área, el primero de la lista."""
    return max(rostros, key=lambda rostro: rostro.ancho * rostro.alto)


def _esta_girado(rostro):
    """Verdadero si la nariz se aparta del medio de los ojos."""
    distancia_ojos = abs(rostro.ojo_izquierda[0] - rostro.ojo_derecha[0])
    # Solo cuenta el desplazamiento horizontal: la nariz queda debajo de
    # los ojos, así que la distancia directa siempre es grande.
    medio_ojos = (rostro.ojo_izquierda[0] + rostro.ojo_derecha[0]) / 2
    return (distancia_ojos > 0
            and abs(rostro.nariz[0] - medio_ojos)
            > DESVIO_LADO * distancia_ojos)


def _codigos_luz(luz_rostro, luz_fondo):
    """Códigos de luz del rostro: contraluz excluye a oscuro."""
    if luz_rostro is None:
        return {"contraluz": False, "oscuro": False}
    contraluz = luz_fondo is not None \
        and luz_fondo - luz_rostro > DIFERENCIA_CONTRALUZ
    return {"contraluz": contraluz,
            "oscuro": luz_rostro < LUZ_OSCURO and not contraluz}


def analizar(rostros, ancho_imagen, alto_imagen, espejo=False, luz_rostro=None,
               luz_fondo=None, congelada=False):
    """Problemas del rostro principal, en orden de prioridad.

    El principal es el de mayor área; a igual área, el primero de la
    lista. Con la cámara de frente, el lado izquierdo de la imagen es el
    derecho de la persona, así que en espejo los avisos horizontales se
    intercambian para decir el movimiento que la persona tiene que hacer.
    Con `congelada`, los problemas son solo ese: lo demás describe una
    imagen vieja.
    """
    if congelada:
        return Encuadre(cantidad=len(rostros), problemas=("congelada",))
    if not rostros:
        return Encuadre(cantidad=0, problemas=("sin_rostro",))
    elegido = principal(rostros)
    centro_x = (elegido.x + elegido.ancho / 2) / ancho_imagen
    izquierda = centro_x < UMBRAL_IZQUIERDA
    derecha = centro_x > UMBRAL_DERECHA
    if espejo:
        izquierda, derecha = derecha, izquierda
    cortado_arriba = elegido.y <= BORDE_CORTADO_ARRIBA * alto_imagen
    cortado_abajo = (elegido.y + elegido.alto
                     >= BORDE_CORTADO_ABAJO * alto_imagen)
    altura_ojos = (elegido.ojo_izquierda[1] + elegido.ojo_derecha[1]) / 2
    altura_ojos /= alto_imagen
    alto = altura_ojos < OJO_ALTO and not cortado_arriba
    bajo = altura_ojos > OJO_BAJO and not cortado_abajo
    tamano = elegido.alto / alto_imagen
    lejos = tamano < TAMANO_LEJOS
    cerca = tamano > TAMANO_CERCA
    girado = _esta_girado(elegido)
    # En píxeles, para que la proporción de la imagen no deforme el ángulo.
    delta_x = elegido.ojo_derecha[0] - elegido.ojo_izquierda[0]
    delta_y = elegido.ojo_derecha[1] - elegido.ojo_izquierda[1]
    inclinado = abs(math.degrees(math.atan2(delta_y, delta_x))) \
        > ANGULO_INCLINADO
    hallados = {"cortado_arriba": cortado_arriba,
                "cortado_abajo": cortado_abajo,
                "mover_izquierda": izquierda, "mover_derecha": derecha,
                "alto": alto, "bajo": bajo, "lejos": lejos, "cerca": cerca,
                "girado": girado, "inclinado": inclinado}
    hallados.update(_codigos_luz(luz_rostro, luz_fondo))
    problemas = tuple(codigo for codigo in ORDEN_PROBLEMAS
                      if hallados[codigo])
    return Encuadre(cantidad=len(rostros), problemas=problemas)


def frase(encuadre):
    """Texto del encuadre en el idioma elegido al momento de llamarla."""
    if "congelada" in encuadre.problemas:
        # Traductores: aviso de encuadre, la imagen no cambia.
        return _("Imagen congelada.")
    if encuadre.cantidad == 0:
        # Traductores: aviso de encuadre, sin rostros en la imagen.
        return _("Ningún rostro.")
    partes = []
    if encuadre.cantidad > 1:
        # Traductores: aviso de encuadre, {n} es cuántos rostros hay.
        partes.append(ngettext("{n} rostro.", "{n} rostros.",
                               encuadre.cantidad).format(n=encuadre.cantidad))
    if not encuadre.problemas:
        if encuadre.cantidad > 1:
            # Traductores: aviso de encuadre, el principal está centrado.
            partes.append(_("Rostro principal centrado."))
        else:
            # Traductores: aviso de encuadre, sin problemas.
            partes.append(_("Rostro centrado."))
        return " ".join(partes)
    partes.extend(_(_FRASE_POR_PROBLEMA[codigo])
                  for codigo in encuadre.problemas)
    return " ".join(partes)


@dataclass
class ContadorCongelada:
    """Dice si la imagen lleva congelada 5,0 s seguidos, sin hilos.

    Una cámara viva nunca da dos cuadros idénticos por el ruido del
    sensor, y OBS repite el último cuadro cuando la cámara se cuelga
    (hipótesis a medir con OBS): si la huella no cambia en 5,0 s
    seguidos, la imagen está congelada. Una huella distinta reinicia la
    cuenta, así que un cuadro quieto un momento no avisa.
    """

    _huella: object = field(default=None, init=False, repr=False)
    _inicio: float = field(default=0.0, init=False, repr=False)

    def observar(self, huella, ahora):
        """Verdadero cuando la misma huella lleva 5,0 s seguidos."""
        if huella != self._huella:
            self._huella = huella
            self._inicio = ahora
            return False
        return ahora - self._inicio >= ESPERA_CONGELADA


@dataclass
class VigiaEncuadre:
    """Decide cuándo el encuadre merece un aviso automático, sin hilos.

    Recién creado da por anunciado que está bien. Pasar a mal se anuncia
    como «fuera» a los 3,0 s seguidos mal; volver a bien como «dentro» al
    1,5 s seguido bien. Estando fuera, un cambio de problemas se vuelve a
    avisar cuando los nuevos llevan 3,0 s iguales y pasaron 10 s desde el
    último aviso. Cualquier observación del lado contrario reinicia la
    cuenta, así que un parpadeo nunca avisa. Otra vía obvia, avisar cada
    cierto tiempo, diría casi siempre «centrado» y se pisaría con el chat.
    """

    _anunciado: str = field(default="dentro", init=False)
    _anunciados: object = field(default=None, init=False)
    _racha_mal: object = field(default=None, init=False)
    _inicio_racha: float = field(default=0.0, init=False)
    _mismos: object = field(default=None, init=False)
    _inicio_mismos: float = field(default=0.0, init=False)
    _ultimo_aviso: object = field(default=None, init=False)

    def reiniciar(self):
        """Lo deja como recién creado: da por anunciado que está bien."""
        self._anunciado = "dentro"
        self._anunciados = None
        self._racha_mal = None
        self._inicio_racha = 0.0
        self._mismos = None
        self._inicio_mismos = 0.0
        self._ultimo_aviso = None

    def observar(self, encuadre, ahora):
        """Devuelve el Aviso que toca, o None si no toca avisar."""
        mal = bool(encuadre.problemas)
        if self._racha_mal is None or self._racha_mal != mal:
            self._racha_mal = mal
            self._inicio_racha = ahora
        if self._mismos is None or self._mismos != encuadre.problemas:
            self._mismos = encuadre.problemas
            self._inicio_mismos = ahora
        if mal:
            return self._observar_mal(encuadre, ahora)
        if self._anunciado == "fuera" \
                and ahora - self._inicio_racha >= ESPERA_DENTRO:
            self._anunciado = "dentro"
            self._ultimo_aviso = ahora
            # Traductores: aviso de encuadre, volvió a estar bien.
            return Aviso(tipo="dentro", frase=_("Rostro centrado."))
        return None

    def _observar_mal(self, encuadre, ahora):
        if self._anunciado == "fuera" and self._anunciados == encuadre.problemas:
            return None
        if self._anunciado == "fuera":
            if ahora - self._inicio_mismos < ESPERA_FUERA:
                return None
            if self._ultimo_aviso is not None \
                    and ahora - self._ultimo_aviso < ESPERA_REAVISO:
                return None
        elif ahora - self._inicio_racha < ESPERA_FUERA:
            return None
        self._anunciado = "fuera"
        self._anunciados = encuadre.problemas
        self._ultimo_aviso = ahora
        return Aviso(tipo="fuera", frase=frase(encuadre))
