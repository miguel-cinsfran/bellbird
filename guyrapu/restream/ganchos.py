"""Ganchos para transmitir con un perfil de Restream.

Lee los canales de la cuenta, prepara los canales y el perfil de OBS antes
de que el supervisor inicie la transmisión, elige el destino y el usuario
con los que se crea el supervisor, y devuelve los canales a su estado
anterior al terminar. Sin wx en el módulo: lo que toca la interfaz se pide
al frame.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from guyrapu.core import diagnostico
from guyrapu.core.idioma import N_, _
from guyrapu.obs import obs_destinos
from guyrapu.restream import transmitir
from guyrapu.youtube.emision import EmisionError

logger = diagnostico.obtener_logger(__name__)

MENSAJE_SIN_CUENTA = N_(
    "Para transmitir con un perfil de Restream hace falta conectar la "
    "cuenta, en el cuadro Restream, pestaña Cuenta.")
MENSAJE_PREPARANDO = N_("Preparando Restream para {nombre}.")
MENSAJE_NO_TIKTOK = N_(
    "Directo iniciado con Restream. Conecta el chat manualmente.")


@dataclass
class Contexto:
    """El destino y el usuario con los que se crea el supervisor."""

    destino: str = ""
    usuario: str = ""


class Restaurador:
    """Devuelve los canales cambiados a su estado anterior, de a uno."""

    def __init__(self, cuenta_mod):
        self._cuenta = cuenta_mod
        self._cambios = []
        self._candado = threading.Lock()

    def anotar(self, cambio) -> None:
        with self._candado:
            self._cambios.append(cambio)

    def restaurar(self) -> None:
        with self._candado:
            cambios, self._cambios = self._cambios, []
        for cambio in cambios:
            try:
                self._cuenta.activar_canal(cambio.canal_id, cambio.antes)
            except Exception as error:
                logger.warning(
                    "no se pudo restaurar el canal %s de Restream: %s",
                    cambio.canal_id, error)


def _cuenta():
    from guyrapu.restream import cuenta as modulo
    return modulo


def cuenta_conectada(cuenta_mod=None) -> bool:
    """¿Hay una cuenta de Restream conectada en esta instalación?"""
    try:
        return bool((cuenta_mod or _cuenta()).sesion().conectada())
    except Exception:
        return False


def cargar_perfiles():
    """Los perfiles guardados, en el orden de `perfiles_restream.json`."""
    from guyrapu.core import paths
    from guyrapu.restream import perfiles as modulo
    return modulo.cargar(paths.perfiles_restream())


def destino_de_opcion(opcion, perfiles=None) -> str:
    """El perfil de OBS de una opción, con los perfiles ya leídos o no."""
    lista = perfiles if perfiles is not None else cargar_perfiles()
    return transmitir.destino_obs(opcion, lista)


def _aplicar_cambios(perfil, canales, cuenta_mod, restaurador) -> None:
    for cambio in transmitir.plan_canales(perfil, canales):
        cuenta_mod.activar_canal(cambio.canal_id, cambio.activo)
        restaurador.anotar(cambio)


def _cambiar_titulo(perfil, canales, cuenta_mod) -> None:
    if not perfil.titulo:
        return
    for canal in transmitir.canales_del_perfil(perfil, canales):
        cuenta_mod.cambiar_meta(canal.id, perfil.titulo, perfil.descripcion)


def _preparar_emision(perfil, canales, al_anunciar, cuenta_mod, restaurador,
                      escribir):
    def preparar(cliente, parada=None):
        al_anunciar(_(MENSAJE_PREPARANDO).format(nombre=perfil.nombre),
                    "conectando")
        try:
            _aplicar_cambios(perfil, canales, cuenta_mod, restaurador)
            _cambiar_titulo(perfil, canales, cuenta_mod)
            clave = cuenta_mod.clave_cuenta()
            destino = transmitir.destino_obs(
                transmitir.PREFIJO + perfil.nombre, (perfil,))
            escribir(cliente, obs_destinos.Destino(
                destino, clave.servidor, clave.clave), parada=parada)
        except Exception as error:
            restaurador.restaurar()
            raise EmisionError(str(error)) from error
        return None
    return preparar


def armar(opcion, al_anunciar, canales, cuenta_mod=None, perfiles=None,
          escribir=None):
    """Arma el gancho de preparación y la restauración de una opción.

    Los canales ya vienen leídos por el hilo que arma la transmisión.
    Devuelve `(preparar_emision, restaurar)`.
    """
    modulo_cuenta = cuenta_mod or _cuenta()
    lista = perfiles if perfiles is not None else cargar_perfiles()
    perfil = transmitir.perfil_de_opcion(opcion, lista)
    restaurador = Restaurador(modulo_cuenta)
    preparar = _preparar_emision(
        perfil, canales, al_anunciar, modulo_cuenta, restaurador,
        escribir or obs_destinos.preparar_destino)
    return preparar, restaurador.restaurar


def envolver_anunciar(al_anunciar, contexto):
    """Ajusta los avisos del supervisor para un perfil de Restream."""
    def anunciar(frase, sonido, importante=False):
        if not sonido and frase == _("Creando el directo en YouTube."):
            return
        al_anunciar(frase, sonido, importante)
        if contexto.destino == "Restream" and sonido == "conectado":
            al_anunciar(_(MENSAJE_NO_TIKTOK), "al_aire", True)
    return anunciar


def _anunciar_de_frame(frame):
    def al_anunciar(frase, sonido, importante=False):
        from guyrapu.ui import gui as _gui
        from guyrapu.ui.aviso_importante import avisar

        def _decir():
            if not getattr(frame, "_alive", True):
                return
            if importante:
                avisar(frase, sonido,
                       error=sonido in ("error", "transmision_problema"))
                return
            if sonido:
                _gui._snd.reproducir(sonido)
            _gui.anunciar(frase)
        _gui.wx.CallAfter(_decir)
    return al_anunciar


def _conectar_chat(frame):
    def al_conectar_chat(url):
        from guyrapu.ui import gui as _gui

        def _conectar():
            if not getattr(frame, "_alive", True):
                return
            if frame._conectado or frame._conectando:
                _gui.anunciar(
                    _("El chat ya estaba conectado y no se cambió."))
                return
            try:
                frame.txt_url.SetValue(url)
            except Exception as error:
                logger.debug("no se pudo mostrar la dirección: %s", error)
            frame.sesion.conexion_propia = True
            frame._on_conectar(None)
        _gui.wx.CallAfter(_conectar)
    return al_conectar_chat


def _al_terminar(frame, restaurar):
    def al_terminar():
        try:
            frame._al_terminar_supervisor()
        finally:
            diagnostico.crear_hilo(
                restaurar, "RestaurarRestream").start()
    return al_terminar


def _en_interfaz(frame, funcion, *args):
    if not getattr(frame, "_alive", True):
        return
    from guyrapu.ui import gui as _gui
    _gui.wx.CallAfter(funcion, *args)


def _destino_supervisor(perfil, canales):
    usuario = transmitir.usuario_tiktok(perfil, canales)
    return ("TikTok", usuario) if usuario else ("Restream", "")


def _crear_supervisor(frame, modulo_cuenta, opcion, lista, perfil, destino,
                      usuario, canales):
    from guyrapu.core import paths
    from guyrapu.obs.obs_supervisor import SupervisorTransmision

    if not getattr(frame, "_alive", True):
        return
    contexto = Contexto(destino=destino, usuario=usuario)
    al_anunciar = _anunciar_de_frame(frame)
    envoltura = envolver_anunciar(al_anunciar, contexto)
    preparar, restaurar = armar(
        opcion, envoltura, canales, cuenta_mod=modulo_cuenta, perfiles=lista)
    supervisor = SupervisorTransmision(
        destino, usuario,
        al_anunciar=envoltura,
        al_conectar_chat=_conectar_chat(frame),
        al_terminar=_al_terminar(frame, restaurar),
        ruta_fin_pendiente=paths.fin_pendiente(),
        **_parametros_supervisor(frame, envoltura),
        preparar_emision=preparar)
    frame._supervisor = supervisor
    supervisor.iniciar()
    frame._actualizar_boton_directo()


def _leer_canales(frame, modulo_cuenta, opcion, lista, perfil):
    try:
        canales = modulo_cuenta.canales()
    except Exception as error:
        _anunciar_de_frame(frame)(str(error), "transmision_problema")
        return
    destino, usuario = _destino_supervisor(perfil, canales)
    _en_interfaz(frame, _crear_supervisor, frame, modulo_cuenta, opcion,
                 lista, perfil, destino, usuario, canales)


def supervisar_restream(frame, opcion, revision=None, cuenta_mod=None) -> None:
    """Lee los canales y crea el supervisor con el destino ya elegido."""
    del revision
    modulo_cuenta = cuenta_mod or _cuenta()
    if not cuenta_conectada(modulo_cuenta):
        _anunciar_de_frame(frame)(_(MENSAJE_SIN_CUENTA),
                                  "transmision_problema", True)
        return
    lista = cargar_perfiles()
    perfil = transmitir.perfil_de_opcion(opcion, lista)
    if perfil is None:
        _anunciar_de_frame(frame)(
            _("Elige primero a dónde transmitir, en Transmitir a."),
            "transmision_problema", True)
        return
    diagnostico.crear_hilo(
        lambda: _leer_canales(frame, modulo_cuenta, opcion, lista, perfil),
        "PrepararRestream").start()


def _parametros_supervisor(frame, al_anunciar):
    from guyrapu.ui import gui_transmitir
    return gui_transmitir._parametros_supervisor(frame, al_anunciar)
