"""Emisión de YouTube: cuerpo del directo y paso que lo deja listo.

Puro salvo lo inyectado: el cliente de YouTube y el de OBS entran por
parámetro, así se prueba con dobles sin tocar la API real.
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from ytchat.core import diagnostico
from ytchat.core.idioma import N_, _
from ytchat.obs import obs_cliente
from ytchat.obs import obs_destinos
from ytchat.youtube import youtube_api

logger = diagnostico.obtener_logger(__name__)

PRIVACIDADES = ("public", "unlisted", "private")
# Traductores: privacidad del directo; una sola palabra.
ETIQUETAS_PRIVACIDAD = {"public": N_("Público"), "unlisted": N_("No listado"),
                        "private": N_("Privado")}
PRIVACIDAD_INICIAL = "unlisted"

# Latencia del directo: valores que acepta `contentDetails.latencyPreference`.
LATENCIAS = ("normal", "low", "ultraLow")
# Traductores: latencia del directo; una sola palabra.
ETIQUETAS_LATENCIA = {"normal": N_("Normal"), "low": N_("Baja"),
                      "ultraLow": N_("Ultrabaja")}
LATENCIA_INICIAL = "normal"

# Categorías de YouTube ofrecidas en el diálogo: (id de la API, texto).
# Traductores: categoría de YouTube; una sola palabra.
CATEGORIAS = (
    ("", N_("Sin cambiar")),
    ("20", N_("Videojuegos")),
    ("22", N_("Personas y blogs")),
    # Traductores: categoría de YouTube; una sola palabra.
    ("24", N_("Entretenimiento")),
    ("10", N_("Música")),
    ("27", N_("Educación")),
    ("28", N_("Ciencia y tecnología")),
    # Traductores: categoría de YouTube; una sola palabra.
    ("17", N_("Deportes")),
    ("23", N_("Comedia")),
    ("25", N_("Noticias y política")),
    ("26", N_("Consejos y estilo")),
)


# Límite de `snippet.tags`: la suma de los caracteres de todas las etiquetas.
LIMITE_ETIQUETAS = 500


def chat_legible(privacidad) -> bool:
    """Dice si el chat se puede leer por la vía pública con esa privacidad."""
    return privacidad != "private"


class EmisionError(Exception):
    """Fallo listo para anunciar tal cual."""


def cuerpo_emision(titulo, descripcion, privacidad, inicio_iso,
                   latencia="normal", ninos=False, dvr=True) -> dict:
    """Arma el cuerpo de liveBroadcasts.insert para el directo.

    Los tres últimos campos son opcionales: latencia (normal, low o
    ultraLow), hecho para niños y permitir rebobinar. Una latencia
    desconocida cae a normal, como los llamados de hoy.
    """
    titulo = (titulo or "").strip()
    if not titulo:
        raise EmisionError(_("Falta el título del directo."))
    titulo = titulo[:100]
    descripcion = (descripcion or "").strip()[:5000]
    if privacidad not in PRIVACIDADES:
        raise ValueError(_("Privacidad inválida: {privacidad}.").format(
            privacidad=privacidad))
    if latencia not in LATENCIAS:
        latencia = LATENCIA_INICIAL
    return {"snippet": {"title": titulo, "description": descripcion,
                        "scheduledStartTime": inicio_iso},
            "status": {"privacyStatus": privacidad,
                       "selfDeclaredMadeForKids": bool(ninos)},
            "contentDetails": {"enableAutoStart": True,
                                "enableAutoStop": False,
                                "latencyPreference": latencia,
                                "enableDvr": bool(dvr)}}


def resultado_directo(titulo, descripcion, privacidad,
                      latencia=LATENCIA_INICIAL, ninos=False, dvr=True,
                      categoria="", etiquetas="", miniatura="", lista="",
                      lista_titulo="") -> dict:
    """Valida los valores de la ventana y arma el dict del directo.

    Pura y sin ventanas: la usan el diálogo y las pruebas. El título
    vacío anuncia «Falta el título del directo.» vía excepción, igual
    que `cuerpo_emision`. La lista de etiquetas la arma
    `etiquetas_de_texto` a partir del texto separado por comas.
    """
    titulo = (titulo or "").strip()
    if not titulo:
        raise EmisionError(_("Falta el título del directo."))
    if privacidad not in PRIVACIDADES:
        privacidad = PRIVACIDAD_INICIAL
    if latencia not in LATENCIAS:
        latencia = LATENCIA_INICIAL
    if categoria not in {identificador for identificador, _texto in CATEGORIAS}:
        categoria = ""
    lista = (lista or "").strip()
    lista_titulo = (lista_titulo or "").strip() if lista else ""
    return {"titulo": titulo[:100], "descripcion": descripcion or "",
            "privacidad": privacidad, "latencia": latencia,
            "ninos": bool(ninos), "dvr": bool(dvr), "categoria": categoria,
            "etiquetas": etiquetas_de_texto(etiquetas),
            "miniatura": (miniatura or "").strip(),
            "lista": lista, "lista_titulo": lista_titulo}


def etiquetas_de_texto(texto) -> list[str]:
    """Separa por comas, limpia y descarta repetidas sin pasar de 500.

    Los espacios de los bordes y los huecos vacíos no cuentan. Las
    repetidas se comparan sin distinguir mayúsculas y se conserva la
    primera. La lista se corta en cuanto la suma de caracteres de las
    etiquetas pasaría el límite de `snippet.tags`.
    """
    vistas: set[str] = set()
    salida: list[str] = []
    total = 0
    for trozo in (texto or "").split(","):
        etiqueta = trozo.strip()
        if not etiqueta:
            continue
        clave = etiqueta.lower()
        if clave in vistas:
            continue
        if total + len(etiqueta) > LIMITE_ETIQUETAS:
            break
        vistas.add(clave)
        salida.append(etiqueta)
        total += len(etiqueta)
    return salida


def error_de_miniatura(ruta, tamanio=os.path.getsize) -> str | None:
    """None si la miniatura sirve; si no, la frase del defecto.

    Exige un archivo existente con extensión JPG o PNG de 2 MB o menos.
    `tamanio` se inyecta en las pruebas para no tocar el disco.
    """
    ruta = (ruta or "").strip()
    if not ruta:
        return _("No se encontró el archivo de la miniatura.")
    if os.path.splitext(ruta)[1].lower() not in (".jpg", ".jpeg", ".png"):
        return _("La miniatura tiene que ser JPG o PNG.")
    try:
        bytes_ = tamanio(ruta)
    except OSError:
        return _("No se encontró el archivo de la miniatura.")
    if bytes_ > 2 * 1024 * 1024:
        return _("La miniatura pasa de 2 MB.")
    return None


def titulo_por_defecto(ahora: datetime) -> str:
    """Título con la fecha del día para el directo."""
    return _("Directo del {fecha}").format(fecha=ahora.strftime("%d/%m/%Y"))


def url_video(id_video: str) -> str:
    """URL pública del vídeo a partir de su id."""
    return "https://www.youtube.com/watch?v=" + id_video


def opciones_lista(listas, id_recordado, titulo_recordado
                   ) -> tuple[list[tuple[str, str]], int]:
    """Opciones del selector de listas y el índice a seleccionar.

    La primera opción siempre es («», «Ninguna»). Con `listas` en None
    (todavía sin cargar) solo van «Ninguna» y, si hay id recordado, su
    título. Con las listas cargadas van todas, y se elige la del id
    recordado si está o «Ninguna» (índice 0) si no. Sin id recordado el
    índice es siempre 0.
    """
    # Traductores: primera opción de la lista; ninguna elegida.
    opciones: list[tuple[str, str]] = [("", _("Ninguna"))]
    id_recordado = (id_recordado or "").strip()
    if listas is None:
        if id_recordado:
            titulo = (titulo_recordado or "").strip() or _("Lista guardada")
            opciones.append((id_recordado, titulo))
            return opciones, 1
        return opciones, 0
    for id_lista, titulo in listas:
        opciones.append((id_lista, titulo))
    if not id_recordado:
        return opciones, 0
    for indice, (id_lista, _titulo) in enumerate(opciones):
        if id_lista == id_recordado:
            return opciones, indice
    return opciones, 0


def cargador_listas(cliente_yt, guardar_token=None):
    """Devuelve una función sin argumentos que carga las listas del canal.

    Guarda el token renovado si hay uno, también cuando la consulta falla,
    igual que `_guardar_si_hay_nuevo` de `ganchos_youtube`.
    """

    def cargar():
        try:
            return cliente_yt.listas_del_canal()
        finally:
            if guardar_token is not None:
                try:
                    nuevo = cliente_yt.token_actualizado()
                except Exception:
                    nuevo = None
                if nuevo:
                    guardar_token(nuevo)

    return cargar


def _aviso_extras(avisar, frase):
    if avisar is None:
        return
    try:
        avisar(frase)
    except Exception as fallo:
        logger.debug("no se pudo anunciar el aviso de extras: %s", fallo)


def _aplicar_extras(cliente_yt, id_video, extras, avisar) -> None:
    """Aplica categoría, etiquetas, miniatura y lista tras dejar listo OBS.

    Cada extra va en su propio try: si falla se avisa la frase y se sigue.
    Un fallo nunca borra el directo ni se relanza.
    """
    if not extras:
        return
    categoria = (extras.get("categoria") or "").strip()
    etiquetas = extras.get("etiquetas") or []
    miniatura = (extras.get("miniatura") or "").strip()
    lista = (extras.get("lista") or "").strip()
    if categoria or etiquetas:
        try:
            cliente_yt.actualizar_categoria_y_etiquetas(
                id_video, extras.get("titulo") or "",
                extras.get("descripcion") or "", categoria, etiquetas)
        except Exception as exc:
            _aviso_extras(
                avisar,
                _("No se pudieron poner la categoría y las etiquetas: "
                  "{detalle}").format(
                      detalle=youtube_api.mensaje_error_api(exc)))
    if miniatura:
        try:
            cliente_yt.poner_miniatura(id_video, miniatura)
        except Exception as exc:
            _aviso_extras(avisar, youtube_api.mensaje_error_miniatura(exc))
    if lista:
        try:
            cliente_yt.agregar_a_lista(lista, id_video)
        except Exception as exc:
            _aviso_extras(
                avisar,
                _("No se pudo agregar el directo a la lista: "
                  "{detalle}").format(
                      detalle=youtube_api.mensaje_error_api(exc)))


def preparar_en_youtube(cliente_yt, cliente_obs, cuerpo, parada=None,
                        preparar_destino=obs_destinos.preparar_destino,
                        guardar_token=None, extras=None, avisar=None) -> str:
    """Crea la emisión, la vincula y carga servidor y clave en OBS.

    Devuelve el id del vídeo. Si vincular o preparar fallan, borra la
    emisión para no dejar directos huérfanos y relanza el error original.
    Después, y sin poder tumbar el directo, aplica los `extras` (categoría,
    etiquetas y miniatura); cada fallo se anuncia con `avisar` y se sigue.
    """
    try:
        flujo = cliente_yt.flujo_reutilizable()
        if flujo is None:
            raise EmisionError(
                _("La cuenta de YouTube no tiene una clave de emisión "
                  "reutilizable. Se crea en YouTube Studio, en Emitir en "
                  "directo."))
        id_flujo, servidor, clave = flujo
        id_video = cliente_yt.crear_emision(cuerpo)
        try:
            cliente_yt.vincular_emision(id_video, id_flujo)
            preparar_destino(
                cliente_obs, obs_destinos.Destino("YouTube", servidor, clave),
                parada=parada)
        except Exception:
            try:
                cliente_yt.borrar_emision(id_video)
            except Exception as fallo_borrado:
                logger.debug("no se pudo borrar la emisión %s: %s",
                             id_video, fallo_borrado)
            raise
        _aplicar_extras(cliente_yt, id_video, extras, avisar)
        return id_video
    except EmisionError:
        raise
    except obs_cliente.ObsError:
        raise
    except Exception as exc:
        raise EmisionError(
            youtube_api.mensaje_error_api(exc)) from exc
    finally:
        if guardar_token is not None:
            try:
                nuevo = cliente_yt.token_actualizado()
            except Exception:
                nuevo = None
            if nuevo:
                guardar_token(nuevo)


def finalizar_en_youtube(cliente_yt, id_video) -> bool:
    """Finaliza o borra la emisión según su estado, y devuelve True.

    Con el directo al aire ("live", "liveStarting", "testing") lo pasa a
    terminada; si nunca salió ("created", "ready") lo borra para no dejar
    directos huérfanos; si ya terminó o no existe no hace nada. Las
    excepciones de la API salen hacia quien llama.
    """
    estado = cliente_yt.estado_emision(id_video)
    if estado in ("live", "liveStarting", "testing"):
        cliente_yt.finalizar_emision(id_video)
    elif estado in ("created", "ready"):
        cliente_yt.borrar_emision(id_video)
    return True


def ganchos_youtube(cliente_yt, cuerpo, guardar_token, extras=None,
                    avisar=None):
    """Devuelve (preparar, esperar, finalizar) para el supervisor.

    Adapta `preparar_en_youtube`, `esperar_en_vivo` y
    `finalizar_en_youtube` a las firmas que espera
    `SupervisorTransmision`, con el cliente y el cuerpo ya fijos.
    """

    def _guardar_si_hay_nuevo():
        if guardar_token is None:
            return
        try:
            nuevo = cliente_yt.token_actualizado()
        except Exception:
            nuevo = None
        if nuevo:
            guardar_token(nuevo)

    def preparar_emision(cliente_obs, parada):
        return preparar_en_youtube(
            cliente_yt, cliente_obs, cuerpo, parada=parada,
            guardar_token=guardar_token, extras=extras, avisar=avisar)

    def esperar_emision(id_video, parada, limite=120.0):
        return esperar_en_vivo(
            cliente_yt.estado_emision, id_video, parada, limite=limite)

    def finalizar_emision(id_video):
        try:
            return finalizar_en_youtube(cliente_yt, id_video)
        finally:
            _guardar_si_hay_nuevo()

    return preparar_emision, esperar_emision, finalizar_emision


def esperar_en_vivo(consultar_estado, id_video, parada=None, cada=5.0,
                    limite=120.0, dormir=time.sleep,
                    reloj=time.monotonic) -> bool:
    """Consulta el estado hasta ver "live", agotar el límite o la parada."""
    inicio = reloj()
    while True:
        if parada is not None and parada.is_set():
            return False
        try:
            estado = consultar_estado(id_video)
        except Exception:
            estado = ""
        if estado == "live":
            return True
        if reloj() - inicio >= limite:
            return False
        dormir(cada)
