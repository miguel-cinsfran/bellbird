"""Fines de directo pedidos a YouTube y todavía sin confirmar.

Cuando OBS deja de transmitir, Bellbird pide a YouTube que finalice el directo.
Si la red falla, el pedido se anota aquí con su fecha y se reintenta: en un
hilo mientras la app siga abierta, y al volver a abrirla si se cerró antes de
la confirmación. La E/S va aparte de la lógica para poder probar el reintento
con un reloj y un dormir falsos.
"""

from __future__ import annotations

from datetime import datetime

from bellbird.core import archivos
from bellbird.core import diagnostico

logger = diagnostico.obtener_logger(__name__)

# Cada cuánto se reintenta el fin del directo y cuándo se deja de intentar.
INTERVALO_REINTENTO = 15.0
LIMITE_REINTENTO = 600.0


def leer(ruta) -> list[dict]:
    """Lista de pendientes del JSON.

    Un archivo que falta, está roto o no es una lista se lee como lista
    vacía, sin lanzar: no hay que perder la revisión por un archivo ajeno.
    Se descartan las entradas sin id.
    """
    datos = archivos.leer_json(ruta, [])
    if not isinstance(datos, list):
        return []
    return [entrada for entrada in datos
            if isinstance(entrada, dict) and entrada.get("id")]


def anotar(ruta, id_video, ahora=None) -> list[dict]:
    """Anota el id con la fecha en que se pidió, sin duplicar.

    Si el id ya está, devuelve la lista tal cual sin reescribir. Con un id
    vacío no toca el archivo.
    """
    id_video = (id_video or "").strip()
    pendientes = leer(ruta)
    if not id_video or any(e["id"] == id_video for e in pendientes):
        return pendientes
    momento = ahora or datetime.now()
    pendientes.append({"id": id_video,
                       "fecha": momento.isoformat(timespec="seconds")})
    archivos.escribir_json_atomico(ruta, pendientes, indent=1)
    return pendientes


def quitar(ruta, id_video) -> list[dict]:
    """Quita el id del archivo y devuelve la lista restante.

    Solo reescribe si el id estaba: no crea un archivo por una baja que no
    cambió nada.
    """
    id_video = (id_video or "").strip()
    original = leer(ruta)
    restantes = [e for e in original if e["id"] != id_video]
    if len(restantes) != len(original):
        archivos.escribir_json_atomico(ruta, restantes, indent=1)
    return restantes


def reintentar(intento, dormir, reloj, intervalo=INTERVALO_REINTENTO,
               limite=LIMITE_REINTENTO) -> bool:
    """Reintenta `intento()` cada `intervalo` hasta lograrlo o rendirse.

    El plazo corre desde la primera llamada, que es el fallo que disparó el
    reintento. `intento` lanza si el fin todavía no se confirmó. Cada fallo
    se registra. Devuelve True si algún intento salió bien.
    """
    inicio = reloj()
    while True:
        dormir(intervalo)
        try:
            intento()
        except Exception as error:
            logger.info("reintento del fin del directo falló: %s", error)
        else:
            return True
        if reloj() - inicio >= limite:
            return False
