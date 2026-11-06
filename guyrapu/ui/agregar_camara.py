"""Agregar una cámara de Windows a OBS desde la interfaz.

Dueño de todo el flujo: leer las cámaras del sistema, preguntar cuál si hay
varias, agregarla a la escena al aire y anunciar dónde quedó.
"""

from __future__ import annotations

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.obs import obs_camara
from guyrapu.obs import obs_camara_nueva
from guyrapu.obs import obs_cliente
from guyrapu.obs import obs_disposicion
from guyrapu.obs import obs_panel
from guyrapu.ui.accesibilidad import anunciar


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


def agregar(ventana, al_agregar, al_pedir_nombre=None):
    """Agrega una cámara de Windows a OBS sin bloquear la interfaz."""
    diagnostico.crear_hilo(
        lambda: _consultar_camaras(ventana, al_agregar, al_pedir_nombre),
        "AgregarCamara").start()


def _consultar_camaras(ventana, al_agregar, al_pedir_nombre=None):
    cliente = None
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        escena = _escena_al_aire(cliente)
        camaras = obs_camara_nueva.camaras_disponibles(cliente, escena)
        existentes, ocupados = {}, set()
        if al_pedir_nombre is not None:
            existentes = obs_camara_nueva.camaras_existentes(cliente)
            ocupados = obs_camara_nueva.nombres_ocupados(cliente)
    except Exception as exc:
        wx.CallAfter(anunciar, obs_cliente.mensaje_de_fallo_obs(exc))
        return
    finally:
        cerrar_cliente(cliente)
    wx.CallAfter(_camaras_windows, ventana, al_agregar, camaras,
                 al_pedir_nombre, existentes, ocupados)


def _camaras_windows(ventana, al_agregar, camaras, al_pedir_nombre=None,
                     existentes=None, ocupados=()):
    if not ventana:
        return
    if not camaras:
        anunciar(_("Windows no tiene ninguna cámara disponible para OBS."))
    elif len(camaras) == 1:
        _decidir(ventana, al_agregar, camaras[0][1], al_pedir_nombre,
                 existentes, ocupados)
    else:
        _preguntar_camara(ventana, al_agregar, camaras, al_pedir_nombre,
                          existentes, ocupados)


def _preguntar_camara(ventana, al_agregar, camaras, al_pedir_nombre=None,
                      existentes=None, ocupados=()):
    valor = pedir_camara(ventana, camaras)
    if valor is None:
        return
    _decidir(ventana, al_agregar, valor, al_pedir_nombre, existentes,
             ocupados)


def pedir_camara(padre, opciones, actual=""):
    """Abre el cuadro de cámaras y devuelve el valor elegido, sin agregar."""
    if not opciones:
        return None
    valores = [valor for _nombre, valor in opciones]
    dialogo = wx.SingleChoiceDialog(
        padre, _("Cámaras de Windows:"), _("Elegir cámara"),
        [nombre for nombre, _valor in opciones])
    try:
        if actual in valores:
            dialogo.SetSelection(valores.index(actual))
        if dialogo.ShowModal() != wx.ID_OK:
            return None
        indice = dialogo.GetSelection()
    finally:
        dialogo.Destroy()
    return valores[indice] if 0 <= indice < len(valores) else None


def _decidir(ventana, al_agregar, valor, al_pedir_nombre, existentes,
             ocupados):
    if valor in (existentes or {}):
        _agregar_en_hilo(ventana, al_agregar, valor)
        return
    if al_pedir_nombre is None:
        _agregar_en_hilo(ventana, al_agregar, valor)
        return
    nombre = al_pedir_nombre(ocupados)
    if nombre:
        _agregar_en_hilo(ventana, al_agregar, valor, nombre)


def _agregar_en_hilo(ventana, al_agregar, valor, nombre=""):
    diagnostico.crear_hilo(
        lambda: _agregar_camara_en_obs(ventana, al_agregar, valor, nombre),
        "AgregarCamara").start()


def _agregar_camara_en_obs(ventana, al_agregar, valor, nombre=""):
    cliente = None
    try:
        cliente = obs_cliente.ClienteObs(obs_cliente.leer_ajustes())
        cliente.conectar()
        escena = _escena_al_aire(cliente)
        nombre, nueva = obs_camara_nueva.agregar(cliente, escena, valor, nombre=nombre)
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
        "Para moverla, usa Posición y tamaño, en la pestaña Escena del "
        "Panel de OBS.")
    anunciar(mensaje)
