"""Cómo se conecta la cuenta de Restream de esta instalación.

La sesión es una sola para toda la app: guarda sus tokens en
`credenciales.json` y los renueva con el servicio publicado. Conectar y
desconectar no saben de interfaz: reciben lo que necesitan por parámetro.
"""

from __future__ import annotations

import threading
import webbrowser

from bellbird.restream import api, oauth
from bellbird.restream.sesion import Sesion
from bellbird.youtube import credenciales

_CANDADO = threading.Lock()
_sesion = None


def _cargar():
    return credenciales.cargar().get("restream_token")


def _guardar(datos):
    credenciales.guardar_campo("restream_token", datos)


def sesion() -> Sesion:
    """La única sesión de Restream de la app, creada la primera vez."""
    global _sesion
    with _CANDADO:
        if _sesion is None:
            _sesion = Sesion(
                cargar=_cargar,
                guardar=_guardar,
                renovar=lambda token: oauth.renovar(oauth.SERVICIO, token),
            )
        return _sesion


def conectar(parada=None, abrir=webbrowser.open) -> None:
    """Abre el navegador, espera la vuelta y guarda los tokens."""
    codigo, redirect_uri = oauth.esperar_codigo(abrir, parada=parada)
    tokens = oauth.canjear(oauth.SERVICIO, codigo, redirect_uri)
    sesion().establecer(tokens)


def desconectar(cliente=None) -> None:
    """Revoca el token de renovación y borra la sesión, pase lo que pase."""
    actual = sesion()
    token = actual.token_de_renovacion()
    try:
        if token:
            oauth.revocar(token, cliente)
    finally:
        actual.borrar()


def canales(cliente=None):
    """Canales de la cuenta, con el token vigente."""
    return api.canales(sesion().token(), cliente)


def perfil(cliente=None):
    """Correo y usuario de la cuenta, con el token vigente."""
    return api.perfil(sesion().token(), cliente)


def eliminar_canal(identificador, cliente=None):
    """Elimina un canal de la cuenta, con el token vigente."""
    return api.eliminar_canal(sesion().token(), identificador, cliente)


def eventos(tipo, cliente=None):
    """Eventos del tipo pedido, con el token vigente."""
    return api.eventos(sesion().token(), tipo, cliente)


def estadisticas(identificador, cliente=None):
    """Estadísticas del evento, con el token vigente."""
    return api.estadisticas(sesion().token(), identificador, cliente)


def _reiniciar() -> None:
    """Olvida la sesión creada, solo para las pruebas."""
    global _sesion
    with _CANDADO:
        _sesion = None
