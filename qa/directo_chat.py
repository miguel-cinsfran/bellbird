"""Pasos de escritura y corte del banco del directo real.

Lo puro (juicios sobre textos ya leídos) vive acá con pruebas en
`tests/test_qa_directo_chat.py`. Lo impuro (UI Automation por patrón de
valor, archivos de pedido del corte y API de YouTube) también vive acá,
pero recibe lo que necesita como argumentos y no importa nada de
`directo_real.py`, para no armar un import circular.

El corte lo hace la tarea BellbirdCorteRed, que el advisor lanza antes
del banco: acá solo se escribe el pedido con los segundos y se espera el
`.hecho`. Durante el corte todo Python queda sin red, así que entre el
pedido y la reconexión no se llama a la API: solo se leen archivos.
"""

from __future__ import annotations

import os
import time

# Tope del corte, igual que en `herramientas/corte_red.ps1`.
TOPE_CORTE = 30
# Archivos por los que el banco habla con la tarea del corte.
RUTA_PEDIDO = r"C:\Users\Public\bellbird_corte_red.pedido"
RUTA_HECHO = r"C:\Users\Public\bellbird_corte_red.hecho"
# Nombres que da UI Automation, salen de las etiquetas y no del name= de wx.
NOMBRE_CUADRO = "Mensaje:"
NOMBRE_BOTON = "Enviar"
# Anuncios de la app, copiados del código.
ANUNCIO_ENVIADO = "Mensaje enviado al chat"
AVISO_PERDIDA = "Se perdió la conexión con el chat"
AVISO_RECONEXION = "Chat reconectado."
FINALES_PROHIBIDOS = (
    "El directo terminó. Chat desconectado.",
    "Se agotaron los",
    "La conexión se cerró y la reconexión está desactivada.",
)


def limitar_corte(segundos) -> int:
    """Segundos de corte dentro del tope: 0 se queda en 0."""
    try:
        valor = int(segundos)
    except (TypeError, ValueError):
        return 0
    return max(0, min(TOPE_CORTE, valor))


def leer_hecho(texto) -> tuple[bool, str]:
    """Si el `.hecho` de la tarea cuenta un corte bien hecho."""
    limpio = (texto or "").lstrip("﻿").strip()
    if not limpio:
        return (False, "la tarea BellbirdCorteRed no respondió: "
                       "lánzala antes del banco")
    if limpio.lower().startswith("error"):
        motivo = limpio[5:].strip() or limpio
        return (False, motivo)
    bajo = limpio.lower()
    if "cortada" in bajo and "reconecta" in bajo:
        return (True, limpio)
    return (False, f"respuesta inesperada de la tarea: «{limpio}»")


def mensaje_en_respuesta(respuesta, texto) -> bool:
    """Si el texto está en la respuesta de `liveChatMessages().list`."""
    if not texto:
        return False
    items = ((respuesta or {}).get("items", [])) or []
    for item in items:
        snippet = (item or {}).get("snippet") or {}
        if texto in (snippet.get("displayMessage") or ""):
            return True
        detalles = snippet.get("textMessageDetails") or {}
        if texto in (detalles.get("messageText") or ""):
            return True
    return False


def repetidos(lineas_chat, comentarios) -> list[str]:
    """Comentarios que aparecen más de una vez en las líneas del chat."""
    lineas = list(lineas_chat or [])
    dobles = []
    for comentario in comentarios or ():
        if not comentario:
            continue
        veces = sum(1 for linea in lineas
                    if comentario in (linea or ""))
        if veces > 1:
            dobles.append(comentario)
    return dobles


def estado_reconexion(anuncios) -> tuple[bool, str]:
    """Juicio del paso de reconexión sobre los anuncios ya recortados."""
    base = (anuncios or "").lower()
    perdidas = base.count(AVISO_PERDIDA.lower())
    etiqueta = "aviso de pérdida" if perdidas == 1 else "avisos de pérdida"
    for final in FINALES_PROHIBIDOS:
        if final.lower() in base:
            return (False, f"«{final}» tras {perdidas} {etiqueta}: "
                           f"el chat se cerró")
    if not perdidas:
        return (False, "0 avisos de pérdida: sin "
                       "«Se perdió la conexión con el chat»")
    primera = base.find(AVISO_PERDIDA.lower())
    if base.find(AVISO_RECONEXION.lower(), primera) < 0:
        return (False, f"{perdidas} {etiqueta} pero sin "
                       f"«Chat reconectado.» después")
    return (True, f"«Chat reconectado.» tras {perdidas} {etiqueta}")


def poner_texto(cuadro, texto) -> None:
    """Escribe en el cuadro por el patrón de valor de UIA, sin teclas."""
    metodos = [getattr(cuadro, nombre, None)
               for nombre in ("set_edit_text", "set_value")]
    utiles = [metodo for metodo in metodos if callable(metodo)]
    if not utiles:
        raise RuntimeError("el cuadro no expone el patrón de valor")
    error = ""
    for metodo in utiles:
        try:
            metodo(texto)
            return
        except Exception as exc:
            error = str(exc)
    raise RuntimeError(f"no se pudo escribir en el cuadro ({error})")


def escribir_desde_app(principal, texto, ruta_anuncios, marca,
                       leer_anuncios, esperar_anuncio, control,
                       leer_respuesta) -> tuple[bool, str]:
    """Escribe el texto desde la app y lo busca después por la API."""
    try:
        poner_texto(control(principal, NOMBRE_CUADRO, "Edit"), texto)
    except Exception as exc:
        return (False, f"no se pudo escribir el mensaje: {exc}")
    try:
        control(principal, NOMBRE_BOTON, "Button").invoke()
    except Exception as exc:
        return (False, f"no se pudo pulsar «{NOMBRE_BOTON}»: {exc}")
    if esperar_anuncio(ruta_anuncios, (ANUNCIO_ENVIADO,), 30,
                       marca) is None:
        return (False, f"sin «{ANUNCIO_ENVIADO}» en 30 s")
    fin = time.time() + 30
    ultimo_error = ""
    while True:
        try:
            if mensaje_en_respuesta(leer_respuesta(), texto):
                return (True, f"«{texto}» llegó al chat")
        except Exception as exc:
            ultimo_error = str(exc)
        if time.time() >= fin:
            detalle = f"«{texto}» no volvió por la API en 30 s"
            if ultimo_error:
                detalle += f" ({ultimo_error})"
            return (False, detalle)
        time.sleep(3)


def paso_corte(segundos, ruta_anuncios, leer_anuncios,
               ruta_pedido=RUTA_PEDIDO,
               ruta_hecho=RUTA_HECHO) -> tuple[bool, str, int]:
    """Pide el corte a la tarea y espera su `.hecho`.

    Devuelve (bien, detalle, marca): la marca es el largo de los
    anuncios antes del pedido, para recortar desde ahí la reconexión.
    """
    marca = len(leer_anuncios(ruta_anuncios))
    try:
        os.remove(ruta_hecho)
    except OSError:
        pass
    try:
        with open(ruta_pedido, "w", encoding="utf-8") as f:
            f.write(str(int(segundos)))
    except OSError as exc:
        return (False, f"no se pudo pedir el corte: {exc}", marca)
    fin = time.time() + int(segundos) + 30
    while True:
        try:
            with open(ruta_hecho, encoding="utf-8") as f:
                contenido = f.read()
        except OSError:
            contenido = ""
        if (contenido or "").strip():
            bien, detalle = leer_hecho(contenido)
            return (bien, detalle, marca)
        if time.time() >= fin:
            bien, detalle = leer_hecho("")
            return (bien, detalle, marca)
        time.sleep(1)


def esperar_reconexion(ruta_anuncios, marca, segundos,
                       leer_anuncios) -> tuple[bool, str]:
    """Espera la pérdida y la reconexión en los anuncios desde la marca."""
    fin = time.time() + int(segundos) + 90
    ultimo = ""
    while True:
        texto = leer_anuncios(ruta_anuncios)[marca:]
        bien, detalle = estado_reconexion(texto)
        if bien:
            return (True, detalle)
        bajo = (texto or "").lower()
        if any(final.lower() in bajo for final in FINALES_PROHIBIDOS):
            return (False, detalle)
        ultimo = detalle
        if time.time() >= fin:
            return (False, f"{ultimo} "
                           f"(sin reconexión en {int(segundos) + 90} s)")
        time.sleep(1)


def leer_despues(cliente, id_chat, ruta_chat, texto, comentario_faltante,
                 detalle_lista) -> tuple[bool, str]:
    """Comenta por la API y lo busca en el archivo del chat de la app."""
    try:
        cliente.enviar_mensaje_live(id_chat, texto)
    except Exception as exc:
        return (False, f"no se pudo comentar por la API: {exc}")
    try:
        faltante, leidos = comentario_faltante(ruta_chat, [texto], 30)
    except Exception as exc:
        return (False, f"leyendo el chat de la app: {exc}")
    if faltante is None:
        return (True, f"«{texto}» está en la lista del chat")
    return (False, f"«{texto}» no apareció en 30 s "
                   f"({detalle_lista(leidos)})")


def comprobar_sin_repetidos(ruta_chat, comentarios) -> tuple[bool, str]:
    """Cada comentario esperado aparece una sola vez en el chat."""
    try:
        with open(ruta_chat, encoding="utf-8") as f:
            lineas = f.read().splitlines()
    except OSError as exc:
        return (False, f"no se pudo leer el archivo del chat: {exc}")
    dobles = repetidos(lineas, comentarios)
    if dobles:
        return (False, f"«{dobles[0]}» aparece más de una vez tras el corte")
    return (True, f"{len(list(comentarios or ()))} comentarios sin repetir")
