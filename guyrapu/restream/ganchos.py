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
from guyrapu.restream import transmitir, youtube_por_restream
from guyrapu.youtube import emision
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
    """El destino, el usuario y si el perfil tiene YouTube."""

    destino: str = ""
    usuario: str = ""
    youtube: bool = False


class Restaurador:
    """Devuelve los canales a su estado anterior y borra el manual de YouTube."""

    def __init__(self, cuenta_mod):
        self._cuenta = cuenta_mod
        self._cambios = []
        self._manuales = []
        self._candado = threading.Lock()

    def anotar(self, cambio) -> None:
        with self._candado:
            self._cambios.append(cambio)

    def anotar_manual(self, identificador) -> None:
        with self._candado:
            self._manuales.append(identificador)

    def restaurar(self) -> None:
        with self._candado:
            cambios, self._cambios = self._cambios, []
            manuales, self._manuales = self._manuales, []
        for identificador in manuales:
            self._borrar_manual(identificador)
        for cambio in cambios:
            try:
                self._cuenta.activar_canal(cambio.canal_id, cambio.antes)
            except Exception as error:
                logger.warning(
                    "no se pudo restaurar el canal %s de Restream: %s",
                    cambio.canal_id, error)

    def _borrar_manual(self, identificador) -> None:
        try:
            self._cuenta.eliminar_canal(identificador)
        except Exception as error:
            logger.warning(
                "no se pudo borrar el manual %s de Restream: %s",
                identificador, error)


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
    datos = perfil.directo or {}
    titulo = datos.get("titulo") or ""
    if not titulo:
        return
    for canal in transmitir.canales_del_perfil(perfil, canales):
        cuenta_mod.cambiar_meta(canal.id, titulo,
                                datos.get("descripcion", ""))


def _preparar_youtube(perfil, cliente_obs, parada, cuenta_mod, restaurador,
                      preparados, al_anunciar):
    def avisar(frase):
        al_anunciar(frase, None)

    return emision.preparar_en_youtube(
        preparados["cliente"], cliente_obs, preparados["cuerpo"],
        parada=parada,
        preparar_destino=youtube_por_restream.preparar_destino(
            cuenta_mod, restaurador),
        guardar_token=preparados.get("guardar_token"),
        extras=preparados.get("extras"), avisar=avisar)


def _borrar_emision(preparados, id_video) -> None:
    try:
        emision.finalizar_en_youtube(preparados["cliente"], id_video)
    except Exception as error:
        logger.warning("no se pudo borrar la emisión %s: %s", id_video, error)


def _revertir(preparados, id_video, restaurador) -> None:
    if id_video is not None:
        _borrar_emision(preparados, id_video)
    restaurador.restaurar()


def _preparar_emision(perfil, canales, al_anunciar, cuenta_mod, restaurador,
                      escribir, preparados=None):
    def preparar(cliente, parada=None):
        al_anunciar(_(MENSAJE_PREPARANDO).format(nombre=perfil.nombre), "conectando")
        id_video = None
        try:
            vivos = youtube_por_restream.borrar_sobrantes(cuenta_mod, canales)
            _aplicar_cambios(perfil, vivos, cuenta_mod, restaurador)
            _cambiar_titulo(perfil, vivos, cuenta_mod)
            if perfil.youtube and preparados is not None:
                id_video = _preparar_youtube(
                    perfil, cliente, parada, cuenta_mod, restaurador,
                    preparados, al_anunciar)
            clave = cuenta_mod.clave_cuenta()
            escribir(cliente, obs_destinos.Destino(
                transmitir.destino_obs(
                    transmitir.PREFIJO + perfil.nombre, (perfil,)),
                clave.servidor, clave.clave), parada=parada)
        except Exception as error:
            _revertir(preparados, id_video, restaurador)
            raise EmisionError(str(error)) from error
        return id_video
    return preparar


def armar(opcion, al_anunciar, canales, cuenta_mod=None, perfiles=None,
          escribir=None, perfil=None, preparados=None):
    """Arma el gancho de preparación y la restauración de una opción.

    Los canales ya vienen leídos por el hilo que arma la transmisión.
    Devuelve `(preparar_emision, restaurar, ganchos_del_supervisor)`.
    """
    modulo_cuenta = cuenta_mod or _cuenta()
    lista = perfiles if perfiles is not None else cargar_perfiles()
    if perfil is None:
        perfil = transmitir.perfil_de_opcion(opcion, lista)
    restaurador = Restaurador(modulo_cuenta)
    preparar = _preparar_emision(
        perfil, canales, al_anunciar, modulo_cuenta, restaurador,
        escribir or obs_destinos.preparar_destino, preparados=preparados)
    ganchos = {}
    if perfil.youtube and preparados is not None:
        ganchos = {"esperar_emision": preparados.get("esperar"),
                   "finalizar_emision": preparados.get("finalizar")}
    return preparar, restaurador.restaurar, ganchos


def envolver_anunciar(al_anunciar, contexto):
    """Ajusta los avisos del supervisor para un perfil de Restream."""
    def anunciar(frase, sonido, importante=False):
        if (not sonido and not contexto.youtube
                and frase == _("Creando el directo en YouTube.")):
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


def _conectar_chat(frame, youtube=False, guardados=None):
    def al_conectar_chat(url):
        from guyrapu.ui import gui as _gui

        def _conectar():
            if not getattr(frame, "_alive", True):
                return
            if youtube:
                from guyrapu.ui import inicio_youtube
                if inicio_youtube.sin_chat(frame, guardados or {}, url):
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


def _crear_vigia(modulo_cuenta, canales, al_anunciar, supervisor_actual):
    """El vigía del estado de Restream, con los nombres de los canales."""
    from guyrapu.restream import senal, vigia

    destinos = {canal.id: canal.texto for canal in canales}
    analizador = senal.AnalizadorSenal(destinos)

    def al_recibir(texto):
        supervisor = supervisor_actual()
        if (supervisor is None or supervisor.deteniendo
                or not supervisor.activo):
            return
        for aviso in analizador.recibir(texto):
            al_anunciar(aviso.frase, aviso.sonido)

    def debe_seguir():
        supervisor = supervisor_actual()
        return (supervisor is not None and supervisor.activo
                and not supervisor.deteniendo)

    return vigia.VigiaSenal(
        lambda: modulo_cuenta.sesion().token(),
        al_recibir, debe_seguir=debe_seguir)


def _al_terminar(frame, restaurar):
    def al_terminar():
        vigia_senal = getattr(frame, "_vigia_restream", None)
        if vigia_senal is not None:
            vigia_senal.detener()
        try:
            frame._al_terminar_supervisor()
        finally:
            diagnostico.crear_hilo(
                restaurar, "RestaurarRestream").start()
    return al_terminar


def _arrancar_vigia(modulo_cuenta, canales, al_anunciar, frame):
    vigia_senal = _crear_vigia(
        modulo_cuenta, canales, al_anunciar, lambda: frame._supervisor)
    frame._vigia_restream = vigia_senal
    vigia_senal.iniciar()


def _en_interfaz(frame, funcion, *args):
    if not getattr(frame, "_alive", True):
        return
    from guyrapu.ui import gui as _gui
    _gui.wx.CallAfter(funcion, *args)


def _destino_supervisor(perfil, canales):
    chat = transmitir.chat_del_perfil(perfil, canales)
    if chat == "youtube" and perfil.youtube:
        return ("YouTube", "")
    usuario = transmitir.usuario_tiktok(perfil, canales)
    if chat == "tiktok" and usuario:
        return ("TikTok", usuario)
    return ("Restream", "")


def _instanciar_supervisor(frame, destino, usuario, perfil, envoltura,
                           restaurar, preparar, extras):
    from guyrapu.core import paths
    from guyrapu.obs.obs_supervisor import SupervisorTransmision
    return SupervisorTransmision(
        destino, usuario, al_anunciar=envoltura,
        al_conectar_chat=_conectar_chat(
            frame, youtube=destino == "YouTube", guardados=perfil.directo),
        al_terminar=_al_terminar(frame, restaurar),
        ruta_fin_pendiente=paths.fin_pendiente(),
        **_parametros_supervisor(frame, envoltura),
        preparar_emision=preparar, **extras)


def _crear_supervisor(frame, modulo_cuenta, opcion, perfil, destino, usuario,
                      canales, preparados=None):
    if not getattr(frame, "_alive", True):
        return
    contexto = Contexto(destino, usuario, youtube=perfil.youtube)
    envoltura = envolver_anunciar(_anunciar_de_frame(frame), contexto)
    preparar, restaurar, extras = armar(
        opcion, envoltura, canales, cuenta_mod=modulo_cuenta,
        perfiles=[perfil], perfil=perfil, preparados=preparados)
    supervisor = _instanciar_supervisor(
        frame, destino, usuario, perfil, envoltura, restaurar, preparar,
        extras)
    frame._supervisor = supervisor
    supervisor.iniciar()
    _arrancar_vigia(modulo_cuenta, canales, envoltura, frame)
    frame._actualizar_boton_directo()


def _preparar_ui(frame, modulo_cuenta, opcion, lista, perfil, canales,
                 revision):
    from guyrapu.restream import perfiles as modulo
    from guyrapu.ui import inicio_youtube
    perfil = modulo.normalizar_youtube(perfil, canales)
    armado = inicio_youtube.pedir_y_guardar_perfil(frame, revision, perfil,
                                                  lista)
    if armado is None:
        return
    perfil, preparados = armado
    destino, usuario = _destino_supervisor(perfil, canales)
    _crear_supervisor(frame, modulo_cuenta, opcion, perfil, destino, usuario,
                      canales, preparados=preparados)


def _leer_canales(frame, modulo_cuenta, opcion, lista, perfil, revision):
    try:
        canales = modulo_cuenta.canales()
    except Exception as error:
        _anunciar_de_frame(frame)(str(error), "transmision_problema")
        return
    _en_interfaz(frame, _preparar_ui, frame, modulo_cuenta, opcion, lista,
                 perfil, canales, revision)


def supervisar_restream(frame, opcion, revision=None, cuenta_mod=None) -> None:
    """Lee los canales y crea el supervisor con el destino ya elegido."""
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
        lambda: _leer_canales(frame, modulo_cuenta, opcion, lista, perfil,
                              revision),
        "PrepararRestream").start()


def _parametros_supervisor(frame, al_anunciar):
    from guyrapu.ui import gui_transmitir
    return gui_transmitir._parametros_supervisor(frame, al_anunciar)
