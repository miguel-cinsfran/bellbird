"""Pedidos y respuestas de IA con visión, sin red ni disco.

La app programa protocolos, no proveedores. Este módulo arma el
pedido HTTP de cada uno y lee su respuesta o la convierte en ErrorIA.
"""

import base64
import json
import re
from dataclasses import dataclass

CHAT = "chat"
RESPONSES = "responses"
ANTHROPIC = "anthropic"
GEMINI = "gemini"

CLAVE_RECHAZADA = "clave_rechazada"
CUOTA = "cuota"
MODELO_INEXISTENTE = "modelo_inexistente"
BLOQUEADA = "bloqueada"
SIN_TEXTO_POR_TOKENS = "sin_texto_por_tokens"
RESPUESTA_VACIA = "respuesta_vacia"
SERVIDOR = "servidor"
RECHAZO = "rechazo"
SIN_RED = "sin_red"
TIEMPO_AGOTADO = "tiempo_agotado"

_TOPE_DETALLE = 300

# La cuota de un modelo de Gemini sin nivel gratuito llega en el texto del
# 429 con el cero, que es lo único que distingue «sin nivel gratuito» de
# «cuota agotada por hoy». Se mira antes de recortar el detalle.
_RE_SIN_NIVEL_GRATUITO = re.compile(r"free_tier[^\n]*limit:\s*0\b")


@dataclass(frozen=True)
class Mensaje:
    rol: str
    texto: str = ""
    imagen: bytes | None = None


@dataclass
class Pedido:
    protocolo: str
    url: str
    cabeceras: dict
    cuerpo: dict


@dataclass
class Respuesta:
    texto: str
    cortada: bool = False


class ErrorIA(Exception):
    def __init__(self, tipo, detalle="", sin_nivel_gratuito=False):
        super().__init__(f"{tipo}: {detalle}")
        self.tipo = tipo
        self.detalle = detalle
        self.sin_nivel_gratuito = sin_nivel_gratuito


def _base64_imagen(datos):
    return base64.b64encode(datos).decode("ascii")


def _con_extra(cabeceras, extra):
    if extra:
        cabeceras.update(extra)
    return cabeceras


def _pedido_chat(base, modelo, clave, sistema, mensajes, max_tokens):
    cuerpo_mensajes = [{"role": "system", "content": sistema}]
    for mensaje in mensajes:
        if mensaje.rol == "asistente" and mensaje.imagen is None:
            cuerpo_mensajes.append(
                {"role": "assistant", "content": mensaje.texto})
            continue
        partes = []
        if mensaje.texto:
            partes.append({"type": "text", "text": mensaje.texto})
        if mensaje.imagen is not None:
            partes.append({"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64,"
                + _base64_imagen(mensaje.imagen)}})
        rol = "assistant" if mensaje.rol == "asistente" else "user"
        if mensaje.rol == "asistente" and len(partes) == 1 \
                and partes[0].get("type") == "text":
            cuerpo_mensajes.append(
                {"role": rol, "content": partes[0]["text"]})
        else:
            cuerpo_mensajes.append({"role": rol, "content": partes})
    cuerpo = {"model": modelo, "messages": cuerpo_mensajes,
              "max_tokens": max_tokens}
    return Pedido(CHAT, f"{base}/chat/completions",
                  {"Content-Type": "application/json",
                   "Authorization": f"Bearer {clave}"}, cuerpo)


def _pedido_responses(base, modelo, clave, sistema, mensajes, max_tokens):
    turnos = []
    for mensaje in mensajes:
        contenido = []
        if mensaje.rol == "asistente":
            if mensaje.texto:
                contenido.append(
                    {"type": "output_text", "text": mensaje.texto})
            if mensaje.imagen is not None:
                contenido.append({"type": "input_image", "image_url":
                                  "data:image/jpeg;base64,"
                                  + _base64_imagen(mensaje.imagen)})
            turnos.append({"role": "assistant", "content": contenido})
            continue
        if mensaje.texto:
            contenido.append({"type": "input_text", "text": mensaje.texto})
        if mensaje.imagen is not None:
            contenido.append({"type": "input_image", "image_url":
                              "data:image/jpeg;base64,"
                              + _base64_imagen(mensaje.imagen)})
        turnos.append({"role": "user", "content": contenido})
    cuerpo = {"model": modelo, "instructions": sistema, "input": turnos,
              "max_output_tokens": max_tokens}
    return Pedido(RESPONSES, f"{base}/responses",
                  {"Content-Type": "application/json",
                   "Authorization": f"Bearer {clave}"}, cuerpo)


def _pedido_anthropic(base, modelo, clave, sistema, mensajes, max_tokens):
    cuerpo_mensajes = []
    for mensaje in mensajes:
        if mensaje.rol == "asistente" and mensaje.imagen is None:
            cuerpo_mensajes.append(
                {"role": "assistant", "content": mensaje.texto})
            continue
        bloques = []
        if mensaje.imagen is not None:
            bloques.append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": _base64_imagen(mensaje.imagen)}})
        if mensaje.texto:
            bloques.append({"type": "text", "text": mensaje.texto})
        rol = "assistant" if mensaje.rol == "asistente" else "user"
        cuerpo_mensajes.append({"role": rol, "content": bloques})
    cuerpo = {"model": modelo, "system": sistema,
              "messages": cuerpo_mensajes, "max_tokens": max_tokens}
    return Pedido(ANTHROPIC, f"{base}/messages",
                  {"Content-Type": "application/json",
                   "x-api-key": clave,
                   "anthropic-version": "2023-06-01"}, cuerpo)


def _pedido_gemini(base, modelo, clave, sistema, mensajes, max_tokens):
    contenidos = []
    for mensaje in mensajes:
        partes = []
        if mensaje.imagen is not None:
            partes.append({"inline_data": {
                "mime_type": "image/jpeg",
                "data": _base64_imagen(mensaje.imagen)}})
        if mensaje.texto:
            partes.append({"text": mensaje.texto})
        rol = "model" if mensaje.rol == "asistente" else "user"
        contenidos.append({"role": rol, "parts": partes})
    cuerpo = {"systemInstruction": {"parts": [{"text": sistema}]},
              "contents": contenidos,
              "generationConfig": {"maxOutputTokens": max_tokens}}
    return Pedido(GEMINI, f"{base}/models/{modelo}:generateContent",
                  {"Content-Type": "application/json",
                   "x-goog-api-key": clave}, cuerpo)


def armar_pedido(protocolo, base, modelo, clave, sistema, mensajes,
                 max_tokens, cabeceras_extra=None):
    constructores = {CHAT: _pedido_chat, RESPONSES: _pedido_responses,
                     ANTHROPIC: _pedido_anthropic, GEMINI: _pedido_gemini}
    constructor = constructores.get(protocolo)
    if constructor is None:
        raise ValueError(f"protocolo desconocido: {protocolo}")
    pedido = constructor(base.rstrip("/"), modelo, clave, sistema,
                         mensajes, max_tokens)
    pedido.cabeceras = _con_extra(pedido.cabeceras, cabeceras_extra)
    return pedido


def _recortar(texto):
    if not isinstance(texto, str):
        return ""
    return texto[:_TOPE_DETALLE]


def _sin_nivel_gratuito(estado, mensaje):
    if estado != 429 or not isinstance(mensaje, str):
        return False
    return bool(_RE_SIN_NIVEL_GRATUITO.search(mensaje))


def _mensaje_de_error(datos):
    if not isinstance(datos, dict):
        return ""
    error = datos.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    if isinstance(error, str):
        return error
    mensaje = datos.get("message")
    if isinstance(mensaje, str):
        return mensaje
    return ""


def _tipo_por_estado(estado, mensaje, crudo):
    if estado in (401, 403):
        return CLAVE_RECHAZADA
    if estado == 429:
        return CUOTA
    if estado == 404:
        return MODELO_INEXISTENTE
    if estado >= 500:
        return SERVIDOR
    if estado == 400:
        junto = f"{mensaje}\n{crudo}".lower()
        if "api_key_invalid" in junto or "invalid credential" in junto:
            return CLAVE_RECHAZADA
        if "model is unavailable" in junto \
                or "model_not_found" in junto \
                or "does not exist" in junto:
            return MODELO_INEXISTENTE
        return RECHAZO
    if 400 <= estado < 500:
        return RECHAZO
    return RESPUESTA_VACIA


def _error_de_estado(estado, crudo, datos):
    mensaje = _mensaje_de_error(datos) if datos is not None else ""
    detalle = _recortar(mensaje) if mensaje else _recortar(crudo)
    return ErrorIA(_tipo_por_estado(estado, mensaje, crudo), detalle,
                   _sin_nivel_gratuito(estado, mensaje or crudo))


def _texto_chat(datos):
    opciones = datos.get("choices")
    if not isinstance(opciones, list) or not opciones:
        return "", False
    primera = opciones[0]
    if not isinstance(primera, dict):
        return "", False
    mensaje = primera.get("message")
    if not isinstance(mensaje, dict):
        return "", False
    contenido = mensaje.get("content")
    if isinstance(contenido, str):
        texto = contenido
    elif isinstance(contenido, list):
        texto = "".join(
            parte.get("text", "") for parte in contenido
            if isinstance(parte, dict) and parte.get("type") == "text"
            and isinstance(parte.get("text"), str))
    else:
        texto = ""
    return texto, primera.get("finish_reason") == "length"


def _texto_responses(datos):
    salida = datos.get("output")
    textos = []
    if isinstance(salida, list):
        for elemento in salida:
            if not isinstance(elemento, dict):
                continue
            if elemento.get("type") != "message":
                continue
            contenido = elemento.get("content")
            if not isinstance(contenido, list):
                continue
            for bloque in contenido:
                if not isinstance(bloque, dict):
                    continue
                if bloque.get("type") == "output_text" \
                        and isinstance(bloque.get("text"), str):
                    textos.append(bloque["text"])
    return "".join(textos), datos.get("status") == "incomplete"


def _texto_anthropic(datos):
    contenido = datos.get("content")
    textos = []
    if isinstance(contenido, list):
        for bloque in contenido:
            if not isinstance(bloque, dict):
                continue
            if bloque.get("type") == "text" \
                    and isinstance(bloque.get("text"), str):
                textos.append(bloque["text"])
    return "".join(textos), datos.get("stop_reason") == "max_tokens"


def _texto_gemini(datos):
    candidatos = datos.get("candidates")
    if not isinstance(candidatos, list) or not candidatos:
        primero = {}
    elif isinstance(candidatos[0], dict):
        primero = candidatos[0]
    else:
        primero = {}
    contenido = primero.get("content") if isinstance(primero, dict) else None
    partes = contenido.get("parts") if isinstance(contenido, dict) else None
    textos = []
    if isinstance(partes, list):
        for parte in partes:
            if not isinstance(parte, dict):
                continue
            if parte.get("thought") is True:
                continue
            if isinstance(parte.get("text"), str):
                textos.append(parte["text"])
    terminacion = primero.get("finishReason") \
        if isinstance(primero, dict) else None
    respuesta = datos.get("promptFeedback")
    bloqueo = respuesta.get("blockReason") \
        if isinstance(respuesta, dict) else None
    bloqueada = bool(bloqueo) or terminacion in (
        "SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST")
    return "".join(textos), terminacion == "MAX_TOKENS", bloqueada, \
        str(bloqueo or terminacion or "")


def leer_respuesta(protocolo, estado, cuerpo):
    if isinstance(cuerpo, bytes):
        crudo = cuerpo.decode("utf-8", errors="replace")
    elif isinstance(cuerpo, str):
        crudo = cuerpo
    else:
        crudo = str(cuerpo)
    try:
        datos = json.loads(crudo)
    except ValueError:
        datos = None
    if estado != 200:
        raise _error_de_estado(estado, crudo, datos)
    if not isinstance(datos, dict):
        raise ErrorIA(RESPUESTA_VACIA, _recortar(crudo))
    if protocolo == GEMINI:
        texto, sin_tokens, bloqueada, detalle_bloqueo = _texto_gemini(datos)
    elif protocolo == CHAT:
        texto, sin_tokens = _texto_chat(datos)
        bloqueada, detalle_bloqueo = False, ""
    elif protocolo == RESPONSES:
        texto, sin_tokens = _texto_responses(datos)
        bloqueada, detalle_bloqueo = False, ""
    elif protocolo == ANTHROPIC:
        texto, sin_tokens = _texto_anthropic(datos)
        bloqueada, detalle_bloqueo = False, ""
    else:
        raise ValueError(f"protocolo desconocido: {protocolo}")
    texto = texto.strip()
    if texto:
        return Respuesta(texto, cortada=bool(sin_tokens))
    if bloqueada:
        raise ErrorIA(BLOQUEADA, _recortar(detalle_bloqueo or crudo))
    if sin_tokens:
        raise ErrorIA(SIN_TEXTO_POR_TOKENS, _recortar(crudo))
    raise ErrorIA(RESPUESTA_VACIA, _recortar(crudo))
