"""Cuota de la API de YouTube que gasta la app por día del Pacífico.

Su única razón para cambiar es cuánto consume la app de las 10.000 unidades
diarias del cliente de Google compartido. La API no informa cuánto queda, así
que se suma el costo oficial de cada petición en el momento de ejecutarla.

El conteo se engancha en un solo lugar: googleapiclient construye cada
petición con la clase que recibe `build(..., requestBuilder=...)`.
"""

from __future__ import annotations

import datetime as dt
import json
import threading

from guyrapu.core import archivos, diagnostico, paths

logger = diagnostico.obtener_logger(__name__)

# Costos oficiales por «recurso.método», en unidades por petición.
# Fuente: developers.google.com/youtube/v3/determine_quota_cost,
# «Last updated 2026-10-15», medido el 31/10/2026.
FECHA_COSTOS = "15/10/2026"

COSTOS: dict[str, int] = {
    "activities.list": 1,
    "channels.list": 1,
    "channels.update": 50,
    "comments.list": 1,
    "comments.insert": 50,
    "comments.update": 50,
    "comments.setModerationStatus": 50,
    "comments.delete": 50,
    "commentThreads.list": 1,
    "commentThreads.insert": 50,
    "commentThreads.update": 50,
    "liveBroadcasts.bind": 1,
    "liveBroadcasts.delete": 1,
    "liveBroadcasts.insert": 1,
    "liveBroadcasts.insertCuepoint": 1,
    "liveBroadcasts.list": 1,
    "liveBroadcasts.transition": 1,
    "liveBroadcasts.update": 1,
    "liveChatBans.delete": 200,
    "liveChatBans.insert": 200,
    "liveChatMessages.delete": 20,
    "liveChatMessages.insert": 20,
    "liveChatMessages.list": 5,
    "liveChatMessages.transition": 20,
    "liveChatModerators.delete": 200,
    "liveChatModerators.insert": 200,
    "liveChatModerators.list": 50,
    "liveStreams.delete": 1,
    "liveStreams.insert": 1,
    "liveStreams.list": 1,
    "liveStreams.update": 1,
    "playlistItems.list": 1,
    "playlistItems.insert": 50,
    "playlistItems.update": 50,
    "playlistItems.delete": 50,
    "playlists.list": 1,
    "playlists.insert": 50,
    "playlists.update": 50,
    "playlists.delete": 50,
    "search.list": 1,
    "superChatEvents.list": 1,
    "thumbnails.set": 50,
    "videoCategories.list": 1,
    "videos.list": 1,
    "videos.update": 50,
    "videos.rate": 50,
    "videos.getRating": 1,
}

# Las llamadas salen de varios hilos del cliente de YouTube.
_LOCK = threading.Lock()

_CLASE_CONTADORA = None


def costo(metodo: str) -> int:
    """Unidades que cuesta una petición; toda petición válida o inválida
    cuesta al menos 1 según la página de Google."""
    nombre = (metodo or "").removeprefix("youtube.")
    return COSTOS.get(nombre, 1)


def dia_pacifico(ahora_utc: dt.datetime) -> dt.date:
    """Día de Los Ángeles para un instante UTC.

    Regla de horario de verano de EE. UU.: UTC-7 desde el segundo domingo de
    marzo a las 2:00 locales hasta el primer domingo de noviembre a las 2:00
    locales; el resto del año, UTC-8. No se usa zoneinfo porque en Windows sin
    el paquete tzdata no conoce «America/Los_Angeles».
    """
    if ahora_utc.tzinfo is None:
        ahora_utc = ahora_utc.replace(tzinfo=dt.timezone.utc)
    utc = ahora_utc.astimezone(dt.timezone.utc)
    anio = utc.year
    comienzo = dt.datetime(anio, 3, _domingo(anio, 3, 2), 10, 0,
                           tzinfo=dt.timezone.utc)
    fin = dt.datetime(anio, 11, _domingo(anio, 11, 1), 9, 0,
                      tzinfo=dt.timezone.utc)
    horas = 7 if comienzo <= utc < fin else 8
    return (utc - dt.timedelta(hours=horas)).date()


def _domingo(anio: int, mes: int, orden: int) -> int:
    """Día del mes del enésimo domingo (orden 1 es el primero)."""
    primero = dt.date(anio, mes, 1)
    return 1 + (6 - primero.weekday()) % 7 + 7 * (orden - 1)


def _leer_hoy(ahora_utc=None) -> dict:
    hoy = dia_pacifico(ahora_utc or dt.datetime.now(dt.timezone.utc)).isoformat()
    datos = archivos.leer_json(paths.cuota_youtube(), {})
    if not isinstance(datos, dict) or datos.get("dia") != hoy:
        return {"dia": hoy, "unidades": 0, "por_metodo": {}}
    try:
        unidades = int(datos.get("unidades", 0))
    except (TypeError, ValueError):
        unidades = 0
    por_metodo = datos.get("por_metodo")
    if not isinstance(por_metodo, dict):
        por_metodo = {}
    return {"dia": hoy, "unidades": unidades, "por_metodo": por_metodo}


def _registrar(metodo: str, ahora_utc=None) -> None:
    """Suma el costo de una petición al contador del día y lo guarda."""
    nombre = (metodo or "").removeprefix("youtube.")
    unidades_nuevas = costo(nombre)
    with _LOCK:
        datos = _leer_hoy(ahora_utc)
        datos["unidades"] += unidades_nuevas
        datos["por_metodo"][nombre] = (
            datos["por_metodo"].get(nombre, 0) + unidades_nuevas)
        try:
            archivos.escribir_texto_atomico(
                paths.cuota_youtube(),
                json.dumps(datos, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("No se pudo guardar la cuota de YouTube: %s", exc)


def usadas_hoy(ahora_utc=None) -> int:
    """Unidades gastadas hoy en este equipo, según el día del Pacífico."""
    with _LOCK:
        return _leer_hoy(ahora_utc)["unidades"]


def clase_contadora():
    """Subclase de HttpRequest que suma el costo antes de ejecutar.

    El import es perezoso porque la app funciona sin googleapiclient instalado.
    """
    global _CLASE_CONTADORA
    if _CLASE_CONTADORA is None:
        from googleapiclient.http import HttpRequest

        class _Contadora(HttpRequest):
            def execute(self, http=None, num_retries=0):
                _registrar(self.methodId)
                return super().execute(http=http, num_retries=num_retries)

        _CLASE_CONTADORA = _Contadora
    return _CLASE_CONTADORA


def construir(**kwargs):
    """Construye el servicio de YouTube con el conteo de cuota enganchado."""
    from googleapiclient.discovery import build
    return build("youtube", "v3", requestBuilder=clase_contadora(), **kwargs)
