"""Video de verificación de youtube.force-ssl: copia, graba, conduce y limpia."""

from __future__ import annotations

import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

import directo_real as dr  # noqa: E402
import video_chrome  # noqa: E402
import video_consentimiento  # noqa: E402
import video_montaje as montaje  # noqa: E402
from conducir import contestar_salir_si_aparece  # noqa: E402
from video_recorrido import (  # noqa: E402
    DEMO_PRIVACIDAD, DEMO_TITULO, Corte, FalloPaso, Recorrido,
    cliente_de_la_copia, consentir, iniciar, minimizar_consola, paso_de,
    por_el_directo, ventana_principal,
)

SALIDA = RAIZ / "qa" / "salida" / "video"
NOMBRE_VIDEO = "guyrapu-force-ssl.mp4"
_SIN_GUARDAR = SimpleNamespace(guardar_campo=lambda *args: None)


def _no_molestar():
    from pywinauto import Desktop
    for ventana in Desktop(backend="uia").windows():
        try:
            for control in ventana.descendants():
                try:
                    if control.element_info.control_type != "Button":
                        continue
                    rotulo = (control.window_text() or "").strip().lower()
                except Exception:
                    continue
                if rotulo in ("no molestar", "do not disturb"):
                    return control
        except Exception:
            pass
    return None


def _estado_interruptor(control):
    try:
        return control.get_toggle_state()
    except Exception:
        return control.iface_toggle.CurrentToggleState


def _alternar_interruptor(control):
    try:
        control.toggle()
    except Exception:
        control.iface_toggle.Toggle()


def _abrir_no_molestar():
    from pywinauto import keyboard
    keyboard.send_keys("{VK_LWIN down}n{VK_LWIN up}")
    time.sleep(2)
    control = _no_molestar()
    if control is None:
        keyboard.send_keys("{ESC}")
        raise RuntimeError("no se encontró No molestar")
    return control


def encender_no_molestar():
    from pywinauto import keyboard
    control = _abrir_no_molestar()
    encendido = False
    if _estado_interruptor(control) == 0:
        _alternar_interruptor(control)
        if _estado_interruptor(control) != 1:
            keyboard.send_keys("{ESC}")
            raise RuntimeError("No molestar no quedó encendido")
        encendido = True
    keyboard.send_keys("{ESC}")
    return encendido


def restaurar_no_molestar(encendido):
    if not encendido:
        return
    from pywinauto import keyboard
    control = _abrir_no_molestar()
    if _estado_interruptor(control) == 1:
        _alternar_interruptor(control)
        if _estado_interruptor(control) != 0:
            keyboard.send_keys("{ESC}")
            raise RuntimeError("No molestar no quedó apagado")
    keyboard.send_keys("{ESC}")


def copiar_programa(destino) -> None:
    def ignorar(directorio, nombres):
        ruta = Path(directorio)
        fuera = set()
        if ruta == RAIZ:
            fuera.update({"data", ".venv", ".git"})
        if ruta == RAIZ / "qa":
            fuera.add("salida")
        fuera.update(n for n in nombres if n == "__pycache__")
        return fuera

    shutil.copytree(RAIZ, destino, ignore=ignorar)
    # El programa no crea `data` en un primer arranque: vacía, la copia
    # empieza sin sesión y la que se inicie en el video queda solo ahí.
    (Path(destino) / "data").mkdir()
    (Path(destino) / "data" / "config.ini").write_text(
        "[ui]\nautoplay_reproductor = false\n", encoding="utf-8")


def _lanzar(copia, anuncios, chat):
    ruta = Path(copia).parent / "lanzador_video.py"
    ruta.write_text(dr._LANZADOR.format(repo=str(copia)), encoding="utf-8")
    entorno = dict(os.environ, GUYRAPU_IDIOMA="en",
                   DIRECTO_REAL_ANUNCIOS=str(anuncios),
                   DIRECTO_REAL_CHAT=str(chat))
    return subprocess.Popen([sys.executable, str(ruta)],
                            cwd=str(copia), env=entorno)


def _empezar_grabacion(salida):
    return subprocess.Popen(montaje.args_grabacion(str(salida)),
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _parar_grabacion(proceso) -> None:
    if proceso is None or proceso.poll() is not None:
        return
    try:
        proceso.stdin.write(b"q")
        proceso.stdin.flush()
        proceso.wait(20)
    except Exception:
        try:
            proceso.kill()
        except Exception:
            pass


def _ffmpeg(argumentos, cwd=None) -> None:
    subprocess.run(argumentos, check=True, capture_output=True, cwd=cwd)


def _montar(rec, portada, grabacion, video) -> None:
    tmp = Path(portada).parent
    unido = tmp / "unido.mp4"
    _ffmpeg(montaje.args_portada(str(portada), montaje.PORTADA,
                                 montaje.PORTADA_SEGUNDOS))
    _ffmpeg(montaje.args_unir(str(portada), str(grabacion), str(unido)))
    (tmp / "subtitulos.srt").write_text(
        montaje.armar_srt(rec.pasos, montaje.PORTADA_SEGUNDOS),
        encoding="utf-8")
    _ffmpeg(montaje.args_quemar(str(unido), "subtitulos.srt", str(video)),
            cwd=str(tmp))


def _duracion(ruta) -> float:
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)],
        capture_output=True, text=True, check=True)
    return float((salida.stdout or "0").strip())


def _sacar_cuadros(rec, video, carpeta) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    _ffmpeg(montaje.args_cuadro(str(video), 1.0,
                                str(carpeta / "0.png")))
    for paso in rec.pasos:
        medio = ((paso["inicio"] + paso["fin"]) / 2
                 + montaje.PORTADA_SEGUNDOS)
        _ffmpeg(montaje.args_cuadro(
            str(video), medio, str(carpeta / f"{paso['numero']}.png")))


def _captura_error(paso: int) -> None:
    try:
        _ffmpeg(montaje.args_captura_pantalla(
            str(SALIDA / f"error-{paso}.png")))
    except Exception:
        pass


def _borrar(cliente, id_video) -> None:
    try:
        titulo, privacidad = dr._datos_video(cliente, id_video)
        if titulo != DEMO_TITULO or privacidad != DEMO_PRIVACIDAD:
            print(f"No se borra el video {id_video}: no es el de la prueba")
            return
        cliente._escritura().videos().delete(id=id_video).execute()
        print(f"Video borrado: {id_video}")
    except Exception as exc:
        print(f"No se pudo borrar el video {id_video}: {type(exc).__name__}: {exc!r}")


def _limpiar(estado) -> None:
    cliente = estado.get("cliente")
    id_video = estado.get("id_video")
    if not id_video and estado.get("pulso") and cliente is not None:
        try:
            hallado, titulo, privacidad = dr._buscar_video_por_titulo(
                cliente, DEMO_TITULO)
        except Exception:
            hallado, titulo, privacidad = ("", "", "")
        if hallado and hallado not in estado.get("previos", set()) \
                and titulo == DEMO_TITULO and privacidad == DEMO_PRIVACIDAD:
            id_video = hallado
    if id_video:
        if not estado.get("finalizado"):
            gestor = None
            try:
                gestor = dr._gestor_obs()
            except Exception:
                pass
            dr._detener_y_finalizar(gestor, cliente, _SIN_GUARDAR, id_video)
            if gestor is not None:
                gestor.cerrar()
        _borrar(cliente, id_video)
    video_consentimiento.revocar_token(estado.get("programa"))
    try:
        if estado.get("chrome") is not None:
            video_chrome.cerrar_pestana(estado["chrome"], 1)
    except Exception:
        pass
    principal = estado.get("principal")
    if principal is not None:
        try:
            principal.close()
        except Exception:
            pass
        try:
            contestar_salir_si_aparece(segundos=6.0)
        except Exception:
            pass
    app = estado.get("app")
    if app is not None and app.poll() is None:
        try:
            app.kill()
        except Exception:
            pass
    copia = estado.get("copia")
    if copia and Path(copia).exists():
        shutil.rmtree(copia, ignore_errors=True)


def _cerrar(estado, rec, grabacion, no_molestar, hasta=None) -> None:
    rec = rec or estado.get("rec")
    grabacion = grabacion or estado.get("grabacion")
    if rec is not None:
        rec.terminar()
    _parar_grabacion(grabacion)
    if hasta is not None:
        try:
            shutil.copy2(Path(estado["copia"]) / "grabacion.mp4",
                         SALIDA / "crudo.mkv")
        except Exception as exc:
            print(f"Sin crudo: {type(exc).__name__}: {exc!r}")
    try:
        _limpiar(estado)
    finally:
        try:
            restaurar_no_molestar(no_molestar)
        except Exception as exc:
            print(f"No se pudo restaurar No molestar: "
                  f"{type(exc).__name__}: {exc!r}")


def _comprobar_autoplay(programa) -> None:
    ruta = Path(programa) / "data" / "config.ini"
    parser = configparser.ConfigParser()
    try:
        parser.read(ruta, encoding="utf-8")
        valor = parser.get("ui", "autoplay_reproductor", fallback="")
    except Exception as exc:
        raise FalloPaso(0, f"no se pudo leer config.ini: "
                           f"{type(exc).__name__}: {exc!r}") from exc
    if valor.strip().lower() != "false":
        raise FalloPaso(0, f"config.ini quedó con "
                           f"autoplay_reproductor = {valor!r}")


def _preparar(estado, anuncios, chat):
    copiar_programa(estado["programa"])
    estado["grabacion"] = grabacion = _empezar_grabacion(
        Path(estado["copia"]) / "grabacion.mp4")
    estado["rec"] = rec = Recorrido()
    estado["app"] = _lanzar(estado["programa"], anuncios, chat)
    estado["principal"] = principal = ventana_principal(90)
    principal.maximize()
    time.sleep(4)
    _comprobar_autoplay(estado["programa"])
    return rec, grabacion, principal


def _corta(rec, hasta, numero) -> None:
    if hasta is not None and numero >= hasta:
        raise Corte()


def _sesion(principal, rec, programa, hasta, estado) -> None:
    prefs = iniciar(principal, rec)
    try:
        _corta(rec, hasta, 1)
        chrome = video_chrome.ventana_de_google(90)
        with paso_de(rec, 2):
            chrome.maximize()
            video_consentimiento.comprobar_burbuja(chrome, 2)
        _corta(rec, hasta, 2)
        estado["permiso_ya_dado"] = consentir(
            chrome, programa / "data", rec)
        _corta(rec, hasta, 3)
    finally:
        try:
            prefs.close()
        except Exception:
            pass


def codigo_de_salida(codigo: int, permiso_ya_dado: bool) -> int:
    if permiso_ya_dado:
        return codigo or 2
    return codigo


def _correr(hasta=None) -> int:
    minimizar_consola()
    SALIDA.mkdir(parents=True, exist_ok=True)
    trabajo = Path(tempfile.mkdtemp(prefix="guyrapu-video-"))
    programa = trabajo / "programa"
    anuncios = trabajo / "video_anuncios.txt"
    chat = trabajo / "video_chat.txt"
    anuncios.write_text("", encoding="utf-8")
    chat.write_text("", encoding="utf-8")
    estado = {"copia": str(trabajo), "programa": str(programa),
              "previos": set(), "pulso": False, "finalizado": False}
    grabacion = rec = None
    codigo = 0
    no_molestar = False
    try:
        no_molestar = encender_no_molestar()
        estado["chrome"] = video_chrome.preparar_chrome()
        rec, grabacion, principal = _preparar(estado, anuncios, chat)
        _sesion(principal, rec, programa, hasta, estado)
        estado["cliente"] = cliente_de_la_copia(programa)
        por_el_directo(principal, rec, anuncios, chat, estado, hasta)
        _parar_grabacion(grabacion)
        grabacion = None
        video = SALIDA / NOMBRE_VIDEO
        _montar(rec, trabajo / "portada.mp4",
                trabajo / "grabacion.mp4", video)
        segundos = _duracion(video)
        if not 180.0 <= segundos <= 300.0:
            raise FalloPaso(10, f"el video dura {segundos:.0f} s")
        _sacar_cuadros(rec, video, SALIDA / "cuadros")
    except Corte:
        print(f"Corte pedido después del paso {rec.ultimo}")
    except FalloPaso as exc:
        codigo = 1
        print(f"FALLÓ {exc} ({type(exc).__name__}: {exc!r})")
        _captura_error(exc.paso)
    except Exception as exc:
        codigo = 1
        paso = rec.ultimo if rec is not None else 0
        print(f"FALLÓ el paso {paso}: {type(exc).__name__}: {exc!r}")
        _captura_error(paso)
    finally:
        _cerrar(estado, rec, grabacion, no_molestar, hasta)
    ya_dado = estado.get("permiso_ya_dado", False)
    codigo = codigo_de_salida(codigo, ya_dado)
    if ya_dado:
        print(video_consentimiento.AVISO_PERMISO)
    return codigo


def main(argv=None) -> int:
    analizador = argparse.ArgumentParser(description="Video de force-ssl.")
    analizador.add_argument("--hasta", type=int, choices=range(1, 11),
                            help="corta y limpia")
    return _correr(analizador.parse_args(argv).hasta)


if __name__ == "__main__":
    sys.exit(main())
