"""Elección y anuncios de las fuentes de audio de OBS."""

import unicodedata

from bellbird.core.idioma import N_, _


def _contiene_microfono(nombre: str) -> bool:
    normalizado = unicodedata.normalize("NFD", nombre.casefold())
    sin_tildes = "".join(
        caracter for caracter in normalizado
        if unicodedata.category(caracter) != "Mn")
    return "mic" in sin_tildes


def es_microfono(fuente: str) -> bool:
    """¿La fuente es de micrófono? Decide el nombre, como el anuncio."""
    return _contiene_microfono(fuente)


def elegir_microfono(entradas, preferido: str, especial: str = "") -> str:
    nombres = [nombre for nombre, _tipo in entradas]
    for candidato in (preferido, especial):
        if candidato in nombres:
            return candidato
    return next((n for n, t in entradas if t == "wasapi_input_capture"),
                next((n for n, u in entradas if _contiene_microfono(n)), ""))


def nombre_corto(nombre: str) -> str:
    """Nombre del dispositivo sin el envoltorio que agrega Windows."""
    texto = str(nombre or "")
    if texto.endswith(")") and " (" in texto:
        corto = texto[texto.find(" (") + 2:-1].strip()
        if corto:
            return corto
    return texto


def _frase_predeterminado(corto: str) -> str:
    if corto:
        # Traductores: {corto} es el nombre corto del dispositivo.
        return _("Micrófono activado: predeterminado de Windows, "
                 "{corto}").format(corto=corto)
    return _("Micrófono activado: predeterminado de Windows")


def _frase_fijo(corto: str) -> str:
    if corto:
        # Traductores: {corto} es el nombre corto del dispositivo.
        return _("Micrófono activado: {corto}").format(corto=corto)
    return _("Micrófono activado")


def _frase_activada(dispositivo: str, predeterminado: bool) -> str:
    corto = nombre_corto(dispositivo) if dispositivo else ""
    if predeterminado:
        return _frase_predeterminado(corto)
    return _frase_fijo(corto)


def _frase_silenciado_predeterminado(corto: str) -> str:
    if corto:
        # Traductores: {corto} es el nombre corto del dispositivo.
        return _("Micrófono silenciado: predeterminado de Windows, "
                 "{corto}").format(corto=corto)
    return _("Micrófono silenciado: predeterminado de Windows")


def _frase_silenciado_fijo(corto: str) -> str:
    if corto:
        # Traductores: {corto} es el nombre corto del dispositivo.
        return _("Micrófono silenciado: {corto}").format(corto=corto)
    return _("Micrófono silenciado")


def _frase_silenciado(dispositivo: str, predeterminado: bool) -> str:
    corto = nombre_corto(dispositivo) if dispositivo else ""
    if predeterminado:
        return _frase_silenciado_predeterminado(corto)
    return _frase_silenciado_fijo(corto)


# Traductores: estado de la fuente de audio; se muestra tras su nombre.
ESTADO_SILENCIADO = N_("silenciado")
# Traductores: estado de la fuente de audio; se muestra tras su nombre.
ESTADO_ACTIVADO = N_("activado")


def _frase(fuente: str, estado: str, dispositivo: str,
           predeterminado: bool) -> str:
    if _contiene_microfono(fuente):
        if estado == "silenciado":
            return _frase_silenciado(dispositivo, predeterminado)
        return _frase_activada(dispositivo, predeterminado)
    # Traductores: {fuente} es el nombre de la fuente y {estado} su estado.
    return _("{fuente} {estado}").format(fuente=fuente, estado=_(estado))


def frase_microfono(fuente: str, silenciado: bool, dispositivo: str = "",
                    predeterminado: bool = False) -> str:
    """Compone el anuncio posterior a cambiar el silencio."""
    if not fuente:
        return _("OBS no tiene ninguna fuente de audio")
    estado = ESTADO_SILENCIADO if silenciado else ESTADO_ACTIVADO
    return _frase(fuente, estado, dispositivo, predeterminado)


# -80 dBFS: debajo queda indistinguible del silencio. Medido en OBS 32.2.2
# el 23/10: un micrófono prendido sin hablar sobresale con pico de 0,049.
UMBRAL_SENAL = 0.0001

TEXTO_SIN_SENAL = N_("El micrófono no recibe sonido. Revisa cuál está "
                     "elegido en Windows o en OBS.")


def _nivel_de_canal(canal) -> float:
    # El canal trae [magnitud, pico, pico de entrada]; el índice 2 es
    # anterior al volumen de OBS y no lo tapa. Sin los tres, el que haya.
    return canal[2] if len(canal) > 2 else canal[-1]


def _niveles_de(eventos, fuente: str):
    for evento in eventos:
        for entrada in evento.get("inputs") or ():
            if entrada.get("inputName") != fuente:
                continue
            for canal in entrada.get("inputLevelsMul") or ():
                yield _nivel_de_canal(canal)


def tiene_senal(eventos, fuente: str) -> bool | None:
    """¿Entró algo por la fuente en los eventos medidos? None si ninguna
    muestra de esa fuente llegó; con muestras, si superó el umbral."""
    niveles = list(_niveles_de(eventos, fuente))
    if not niveles:
        return None
    return max(niveles) > UMBRAL_SENAL
