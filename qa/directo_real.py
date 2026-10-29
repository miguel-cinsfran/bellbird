"""Directo real de prueba de punta a punta, para correr a mano.

Hace un directo de YouTube «No listado» de alrededor de un minuto desde
la aplicación real, conducida por UI Automation (Invoke, sin teclas),
comprueba cada paso, lo finaliza, BORRA el vídeo del canal y deja la
configuración y OBS como estaban.

Antes de salir al aire arma la escena como la de quien usa la app: dos
ventanas de color («Cámara de prueba» y «Aplicación de prueba», de
`qa/ventana_de_prueba.py`) capturadas encima del panel de chat. Al aire
comprueba que la app puso el panel adelante, que YouTube espera la señal
manual, manda tres comentarios al chat, los busca en la lista de la app y
mira en la imagen de OBS que el panel se ve. Al finalizar espera que
YouTube dé el directo por terminado y recién ahí borra el vídeo. Si falla
a mitad, la limpieza detiene la transmisión, finaliza por API, borra el
vídeo y desarma la escena igual.

No corre dentro de la suite ni del hook: crea y borra un vídeo de verdad
en el canal de la sesión iniciada. Se lanza dentro del escritorio aparte,
que es donde la aplicación hija queda visible para UI Automation:

    python herramientas/escritorio_aparte.py .venv\\Scripts\\python.exe qa/directo_real.py

Sin sesión de Google iniciada se niega a correr. Nunca toca código de la
aplicación: si el id del vídeo no aparece en los anuncios ni la API
permite encontrarlo por título, se detiene y lo dice.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

from bellbird.core.config import APP_NAME  # noqa: E402

from conducir import contestar_salir_si_aparece

PREFIJO_TITULO = "Prueba de YTChat"
PRIVACIDAD_ESPERADA = "unlisted"
PREFIJO_LISTA = "Prueba de YTChat lista"
PRIVACIDAD_LISTA = "private"
DESCRIPCION_PRUEBA = (
    "Directo de prueba de YTChat, se borra al terminar."
)

# Opciones del directo que la prueba deja puestas y después comprueba: latencia
# ultrabaja, rebobinar apagado y categoría Educación. Las etiquetas no se
# comprueban contra la API, que no las devuelve en un directo: se revisan en
# YouTube Studio. La miniatura se genera en un archivo temporal de un color.
LATENCIA_PRUEBA = "ultraLow"
CATEGORIA_PRUEBA = "27"
ETIQUETAS_PRUEBA = "prueba, bellbird"
ANCHO_MINIATURA = 1280
ALTO_MINIATURA = 720
COLOR_MINIATURA = (30, 60, 120)

# Volumen al que suena todo durante la prueba, para no molestar a quien
# trabaja en la misma PC: voz, sonidos y reproductor quedan al 12 %.
VOLUMEN_PRUEBA = 0.12

# Escena de prueba: imita la de quien usa la app, con dos capturas de
# ventana encima del panel de chat. Título y color de cada ventana.
VENTANA_CAMARA = ("Cámara de prueba", "00C000")
VENTANA_APLICACION = ("Aplicación de prueba", "C000C0")
FUENTE_CAMARA = "Prueba YTChat cámara"
FUENTE_APLICACION = "Prueba YTChat aplicación"
ANUNCIO_PANEL_ADELANTE = "el panel de chat estaba detrás de"
COMENTARIOS_PRUEBA = ("Comentario de prueba 1", "Comentario de prueba 2",
                      "Comentario de prueba 3")
# Tamaño con el que se crea el panel si la escena no lo tenía, igual que
# los valores iniciales del diálogo de transmisión.
PANEL_ANCHO = 460
PANEL_ALTO = 620
COLORES_VENTANAS = ((0, 192, 0), (192, 0, 192))

# Fragmentos que anuncian un error al salir al aire, en vez del éxito.
ERRORES_AL_AIRE = ("no se pudo", "error", "falló", "no tiene")
OK_AL_AIRE = "ya está al aire"
OK_CHAT = "conectado al directo"
OK_FIN = ("detenid", "finaliz", "terminó")

# Auxiliar de wx para decodificar PNG sin ventanas: guarda la instancia
# para que el recolector no la libere mientras se usa la imagen.
_APP_WX = None


def _asegurar_app_wx() -> None:
    """Crea un wx.App mínimo si todavía no existe, sin abrir ventanas."""
    import wx
    global _APP_WX
    if wx.GetApp() is None:
        _APP_WX = wx.App(False)


def armar_titulo(hora: str) -> str:
    """Título de la prueba con la hora, para encontrarlo después por API."""
    return f"{PREFIJO_TITULO} {(hora or '').strip()}".strip()


def es_borrable(titulo: str, privacidad: str) -> bool:
    """Solo se borra lo que la herramienta creó: título propio y no listado."""
    return (titulo or "").startswith(PREFIJO_TITULO) \
        and (privacidad or "") == PRIVACIDAD_ESPERADA


def armar_titulo_lista(hora: str) -> str:
    """Título de la lista de prueba con la hora, para encontrarla después."""
    return f"{PREFIJO_LISTA} {(hora or '').strip()}".strip()


def es_lista_borrable(titulo: str, privacidad: str) -> bool:
    """Solo se borra la lista que creó la prueba: prefijo propio y privada."""
    return (titulo or "").startswith(PREFIJO_LISTA) \
        and (privacidad or "") == PRIVACIDAD_LISTA


def extraer_id_video(texto: str) -> str:
    """Saca el id del vídeo de un anuncio o registro, o cadena vacía."""
    texto = texto or ""
    for patron in (r"watch\?v=([A-Za-z0-9_-]{11})",
                   r"youtu\.be/([A-Za-z0-9_-]{11})",
                   r"/(?:live|shorts|embed|v|e)/([A-Za-z0-9_-]{11})"):
        coincidencia = re.search(patron, texto)
        if coincidencia:
            return coincidencia.group(1)
    return ""


def primer_faltante(anuncios: str, fragmentos: list[str]) -> str | None:
    """Primer fragmento esperado que no aparece en los anuncios, o None."""
    base = (anuncios or "").lower()
    for fragmento in fragmentos:
        if (fragmento or "").lower() not in base:
            return fragmento
    return None


def faltas_de_opciones(contenido, snippet) -> list[str]:
    """Opciones pedidas que no llegaron al directo, según la API.

    `contenido` es el `contentDetails` de liveBroadcasts y `snippet` el del
    vídeo. Se pide latencia ultrabaja, rebobinar apagado (enableDvr False)
    y categoría Educación.
    """
    contenido = contenido or {}
    snippet = snippet or {}
    faltas: list[str] = []
    if (contenido.get("latencyPreference") or "") != LATENCIA_PRUEBA:
        faltas.append("latencia ultrabaja")
    if contenido.get("enableDvr") is not False:
        faltas.append("rebobinar apagado")
    if (snippet.get("categoryId") or "") != CATEGORIA_PRUEBA:
        faltas.append("categoría Educación")
    # Las etiquetas no se comprueban: la API no las devuelve en un directo.
    return faltas


def estado_miniatura(anuncios: str) -> tuple[bool, str]:
    """Si la miniatura quedó bien o falló, leyendo los anuncios.

    Pasa cuando no hubo anuncio de fallo. Un rechazo por canal sin verificar
    por teléfono (403) también cuenta como bien: es lo esperado si la cuenta
    no está verificada. Cualquier otro anuncio de fallo la marca mal.
    """
    from bellbird.youtube import youtube_api
    texto = (anuncios or "").lower()
    if youtube_api.FRASE_MINiatura_SIN_VERIFICAR.lower() in texto:
        return (True, "el canal no está verificado por teléfono: YouTube la "
                      "rechazó como se esperaba")
    if "no se pudo poner la miniatura" in texto:
        return (False, "la app anunció que no pudo poner la miniatura")
    return (True, "sin avisos: la miniatura quedó")


def estado_lista(anuncios: str, en_la_lista: bool) -> tuple[bool, str]:
    """Si el directo quedó en la lista, leyendo anuncios y API.

    El anuncio de la app gana aunque la API diga que sí: si la app avisó que
    no pudo agregarlo, se le cree a la app. Sin ese aviso, manda la API.
    """
    texto = (anuncios or "").lower()
    if "no se pudo agregar el directo a la lista" in texto:
        return (False, "la app anunció que no pudo agregarlo a la lista")
    if en_la_lista:
        return (True, "el directo está en la lista")
    return (False, "la API no muestra el directo en la lista")


def decidir_cerrar_obs(estaba_abierto: bool) -> bool:
    """Si OBS ya estaba abierto no se lo cierra; si lo abrió la app, sí."""
    return not bool(estaba_abierto)


def _respaldar_sonidos(ruta, respaldo) -> bool:
    """Respalda `sounds.ini` en `respaldo`; si no existe no crea nada."""
    try:
        shutil.copy2(ruta, respaldo)
        return True
    except OSError:
        return False


def _restaurar_sonidos(ruta, respaldo, habia: bool) -> None:
    """Restaura `sounds.ini` desde el respaldo, si lo había."""
    try:
        if habia:
            shutil.copy2(respaldo, ruta)
    except OSError:
        pass


# Umbral de la comprobación visual: el panel pasa si al menos el 2 % de sus
# píxeles no son del color de las ventanas de prueba que lo tapaban. El panel
# tiene fondo transparente y solo pinta las cajas de los mensajes, así que aun
# adelante deja ver casi todo lo de abajo; tapado del todo por un color liso
# da 0 %.
UMBRAL_PANEL_VISIBLE = 0.02
# Margen por canal al comparar colores, para que la compresión del PNG no
# convierta un verde casi exacto en un falso tapado.
TOLERANCIA_COLOR = 32


def _coincide_alguno(pixel, colores, tolerancia) -> bool:
    """Si el píxel cae dentro del margen de alguno de los colores dados."""
    try:
        r, g, b = pixel
    except (TypeError, ValueError):
        return False
    margen = max(0, tolerancia)
    for color in colores or ():
        try:
            cr, cg, cb = color
        except (TypeError, ValueError):
            continue
        if max(abs(r - cr), abs(g - cg), abs(b - cb)) <= margen:
            return True
    return False


def fraccion_de_color(pixeles, colores, tolerancia) -> float:
    """Qué parte de los píxeles coincide con alguno de los colores dados.

    Cada píxel y cada color son ternas (rojo, verde, azul). Sin píxeles
    devuelve 0.0.
    """
    lista = list(pixeles or [])
    if not lista:
        return 0.0
    tapados = sum(1 for pixel in lista
                  if _coincide_alguno(pixel, colores, tolerancia))
    return tapados / len(lista)


def panel_visible(pixeles, colores) -> bool:
    """Si el panel se ve en la captura: al menos un 2 % propio.

    Pasa cuando al menos el 2 % de los píxeles no es de ninguno de los colores
    de las ventanas de prueba (si todo es verde o magenta, se sigue viendo la
    ventana, no el panel).
    """
    lista = list(pixeles or [])
    if not lista:
        return False
    tapados = sum(1 for pixel in lista
                  if _coincide_alguno(pixel, colores, TOLERANCIA_COLOR))
    libres = len(lista) - tapados
    return libres / len(lista) >= UMBRAL_PANEL_VISIBLE


def rectangulo_del_panel(transformacion, ancho_captura, ancho_lienzo,
                         alto_captura=None, alto_lienzo=None) -> tuple:
    """Rectángulo del panel en píxeles de la captura, recortado a ella.

    Escala con el cociente entre el ancho de la captura y el del lienzo, por
    si OBS devolvió la imagen a otro tamaño. Lo que queda fuera se recorta;
    si el panel está entero fuera, el ancho o el alto dan cero.
    """
    datos = transformacion or {}

    def numero(clave):
        try:
            return float(datos.get(clave, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    try:
        escala = (ancho_captura / ancho_lienzo) if ancho_lienzo else 1.0
    except (TypeError, ZeroDivisionError):
        escala = 1.0
    if not escala > 0:
        escala = 1.0
    ancho_fuente = numero("width") or numero("sourceWidth")
    alto_fuente = numero("height") or numero("sourceHeight")
    x = int(round(numero("positionX") * escala))
    y = int(round(numero("positionY") * escala))
    ancho = int(round(max(0.0, ancho_fuente) * escala))
    alto = int(round(max(0.0, alto_fuente) * escala))
    izquierda = max(0, x)
    arriba = max(0, y)
    derecha = x + ancho
    if ancho_captura:
        derecha = min(derecha, ancho_captura)
    abajo = y + alto
    if alto_captura:
        abajo = min(abajo, alto_captura)
    return (izquierda, arriba, max(0, derecha - izquierda),
            max(0, abajo - arriba))


def id_para_limpiar(id_conocido, encontrado_por_titulo,
                    pulso_transmitir) -> str:
    """Qué id usar en la limpieza: el conocido gana, si no el hallado.

    Sin id conocido y con Transmitir pulsado (o salida al aire, que lo
    implica) se usa lo encontrado por título; sin pulsar no se busca y
    se devuelve cadena vacía.
    """
    if (id_conocido or ""):
        return id_conocido
    if not pulso_transmitir:
        return ""
    return encontrado_por_titulo or ""


def pasos_de_limpieza(salio_al_aire, finalizado, id_video,
                      creo_panel, pulso_transmitir=False) -> list:
    """Orden de la limpieza final, pase lo que pase, del punto 5 del encargo.

    Si salió al aire y YouTube no lo dio por terminado, primero se detiene
    la transmisión y se finaliza por API; si la falla fue antes de salir al
    aire pero ya se había pulsado «Transmitir», se intenta lo mismo porque
    la app pudo haber creado la emisión igual. Después se borra el vídeo
    pendiente, se quitan las capturas de prueba (y el panel si lo creó la
    herramienta), se cierran las ventanas y se deja todo como estaba.
    """
    pasos = []
    if (salio_al_aire or bool(pulso_transmitir)) and not finalizado:
        pasos.append("detener_y_finalizar")
    if id_video:
        pasos.append("borrar_video")
    pasos.append("quitar_capturas")
    if creo_panel:
        pasos.append("quitar_panel")
    pasos.extend(("cerrar_ventanas", "cerrar_app_y_restaurar"))
    return pasos


def _ayuda() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Directo real de prueba: crea un «No listado» de un "
                    "minuto, lo finaliza y lo borra. Corre dentro del "
                    "escritorio aparte, nunca en la suite.")
    parser.add_argument("--duracion", type=int, default=60,
                        help="segundos al aire antes de finalizar "
                             "(por defecto 60)")
    parser.add_argument("--timeout-salida", type=int, default=240,
                        help="segundos esperando «ya está al aire» "
                             "(por defecto 240)")
    parser.add_argument("--timeout-chat", type=int, default=90,
                        help="segundos esperando el chat conectado "
                             "(por defecto 90)")
    parser.add_argument("--timeout-fin", type=int, default=90,
                        help="segundos esperando «Transmisión detenida» "
                             "(por defecto 90)")
    parser.add_argument("--corte", type=int, default=0,
                        help="segundos de corte de red tras escribir desde "
                             "la app, con la tarea BellbirdCorteRed ya "
                             "lanzada (0 sin corte, tope 30)")
    return parser


# -- Impuro: archivos, procesos, UI Automation y API. Fuera de las pruebas. --

_LANZADOR = """\
import os, sys, time
REPO = {repo!r}
LOG = os.environ.get("DIRECTO_REAL_ANUNCIOS", "")
LOG_CHAT = os.environ.get("DIRECTO_REAL_CHAT", "")
sys.path.insert(0, REPO)
os.chdir(REPO)
sys.argv = [os.path.join(REPO, "main.py")]
import bellbird.ui.gui as g
_orig = g.anunciar

def _anunciar(texto, urgente=True):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(texto) + "\\n")
    except OSError:
        pass
    _orig(texto, urgente)

g.anunciar = _anunciar
_orig_agregar = g.YTChatFrame.agregar_mensaje_chat

def _agregar_mensaje(self, *args, **kwargs):
    try:
        autor = kwargs.get("autor", args[0] if len(args) > 0 else "")
        mensaje = kwargs.get("mensaje", args[1] if len(args) > 1 else "")
        hora = kwargs.get("hora", args[2] if len(args) > 2 else "")
        with open(LOG_CHAT, "a", encoding="utf-8") as f:
            f.write(str(hora) + " " + str(autor) + ": " + str(mensaje)
                    + "\\n")
    except OSError:
        pass
    return _orig_agregar(self, *args, **kwargs)

g.YTChatFrame.agregar_mensaje_chat = _agregar_mensaje
import bellbird.player.reproductor as _rep
_orig_rep_init = _rep.ReproductorPanel.__init__

def _rep_init(self, *a, **k):
    _orig_rep_init(self, *a, **k)
    try:
        self._vol = 12
    except Exception:
        pass
    try:
        sld = getattr(self, "sld_vol", None)
        if sld is not None:
            sld.SetValue(12)
    except Exception:
        pass

_rep.ReproductorPanel.__init__ = _rep_init
import main
main.main()
"""


def _leer_anuncios(ruta: str) -> str:
    try:
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _esperar_anuncio(ruta: str, fragmentos: tuple[str, ...],
                     segundos: int, desde: int = 0) -> str | None:
    fin = time.time() + segundos
    while time.time() < fin:
        texto = _leer_anuncios(ruta)[desde:].lower()
        for fragmento in fragmentos:
            if fragmento.lower() in texto:
                return fragmento
        time.sleep(1)
    return None


def _escritorio():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def _ventana(titulo_parcial: str, segundos: int = 30):
    from pywinauto import Desktop
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            for ventana in Desktop(backend="uia").windows():
                try:
                    if titulo_parcial in (ventana.window_text() or ""):
                        return ventana
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"no apareció la ventana «{titulo_parcial}»")


def _dialogo_hijo(principal, titulo_parcial: str, segundos: int = 20):
    """Los modales cuelgan de la ventana principal, no salen sueltos."""
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            for hijo in principal.descendants(control_type="Window"):
                try:
                    if titulo_parcial in (hijo.window_text() or ""):
                        return hijo
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    return _ventana(titulo_parcial, 5)


def _control(raiz, nombre: str, tipo: str | None = None,
             segundos: int = 20):
    """Busca por nombre exacto y visible entre los descendientes."""
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            candidatos = raiz.descendants(control_type=tipo) \
                if tipo else raiz.descendants()
            for candidato in candidatos:
                try:
                    if candidato.window_text() == nombre \
                            and candidato.is_visible():
                        return candidato
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"no apareció el control «{nombre}»")


def _leer_valor(control) -> str:
    try:
        valor = control.selected_text()
        if valor:
            return str(valor)
    except Exception:
        pass
    try:
        valor = control.get_value()
        if valor:
            return str(valor)
    except Exception:
        pass
    try:
        return str(control.window_text() or "")
    except Exception:
        return ""


def _obs_en_ejecucion() -> bool:
    try:
        salida = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq obs64.exe"],
            capture_output=True, text=True, timeout=15)
        return "obs64.exe" in (salida.stdout or "").lower()
    except Exception:
        return False


def _limpiar_sentinel() -> int:
    """Borra los restos de cierres forzados para que OBS no pida modo seguro."""
    base = os.environ.get("APPDATA", "")
    if not base:
        return 0
    borrados = 0
    for resto in glob.glob(os.path.join(
            base, "obs-studio", ".sentinel", "run_*")):
        try:
            os.remove(resto)
            borrados += 1
        except OSError:
            pass
    return borrados


def _cerrar_obs():
    try:
        subprocess.run(["taskkill", "/IM", "obs64.exe"],
                       capture_output=True, timeout=30)
        time.sleep(5)
        if _obs_en_ejecucion():
            subprocess.run(["taskkill", "/F", "/IM", "obs64.exe"],
                           capture_output=True, timeout=30)
    except Exception:
        pass


def _cliente_youtube():
    from bellbird.core import paths  # noqa: F401  (raíz del paquete)
    from bellbird.youtube import credenciales, youtube_api
    datos = credenciales.efectivas(credenciales.cargar())
    return youtube_api.ClienteYouTube(datos), credenciales


def _guardar_token_si_renovo(cliente, credenciales) -> None:
    try:
        nuevo = cliente.token_actualizado()
    except Exception:
        nuevo = None
    if nuevo:
        try:
            credenciales.guardar_campo("token", nuevo)
        except Exception:
            pass


def _buscar_video_por_titulo(cliente, titulo: str):
    """El más reciente con `mine=True` cuyo título sea el de la prueba."""
    resp = cliente._escritura().liveBroadcasts().list(
        part="id,snippet,status", mine=True, maxResults=25).execute()
    for item in resp.get("items", []) or []:
        snippet = item.get("snippet") or {}
        if snippet.get("title") == titulo:
            estado = item.get("status") or {}
            return (item.get("id") or "", snippet.get("title") or "",
                    estado.get("privacyStatus") or "")
    return ("", "", "")


def _datos_video(cliente, id_video: str):
    resp = cliente._escritura().videos().list(
        part="snippet,status", id=id_video).execute()
    items = resp.get("items", []) or []
    if not items:
        return ("", "")
    snippet = items[0].get("snippet") or {}
    estado = items[0].get("status") or {}
    return (snippet.get("title") or "", estado.get("privacyStatus") or "")


def _borrar_video(cliente, credenciales, id_video: str) -> tuple[bool, str]:
    titulo, privacidad = _datos_video(cliente, id_video)
    if not es_borrable(titulo, privacidad):
        return (False, f"no se borra: título «{titulo}» con privacidad "
                       f"«{privacidad}», no es de la prueba")
    cliente._escritura().videos().delete(id=id_video).execute()
    _guardar_token_si_renovo(cliente, credenciales)
    return (True, "")


def _crear_lista(cliente, titulo: str) -> str:
    """Crea una lista de reproducción privada y devuelve su id."""
    resp = cliente._escritura().playlists().insert(
        part="snippet,status",
        body={"snippet": {"title": titulo,
                          "description": "Lista de prueba de YTChat, "
                                         "se borra al terminar."},
              "status": {"privacyStatus": PRIVACIDAD_LISTA}}).execute()
    return (resp or {}).get("id") or ""


def _video_en_lista(cliente, id_lista: str, id_video: str) -> bool:
    """Si la lista ya muestra el vídeo, según la API."""
    resp = cliente._escritura().playlistItems().list(
        part="id", playlistId=id_lista, videoId=id_video,
        maxResults=5).execute()
    return bool((resp or {}).get("items"))


def _borrar_lista(cliente, id_lista: str) -> tuple[bool, str]:
    """Borra la lista, solo si es de la prueba; devuelve (borrada, motivo)."""
    resp = cliente._escritura().playlists().list(
        part="snippet,status", id=id_lista).execute()
    items = (resp or {}).get("items", []) or []
    if not items:
        return (False, f"no se borra: la lista «{id_lista}» no existe")
    snippet = items[0].get("snippet") or {}
    estado = items[0].get("status") or {}
    titulo = snippet.get("title") or ""
    privacidad = estado.get("privacyStatus") or ""
    if not es_lista_borrable(titulo, privacidad):
        return (False, f"no se borra: título «{titulo}» con privacidad "
                       f"«{privacidad}», no es de la prueba")
    cliente._escritura().playlists().delete(id=id_lista).execute()
    return (True, "")


def _abrir_ventanas_prueba() -> list:
    """Abre las dos ventanas de color que tapan el panel en la escena."""
    guion = RAIZ / "qa" / "ventana_de_prueba.py"
    procesos = []
    for titulo, color in (VENTANA_CAMARA, VENTANA_APLICACION):
        procesos.append(subprocess.Popen(
            [sys.executable, str(guion), "--titulo", titulo,
             "--color", color]))
    return procesos


def _cerrar_ventanas_prueba(procesos) -> None:
    for proceso in procesos or ():
        try:
            if proceso.poll() is None:
                proceso.terminate()
        except Exception:
            pass


def _puerto_panel(ruta_config) -> int:
    """Puerto del panel leído del config.ini, sin migrar ni salir."""
    import configparser
    parser = configparser.ConfigParser()
    try:
        if parser.read(ruta_config, encoding="utf-8"):
            return int(parser.get("overlay", "puerto", fallback="8730"))
    except (configparser.Error, ValueError):
        pass
    return 8730


def _gestor_obs():
    from bellbird.obs.obs_panel import GestorPanelObs
    gestor = GestorPanelObs()
    gestor.conectar()
    return gestor


def _valores_ventanas(gestor, escena, segundos: int = 15) -> dict:
    """Valor `window` de OBS para cada ventana de prueba, por título."""
    from bellbird.obs import obs_captura
    esperados = (VENTANA_CAMARA[0], VENTANA_APLICACION[0])
    fin = time.time() + segundos
    valores: dict = {}
    while True:
        try:
            opciones, _ = obs_captura.ventanas(gestor._cliente, escena)
        except Exception:
            opciones = ()
        valores = {}
        for legible, valor in opciones or ():
            for titulo in esperados:
                if titulo in (legible or "") or titulo in (valor or ""):
                    valores[titulo] = valor
        if len(valores) == len(esperados) or time.time() >= fin:
            return valores
        time.sleep(1)


def _quitar_fuente(gestor, escena: str, nombre: str,
                   borrar_entrada: bool = False) -> None:
    """Saca la fuente de la escena y, si es propia, borra la entrada."""
    try:
        elementos = gestor._pedir(
            "GetSceneItemList", {"sceneName": escena}).get(
            "sceneItems", ()) or ()
    except Exception:
        return
    for elemento in elementos:
        if elemento.get("sourceName") == nombre \
                and elemento.get("sceneItemId") is not None:
            try:
                gestor._pedir("RemoveSceneItem",
                              {"sceneName": escena,
                               "sceneItemId": elemento.get("sceneItemId")})
            except Exception:
                pass
    if borrar_entrada:
        try:
            gestor._pedir("RemoveInput", {"inputName": nombre})
        except Exception:
            pass


def _crear_captura(gestor, escena: str, nombre: str, valor_ventana: str,
                   ancho: int, alto: int) -> None:
    """Agrega una captura de ventana a pantalla completa sobre el panel."""
    _quitar_fuente(gestor, escena, nombre, borrar_entrada=True)
    respuesta = gestor._pedir(
        "CreateInput", {"sceneName": escena, "inputName": nombre,
                        "inputKind": "window_capture",
                        "inputSettings": {"window": valor_ventana},
                        "sceneItemEnabled": True}) or {}
    identificador = respuesta.get("sceneItemId")
    if identificador is None:
        elementos = gestor._pedir(
            "GetSceneItemList", {"sceneName": escena}).get(
            "sceneItems", ()) or ()
        for elemento in elementos:
            if elemento.get("sourceName") == nombre:
                identificador = elemento.get("sceneItemId")
                break
    if identificador is None:
        raise RuntimeError(f"OBS no devolvió el elemento «{nombre}»")
    gestor._pedir("SetSceneItemTransform",
                  {"sceneName": escena, "sceneItemId": identificador,
                   "sceneItemTransform": {
                       "positionX": 0, "positionY": 0, "alignment": 5,
                       "boundsType": "OBS_BOUNDS_SCALE_INNER",
                       "boundsAlignment": 0,
                       "boundsWidth": ancho, "boundsHeight": alto}})


def _armar_escena_prueba(gestor, url_panel: str) -> tuple[str, bool]:
    """Deja la escena al aire como la de quien usa la app.

    Devuelve (escena, creo_panel): el panel solo se crea si no estaba, y se
    anota para quitarlo después. Las dos capturas quedan encima del panel.
    """
    from bellbird.obs.obs_panel import NOMBRE_FUENTE
    escena = gestor.escena_al_aire()
    if not escena:
        raise RuntimeError("OBS no tiene escena al aire")
    creo_panel = False
    if NOMBRE_FUENTE not in gestor.fuentes(escena):
        gestor.asegurar_fuente(escena, url_panel, PANEL_ANCHO, PANEL_ALTO)
        creo_panel = True
    lienzo = gestor._pedir("GetVideoSettings") or {}
    ancho = lienzo.get("baseWidth", 0) or 1920
    alto = lienzo.get("baseHeight", 0) or 1080
    valores = _valores_ventanas(gestor, escena)
    for nombre, titulo in ((FUENTE_CAMARA, VENTANA_CAMARA[0]),
                           (FUENTE_APLICACION, VENTANA_APLICACION[0])):
        if titulo not in valores:
            raise RuntimeError(
                f"OBS no ve la ventana «{titulo}» en sus capturas")
        _crear_captura(gestor, escena, nombre, valores[titulo], ancho, alto)
        gestor.al_frente(escena, fuente=nombre)
    return (escena, creo_panel)


def _live_chat_id(cliente, id_video: str) -> str:
    resp = cliente._escritura().liveBroadcasts().list(
        part="snippet", id=id_video).execute()
    items = resp.get("items", []) or []
    if not items:
        return ""
    return ((items[0].get("snippet") or {}).get("liveChatId") or "")


def _auto_stop(cliente, id_video: str):
    """Valor de `enableAutoStop`: False si YouTube espera la señal manual."""
    resp = cliente._escritura().liveBroadcasts().list(
        part="contentDetails", id=id_video).execute()
    items = resp.get("items", []) or []
    if not items:
        return None
    return ((items[0].get("contentDetails") or {}).get("enableAutoStop"))


def _leer_opciones(cliente, id_video: str) -> tuple[dict, dict]:
    """`contentDetails` del directo y `snippet` del vídeo, tal cual la API."""
    resp = cliente._escritura().liveBroadcasts().list(
        part="contentDetails", id=id_video).execute()
    items = resp.get("items", []) or []
    contenido = (items[0].get("contentDetails") or {}) if items else {}
    resp_video = cliente._escritura().videos().list(
        part="snippet", id=id_video).execute()
    items_video = resp_video.get("items", []) or []
    snippet = (items_video[0].get("snippet") or {}) if items_video else {}
    return (contenido, snippet)


def _crear_miniatura_prueba(destino: str) -> str:
    """Genera un JPG de un solo color para subir como miniatura."""
    import wx
    _asegurar_app_wx()
    imagen = wx.Image(ANCHO_MINIATURA, ALTO_MINIATURA)
    rojo, verde, azul = COLOR_MINIATURA
    imagen.SetRGB(wx.Rect(0, 0, ANCHO_MINIATURA, ALTO_MINIATURA),
                  rojo, verde, azul)
    if not imagen.SaveFile(destino, wx.BITMAP_TYPE_JPEG):
        raise RuntimeError("no se pudo generar la miniatura de prueba")
    return destino


def _comentario_faltante(ruta_chat, comentarios,
                         segundos: int = 30) -> tuple[str | None,
                                                      list[str] | None]:
    """Primer comentario que no aparece en el archivo del chat, o None.

    Devuelve (faltante, leídos): leídos lleva las líneas del archivo,
    o None si todavía no se pudo leer el archivo.
    """
    fin = time.time() + segundos
    leidos: list[str] | None = None
    while True:
        try:
            with open(ruta_chat, encoding="utf-8") as f:
                texto = f.read()
            leidos = texto.splitlines()
        except OSError:
            texto = ""
        faltante = next((comentario for comentario in comentarios
                         if comentario not in texto), None)
        if faltante is None:
            return (None, leidos)
        if time.time() >= fin:
            return (faltante, leidos)
        time.sleep(1)


def _detalle_lista_chat(leidos: list[str] | None) -> str:
    """Cuántas líneas tenía el archivo del chat y las tres últimas."""
    if leidos is None:
        return "no se encontró el archivo del chat"
    if not leidos:
        return "lista vacía (0 elementos)"
    ultimos = ", ".join(f"«{texto}»" for texto in leidos[-3:])
    return f"{len(leidos)} elementos; últimos: {ultimos}"


def _transformacion_panel(gestor, escena: str) -> dict:
    from bellbird.obs.obs_panel import NOMBRE_FUENTE
    elementos = gestor._pedir(
        "GetSceneItemList", {"sceneName": escena}).get(
        "sceneItems", ()) or ()
    for elemento in elementos:
        if elemento.get("sourceName") == NOMBRE_FUENTE:
            return elemento.get("sceneItemTransform", {}) or {}
    return {}


def _pixeles_panel(ruta_png: str, rectangulo) -> tuple[list, int, int]:
    """Píxeles (rojo, verde, azul) del rectángulo, sin abrir ventanas."""
    import wx
    _asegurar_app_wx()
    imagen = wx.Image(ruta_png, wx.BITMAP_TYPE_PNG)
    ancho, alto = imagen.GetWidth(), imagen.GetHeight()
    datos = imagen.GetData()
    x, y, ancho_rec, alto_rec = rectangulo
    x = max(0, min(x, ancho))
    y = max(0, min(y, alto))
    ancho_rec = max(0, min(ancho_rec, ancho - x))
    alto_rec = max(0, min(alto_rec, alto - y))
    pixeles = []
    for fila in range(y, y + alto_rec):
        base = (fila * ancho + x) * 3
        for columna in range(ancho_rec):
            i = base + columna * 3
            pixeles.append((datos[i], datos[i + 1], datos[i + 2]))
    return (pixeles, ancho, alto)


def _comprobar_panel_en_imagen(gestor, escena: str, destino_png: str,
                               segundos: int = 15) -> tuple[bool, str]:
    """Si el panel se ve en la imagen que OBS saca al aire.

    Devuelve (pasa, detalle): el detalle lleva la ruta del PNG guardado.
    """
    datos = None
    fin = time.time() + segundos
    while True:
        try:
            datos = gestor._pedir("GetSourceScreenshot",
                                  {"sourceName": escena,
                                   "imageFormat": "png"}) or {}
            if datos.get("imageData"):
                break
        except Exception:
            datos = None
        if time.time() >= fin:
            break
        time.sleep(1)
    crudo = (datos or {}).get("imageData", "") or ""
    if "," in crudo:
        crudo = crudo.split(",", 1)[1]
    if not crudo:
        return (False, "OBS no devolvió la imagen")
    import base64
    try:
        os.makedirs(os.path.dirname(os.path.abspath(destino_png)),
                    exist_ok=True)
    except OSError:
        pass
    with open(destino_png, "wb") as f:
        f.write(base64.b64decode(crudo))
    lienzo = gestor._pedir("GetVideoSettings") or {}
    transformacion = _transformacion_panel(gestor, escena)
    if not transformacion:
        return (False, f"sin panel en la escena ({destino_png})")
    ancho_img, alto_img = _tamano_imagen(destino_png)
    rectangulo = rectangulo_del_panel(
        transformacion, ancho_img, lienzo.get("baseWidth", 0) or ancho_img,
        alto_img, lienzo.get("baseHeight", 0) or alto_img)
    pixeles, _, _ = _pixeles_panel(destino_png, rectangulo)
    if panel_visible(pixeles, COLORES_VENTANAS):
        return (True, destino_png)
    return (False, f"el panel sigue tapado ({destino_png})")


def _tamano_imagen(ruta_png: str) -> tuple[int, int]:
    import wx
    _asegurar_app_wx()
    imagen = wx.Image(ruta_png, wx.BITMAP_TYPE_PNG)
    return (imagen.GetWidth(), imagen.GetHeight())


def _esperar_estado(cliente, id_video: str, esperado: str = "complete",
                    segundos: int = 30, intervalo: int = 3) -> str:
    """Estado del ciclo de vida hasta que llegue el esperado o venza."""
    ultimo = ""
    fin = time.time() + segundos
    while True:
        try:
            ultimo = cliente.estado_emision(id_video) or ""
        except Exception:
            pass
        if ultimo == esperado:
            return ultimo
        if time.time() >= fin:
            return ultimo
        time.sleep(intervalo)


def _detener_y_finalizar(gestor, cliente, credenciales,
                         id_video: str) -> tuple[bool, str]:
    """Detiene la transmisión y finaliza por API, lo mejor que se pueda."""
    errores = []
    if gestor is not None:
        try:
            gestor.detener_transmision()
        except Exception as exc:
            errores.append(f"OBS no se detuvo: {exc}")
    if id_video:
        try:
            cliente.finalizar_emision(id_video)
            _guardar_token_si_renovo(cliente, credenciales)
        except Exception as exc:
            errores.append(f"la API no finalizó: {exc}")
    else:
        errores.append("sin id del vídeo")
    if errores:
        return (False, "; ".join(errores))
    return (True, "transmisión detenida y directo finalizado")


def _correr(args) -> tuple[list[tuple[str, bool, str]], int]:
    from bellbird.core import config, paths
    from bellbird.youtube import credenciales

    pasos: list[tuple[str, bool, str]] = []

    def anotar(nombre: str, bien: bool, detalle: str = "") -> None:
        pasos.append((nombre, bien, detalle))

    if not credenciales.hay_sesion():
        print("Sin sesión de Google iniciada: inicia sesión en la "
              "aplicación y vuelve a correr esta herramienta.")
        return ([("sesión de Google", False, "sin token")], 2)

    raiz = paths.carpeta_instalacion()
    ruta_config = paths.config_ini()
    ruta_sonidos = paths.sounds_ini()
    respaldo = tempfile.mktemp(prefix="directo-real-config-",
                                suffix=".ini")
    try:
        shutil.copy2(ruta_config, respaldo)
    except OSError as exc:
        print(f"No se pudo respaldar config.ini: {exc}")
        return ([("respaldo de config.ini", False, str(exc))], 2)
    respaldo_sonidos = tempfile.mktemp(prefix="directo-real-sounds-",
                                       suffix=".ini")
    habia_sonidos = _respaldar_sonidos(ruta_sonidos, respaldo_sonidos)

    hora = time.strftime("%H:%M")
    titulo = armar_titulo(hora)
    titulo_lista = armar_titulo_lista(hora)
    tmpdir = tempfile.mkdtemp(prefix="directo-real-")
    ruta_anuncios = os.path.join(tmpdir, "anuncios.txt")
    ruta_chat = os.path.join(tmpdir, "chat.txt")
    ruta_lanzador = os.path.join(tmpdir, "app_directo_real.py")
    open(ruta_anuncios, "w").close()
    open(ruta_chat, "w").close()
    salida: list[tuple[str, bool, str]] = pasos
    app = None
    principal = None
    estaba_obs = _obs_en_ejecucion()
    id_video = ""
    id_lista = ""
    borrado_id = ""
    enlace_manual = ""
    salio_al_aire = False
    finalizado = False
    pulso_transmitir = False
    creo_panel = False
    escena_prueba = ""
    gestor_obs = None
    ventanas_prueba: list = []
    ruta_miniatura = ""

    try:
        from bellbird.core.config import codificar_texto_ini
        ruta_miniatura = os.path.join(tmpdir, "miniatura-prueba.jpg")
        try:
            _crear_miniatura_prueba(ruta_miniatura)
            detalle_miniatura = f"miniatura temporal «{ruta_miniatura}»"
        except Exception as exc:
            ruta_miniatura = ""
            detalle_miniatura = f"sin miniatura ({exc})"
        try:
            cliente_lista, creds_lista = _cliente_youtube()
            id_lista = _crear_lista(cliente_lista, titulo_lista)
            _guardar_token_si_renovo(cliente_lista, creds_lista)
            if not id_lista:
                raise RuntimeError("la API no devolvió el id de la lista")
            config.guardar_opcion(ruta_config, "transmision", "youtube_lista",
                                  id_lista)
            config.guardar_opcion(ruta_config, "transmision",
                                  "youtube_lista_titulo",
                                  codificar_texto_ini(titulo_lista))
        except Exception as exc:
            anotar("lista de prueba", False, str(exc))
            return (salida, 1)
        anotar("lista de prueba", True,
               f"lista «{titulo_lista}» (id {id_lista})")
        config.guardar_opcion(ruta_config, "transmision", "destino",
                              "YouTube")
        config.guardar_opcion(ruta_config, "transmision", "youtube_titulo",
                              codificar_texto_ini(titulo))
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_descripcion",
                              codificar_texto_ini(DESCRIPCION_PRUEBA))
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_privacidad", PRIVACIDAD_ESPERADA)
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_latencia", LATENCIA_PRUEBA)
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_ninos", "false")
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_dvr", "false")
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_categoria", CATEGORIA_PRUEBA)
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_etiquetas",
                              codificar_texto_ini(ETIQUETAS_PRUEBA))
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_miniatura",
                              codificar_texto_ini(ruta_miniatura))
        config.guardar_opcion(ruta_config, "overlay", "activo", "true")
        config.guardar_opcion(ruta_config, "voz", "volumen",
                              str(VOLUMEN_PRUEBA))
        if habia_sonidos:
            config.guardar_opcion(ruta_sonidos, "sonidos", "volumen",
                                  str(VOLUMEN_PRUEBA))
            detalle_volumen = "volumen al 12 %"
        else:
            detalle_volumen = "volumen al 12 % (sin sounds.ini, no se creó)"
        anotar("configuración previa", True,
               f"destino YouTube, título «{titulo}», privacidad unlisted, "
               f"latencia {LATENCIA_PRUEBA}, rebobinar apagado, categoría "
               f"{CATEGORIA_PRUEBA}, etiquetas {ETIQUETAS_PRUEBA}, "
               f"{detalle_miniatura}, panel activado, {detalle_volumen}")
        if not estaba_obs:
            _limpiar_sentinel()
            anotar("OBS sin modo seguro", True, "sentinel limpio")
        else:
            anotar("OBS sin modo seguro", True,
                   "ya estaba abierto, no se toca el sentinel")

        with open(ruta_lanzador, "w", encoding="utf-8") as f:
            f.write(_LANZADOR.format(repo=str(raiz)))
        try:
            ventanas_prueba = _abrir_ventanas_prueba()
            anotar("ventanas de prueba", True,
                   "«Cámara de prueba» y «Aplicación de prueba» abiertas")
        except Exception as exc:
            anotar("ventanas de prueba", False, str(exc))
            return (salida, 1)
        entorno = dict(os.environ,
                       DIRECTO_REAL_ANUNCIOS=ruta_anuncios,
                       DIRECTO_REAL_CHAT=ruta_chat)
        app = subprocess.Popen([sys.executable, ruta_lanzador],
                               cwd=str(raiz), env=entorno)
        try:
            principal = _ventana(APP_NAME, 60)
            time.sleep(4)
            anotar("ventana principal", True, f"pid {app.pid}")
        except RuntimeError as exc:
            anotar("ventana principal", False, str(exc))
            return (salida, 1)

        try:
            _control(principal, "Transmitir en directo", "Button").invoke()
            dialogo = _dialogo_hijo(principal, "Transmitir a", 20)
            destino = _leer_valor(
                _control(dialogo, "Transmitir a", "ComboBox"))
            anotar("diálogo de destino", True, f"destino «{destino}»")
            if "YouTube" not in destino:
                anotar("destino YouTube", False,
                       f"la lista dice «{destino}»")
                return (salida, 1)
            _control(dialogo, "Continuar", "Button").invoke()
        except RuntimeError as exc:
            anotar("diálogo de destino", False, str(exc))
            return (salida, 1)

        try:
            directo = _dialogo_hijo(principal, "Directo de YouTube", 120)
            revision = _leer_valor(
                _control(directo, "Revisión de OBS", "Edit"))
            titulo_campo = _leer_valor(
                _control(directo, "Título del directo", "Edit"))
            privacidad = _leer_valor(
                _control(directo, "Privacidad", "ComboBox"))
            anotar("diálogo del directo", True,
                   f"título «{titulo_campo}», privacidad «{privacidad}», "
                   f"revisión «{revision}»")
            try:
                gestor_obs = _gestor_obs()
                url_panel = (f"http://127.0.0.1:{_puerto_panel(ruta_config)}"
                             f"/chat")
                escena_prueba, creo_panel = _armar_escena_prueba(
                    gestor_obs, url_panel)
                anotar("escena de prueba", True,
                       f"escena «{escena_prueba}» con dos capturas sobre el "
                       f"panel" + (" (panel creado)" if creo_panel else ""))
            except Exception as exc:
                anotar("escena de prueba", False, str(exc))
                return (salida, 1)
            marca = len(_leer_anuncios(ruta_anuncios))
            _control(directo, "Transmitir", "Button").invoke()
            pulso_transmitir = True
        except RuntimeError as exc:
            anotar("diálogo del directo", False, str(exc))
            return (salida, 1)

        resultado = _esperar_anuncio(
            ruta_anuncios, (OK_AL_AIRE,) + ERRORES_AL_AIRE,
            args.timeout_salida, marca)
        if resultado is None:
            anotar("salir al aire", False,
                   f"sin anuncio en {args.timeout_salida} s")
            return (salida, 1)
        if OK_AL_AIRE not in resultado.lower():
            anotar("salir al aire", False, f"la app anunció «{resultado}»")
            return (salida, 1)
        anotar("salir al aire", True, "«ya está al aire»")
        salio_al_aire = True
        id_video = extraer_id_video(_leer_anuncios(ruta_anuncios)[marca:])
        if ANUNCIO_PANEL_ADELANTE in _leer_anuncios(ruta_anuncios)[marca:].lower():
            anotar("panel adelante", True, "la app lo puso adelante")
        else:
            anotar("panel adelante", False,
                   "sin «El panel de chat estaba detrás de» en los anuncios")
            return (salida, 1)

        try:
            cliente, creds = _cliente_youtube()
        except Exception as exc:
            anotar("YouTube espera la señal", False,
                   f"sin cliente API: {exc}")
            return (salida, 1)
        try:
            if not id_video:
                id_video, _, _ = _buscar_video_por_titulo(cliente, titulo)
            _guardar_token_si_renovo(cliente, creds)
        except Exception as exc:
            anotar("YouTube espera la señal", False,
                   f"no se pudo buscar por API: {exc}")
            return (salida, 1)
        if not id_video:
            anotar("YouTube espera la señal", False,
                   "ni los anuncios ni la API dejaron el id: se detiene "
                   "sin tocar nada")
            return (salida, 1)
        enlace_manual = "https://www.youtube.com/watch?v=" + id_video
        try:
            auto_stop = _auto_stop(cliente, id_video)
        except Exception as exc:
            anotar("YouTube espera la señal", False,
                   f"no se pudo leer contentDetails: {exc}")
            return (salida, 1)
        if auto_stop is False:
            anotar("YouTube espera la señal", True,
                   "enableAutoStop en False")
        else:
            anotar("YouTube espera la señal", False,
                   f"enableAutoStop en {auto_stop!r}, se esperaba False")
            return (salida, 1)

        try:
            contenido, snippet = _leer_opciones(cliente, id_video)
            _guardar_token_si_renovo(cliente, creds)
        except Exception as exc:
            anotar("opciones del directo", False,
                   f"no se pudieron leer de la API: {exc}")
            return (salida, 1)
        faltas = faltas_de_opciones(contenido, snippet)
        if faltas:
            anotar("opciones del directo", False,
                   "no llegaron: " + ", ".join(faltas))
            return (salida, 1)
        anotar("opciones del directo", True,
               "latencia ultrabaja, rebobinar apagado y categoría "
               "Educación; las etiquetas no se pueden comprobar por la "
               "API y se revisan en YouTube Studio")
        bien_miniatura, detalle_miniatura = estado_miniatura(
            _leer_anuncios(ruta_anuncios)[marca:])
        anotar("miniatura del directo", bien_miniatura, detalle_miniatura)
        if not bien_miniatura:
            return (salida, 1)

        en_la_lista = False
        error_lista = ""
        fin_lista = time.time() + 30
        while True:
            try:
                en_la_lista = _video_en_lista(cliente, id_lista, id_video)
                _guardar_token_si_renovo(cliente, creds)
                error_lista = ""
            except Exception as exc:
                en_la_lista = False
                error_lista = str(exc)
            if en_la_lista or time.time() >= fin_lista:
                break
            time.sleep(3)
        bien_lista, detalle_lista = estado_lista(
            _leer_anuncios(ruta_anuncios)[marca:], en_la_lista)
        if not bien_lista and error_lista:
            detalle_lista = f"{detalle_lista} ({error_lista})"
        anotar("lista de reproducción", bien_lista, detalle_lista)
        if not bien_lista:
            return (salida, 1)

        marca_chat = len(_leer_anuncios(ruta_anuncios))
        resultado = _esperar_anuncio(ruta_anuncios, (OK_CHAT,),
                                     args.timeout_chat, marca_chat)
        if resultado is None:
            anotar("chat conectado", False,
                   f"sin «Conectado al directo» en {args.timeout_chat} s")
            return (salida, 1)
        anotar("chat conectado", True, "«Conectado al directo»")
        try:
            id_chat = _live_chat_id(cliente, id_video)
        except Exception as exc:
            anotar("comentarios enviados", False,
                   f"no se pudo leer el liveChatId: {exc}")
            return (salida, 1)
        if not id_chat:
            anotar("comentarios enviados", False,
                   "la API no devolvió liveChatId para el vídeo")
            return (salida, 1)
        try:
            for comentario in COMENTARIOS_PRUEBA:
                cliente.enviar_mensaje_live(id_chat, comentario)
            _guardar_token_si_renovo(cliente, creds)
            anotar("comentarios enviados", True,
                   f"{len(COMENTARIOS_PRUEBA)} al chat del directo")
        except Exception as exc:
            anotar("comentarios enviados", False, str(exc))
            return (salida, 1)
        faltante, leidos = _comentario_faltante(ruta_chat, COMENTARIOS_PRUEBA, 30)
        if faltante is None:
            anotar("comentarios en la app", True,
                   "los tres están en la lista del chat")
        else:
            anotar("comentarios en la app", False,
                   f"«{faltante}» no apareció en 30 s "
                   f"({_detalle_lista_chat(leidos)})")
            return (salida, 1)
        from directo_chat import (comprobar_sin_repetidos,
                                  escribir_desde_app, esperar_reconexion,
                                  leer_despues, limitar_corte, paso_corte)

        def _respuesta_chat():
            return cliente._escritura().liveChatMessages().list(
                liveChatId=id_chat, part="snippet",
                maxResults=200).execute()

        texto_app = "Prueba desde la app " + time.strftime("%H:%M:%S")
        marca_envio = len(_leer_anuncios(ruta_anuncios))
        bien, detalle = escribir_desde_app(
            principal, texto_app, ruta_anuncios, marca_envio, _leer_anuncios,
            _esperar_anuncio, _control, _respuesta_chat)
        _guardar_token_si_renovo(cliente, creds)
        anotar("escribir desde la app", bien, detalle)
        if not bien:
            return (salida, 1)
        corte = limitar_corte(args.corte)
        if corte:
            bien, detalle, marca_corte = paso_corte(
                corte, ruta_anuncios, _leer_anuncios)
            anotar("corte de red", bien, detalle)
            if not bien:
                return (salida, 1)
            bien, detalle = esperar_reconexion(
                ruta_anuncios, marca_corte, corte, _leer_anuncios)
            anotar("reconexión del chat", bien, detalle)
            if not bien:
                return (salida, 1)
            texto_despues = ("Comentario después del corte "
                             + time.strftime("%H:%M:%S"))
            bien, detalle = leer_despues(
                cliente, id_chat, ruta_chat, texto_despues,
                _comentario_faltante, _detalle_lista_chat)
            _guardar_token_si_renovo(cliente, creds)
            anotar("leer después del corte", bien, detalle)
            if not bien:
                return (salida, 1)
            texto_app2 = ("Prueba desde la app tras el corte "
                          + time.strftime("%H:%M:%S"))
            marca_envio2 = len(_leer_anuncios(ruta_anuncios))
            bien, detalle = escribir_desde_app(
                principal, texto_app2, ruta_anuncios, marca_envio2,
                _leer_anuncios, _esperar_anuncio, _control, _respuesta_chat)
            _guardar_token_si_renovo(cliente, creds)
            anotar("escribir después del corte", bien, detalle)
            if not bien:
                return (salida, 1)
            bien, detalle = comprobar_sin_repetidos(
                ruta_chat, COMENTARIOS_PRUEBA)
            anotar("sin repetidos", bien, detalle)
            if not bien:
                return (salida, 1)
        time.sleep(max(0, args.duracion))
        anotar("directo al aire", True, f"{args.duracion} s")

        try:
            destino_foto = raiz / "qa" / "salida"
            destino_foto.mkdir(parents=True, exist_ok=True)
            ruta_png = str(destino_foto
                           / f"directo-real-{time.strftime('%H%M%S')}.png")
            pasa, detalle = _comprobar_panel_en_imagen(
                gestor_obs, escena_prueba, ruta_png)
        except Exception as exc:
            anotar("panel visible en la imagen", False, str(exc))
            return (salida, 1)
        anotar("panel visible en la imagen", pasa, detalle)
        if not pasa:
            return (salida, 1)

        try:
            marca_fin = len(_leer_anuncios(ruta_anuncios))
            _control(principal, "Finalizar directo", "Button").invoke()
            confirmacion = _dialogo_hijo(
                principal, "Finalizar directo", 20)
            _control(confirmacion, "Finalizar directo", "Button").invoke()
        except RuntimeError as exc:
            anotar("finalizar directo", False, str(exc))
            return (salida, 1)
        resultado = _esperar_anuncio(ruta_anuncios, OK_FIN,
                                     args.timeout_fin, marca_fin)
        if resultado is None:
            anotar("finalizar directo", False,
                   f"sin «Transmisión detenida» en {args.timeout_fin} s")
            return (salida, 1)
        anotar("finalizar directo", True, "«Transmisión detenida»")

        estado = _esperar_estado(cliente, id_video)
        if estado == "complete":
            finalizado = True
            anotar("YouTube terminó el directo", True, "estado «complete»")
        else:
            anotar("YouTube terminó el directo", False,
                   f"estado «{estado or 'desconocido'}» tras 30 s, "
                   f"bórralo a mano: {enlace_manual}")
            return (salida, 1)
        try:
            borrado, motivo = _borrar_video(cliente, creds, id_video)
        except Exception as exc:
            anotar("borrar el vídeo", False,
                   f"no se pudo borrar, bórralo a mano: {enlace_manual} "
                   f"({exc})")
            return (salida, 1)
        if not borrado:
            anotar("borrar el vídeo", False,
                   f"{motivo}, bórralo a mano: {enlace_manual}")
            return (salida, 1)
        anotar("borrar el vídeo", True, f"id {id_video}")
        borrado_id = id_video
        id_video = ""
        enlace_manual = ""
        return (salida, 0)
    finally:
        id_por_titulo = False
        if not id_video and (salio_al_aire or pulso_transmitir) \
                and not finalizado:
            try:
                cliente_busqueda, creds_busqueda = _cliente_youtube()
                try:
                    hallado, titulo_hallado, privacidad_hallada = \
                        _buscar_video_por_titulo(cliente_busqueda, titulo)
                    _guardar_token_si_renovo(cliente_busqueda, creds_busqueda)
                except Exception:
                    hallado, titulo_hallado, privacidad_hallada = ("", "", "")
                candidato = hallado \
                    if hallado and es_borrable(titulo_hallado,
                                               privacidad_hallada) else ""
                resuelto = id_para_limpiar(
                    id_video, candidato, salio_al_aire or pulso_transmitir)
                if resuelto:
                    id_video = resuelto
                    id_por_titulo = True
                    if not enlace_manual:
                        enlace_manual = "https://www.youtube.com/watch?v=" \
                            + id_video
            except Exception:
                pass
        for paso in pasos_de_limpieza(salio_al_aire, finalizado, id_video,
                                      creo_panel, pulso_transmitir):
            try:
                if paso == "detener_y_finalizar":
                    if gestor_obs is None:
                        try:
                            gestor_obs = _gestor_obs()
                        except Exception:
                            gestor_obs = None
                    try:
                        cliente_fin, creds_fin = _cliente_youtube()
                    except Exception as exc:
                        anotar(paso, False, f"sin cliente API: {exc}")
                        continue
                    bien, detalle = _detener_y_finalizar(
                        gestor_obs, cliente_fin, creds_fin, id_video)
                    if bien:
                        finalizado = True
                    if bien and id_por_titulo:
                        detalle = f"{detalle} (id por título «{titulo}»)"
                    if not bien and not id_video:
                        detalle = (f"{detalle} (se buscó por título "
                                   f"«{titulo}» sin éxito)")
                    anotar(paso, bien, detalle)
                elif paso == "borrar_video":
                    try:
                        cliente_fin, creds_fin = _cliente_youtube()
                    except Exception as exc:
                        anotar(paso, False,
                               "sin cliente API, bórralo a mano: "
                               f"{enlace_manual or id_video} ({exc})")
                        continue
                    try:
                        borrado, motivo = _borrar_video(
                            cliente_fin, creds_fin, id_video)
                    except Exception as exc:
                        anotar(paso, False,
                               "no se pudo borrar, bórralo a mano: "
                               f"{enlace_manual} ({exc})")
                        continue
                    if borrado:
                        detalle_borrado = f"id {id_video} (limpieza)"
                        if id_por_titulo:
                            detalle_borrado = (
                                f"id {id_video} (por título «{titulo}», "
                                f"limpieza)")
                        anotar(paso, True, detalle_borrado)
                        borrado_id = borrado_id or id_video
                        id_video = ""
                        enlace_manual = ""
                    else:
                        anotar(paso, False,
                               f"{motivo}, bórralo a mano: {enlace_manual}")
                elif paso in ("quitar_capturas", "quitar_panel"):
                    if not escena_prueba:
                        anotar(paso, True, "la escena no se llegó a armar")
                        continue
                    if gestor_obs is None:
                        try:
                            gestor_obs = _gestor_obs()
                        except Exception as exc:
                            anotar(paso, False,
                                   f"sin conexión a OBS: {exc}")
                            continue
                    if paso == "quitar_capturas":
                        _quitar_fuente(gestor_obs, escena_prueba,
                                       FUENTE_CAMARA, borrar_entrada=True)
                        _quitar_fuente(gestor_obs, escena_prueba,
                                       FUENTE_APLICACION, borrar_entrada=True)
                        anotar(paso, True,
                               "«Prueba YTChat cámara» y «Prueba YTChat "
                               "aplicación» fuera de la escena")
                    else:
                        from bellbird.obs.obs_panel import NOMBRE_FUENTE
                        _quitar_fuente(gestor_obs, escena_prueba,
                                       NOMBRE_FUENTE)
                        anotar(paso, True,
                               "panel creado fuera de la escena")
                elif paso == "cerrar_ventanas":
                    _cerrar_ventanas_prueba(ventanas_prueba)
                    anotar(paso, True, "ventanas de prueba cerradas")
                elif paso == "cerrar_app_y_restaurar":
                    try:
                        if principal is not None:
                            try:
                                principal.close()
                                # Con sesión abierta la app pregunta «Salir»:
                                # se contesta Sí si aparece y se sigue como
                                # hoy si no aparece. El `kill` de abajo queda
                                # de red de seguridad.
                                contestar_salir_si_aparece(segundos=8.0)
                                time.sleep(8)
                            except Exception:
                                pass
                        if app is not None and app.poll() is None:
                            try:
                                app.kill()
                            except Exception:
                                pass
                        if gestor_obs is not None:
                            try:
                                gestor_obs.cerrar()
                            except Exception:
                                pass
                        if decidir_cerrar_obs(estaba_obs) \
                                and _obs_en_ejecucion():
                            _cerrar_obs()
                    finally:
                        try:
                            shutil.copy2(respaldo, ruta_config)
                        except OSError:
                            pass
                        try:
                            os.remove(respaldo)
                        except OSError:
                            pass
                        _restaurar_sonidos(ruta_sonidos,
                                           respaldo_sonidos, habia_sonidos)
                        try:
                            os.remove(respaldo_sonidos)
                        except OSError:
                            pass
                    anotar(paso, True,
                           "app cerrada, config.ini y sounds.ini "
                           "restaurados")
            except Exception as exc:
                anotar(paso, False, f"falló la limpieza: {exc}")
        if id_lista:
            try:
                cliente_lista, creds_lista = _cliente_youtube()
                borrada, motivo = _borrar_lista(cliente_lista, id_lista)
                _guardar_token_si_renovo(cliente_lista, creds_lista)
            except Exception as exc:
                borrada, motivo = False, str(exc)
            if borrada:
                anotar("borrar la lista", True, f"id {id_lista}")
            else:
                anotar("borrar la lista", False,
                       f"{motivo}, bórrala a mano en YouTube Studio: "
                       f"id {id_lista}")
        anuncios = _leer_anuncios(ruta_anuncios)
        lineas = [f"{nombre}: {'bien' if bien else 'falló'}"
                  + (f" ({detalle})" if detalle else "")
                  for nombre, bien, detalle in salida]
        if borrado_id:
            lineas.append(f"vídeo borrado: bien (id {borrado_id})")
        elif enlace_manual:
            lineas.append(f"vídeo sin borrar: {enlace_manual}")
        texto = "\n".join(lineas) + "\n\n--- anuncios ---\n" + anuncios
        print(texto)
        try:
            destino_dir = raiz / "qa" / "salida"
            destino_dir.mkdir(parents=True, exist_ok=True)
            nombre = "directo_real-" + time.strftime("%Y%m%d-%H%M%S") \
                + ".txt"
            (destino_dir / nombre).write_text(texto, encoding="utf-8")
        except OSError:
            pass
        try:
            if ruta_miniatura:
                try:
                    os.remove(ruta_miniatura)
                except OSError:
                    pass
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _ayuda().parse_args(argv)
    _, codigo = _correr(args)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
