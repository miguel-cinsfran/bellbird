"""Agregar una cámara de Windows a OBS desde la interfaz.

Dueño de todo el flujo: leer las cámaras del sistema, preguntar cuál si hay
varias, agregarla a la escena al aire y anunciar dónde quedó.
"""

from __future__ import annotations

import wx

from bellbird.core import diagnostico
from bellbird.core.idioma import _
from bellbird.obs import obs_camara
from bellbird.obs import obs_camara_nueva
from bellbird.obs import obs_cliente
from bellbird.obs import obs_disposicion
from bellbird.obs import obs_panel
from bellbird.ui.accesibilidad import anunciar


logger = diagnostico.obtener_logger(__name__)


def _escena_al_aire(cliente):
    datos = cliente.pedir("GetCurrentProgramScene")
    return (datos.get("responseData", {}) or {}).get(
        "currentProgramSceneName", "") or ""


def _descripcion(cliente, escena, nombre):
    snap = obs_panel.GestorPanelObs(cliente).instantanea(escena, fuente=nombre)
    if not snap.ancho or not snap.alto:
        return ""
    componentes = tuple(
        componente for componente in obs_disposicion.COMPONENTES
        if componente not in ("conexion", "escena", "transparencia"))
    return obs_disposicion.describir_fuente(nombre, snap, componentes, "corto")


def cerrar_cliente(cliente):
    if cliente is None:
        return
    try:
        cliente.cerrar()
    except Exception as error:
        logger.debug("no se pudo cerrar el cliente de OBS: %s", error)


def agregar(ventana, al_agregar):
    """Agrega una cámara de Windows a OBS sin bloquear la interfaz."""
    diagnostico.crear_hilo(
        lambda: _consultar_camaras(ventana, al_agregar),
        "AgregarCamara").start()


def _consultar_camaras(ventana, al_agregar):
    cliente = None
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        escena = _escena_al_aire(cliente)
        camaras = obs_camara_nueva.camaras_disponibles(cliente, escena)
    except Exception as exc:
        wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
        return
    finally:
        cerrar_cliente(cliente)
    wx.CallAfter(_camaras_windows, ventana, al_agregar, camaras)


def _camaras_windows(ventana, al_agregar, camaras):
    if not ventana:
        return
    if not camaras:
        anunciar(_("Windows no tiene ninguna cámara disponible para OBS."))
    elif len(camaras) == 1:
        _agregar_en_hilo(ventana, al_agregar, camaras[0][1])
    else:
        _preguntar_camara(ventana, al_agregar, camaras)


def _preguntar_camara(ventana, al_agregar, camaras):
    dialogo = wx.SingleChoiceDialog(
        ventana, _("Cámaras de Windows:"), _("Elegir cámara"),
        [nombre for nombre, valor in camaras])
    try:
        if dialogo.ShowModal() != wx.ID_OK:
            return
        indice = dialogo.GetSelection()
    finally:
        dialogo.Destroy()
    if indice >= 0:
        _agregar_en_hilo(ventana, al_agregar, camaras[indice][1])


def _agregar_en_hilo(ventana, al_agregar, valor):
    diagnostico.crear_hilo(
        lambda: _agregar_camara_en_obs(ventana, al_agregar, valor),
        "AgregarCamara").start()


def _agregar_camara_en_obs(ventana, al_agregar, valor):
    cliente = None
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        escena = _escena_al_aire(cliente)
        nombre, nueva = obs_camara_nueva.agregar(cliente, escena, valor)
        if not nueva:
            wx.CallAfter(_camara_ya_esta, ventana, nombre)
            return
        descripcion = _descripcion(cliente, escena, nombre)
        fuentes = obs_camara.fuentes_video(cliente)
    except Exception as exc:
        wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
        return
    finally:
        cerrar_cliente(cliente)
    wx.CallAfter(_camara_agregada, ventana, al_agregar, nombre, escena,
                 descripcion, fuentes)


def _camara_ya_esta(ventana, nombre):
    if not ventana:
        return
    anunciar(_("Esa cámara ya está en OBS como {nombre}.").format(
        nombre=nombre))


def _camara_agregada(ventana, al_agregar, nombre, escena, descripcion, fuentes):
    if not ventana:
        return
    al_agregar(fuentes)
    mensaje = _("Se agregó {nombre} a la escena {escena}.").format(
        nombre=nombre, escena=escena)
    lugar = _(obs_disposicion.etiqueta_anclaje("inferior-derecha"))
    lugar = lugar[:1].lower() + lugar[1:]
    mensaje += " " + _(
        "Quedó {lugar}, delante de las demás fuentes.").format(lugar=lugar)
    if descripcion:
        mensaje += " " + descripcion
    mensaje += " " + _(
        "Para moverla, usa la pestaña Fuentes de la ventana Escena.")
    anunciar(mensaje)
