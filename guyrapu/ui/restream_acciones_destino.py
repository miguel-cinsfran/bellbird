"""Acciones de la pestaña Destinos: activar, cambiar el título y agregar.

Cada llamada a Restream corre en su hilo y vuelve al hilo de la interfaz con
`VentanaRestream._en_hilo_principal`, que ya descarta lo que llega después de
cerrar la ventana. La clave de un destino manual no se registra ni se anuncia.
"""

from __future__ import annotations

import webbrowser
from dataclasses import replace

import wx

from guyrapu.core import diagnostico
from guyrapu.core.idioma import _
from guyrapu.restream import api, cuenta
from guyrapu.ui.accesibilidad import anunciar
from guyrapu.ui.aviso_importante import avisar
from guyrapu.ui.gui import copiar_al_portapapeles
from guyrapu.ui.restream_dialogos_destino import (
    DialogoDestinoManual,
    DialogoMetaDestino,
)
from guyrapu.voice import sound_player as _snd


abrir_navegador = webbrowser.open


def alternar(ventana):
    """Activa o desactiva el destino elegido y refresca la lista."""
    destino = ventana._pagina_destinos.seleccionado()
    if destino is None:
        return
    nuevo = not destino.activo
    _en_hilo(
        ventana, "RestreamActivar",
        lambda: cuenta.activar_canal(destino.id, nuevo),
        lambda _resultado: _estado_cambiado(ventana, destino, nuevo))


def cambiar_titulo(ventana):
    """Lee el título del destino, lo edita y guarda lo aceptado."""
    destino = ventana._pagina_destinos.seleccionado()
    if destino is None:
        return
    _en_hilo(
        ventana, "RestreamLeerTitulo",
        lambda: cuenta.leer_meta(destino.id),
        lambda meta: _pedir_titulo(ventana, destino, meta))


def agregar_manual(ventana):
    """Pide las plataformas y agrega un destino con servidor y clave."""
    _en_hilo(ventana, "RestreamPlataformas", api.plataformas,
             lambda plataformas: _pedir_manual(ventana, plataformas))


def _en_hilo(ventana, nombre, llamada, al_terminar):
    def _correr():
        try:
            resultado = llamada()
        except Exception as exc:
            ventana._en_hilo_principal(_fallo, ventana, exc)
        else:
            ventana._en_hilo_principal(al_terminar, resultado)

    diagnostico.crear_hilo(_correr, nombre).start()


def _fallo(ventana, error):
    texto = str(error).strip() or _(
        "No se pudo completar la acción con Restream. Vuelve a intentarlo.")
    ventana._error_destinos = texto
    ventana._actualizar_cuenta()
    avisar(texto, "error", error=True)


def _estado_cambiado(ventana, destino, nuevo):
    ventana._destinos = [
        replace(canal, activo=nuevo) if canal.id == destino.id else canal
        for canal in ventana._destinos]
    ventana._error_destinos = ""
    ventana._pagina_destinos.mostrar(ventana._destinos)
    ventana._actualizar_cuenta()
    if nuevo:
        avisar(_("{destino} activado").format(destino=destino.texto))
    else:
        avisar(_("{destino} desactivado").format(destino=destino.texto))


def _pedir_titulo(ventana, destino, meta):
    dialogo = DialogoMetaDestino(ventana, meta)
    try:
        if dialogo.ShowModal() != wx.ID_OK:
            return
        titulo, descripcion = dialogo.datos()
    finally:
        dialogo.Destroy()
        ventana._pagina_destinos.lista.SetFocus()
    _en_hilo(
        ventana, "RestreamCambiarTitulo",
        lambda: cuenta.cambiar_meta(destino.id, titulo, descripcion),
        lambda _resultado: _titulo_cambiado(ventana))


def _titulo_cambiado(ventana):
    ventana._error_destinos = ""
    ventana._actualizar_cuenta()
    avisar(_("Título cambiado."))


def _pedir_manual(ventana, plataformas):
    dialogo = DialogoDestinoManual(ventana, plataformas)
    try:
        if dialogo.ShowModal() != wx.ID_OK:
            return
        datos = dialogo.datos()
    finally:
        dialogo.Destroy()
        ventana._pagina_destinos.lista.SetFocus()
    _en_hilo(
        ventana, "RestreamAgregarManual",
        lambda: cuenta.agregar_canal_manual(*datos),
        lambda canal: _destino_agregado(ventana, canal))


def _destino_agregado(ventana, canal):
    ventana._destinos = [*ventana._destinos, canal]
    ventana._error_destinos = ""
    ventana._pagina_destinos.mostrar(ventana._destinos, elegido=canal.id)
    ventana._pagina_eventos.actualizar_nombres()
    ventana._actualizar_cuenta()
    avisar(_("Destino agregado."))


def abrir_enlace(ventana):
    """Abre en el navegador el enlace del destino elegido."""
    destino = ventana._pagina_destinos.seleccionado()
    if destino is None:
        return
    if not destino.url:
        anunciar(_("Este destino no tiene enlace."))
        return
    abrir_navegador(destino.url)


def copiar_enlace(ventana):
    """Copia el enlace del destino elegido."""
    destino = ventana._pagina_destinos.seleccionado()
    if destino is None:
        return
    if not destino.url:
        anunciar(_("Este destino no tiene enlace."))
        return
    copiar_al_portapapeles(destino.url)
    _snd.reproducir("copiar")
    anunciar(_("Enlace copiado."))
