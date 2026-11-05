"""Lectura de `PollEvent` de TikTokLive hacia el registro de encuestas.

Único módulo que conoce el evento de encuestas de TikTokLive. Única razón
para cambiar: cómo se lee una encuesta de la biblioteca. La etapa se
reconoce por el contenido que llega cargado, nunca por `message_type`.
"""

from __future__ import annotations

from guyrapu.capture import encuestas
from guyrapu.core.tipos_mensaje import TIPO_ENCUESTA, TIPO_ENCUESTA_FIN


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _opciones(contenido) -> list[tuple[str, int]]:
    lista = getattr(contenido, "option_list", None) or []
    opciones = []
    for opcion in lista:
        texto = _texto(getattr(opcion, "display_content", ""))
        if not texto:
            continue
        try:
            votos = max(0, int(getattr(opcion, "votes", 0) or 0))
        except (TypeError, ValueError):
            votos = 0
        opciones.append((texto, votos))
    return opciones


def _titulo(evento) -> str:
    for contenido in (getattr(evento, "start_content", None),
                      getattr(evento, "poll_basic_info", None)):
        titulo = _texto(getattr(contenido, "title", ""))
        if titulo:
            return titulo
    return ""


def _apertura(evento, on_evento) -> None:
    opciones = _opciones(evento.start_content)
    if not opciones:
        return
    id_encuesta = _texto(getattr(evento, "poll_id", ""))
    titulo = _titulo(evento)
    if encuestas.registro.abrir(id_encuesta, titulo, opciones):
        on_evento("", encuestas.frase_apertura(titulo, opciones),
                  TIPO_ENCUESTA, "", "")


def _cierre(evento, on_evento) -> None:
    opciones = _opciones(evento.end_content)
    if not opciones:
        return
    id_encuesta = _texto(getattr(evento, "poll_id", ""))
    titulo = _titulo(evento)
    if encuestas.registro.cerrar(id_encuesta, titulo, opciones):
        titulo = titulo or encuestas.registro.titulo_de(id_encuesta)
        on_evento("", encuestas.frase_cierre(titulo, opciones),
                  TIPO_ENCUESTA_FIN, "", "")


def procesar(evento, on_evento) -> None:
    """Lee una encuesta y avisa cuando se abre o se cierra."""
    fin = getattr(evento, "end_content", None)
    if fin is not None and _opciones(fin):
        _cierre(evento, on_evento)
        return
    inicio = getattr(evento, "start_content", None)
    if inicio is not None and _opciones(inicio):
        _apertura(evento, on_evento)
        return
    actualizacion = getattr(evento, "update_votes_content", None)
    if actualizacion is not None:
        opciones = _opciones(actualizacion)
        if opciones:
            encuestas.registro.votos(
                _texto(getattr(evento, "poll_id", "")), opciones)


def reiniciar() -> None:
    """Olvida las encuestas de la conexión anterior."""
    encuestas.registro.reiniciar()
