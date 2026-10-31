"""Lógica pura del encuadre de cámara y del vigía de avisos.

A partir de los rostros ya detectados, en píxeles, dice qué problemas
tiene el encuadre, arma la frase que se anuncia y decide cuándo un aviso
automático tiene que sonar. Sin wx, sin OpenCV y sin OBS: nadie lo llama
todavía, la detección y la imagen llegan en otros módulos.
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
ESPERA_FUERA = 3.0
ESPERA_DENTRO = 1.5
ESPERA_REAVISO = 10.0

# Prioridad con la que se informan los problemas.
ORDEN_PROBLEMAS = ("cortado_arriba", "cortado_abajo", "mover_izquierda",
                   "mover_derecha", "alto", "bajo", "lejos", "cerca",
                   "girado", "inclinado")


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
    # Traductores: aviso de encuadre, rostro cortado por arriba.
    "cortado_arriba": N_("Rostro cortado arriba."),
    # Traductores: aviso de encuadre, rostro cortado por abajo.
    "cortado_abajo": N_("Rostro cortado abajo."),
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
}


def _area(rostro):
    return rostro.ancho * rostro.alto


def analizar(rostros, ancho_imagen, alto_imagen, espejo=False):
    """Problemas del rostro principal, en orden de prioridad.

    El principal es el de mayor área; a igual área, el primero de la
    lista. Con la cámara de frente, el lado izquierdo de la imagen es el
    derecho de la persona, así que en espejo los avisos horizontales se
    intercambian para decir el movimiento que la persona tiene que hacer.
    """
    if not rostros:
        return Encuadre(cantidad=0, problemas=("sin_rostro",))
    principal = max(rostros, key=_area)
    centro_x = (principal.x + principal.ancho / 2) / ancho_imagen
    izquierda = centro_x < UMBRAL_IZQUIERDA
    derecha = centro_x > UMBRAL_DERECHA
    if espejo:
        izquierda, derecha = derecha, izquierda
    cortado_arriba = principal.y <= BORDE_CORTADO_ARRIBA * alto_imagen
    cortado_abajo = (principal.y + principal.alto
                     >= BORDE_CORTADO_ABAJO * alto_imagen)
    altura_ojos = (principal.ojo_izquierda[1] + principal.ojo_derecha[1]) / 2
    altura_ojos /= alto_imagen
    alto = altura_ojos < OJO_ALTO and not cortado_arriba
    bajo = altura_ojos > OJO_BAJO and not cortado_abajo
    tamano = principal.alto / alto_imagen
    lejos = tamano < TAMANO_LEJOS
    cerca = tamano > TAMANO_CERCA
    distancia_ojos = abs(principal.ojo_izquierda[0]
                         - principal.ojo_derecha[0])
    # Solo cuenta el desplazamiento horizontal: la nariz queda debajo de
    # los ojos, así que la distancia directa siempre es grande.
    medio_ojos = (principal.ojo_izquierda[0] + principal.ojo_derecha[0]) / 2
    girado = (distancia_ojos > 0
              and abs(principal.nariz[0] - medio_ojos)
              > DESVIO_LADO * distancia_ojos)
    # En píxeles, para que la proporción de la imagen no deforme el ángulo.
    delta_x = principal.ojo_derecha[0] - principal.ojo_izquierda[0]
    delta_y = principal.ojo_derecha[1] - principal.ojo_izquierda[1]
    inclinado = abs(math.degrees(math.atan2(delta_y, delta_x))) \
        > ANGULO_INCLINADO
    hallados = {"cortado_arriba": cortado_arriba,
                "cortado_abajo": cortado_abajo,
                "mover_izquierda": izquierda, "mover_derecha": derecha,
                "alto": alto, "bajo": bajo, "lejos": lejos, "cerca": cerca,
                "girado": girado, "inclinado": inclinado}
    problemas = tuple(codigo for codigo in ORDEN_PROBLEMAS
                      if hallados[codigo])
    return Encuadre(cantidad=len(rostros), problemas=problemas)


def frase(encuadre):
    """Texto del encuadre en el idioma elegido al momento de llamarla."""
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
