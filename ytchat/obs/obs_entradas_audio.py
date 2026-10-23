"""Consultar y alternar las entradas de audio de OBS.

Recibe un cliente con `pedir(tipo, datos=None, parada=None)` como
`obs_captura` y no crea conexiones.
"""

from __future__ import annotations

from ytchat.obs import obs_audio


def _datos(cliente, tipo, datos=None, parada=None):
    respuesta = cliente.pedir(tipo, datos, parada=parada)
    return respuesta.get("responseData", {})


def fuentes_audio(cliente, parada=None) -> tuple:
    entradas = _datos(cliente, "GetInputList", parada=parada).get("inputs", ())
    fuentes = []
    for entrada in entradas:
        nombre = entrada.get("inputName", "")
        if not nombre:
            continue
        try:
            silenciada(cliente, nombre, parada)
        except Exception:
            continue
        fuentes.append(nombre)
    return tuple(fuentes)


def silenciada(cliente, fuente, parada=None) -> bool:
    datos = _datos(cliente, "GetInputMute", {"inputName": fuente}, parada)
    return bool(datos.get("inputMuted", False))


def alternar_silencio(cliente, fuente, parada=None) -> bool:
    datos = _datos(cliente, "ToggleInputMute", {"inputName": fuente}, parada)
    return bool(datos.get("inputMuted", False))


def alternar_microfono(gestor, preferido) -> str:
    """Elige el micrófono, alterna su silencio y arma el anuncio."""
    fuente = obs_audio.elegir_microfono(gestor.fuentes_audio(), preferido)
    estado = gestor.alternar_silencio(fuente) if fuente else False
    return obs_audio.frase_microfono(fuente, estado)
