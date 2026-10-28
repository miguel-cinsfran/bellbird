"""Prepara OBS para un destino de emisión cambiando de perfil.

Recibe un objeto cliente con `pedir(tipo, datos=None, parada=None)` y no crea
conexiones, igual que `obs_panel`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ytchat.core.idioma import N_, _
from ytchat.obs import obs_cliente


# Traductores: {destino} es TikTok o YouTube.
MENSAJE_SIN_PERFIL = N_("OBS no tiene un perfil llamado {destino}.")
MENSAJE_EN_TRANSMISION = N_(
    "No se puede cambiar de destino mientras se transmite.")
MENSAJE_SIN_APLICAR = N_("OBS no aplicó el destino. Inténtalo de nuevo.")


DESTINOS = ("TikTok", "YouTube")

# Perfiles que esta ruta sí deja crear al que falta: el supervisor carga
# servidor y clave de la cuenta en el perfil YouTube antes de arrancar OBS,
# así que uno nuevo no emite al vacío. TikTok sigue pidiendo su clave de
# Restream a mano y por eso no está acá.
PERFILES_QUE_SE_CREAN = ("YouTube",)


@dataclass(frozen=True, slots=True)
class Destino:
    perfil: str
    servidor: str | None = None
    clave: str | None = None
    ancho: int | None = None
    alto: int | None = None

    def __post_init__(self):
        if (self.servidor is None) != (self.clave is None):
            raise ValueError("Hay que dar servidor y clave juntos.")
        if (self.ancho is None) != (self.alto is None):
            raise ValueError("Hay que dar ancho y alto juntos.")


def _lista_perfiles(cliente, parada):
    respuesta = cliente.pedir("GetProfileList", parada=parada)
    return respuesta.get("responseData", {}) or {}


def _lista_colecciones(cliente, parada):
    respuesta = cliente.pedir("GetSceneCollectionList", parada=parada)
    return respuesta.get("responseData", {}) or {}


def _esperar(cliente, leer, cumple, parada, espera, intervalo, dormir, reloj,
             mensaje):
    inicio = reloj()
    while True:
        if parada is not None and parada.is_set():
            raise obs_cliente.ObsError(_("Operación cancelada."))
        datos = leer(cliente, parada)
        if cumple(datos):
            return datos
        if reloj() - inicio >= espera:
            raise obs_cliente.ObsError(mensaje)
        dormir(intervalo)


def _esperar_en_lista(cliente, cumple, parada, espera, intervalo, dormir, reloj):
    # OBS responde éxito antes de aplicar el cambio (medido 35-39 ms con
    # error 600 si se pide SetCurrentProfile enseguida); por eso se espera a
    # verlo en GetProfileList en vez de darlo por hecho.
    return _esperar(cliente, _lista_perfiles, cumple, parada, espera,
                    intervalo, dormir, reloj,
                    _("OBS no terminó de cambiar de perfil."))


def coleccion_para(destino, colecciones):
    """Elige la colección de escenas que corresponde a un destino.

    Si hay una colección con el mismo nombre que el destino, esa; si no,
    la primera cuyo nombre no sea un destino; si no hay ninguna, None.
    """
    colecciones = list(colecciones or ())
    if destino in colecciones:
        return destino
    for coleccion in colecciones:
        if coleccion not in DESTINOS:
            return coleccion
    return None


def cambiar_coleccion(cliente, nombre, parada=None, espera=60.0,
                      intervalo=0.05, dormir=time.sleep, reloj=time.monotonic):
    """Deja activa la colección de escenas indicada, esperando a verla."""
    datos = _lista_colecciones(cliente, parada)
    if (datos.get("currentSceneCollectionName", "") or "") == nombre:
        return
    # SetCurrentSceneCollection también responde antes de aplicar el cambio,
    # igual que los perfiles; se espera a verla como actual.
    cliente.pedir("SetCurrentSceneCollection", {"sceneCollectionName": nombre},
                  parada=parada)
    _esperar(cliente, _lista_colecciones,
             lambda vistos: (vistos.get("currentSceneCollectionName", "")
                             or "") == nombre,
             parada, espera, intervalo, dormir, reloj,
             _("OBS no terminó de cambiar de escenas."))


def preparar_para_transmitir(cliente, destino, parada=None, espera=60.0,
                             intervalo=0.05, dormir=time.sleep,
                             reloj=time.monotonic):
    """Deja OBS listo para transmitir al destino: perfil y colección."""
    perfiles = (_lista_perfiles(cliente, parada).get("profiles", ()) or ())
    if destino not in perfiles and destino not in PERFILES_QUE_SE_CREAN:
        # Solo los perfiles de PERFILES_QUE_SE_CREAN dejan que
        # preparar_destino cree el que falta; cualquier otro perfil vacío
        # emitiría a ningún lado.
        raise obs_cliente.ObsError(
            _(MENSAJE_SIN_PERFIL).format(destino=destino))
    perfil_creado = destino not in perfiles
    preparar_destino(cliente, Destino(destino), parada=parada, espera=espera,
                     intervalo=intervalo, dormir=dormir, reloj=reloj)
    colecciones = (_lista_colecciones(cliente, parada).get(
        "sceneCollections", ()) or ())
    nombre = coleccion_para(destino, colecciones)
    if nombre is not None:
        cambiar_coleccion(cliente, nombre, parada=parada, espera=espera,
                          intervalo=intervalo, dormir=dormir, reloj=reloj)
    coleccion = (_lista_colecciones(cliente, parada).get(
        "currentSceneCollectionName", "") or "")
    lienzo = (cliente.pedir("GetVideoSettings", parada=parada).get(
        "responseData", {}) or {})
    return {"destino": destino, "perfil": destino, "coleccion": coleccion,
            "ancho": lienzo.get("baseWidth"), "alto": lienzo.get("baseHeight"),
            "perfil_creado": perfil_creado}


def frase_destino_listo(resultado):
    """Frase de anuncio con el formato del lienzo ya leído de OBS."""
    ancho, alto = resultado["ancho"], resultado["alto"]
    if alto > ancho:
        # Traductores: formato del lienzo dentro de «Listo para transmitir».
        formato = _("vertical")
    elif ancho > alto:
        # Traductores: formato del lienzo dentro de «Listo para transmitir».
        formato = _("horizontal")
    else:
        # Traductores: formato del lienzo dentro de «Listo para transmitir».
        formato = _("cuadrado")
    # Traductores: {destino} es TikTok o YouTube y {ancho} y {alto} sus píxeles.
    frase = (_("Listo para transmitir a {destino}. Formato {formato}, "
               "{ancho} por {alto}.").format(destino=resultado["destino"],
                                             formato=formato, ancho=ancho,
                                             alto=alto))
    if resultado.get("perfil_creado"):
        frase = (_("Se creó en OBS el perfil {destino}.").format(
            destino=resultado["destino"]) + " " + frase)
    return frase


def preparar_destino(cliente, destino, parada=None, espera=60.0,
                     intervalo=0.05, dormir=time.sleep, reloj=time.monotonic):
    """Deja el perfil de OBS listo para emitir al destino indicado."""
    estado = cliente.pedir("GetStreamStatus", parada=parada)
    if (estado.get("responseData", {}) or {}).get("outputActive"):
        raise obs_cliente.ObsError(_(MENSAJE_EN_TRANSMISION))

    datos = _lista_perfiles(cliente, parada)
    perfiles = datos.get("profiles", ()) or ()
    actual = datos.get("currentProfileName", "") or ""
    if destino.perfil not in perfiles:
        cliente.pedir("CreateProfile", {"profileName": destino.perfil},
                      parada=parada)
        datos = _esperar_en_lista(
            cliente,
            lambda vistos: destino.perfil in (vistos.get("profiles", ()) or ())
            or (vistos.get("currentProfileName", "") or "") == destino.perfil,
            parada, espera, intervalo, dormir, reloj)
        perfiles = datos.get("profiles", ()) or ()
        actual = datos.get("currentProfileName", "") or ""
    if actual != destino.perfil:
        cliente.pedir("SetCurrentProfile", {"profileName": destino.perfil},
                      parada=parada)
        _esperar_en_lista(
            cliente,
            lambda vistos: (vistos.get("currentProfileName", "")
                            or "") == destino.perfil,
            parada, espera, intervalo, dormir, reloj)

    if destino.servidor is not None and destino.clave is not None:
        cliente.pedir("SetStreamServiceSettings", {
            "streamServiceType": "rtmp_custom",
            "streamServiceSettings": {"server": destino.servidor,
                                      "key": destino.clave},
        }, parada)
    if destino.ancho is not None and destino.alto is not None:
        cliente.pedir("SetVideoSettings", {
            "baseWidth": destino.ancho, "baseHeight": destino.alto,
            "outputWidth": destino.ancho, "outputHeight": destino.alto,
        }, parada)

    datos = _lista_perfiles(cliente, parada)
    if (datos.get("currentProfileName", "") or "") != destino.perfil:
        raise obs_cliente.ObsError(_(MENSAJE_SIN_APLICAR))
    if destino.servidor is not None and destino.clave is not None:
        respuesta = cliente.pedir("GetStreamServiceSettings", parada=parada)
        ajustes = (respuesta.get("responseData", {}) or {}).get(
            "streamServiceSettings", {}) or {}
        if (ajustes.get("server") != destino.servidor
                or ajustes.get("key") != destino.clave):
            raise obs_cliente.ObsError(_(MENSAJE_SIN_APLICAR))
