"""Decisiones del botón directo de transmisión, sin interfaz.

Vive aparte de wx para poder probarse sin ventana: si el botón se ve, qué
dice y en qué orden se prepara OBS antes de transmitir. Quien llama traduce
los fallos con `obs_cliente.mensaje_de_fallo_obs`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class Preparacion:
    """Resultado de `preparar`: o ya se transmite, o hay revisión."""

    ya_transmitiendo: bool
    revision: Any = None


def es_directo_propio(es_tiktok, usuario_sesion, usuario_guardado,
                      conectado_por_transmision) -> bool:
    """¿El contenido conectado es el directo del propio usuario?

    Vale si la conexión la pidió la transmisión, o si es TikTok y el
    usuario de la sesión coincide con el guardado (sin importar
    mayúsculas ni la arroba inicial). En YouTube solo cuenta la
    conexión pedida: reconocer el canal propio queda para cuando
    exista transmitir a YouTube desde YTChat.
    """
    if conectado_por_transmision:
        return True
    if not es_tiktok:
        return False
    from ytchat.capture import tiktok_vivo
    sesion = tiktok_vivo.usuario_tiktok(usuario_sesion or "")
    guardado = tiktok_vivo.usuario_tiktok(usuario_guardado or "")
    return bool(sesion) and sesion.lower() == guardado.lower()


def boton_visible(conectado, conectando, propio, transmitiendo) -> bool:
    """¿El botón directo se muestra?

    En la pantalla de inicio (sin conexión ni conexión en curso) o en el
    directo propio. Estar transmitiendo no lo muestra por sí solo: en el
    directo de otro no aparece, y para finalizar se vuelve al inicio
    con Desconectar.
    """
    _sin_uso = transmitiendo
    return (not conectado and not conectando) or bool(propio)


def etiqueta(transmitiendo, deteniendo=False):
    """Etiqueta con atajo y nombre accesible según el estado del directo.

    Mientras OBS confirma la parada el botón sigue visible y habilitado:
    solo cambia lo que dice, para que el nombre accesible avise que se
    espera a OBS.
    """
    if deteniendo:
        return ("Deteniendo el directo",
                "Deteniendo el directo, esperando a OBS")
    if transmitiendo:
        return ("&Finalizar directo", "Finalizar directo")
    return ("Transm&itir en directo", "Transmitir en directo")


def preparar(gestor, destino: str, asegurar: Callable, al_anunciar: Callable,
             parada=None) -> Preparacion:
    """Asegura OBS, conecta y deja el destino listo para confirmar.

    Devuelve `Preparacion(ya_transmitiendo=True)` si OBS ya emite (sin
    preparar ni revisar). Si no, prepara el destino (siempre, que es
    idempotente) y devuelve la revisión. Cierra el gestor en `finally`;
    las excepciones salen tal cual para que las traduzca quien llama.
    """
    try:
        asegurar(gestor.conectar, al_anunciar=al_anunciar, parada=parada)
        gestor.conectar()
        if bool(gestor.estado_transmision().get("outputActive", False)):
            return Preparacion(ya_transmitiendo=True)
        if gestor.perfil_actual() != destino:
            al_anunciar(f"Preparando OBS para {destino}.")
        resultado = gestor.preparar_destino(destino)
        if (resultado or {}).get("perfil_creado"):
            al_anunciar(f"Se creó en OBS el perfil {destino}.")
        revision = gestor.revisar(destino)
        return Preparacion(ya_transmitiendo=False, revision=revision)
    finally:
        try:
            gestor.cerrar()
        except Exception:
            pass


class FalloCierreYoutube(Exception):
    """OBS se detuvo pero YouTube no confirmó el fin del directo."""


def finalizar(gestor, finalizar_youtube=None) -> None:
    """Detiene el directo si OBS transmite, para finalizar sin supervisor.

    Conecta, detiene solo con `outputActive` y cierra en `finally`. Con
    `finalizar_youtube` y perfil de OBS en "YouTube" (leído antes de
    detener), lo llama después de detener OBS para cerrar el directo en
    YouTube; si eso falla, sale como `FalloCierreYoutube`.
    """
    try:
        gestor.conectar()
        perfil = None
        if finalizar_youtube is not None:
            try:
                perfil = gestor.perfil_actual()
            except Exception:
                perfil = None
        if bool(gestor.estado_transmision().get("outputActive", False)):
            gestor.detener_transmision()
        if finalizar_youtube is not None and perfil == "YouTube":
            try:
                finalizar_youtube()
            except FalloCierreYoutube:
                raise
            except Exception as exc:
                raise FalloCierreYoutube(
                    "YouTube no confirmó el fin del directo. "
                    "Finalízalo en YouTube Studio.") from exc
    finally:
        try:
            gestor.cerrar()
        except Exception:
            pass
