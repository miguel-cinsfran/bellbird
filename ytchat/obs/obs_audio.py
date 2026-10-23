"""Elección y anuncios de las fuentes de audio de OBS."""

import unicodedata


def _contiene_microfono(nombre: str) -> bool:
    normalizado = unicodedata.normalize("NFD", nombre.casefold())
    sin_tildes = "".join(
        caracter for caracter in normalizado
        if unicodedata.category(caracter) != "Mn")
    return "mic" in sin_tildes


def elegir_microfono(fuentes, preferido: str) -> str:
    """Devuelve la fuente de audio que se usará como micrófono."""
    fuentes = tuple(fuentes)
    if preferido in fuentes:
        return preferido
    return next((fuente for fuente in fuentes if _contiene_microfono(fuente)),
                fuentes[0] if fuentes else "")


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
        return f"Micrófono activado: predeterminado de Windows, {corto}"
    return "Micrófono activado: predeterminado de Windows"


def _frase_fijo(corto: str) -> str:
    if corto:
        return f"Micrófono activado: {corto}"
    return "Micrófono activado"


def _frase_activada(dispositivo: str, predeterminado: bool) -> str:
    corto = nombre_corto(dispositivo) if dispositivo else ""
    if predeterminado:
        return _frase_predeterminado(corto)
    return _frase_fijo(corto)


def _frase(fuente: str, estado: str, dispositivo: str,
           predeterminado: bool) -> str:
    if _contiene_microfono(fuente):
        if estado == "silenciado":
            return "Micrófono silenciado"
        return _frase_activada(dispositivo, predeterminado)
    return f"{fuente} {estado}"


def frase_microfono(fuente: str, silenciado: bool, dispositivo: str = "",
                    predeterminado: bool = False) -> str:
    """Compone el anuncio posterior a cambiar el silencio."""
    if not fuente:
        return "OBS no tiene ninguna fuente de audio"
    estado = "silenciado" if silenciado else "activado"
    return _frase(fuente, estado, dispositivo, predeterminado)
