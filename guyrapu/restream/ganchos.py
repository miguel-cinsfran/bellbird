"""Ganchos para transmitir con un perfil de Restream.

Prepara los canales de la cuenta y el perfil de OBS antes de que el
supervisor inicie la transmisión, elige el destino y el usuario con los que
el supervisor confirma el chat, y devuelve los canales a su estado anterior
al terminar. Sin wx en el módulo: lo que toca la interfaz se pide al frame.
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
    """Lo que el gancho descubre y el supervisor necesita después."""

    supervisor: object = None
    destino: str = ""
    usuario: str = ""
    sin_tiktok: bool = False
    destino_sup: str = ""
    omitir_siguiente: bool = False


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


def _elegir_supervisor(perfil, canales, contexto) -> None:
    tiene_tiktok = any(
        canal.plataforma == "TikTok"
        for canal in transmitir.canales_del_perfil(perfil, canales))
    usuario = transmitir.usuario_tiktok(perfil, canales)
    if tiene_tiktok:
        destino = "TikTok"
    else:
        destino = transmitir.destino_obs(
            transmitir.PREFIJO + perfil.nombre, (perfil,))
    contexto.destino = destino
    contexto.usuario = usuario
    contexto.sin_tiktok = not usuario
    contexto.destino_sup = destino
    if contexto.supervisor is not None:
        contexto.supervisor._destino = destino
        contexto.supervisor._usuario = usuario


def _preparar_emision(perfil, al_anunciar, cuenta_mod, restaurador, contexto,
                      escribir):
    def preparar(cliente, parada=None):
        al_anunciar(_(MENSAJE_PREPARANDO).format(nombre=perfil.nombre),
                    "conectando")
        try:
            canales = cuenta_mod.canales()
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
        _elegir_supervisor(perfil, canales, contexto)
        return None
    return preparar


def armar(opcion, al_anunciar, cuenta_mod=None, perfiles=None, escribir=None,
          contexto=None):
    """Arma el gancho de preparación y la restauración de una opción.

    Devuelve `(preparar_emision, restaurar, contexto)`. El contexto se
    completa cuando el supervisor llama al gancho. Si llega uno, se usa para
    que los avisos y el gancho compartan el mismo estado.
    """
    modulo_cuenta = cuenta_mod or _cuenta()
    lista = perfiles if perfiles is not None else cargar_perfiles()
    perfil = transmitir.perfil_de_opcion(opcion, lista)
    restaurador = Restaurador(modulo_cuenta)
    contexto = contexto if contexto is not None else Contexto()
    preparar = _preparar_emision(
        perfil, al_anunciar, modulo_cuenta, restaurador, contexto,
        escribir or obs_destinos.preparar_destino)
    return preparar, restaurador.restaurar, contexto


def envolver_anunciar(al_anunciar, contexto):
    """Ajusta los avisos del supervisor para un perfil de Restream."""
    def anunciar(frase, sonido):
        if not sonido and frase == _("Creando el directo en YouTube."):
            return
        if contexto.omitir_siguiente and not sonido:
            contexto.omitir_siguiente = False
            return
        al_anunciar(frase, sonido)
        if contexto.sin_tiktok and sonido == "conectado":
            if contexto.destino_sup == "TikTok":
                contexto.omitir_siguiente = True
            al_anunciar(_(MENSAJE_NO_TIKTOK), "al_aire")
    return anunciar


def _anunciar_de_frame(frame):
    def al_anunciar(frase, sonido):
        from guyrapu.ui import gui as _gui

        def _decir():
            if not getattr(frame, "_alive", True):
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


def supervisar_restream(frame, opcion, revision=None) -> None:
    """Arranca el supervisor para un perfil de Restream."""
    del revision
    from guyrapu.core import paths
    from guyrapu.obs.obs_supervisor import SupervisorTransmision

    modulo_cuenta = _cuenta()
    if not cuenta_conectada(modulo_cuenta):
        _anunciar_de_frame(frame)(_(MENSAJE_SIN_CUENTA),
                                  "transmision_problema")
        return
    lista = cargar_perfiles()
    perfil = transmitir.perfil_de_opcion(opcion, lista)
    if perfil is None:
        _anunciar_de_frame(frame)(
            _("Elige primero a dónde transmitir, en Transmitir a."),
            "transmision_problema")
        return
    contexto = Contexto()
    al_anunciar = _anunciar_de_frame(frame)
    envoltura = envolver_anunciar(al_anunciar, contexto)
    preparar, restaurar, contexto = armar(
        opcion, envoltura, modulo_cuenta, lista, contexto=contexto)
    supervisor = SupervisorTransmision(
        transmitir.destino_obs(opcion, lista), "",
        al_anunciar=envoltura,
        al_conectar_chat=_conectar_chat(frame),
        al_terminar=_al_terminar(frame, restaurar),
        ruta_fin_pendiente=paths.fin_pendiente(),
        **_parametros_supervisor(frame, envoltura),
        preparar_emision=preparar)
    contexto.supervisor = supervisor
    frame._supervisor = supervisor
    supervisor.iniciar()
    frame._actualizar_boton_directo()


def _parametros_supervisor(frame, al_anunciar):
    from guyrapu.ui import gui_transmitir
    return gui_transmitir._parametros_supervisor(frame, al_anunciar)
