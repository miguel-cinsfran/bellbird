"""Localiza y abre OBS solo cuando hace falta, sin robar el foco."""

import os
import subprocess
import time

from ytchat.core import subprocesos
from ytchat.core.idioma import N_, _
from ytchat.obs import obs_activacion
from ytchat.obs import obs_cliente


TEXTO_ABRIENDO = N_("Abriendo OBS en segundo plano, en el área de "
                    "notificación. Puede tardar hasta un minuto.")
TEXTO_MODO_SEGURO = N_("OBS se cerró mal la última vez y va a preguntar si "
                       "iniciar en modo seguro. Elige Mostrar OBS en el menú "
                       "Transmisión y después iniciar normalmente.")
TEXTO_SIN_RESPUESTA = N_("OBS se abrió pero no responde. Comprueba que su "
                         "servidor websocket esté activado.")
TEXTO_SIN_RESPUESTA_MODO_SEGURO = N_(
    "OBS no responde. Puede estar esperando que contestes si iniciar "
    "en modo seguro: elige Mostrar OBS en el menú Transmisión.")

_CLAVE_OBS = r"SOFTWARE\OBS Studio"
_CLAVE_OBS_32 = r"SOFTWARE\WOW6432Node\OBS Studio"
_EJECUTABLE = os.path.join("bin", "64bit", "obs64.exe")


class ObsNoInstalado(obs_cliente.ObsError):
    """OBS no está instalado en este equipo."""


def _leer_registro_por_defecto(clave):
    """Lee el valor predeterminado de una clave de OBS o devuelve None."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, clave) as subclave:
            valor, _sin_uso = winreg.QueryValueEx(subclave, "")
            return str(valor) if valor else None
    except (OSError, ValueError):
        return None


def ruta_obs(leer_registro=None, existe=os.path.isfile, entorno=os.environ):
    """Devuelve la ruta de obs64.exe o "" si no se encuentra."""
    leer = leer_registro or _leer_registro_por_defecto
    for clave in (_CLAVE_OBS, _CLAVE_OBS_32):
        try:
            base = leer(clave)
        except Exception:
            base = None
        if base:
            ruta = os.path.join(base, _EJECUTABLE)
            if existe(ruta):
                return ruta
    program_files = entorno.get("ProgramFiles", "")
    if program_files:
        ruta = os.path.join(program_files, "obs-studio", _EJECUTABLE)
        if existe(ruta):
            return ruta
    return ""


def cierre_incorrecto_previo(carpeta=None, listar=os.listdir):
    """Dice si OBS se cerró mal antes, por sus archivos sentinel run_*.

    True si hay algún archivo cuyo nombre empieza con «run_» en la
    carpeta `%APPDATA%\\obs-studio\\.sentinel`. Carpeta inexistente o
    ilegible da False, para no frenar la apertura por avisar."""
    if carpeta is None:
        carpeta = os.path.join(os.environ.get("APPDATA", ""),
                               "obs-studio", ".sentinel")
    try:
        nombres = listar(carpeta)
    except (OSError, ValueError):
        return False
    return any(str(nombre).startswith("run_") for nombre in nombres)


def abrir_obs(ruta, popen=subprocess.Popen):
    """Abre OBS minimizado y sin activarse; no espera ni guarda el proceso."""
    carpeta = os.path.dirname(ruta)
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 7
    try:
        # OBS no trae VCRUNTIME ni MSVCP en su carpeta: sin esto las busca
        # en la _internal heredada del cargador y deja archivos en uso.
        with subprocesos.sin_carpeta_dll_heredada():
            # La ventana minimizada igual se activa sola al terminar de cargar.
            popen([ruta, "--disable-shutdown-check", "--minimize-to-tray"],
                  cwd=carpeta, startupinfo=info,
                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as error:
        raise obs_cliente.ObsError(_("No se pudo abrir OBS.")) from error


def asegurar_obs(probar_conexion, al_anunciar=None, parada=None,
                 en_ejecucion=obs_activacion.obs_esta_en_ejecucion,
                 buscar=ruta_obs, abrir=abrir_obs,
                 dormir=time.sleep, reloj=time.monotonic,
                 limite=120.0, intervalo=2.0,
                 hubo_cierre_incorrecto=cierre_incorrecto_previo):
    """Abre OBS si no corre y espera a que su websocket responda."""
    if parada is not None and parada.is_set():
        return True
    if en_ejecucion():
        return False
    ruta = buscar()
    if not ruta:
        raise ObsNoInstalado(_("OBS no está instalado en este equipo. "
                               "Instálalo desde obsproject.com y vuelve a "
                               "intentarlo."))
    modo_seguro = bool(hubo_cierre_incorrecto())
    if al_anunciar is not None:
        al_anunciar(_(TEXTO_ABRIENDO))
        if modo_seguro:
            al_anunciar(_(TEXTO_MODO_SEGURO))
    abrir(ruta)
    inicio = reloj()
    while True:
        if parada is not None and parada.is_set():
            return True
        try:
            probar_conexion()
            return True
        except Exception:
            pass
        if reloj() - inicio >= limite:
            if modo_seguro:
                raise obs_cliente.ObsError(_(TEXTO_SIN_RESPUESTA_MODO_SEGURO))
            raise obs_cliente.ObsError(_(TEXTO_SIN_RESPUESTA))
        if parada is not None and dormir is time.sleep:
            parada.wait(intervalo)
        else:
            dormir(intervalo)
