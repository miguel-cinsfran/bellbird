"""Ajustes comunes de la suite de pruebas."""

import errno
import os
import socket
from contextlib import contextmanager

os.environ.setdefault("GUYRAPU_IDIOMA", "es")


def _es_destino_local(destino):
    if not isinstance(destino, tuple) or len(destino) < 2:
        return True
    host = destino[0]
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    host = host.strip().lower()
    if host in ("localhost", "::1", "0.0.0.0"):
        return True
    return host.startswith("127.")


def _con_bloqueo(conectar):
    def conectado(sock, destino, *args, **kwargs):
        if not _es_destino_local(destino):
            raise OSError(
                errno.ENETUNREACH,
                "Conexión de red bloqueada durante las pruebas hacia "
                f"{destino[0]}:{destino[1]}")
        return conectar(sock, destino, *args, **kwargs)
    return conectado


if os.environ.get("GUYRAPU_PRUEBAS_CON_RED") != "1":
    # create_connection llama a connect, así que parchear connect alcanza.
    socket.socket.connect = _con_bloqueo(socket.socket.connect)
    socket.socket.connect_ex = _con_bloqueo(socket.socket.connect_ex)


def _instalar_guarda_de_cuadros():
    try:
        import wx
    except Exception:
        return
    for nombre in ("MessageDialog", "RichMessageDialog"):
        clase = getattr(wx, nombre, None)
        if clase is None:
            continue
        original = clase.ShowModal

        def _show_modal(dialogo, *args, __original=original, **kwargs):
            if os.environ.get("GUYRAPU_PRUEBAS_CON_CUADROS") == "1":
                return __original(dialogo, *args, **kwargs)
            try:
                titulo = dialogo.GetTitle()
            except Exception:
                titulo = ""
            raise AssertionError(
                "Una prueba abrió un cuadro de Windows real: "
                f"{titulo}")

        clase.ShowModal = _show_modal


@contextmanager
def cuadros_reales_permitidos():
    """Deja abrir cuadros nativos de verdad mientras dura el contexto."""
    anterior = os.environ.get("GUYRAPU_PRUEBAS_CON_CUADROS")
    os.environ["GUYRAPU_PRUEBAS_CON_CUADROS"] = "1"
    try:
        yield
    finally:
        if anterior is None:
            os.environ.pop("GUYRAPU_PRUEBAS_CON_CUADROS", None)
        else:
            os.environ["GUYRAPU_PRUEBAS_CON_CUADROS"] = anterior


if os.environ.get("GUYRAPU_PRUEBAS_CON_CUADROS") != "1":
    _instalar_guarda_de_cuadros()
