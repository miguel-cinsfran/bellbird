"""Lógica de mensajes programados, sin acceso a la interfaz ni a la red."""

from __future__ import annotations

import json
import math
import re

from bellbird.core import archivos
from bellbird.capture.redaccion import MAXIMO_CHAT as MAX_CARACTERES
from bellbird.core.idioma import _, ngettext


MINUTOS_MINIMOS = 5  # Piso de prudencia contra el antispam.
SEGUNDOS_ENTRE_ENVIOS = 60  # Si dos vencen a la vez, el segundo espera.

VALORES_POR_DEFECTO = {
    "texto": "",
    "minutos_min": 10,
    "minutos_max": 10,
    "activo": False,
    "proximo": 0.0,
}

_URL_RE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)


def validar_mensaje(texto: str, minutos_min: int, minutos_max: int) -> tuple[str, str]:
    """Valida un mensaje y devuelve un error y un aviso, en ese orden."""
    if not texto.strip():
        # Traductores: validación de mensajes programados (error).
        return _("El mensaje no puede estar vacío."), ""
    if len(texto) > MAX_CARACTERES:
        # Traductores: validación de mensajes programados (error). {actual} es el largo y {maximo} el tope.
        return (_("El mensaje tiene {actual} caracteres y el máximo son "
                  "{maximo}.").format(actual=len(texto), maximo=MAX_CARACTERES)), ""
    if minutos_min < MINUTOS_MINIMOS:
        # Traductores: validación de mensajes programados (error). {minimo} es el mínimo.
        return _("El intervalo mínimo son {minimo} minutos.").format(minimo=MINUTOS_MINIMOS), ""
    if minutos_max < minutos_min:
        # Traductores: validación de mensajes programados (error).
        return _("El intervalo máximo no puede ser menor que el mínimo."), ""
    aviso = ""
    # Se avisan las formas habituales de URL; YouTube puede bloquearlas.
    if _URL_RE.search(texto):
        # Traductores: aviso de la ventana de mensajes programados cuando el texto trae un enlace.
        aviso = _("YouTube suele bloquear los enlaces en el chat del directo. "
                  "Escribe el nombre de usuario en vez del enlace completo.")
    return "", aviso


def calcular_proximo(minutos_min: int, minutos_max: int,
                     ahora: float, aleatorio) -> float:
    """Calcula el instante del próximo envío usando un azar inyectado."""
    if minutos_min == minutos_max:
        return ahora + minutos_min * 60
    return ahora + aleatorio(minutos_min * 60, minutos_max * 60)


def iniciar_reloj(mensajes: list[dict], ahora: float, aleatorio) -> None:
    """Da cuerda al reloj de los mensajes activos de esta sesión."""
    for mensaje in mensajes:
        if mensaje.get("activo", False):
            mensaje["proximo"] = calcular_proximo(
                mensaje.get("minutos_min", 10),
                mensaje.get("minutos_max", mensaje.get("minutos_min", 10)),
                ahora, aleatorio)


def elegir_envio(mensajes: list[dict], ahora: float,
                 ultimo_envio: float | None) -> dict | None:
    """Devuelve el mensaje activo vencido más antiguo que puede enviarse."""
    if ultimo_envio is not None and ahora - ultimo_envio < SEGUNDOS_ENTRE_ENVIOS:
        return None
    vencidos = [
        mensaje for mensaje in mensajes
        if mensaje.get("activo", False) and mensaje.get("proximo", float("inf")) <= ahora
    ]
    return min(vencidos, key=lambda mensaje: mensaje["proximo"]) if vencidos else None


def puede_enviar(activo: bool, conectado: bool, es_tiktok: bool,
                 live_chat_id: str, propio: bool, sesion: bool) -> bool:
    """Dice si los mensajes automáticos pueden mandarse ahora mismo.

    Solo al chat de un directo propio de YouTube con sesión iniciada: en
    un directo ajeno la app lee pero no escribe.
    """
    return bool(activo and conectado and not es_tiktok and live_chat_id
                and propio and sesion)


def describir_mensaje(mensaje: dict) -> str:
    """Devuelve la línea accesible que representa un mensaje."""
    if mensaje.get("activo", False):
        # Traductores: estado en la lista de mensajes programados.
        estado = _("Activo")
    else:
        # Traductores: estado en la lista de mensajes programados.
        estado = _("Pausado")
    minimo = mensaje.get("minutos_min", 10)
    maximo = mensaje.get("minutos_max", minimo)
    if minimo == maximo and minimo == 1:
        # Traductores: intervalo en la lista de mensajes programados. {minimo} es cada cuántos minutos.
        intervalo = _("cada {minimo} minuto").format(minimo=minimo)
    elif minimo == maximo:
        # Traductores: intervalo en la lista de mensajes programados. {minimo} es cada cuántos minutos.
        intervalo = _("cada {minimo} minutos").format(minimo=minimo)
    else:
        # Traductores: intervalo en la lista de mensajes programados. {minimo} es el mínimo y {maximo} el máximo.
        intervalo = _("entre {minimo} y {maximo} minutos").format(minimo=minimo, maximo=maximo)
    texto = str(mensaje.get("texto", ""))
    if len(texto) > 60:
        texto = texto[:57] + "..."
    # Traductores: línea de la lista de mensajes programados. {estado} es activo o pausado, {intervalo} la frecuencia y {texto} el contenido.
    return _("{estado}, {intervalo}: {texto}").format(estado=estado, intervalo=intervalo, texto=texto)


def describir_proximo(mensajes: list[dict], ahora: float) -> str:
    """Describe cuándo vence el siguiente mensaje activo."""
    activos = [
        mensaje for mensaje in mensajes
        if mensaje.get("activo", False) and "proximo" in mensaje
    ]
    if not activos:
        return ""
    # proximo <= 0 es el valor recién cargado del disco (aún sin cuerda): no
    # es «en menos de un minuto», es que todavía no se ha programado.
    con_hora = [mensaje["proximo"] for mensaje in activos if mensaje["proximo"] > 0]
    if not con_hora:
        # Traductores: estado F2 de los mensajes automáticos cuando aún no hay hora.
        return _("Próximo mensaje automático: pendiente de programar")
    restante = min(con_hora) - ahora
    if restante < 60:
        # Traductores: estado F2 de los mensajes automáticos cuando falta menos de un minuto.
        return _("Próximo mensaje automático en menos de un minuto")
    minutos = math.ceil(restante / 60)
    # Traductores: estado F2 de los mensajes automáticos. {minutos} es en cuántos minutos se envía.
    return ngettext("Próximo mensaje automático en {minutos} minuto",
                    "Próximo mensaje automático en {minutos} minutos",
                    minutos).format(minutos=minutos)


def _a_bool(valor) -> bool:
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "1", "yes", "si", "sí", "on")
    return bool(valor)


def _normalizar_mensaje(mensaje: dict) -> dict:
    resultado = dict(VALORES_POR_DEFECTO)
    resultado.update(mensaje)
    # Un JSON editado a mano puede traer "10" o "true": se fuerzan los tipos
    # de los campos conocidos para que el temporizador de la GUI no reviente
    # con un TypeError al comparar u operar con ellos.
    for clave, defecto in VALORES_POR_DEFECTO.items():
        valor = resultado[clave]
        try:
            if isinstance(defecto, bool):
                resultado[clave] = _a_bool(valor)
            elif isinstance(defecto, int):
                resultado[clave] = int(float(valor))   # admite "15" y "15.0"
            elif isinstance(defecto, float):
                resultado[clave] = float(valor)
            else:
                resultado[clave] = "" if valor is None else str(valor)
        except (TypeError, ValueError):
            resultado[clave] = defecto
    return resultado


def cargar(ruta) -> list[dict]:
    """Carga mensajes y devuelve una lista segura aunque el archivo esté roto."""
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, list):
            return []
        return [_normalizar_mensaje(mensaje) for mensaje in datos
                if isinstance(mensaje, dict)]
    except Exception:
        return []


def guardar(ruta, mensajes: list[dict]) -> None:
    """Guarda mensajes mediante un temporal para conservar el archivo anterior."""
    archivos.escribir_json_atomico(ruta, mensajes, indent=2)


class ProgramadorMensajes:
    """Estado de los mensajes automáticos de la ventana principal."""

    def __init__(self, mensajes: list[dict]):
        self.mensajes = mensajes
        self.reloj_iniciado = False
        self.ultimo_envio = None
        self.en_curso = False

    def recargar(self, mensajes):
        self.mensajes = mensajes
        self.reloj_iniciado = False

    def detener_reloj(self):
        self.reloj_iniciado = False

    def iniciar_reloj_si_falta(self, ahora, aleatorio):
        if self.reloj_iniciado:
            return
        iniciar_reloj(self.mensajes, ahora, aleatorio)
        self.reloj_iniciado = True

    def siguiente(self, ahora) -> dict | None:
        if self.en_curso:
            return None
        return elegir_envio(self.mensajes, ahora, self.ultimo_envio)

    def empezar_envio(self):
        self.en_curso = True

    def envio_hecho(self, mensaje, ahora, aleatorio):
        self.en_curso = False
        mensaje["proximo"] = calcular_proximo(
            mensaje.get("minutos_min", 10),
            mensaje.get("minutos_max", mensaje.get("minutos_min", 10)),
            ahora, aleatorio)
        self.ultimo_envio = ahora

    def envio_fallido(self):
        self.en_curso = False
