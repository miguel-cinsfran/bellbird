"""Directo real de prueba de punta a punta, para correr a mano.

Hace un directo de YouTube «No listado» de alrededor de un minuto desde
la aplicación real, conducida por UI Automation (Invoke, sin teclas),
comprueba cada paso, lo finaliza, BORRA el vídeo del canal y deja la
configuración y OBS como estaban.

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

PREFIJO_TITULO = "Prueba de YTChat"
PRIVACIDAD_ESPERADA = "unlisted"
DESCRIPCION_PRUEBA = (
    "Directo de prueba de YTChat, se borra al terminar."
)

# Fragmentos que anuncian un error al salir al aire, en vez del éxito.
ERRORES_AL_AIRE = ("no se pudo", "error", "falló", "no tiene")
OK_AL_AIRE = "ya está al aire"
OK_CHAT = "conectado al directo"
OK_FIN = ("detenid", "finaliz", "terminó")


def armar_titulo(hora: str) -> str:
    """Título de la prueba con la hora, para encontrarlo después por API."""
    return f"{PREFIJO_TITULO} {(hora or '').strip()}".strip()


def es_borrable(titulo: str, privacidad: str) -> bool:
    """Solo se borra lo que la herramienta creó: título propio y no listado."""
    return (titulo or "").startswith(PREFIJO_TITULO) \
        and (privacidad or "") == PRIVACIDAD_ESPERADA


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


def decidir_cerrar_obs(estaba_abierto: bool) -> bool:
    """Si OBS ya estaba abierto no se lo cierra; si lo abrió la app, sí."""
    return not bool(estaba_abierto)


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
    return parser


# -- Impuro: archivos, procesos, UI Automation y API. Fuera de las pruebas. --

_LANZADOR = """\
import os, sys, time
REPO = {repo!r}
LOG = os.environ.get("DIRECTO_REAL_ANUNCIOS", "")
sys.path.insert(0, REPO)
os.chdir(REPO)
sys.argv = [os.path.join(REPO, "main.py")]
import ytchat.ui.gui as g
_orig = g.anunciar

def _anunciar(texto, urgente=True):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(texto) + "\\n")
    except OSError:
        pass
    _orig(texto, urgente)

g.anunciar = _anunciar
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
    from ytchat.core import paths  # noqa: F401  (raíz del paquete)
    from ytchat.youtube import credenciales, youtube_api
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


def _correr(args) -> tuple[list[tuple[str, bool, str]], int]:
    from ytchat.core import config, paths
    from ytchat.youtube import credenciales

    pasos: list[tuple[str, bool, str]] = []

    def anotar(nombre: str, bien: bool, detalle: str = "") -> None:
        pasos.append((nombre, bien, detalle))

    if not credenciales.hay_sesion():
        print("Sin sesión de Google iniciada: inicia sesión en la "
              "aplicación y vuelve a correr esta herramienta.")
        return ([("sesión de Google", False, "sin token")], 2)

    raiz = paths.carpeta_instalacion()
    ruta_config = paths.config_ini()
    respaldo = tempfile.mktemp(prefix="directo-real-config-",
                                suffix=".ini")
    try:
        shutil.copy2(ruta_config, respaldo)
    except OSError as exc:
        print(f"No se pudo respaldar config.ini: {exc}")
        return ([("respaldo de config.ini", False, str(exc))], 2)

    hora = time.strftime("%H:%M")
    titulo = armar_titulo(hora)
    tmpdir = tempfile.mkdtemp(prefix="directo-real-")
    ruta_anuncios = os.path.join(tmpdir, "anuncios.txt")
    ruta_lanzador = os.path.join(tmpdir, "app_directo_real.py")
    open(ruta_anuncios, "w").close()
    salida: list[tuple[str, bool, str]] = pasos
    app = None
    principal = None
    estaba_obs = _obs_en_ejecucion()
    id_video = ""
    borrado = False
    enlace_manual = ""

    try:
        from ytchat.core.config import codificar_texto_ini
        config.guardar_opcion(ruta_config, "transmision", "destino",
                              "YouTube")
        config.guardar_opcion(ruta_config, "transmision", "youtube_titulo",
                              codificar_texto_ini(titulo))
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_descripcion",
                              codificar_texto_ini(DESCRIPCION_PRUEBA))
        config.guardar_opcion(ruta_config, "transmision",
                              "youtube_privacidad", PRIVACIDAD_ESPERADA)
        anotar("configuración previa", True,
               f"destino YouTube, título «{titulo}», privacidad unlisted")
        if not estaba_obs:
            _limpiar_sentinel()
            anotar("OBS sin modo seguro", True, "sentinel limpio")
        else:
            anotar("OBS sin modo seguro", True,
                   "ya estaba abierto, no se toca el sentinel")

        with open(ruta_lanzador, "w", encoding="utf-8") as f:
            f.write(_LANZADOR.format(repo=str(raiz)))
        entorno = dict(os.environ,
                       DIRECTO_REAL_ANUNCIOS=ruta_anuncios)
        app = subprocess.Popen([sys.executable, ruta_lanzador],
                               cwd=str(raiz), env=entorno)
        try:
            principal = _ventana("YTChat TTS", 60)
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
            marca = len(_leer_anuncios(ruta_anuncios))
            _control(directo, "Transmitir", "Button").invoke()
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
        id_video = extraer_id_video(_leer_anuncios(ruta_anuncios)[marca:])

        marca_chat = len(_leer_anuncios(ruta_anuncios))
        resultado = _esperar_anuncio(ruta_anuncios, (OK_CHAT,),
                                     args.timeout_chat, marca_chat)
        if resultado is None:
            anotar("chat conectado", False,
                   f"sin «Conectado al directo» en {args.timeout_chat} s")
            return (salida, 1)
        anotar("chat conectado", True, "«Conectado al directo»")
        time.sleep(max(0, args.duracion))
        anotar("directo al aire", True, f"{args.duracion} s")

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

        try:
            cliente, creds = _cliente_youtube()
        except Exception as exc:
            anotar("borrar el vídeo", False, f"sin cliente API: {exc}")
            return (salida, 1)
        try:
            if not id_video:
                id_video, _, _ = _buscar_video_por_titulo(cliente, titulo)
            _guardar_token_si_renovo(cliente, creds)
        except Exception as exc:
            anotar("borrar el vídeo", False,
                   f"no se pudo buscar por API: {exc}")
            return (salida, 1)
        if not id_video:
            anotar("borrar el vídeo", False,
                   "ni los anuncios ni la API dejaron el id: se detiene "
                   "sin tocar nada")
            return (salida, 1)
        enlace_manual = "https://www.youtube.com/watch?v=" + id_video
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
        return (salida, 0)
    finally:
        try:
            if principal is not None:
                try:
                    principal.close()
                    time.sleep(8)
                except Exception:
                    pass
            if app is not None and app.poll() is None:
                try:
                    app.kill()
                except Exception:
                    pass
            if decidir_cerrar_obs(estaba_obs) and _obs_en_ejecucion():
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
        anuncios = _leer_anuncios(ruta_anuncios)
        lineas = [f"{nombre}: {'bien' if bien else 'falló'}"
                  + (f" ({detalle})" if detalle else "")
                  for nombre, bien, detalle in salida]
        if borrado:
            lineas.append(f"vídeo borrado: bien (id {id_video})")
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
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _ayuda().parse_args(argv)
    _, codigo = _correr(args)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
