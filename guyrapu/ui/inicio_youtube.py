"""Cómo empieza un directo de YouTube.

Pide y guarda sus datos, arma los ganchos del supervisor y decide si se
conecta su chat. Lo usa `gui_transmitir.supervisar_transmision` y también
la supervisión de perfiles de Restream que incluyen YouTube.
"""

from __future__ import annotations

from dataclasses import replace

from guyrapu.core.idioma import N_, _
from guyrapu.ui.aviso_importante import avisar

MENSAJE_SIN_GOOGLE = N_(
    "Para transmitir a YouTube hace falta iniciar sesión con Google, en "
    "Preferencias, categoría YouTube.")


def _sesion():
    from guyrapu.ui import gui as _gui
    return _gui.credenciales.cargar()


def hay_sesion() -> bool:
    from guyrapu.ui import gui as _gui
    return bool(_gui.credenciales.hay_sesion(_sesion()))


def _cliente():
    from guyrapu.ui import gui as _gui
    return _gui.youtube_api.ClienteYouTube(
        _gui.credenciales.efectivas(_sesion()))


def _valores(perfil, emision) -> dict:
    """Los valores del cuadro a partir de lo último usado en el perfil."""
    datos = perfil.directo or {}
    etiquetas = datos.get("etiquetas") or []
    if not isinstance(etiquetas, str):
        etiquetas = ", ".join(etiquetas)
    return {
        "titulo": datos.get("titulo", ""),
        "descripcion": datos.get("descripcion", ""),
        "privacidad": datos.get("privacidad", emision.PRIVACIDAD_INICIAL),
        "latencia": datos.get("latencia", emision.LATENCIA_INICIAL),
        "ninos": datos.get("ninos", False),
        "dvr": datos.get("dvr", True),
        "categoria": datos.get("categoria", ""),
        "etiquetas": etiquetas,
        "miniatura": datos.get("miniatura", ""),
        "lista": datos.get("lista", ""),
        "lista_titulo": datos.get("lista_titulo", ""),
    }


def _pedir_datos(frame, revision, cliente, emision, pedir_datos_directo):
    from guyrapu.ui import gui as _gui
    config = frame._config
    return pedir_datos_directo(
        frame,
        config.get("transmision_youtube_titulo", ""),
        config.get("transmision_youtube_descripcion", ""),
        config.get("transmision_youtube_privacidad",
                   emision.PRIVACIDAD_INICIAL),
        revision,
        config.get("transmision_youtube_latencia",
                   emision.LATENCIA_INICIAL),
        config.get("transmision_youtube_ninos", False),
        config.get("transmision_youtube_dvr", True),
        config.get("transmision_youtube_categoria", ""),
        config.get("transmision_youtube_etiquetas", ""),
        config.get("transmision_youtube_miniatura", ""),
        config.get("transmision_youtube_lista", ""),
        config.get("transmision_youtube_lista_titulo", ""),
        emision.cargador_listas(
            cliente, lambda nuevo:
            _gui.credenciales.guardar_campo("token", nuevo)))


def _cuerpo(emision, guardados):
    from datetime import datetime, timezone
    return emision.cuerpo_emision(
        guardados["titulo"], guardados["descripcion"],
        guardados["privacidad"],
        datetime.now(timezone.utc).isoformat(),
        latencia=guardados.get("latencia", emision.LATENCIA_INICIAL),
        ninos=guardados.get("ninos", False),
        dvr=guardados.get("dvr", True))


def _ganchos(cliente, cuerpo, guardados, emision):
    from guyrapu.ui import gui as _gui
    extras = {"categoria": guardados.get("categoria", ""),
              "etiquetas": guardados.get("etiquetas", []),
              "miniatura": guardados.get("miniatura", ""),
              "lista": guardados.get("lista", ""),
              "titulo": guardados["titulo"],
              "descripcion": guardados["descripcion"]}
    preparar, esperar, finalizar = emision.ganchos_youtube(
        cliente, cuerpo,
        lambda nuevo: _gui.credenciales.guardar_campo("token", nuevo),
        extras=extras, avisar=_gui.anunciar)
    return {"preparar_emision": preparar,
            "esperar_emision": esperar,
            "finalizar_emision": finalizar}


def _preparados(cliente, perfil, emision) -> dict:
    from guyrapu.ui import gui as _gui
    datos = _valores(perfil, emision)
    cuerpo = _cuerpo(emision, datos)
    extras = {"categoria": datos.get("categoria", ""),
              "etiquetas": (perfil.directo or {}).get("etiquetas") or [],
              "miniatura": datos.get("miniatura", ""),
              "lista": datos.get("lista", ""),
              "titulo": datos["titulo"],
              "descripcion": datos["descripcion"]}
    def guardar(nuevo):
        _gui.credenciales.guardar_campo("token", nuevo)

    _preparar, esperar, finalizar = emision.ganchos_youtube(
        cliente, cuerpo, guardar, extras=extras, avisar=None)
    return {"cliente": cliente, "cuerpo": cuerpo, "extras": extras,
            "guardar_token": guardar, "esperar": esperar,
            "finalizar": finalizar}


def pedir_y_guardar_perfil(frame, revision, perfil, lista):
    """Pide lo último del perfil y lo guarda con `perfiles.guardar`.

    Devuelve `(perfil, preparados)` o `None` si no se transmite. Los
    `preparados` son None cuando el perfil no tiene YouTube.
    """
    from guyrapu.core import paths
    from guyrapu.restream import perfiles
    from guyrapu.ui import gui as _gui
    from guyrapu.ui.gui_directo_youtube import pedir_datos_directo
    from guyrapu.youtube import emision
    if perfil.youtube and not hay_sesion():
        avisar(_(MENSAJE_SIN_GOOGLE), "transmision_problema", error=True)
        return None
    cargar = None
    cliente = None
    if perfil.youtube:
        cliente = _cliente()
        cargar = emision.cargador_listas(
            cliente, lambda nuevo:
            _gui.credenciales.guardar_campo("token", nuevo))
    pedido = pedir_datos_directo(
        frame, revision=revision, cargar_listas=cargar,
        solo_titulo=not perfil.youtube,
        titulo_ventana=_("Directo con Restream: {nombre}").format(
            nombre=perfil.nombre),
        **_valores(perfil, emision))
    if pedido is None:
        _gui.anunciar(_("No se transmitió."))
        return None
    actualizado = replace(perfil, directo=pedido)
    perfiles.guardar(paths.perfiles_restream(), [
        actualizado if otro.nombre == perfil.nombre else otro
        for otro in lista])
    try:
        preparados = (_preparados(cliente, actualizado, emision)
                      if actualizado.youtube else None)
    except emision.EmisionError as exc:
        avisar(str(exc), error=True)
        return None
    return actualizado, preparados


def pedir_y_armar(frame, revision):
    """Devuelve `(guardados, ganchos)`, o `None` si no se transmite.

    Cuando no se transmite ya anunció el motivo, como antes.
    """
    from guyrapu.ui import gui as _gui
    from guyrapu.ui.gui_directo_youtube import pedir_datos_directo
    from guyrapu.youtube import emision
    if not hay_sesion():
        _gui.anunciar(_(MENSAJE_SIN_GOOGLE))
        return None
    cliente = _cliente()
    pedido = _pedir_datos(frame, revision, cliente, emision,
                          pedir_datos_directo)
    if pedido is None:
        _gui.anunciar(_("No se transmitió."))
        return None
    guardados = frame._guardar_datos_directo_youtube(
        pedido["titulo"], pedido["descripcion"],
        pedido["privacidad"], pedido.get("latencia"),
        pedido.get("ninos", False), pedido.get("dvr", True),
        pedido.get("categoria", ""), pedido.get("etiquetas", []),
        pedido.get("miniatura", ""), pedido.get("lista", ""),
        pedido.get("lista_titulo", ""))
    try:
        cuerpo = _cuerpo(emision, guardados)
    except emision.EmisionError as exc:
        avisar(str(exc), error=True)
        return None
    return guardados, _ganchos(cliente, cuerpo, guardados, emision)


def sin_chat(frame, guardados, url):
    """Avisa si YouTube no ofrece chat legible y guarda el enlace.

    Devuelve `True` cuando ya lo resolvió y no hay que conectar el chat.
    """
    from guyrapu.ui import gui as _gui
    from guyrapu.youtube import emision
    if guardados.get("ninos"):
        frame.sesion.enlace_directo = url
        _gui.anunciar(
            _("El directo está marcado como creado para "
              "niños y YouTube no tiene chat."))
        return True
    if not emision.chat_legible(guardados["privacidad"]):
        frame.sesion.enlace_directo = url
        _gui.anunciar(
            _("El directo es privado y YouTube no permite "
              "leer su chat. Para leerlo, transmite como "
              "público o no listado."))
        return True
    return False
