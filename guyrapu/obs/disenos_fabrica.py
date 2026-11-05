"""Diseños de escena de fábrica y su llenado con las fuentes de una escena.

Su razón para cambiar: qué diseños trae la app y cómo se completan con las
fuentes que la escena ya tiene. No habla con OBS ni con wx.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from guyrapu.core.idioma import N_, _
from guyrapu.obs.disenos_escena import (
    ESTADO_AJUSTA, ESTADO_AJUSTA_SIN_ORIGEN, ESTADO_LLENA, Diseno)


PAPEL_CAMARA = "camara"
PAPEL_PRINCIPAL = ("captura", "otra")

_ETIQUETAS_LUGAR = {
    "principal": N_("la fuente principal"),
    "secundaria": N_("la fuente en la esquina"),
    "izquierda": N_("la fuente a la izquierda"),
    "derecha": N_("la fuente a la derecha"),
}


@dataclass(frozen=True)
class DisenoFabrica:
    """Un diseño de fábrica con el papel que pide cada lugar."""

    clave: str
    nombre: str
    diseno: Diseno
    papeles: dict


FABRICA = (
    DisenoFabrica(
        clave="imagen_esquina",
        nombre=N_("Fuente principal con cámara en una esquina"),
        diseno=Diseno(clase="imagen_en_imagen", esquina="inferior-derecha",
                      tamano="mediana"),
        papeles={"principal": PAPEL_PRINCIPAL, "secundaria": PAPEL_CAMARA}),
    DisenoFabrica(
        clave="imagen_esquina_chat",
        nombre=N_("Fuente principal con cámara y chat a la derecha"),
        diseno=Diseno(clase="imagen_en_imagen", esquina="superior-derecha",
                      tamano="mediana", chat="franja"),
        papeles={"principal": PAPEL_PRINCIPAL, "secundaria": PAPEL_CAMARA}),
    DisenoFabrica(
        clave="camara_esquina",
        nombre=N_("Cámara con la fuente principal en una esquina"),
        diseno=Diseno(clase="imagen_en_imagen", esquina="inferior-derecha",
                      tamano="mediana"),
        papeles={"principal": PAPEL_CAMARA, "secundaria": PAPEL_PRINCIPAL}),
    DisenoFabrica(
        clave="pantalla_juego",
        nombre=N_("Fuente principal a pantalla completa"),
        diseno=Diseno(clase="pantalla_completa"),
        papeles={"principal": PAPEL_PRINCIPAL}),
    DisenoFabrica(
        clave="pantalla_camara",
        nombre=N_("Cámara a pantalla completa"),
        diseno=Diseno(clase="pantalla_completa"),
        papeles={"principal": PAPEL_CAMARA}),
    DisenoFabrica(
        clave="dividida_mitades",
        nombre=N_("Fuente principal y cámara lado a lado"),
        diseno=Diseno(clase="dividida", proporcion="mitades"),
        papeles={"izquierda": PAPEL_PRINCIPAL, "derecha": PAPEL_CAMARA}),
    DisenoFabrica(
        clave="dividida_dos_tercios",
        nombre=N_("Fuente principal grande y cámara a la derecha"),
        diseno=Diseno(clase="dividida", proporcion="dos_tercios"),
        papeles={"izquierda": PAPEL_PRINCIPAL, "derecha": PAPEL_CAMARA}),
)


def lugares(clase):
    """Los lugares que llena una clase de diseño, en el orden del cuadro."""
    if clase == "imagen_en_imagen":
        return ("principal", "secundaria")
    if clase == "dividida":
        return ("izquierda", "derecha")
    return ("principal",)


def completar(diseno, papeles, fuentes):
    """Devuelve el diseño con cada lugar lleno con una fuente de la escena.

    Conserva el nombre que ya trae el diseño si sigue en la escena y no es el
    chat; si no, toma la primera fuente sin usar con el papel del lugar, y
    como último recurso cualquier otra fuente que no sea el chat.
    """
    usadas = set()
    valores = {}
    for lugar in lugares(diseno.clase):
        actual = getattr(diseno, lugar, "")
        if _sirve(actual, fuentes, usadas):
            elegida = actual
        else:
            elegida = (
                _primera_sin_usar(fuentes, usadas, papeles.get(lugar))
                or _primera_sin_usar(fuentes, usadas) or "")
        valores[lugar] = elegida
        if elegida:
            usadas.add(elegida)
    return replace(diseno, **valores)


def motivo_para_no_aplicar(diseno, fuentes):
    """El primer problema que impide aplicar el diseño, o None."""
    nombres = {fuente.nombre for fuente in fuentes}
    vistos = set()
    for lugar in lugares(diseno.clase):
        nombre = getattr(diseno, lugar, "")
        if not nombre or nombre not in nombres:
            return (lugar, _("Elige una fuente para {lugar}.").format(
                lugar=_(_ETIQUETAS_LUGAR[lugar])))
        if nombre in vistos:
            return (lugar, _("{fuente} está en dos lugares. Elige otra.").format(
                fuente=nombre))
        vistos.add(nombre)
    if diseno.chat != "ninguno" and not any(
            fuente.tipo == "chat" for fuente in fuentes):
        return ("chat", _("La escena no tiene el chat en el vídeo. Elige Sin "
                          "chat o activa Mostrar chat en el vídeo en la "
                          "pestaña Transmisión."))
    return None


def resumen(nombre_diseno, estados, sin_mover=()):
    """El anuncio de un diseño aplicado, con una frase por fuente."""
    frases = [_("Diseño aplicado: {nombre}.").format(nombre=nombre_diseno)]
    for fuente, estado in estados:
        if estado == ESTADO_LLENA:
            frases.append(_("{fuente} llena su lugar, con los bordes "
                            "recortados.").format(fuente=fuente))
        elif estado == ESTADO_AJUSTA:
            frases.append(_("{fuente} se ajusta a su lugar.").format(
                fuente=fuente))
        elif estado == ESTADO_AJUSTA_SIN_ORIGEN:
            frases.append(_("{fuente} todavía no informa su tamaño y se ajusta "
                            "a su lugar.").format(fuente=fuente))
    if sin_mover:
        frases.append(_("No se movieron: {fuentes}.").format(
            fuentes=", ".join(sin_mover)))
    return " ".join(frases)


def _sirve(nombre, fuentes, usadas):
    return bool(nombre) and nombre not in usadas and any(
        fuente.nombre == nombre and fuente.tipo != "chat"
        for fuente in fuentes)


def _primera_sin_usar(fuentes, usadas, papel=None):
    for fuente in fuentes:
        if fuente.nombre in usadas or fuente.tipo == "chat":
            continue
        if papel is None or _acepta(papel, fuente.tipo):
            return fuente.nombre
    return ""


def _acepta(papel, tipo):
    if isinstance(papel, tuple):
        return tipo in papel
    return tipo == papel
