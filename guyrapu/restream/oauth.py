"""Inicio de sesión en Restream por OAuth y llamadas al servicio de tokens.

El secreto de la aplicación no vive en la app: el canje y la renovación
pasan por un servicio propio que lo agrega. La revocación va directa a
Restream, que no lo pide. Ningún código, `state` ni token se escribe en el
registro ni en el texto de un error.
"""

from __future__ import annotations

import html
import http.server
import logging
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from guyrapu.core.config import APP_NAME
from guyrapu.core.idioma import _, idioma_actual
from guyrapu.restream import sesion

logger = logging.getLogger(__name__)

CLIENT_ID = "f6eefc35-0057-49eb-93a0-cd2d95ec18be"
SERVICIO = "https://restream-tokens.guyrapu.workers.dev"
PUERTOS = (47615, 47616)
RUTA_VUELTA = "/callback"
PLAZO = 300.0
AUTORIZACION = "https://api.restream.io/login"
REVOCACION = "https://api.restream.io/oauth/revoke"
ESPERA = 15.0
INTERVALO = 0.5


class InicioCancelado(Exception):
    """La persona canceló el inicio de sesión en Restream."""

    def __init__(self):
        super().__init__(
            _("Se canceló el inicio de sesión en Restream."))


class PlazoVencido(Exception):
    """No llegó la vuelta de Restream antes del plazo o se pidió parar."""

    def __init__(self):
        super().__init__(
            _("No llegó la respuesta de Restream a tiempo. Vuelve a intentarlo."))


class PuertosOcupados(Exception):
    """Ninguno de los puertos locales de vuelta se pudo reservar."""

    def __init__(self):
        super().__init__(
            _("Los puertos 47615 y 47616 están ocupados. Cierra la aplicación "
              "que los usa y vuelve a intentarlo."))


class FalloServicio(Exception):
    """El servicio de tokens o la red no permitieron completar la operación."""

    def __init__(self):
        super().__init__(
            _("No se pudo completar el inicio de sesión con Restream. "
              "Vuelve a intentarlo."))


def url_autorizacion(redirect_uri, state, client_id=CLIENT_ID):
    """Dirección de Restream a la que se manda el navegador."""
    parametros = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTORIZACION}?{urlencode(parametros)}"


def _pagina(exito):
    """Página corta que el navegador muestra al volver de Restream."""
    if exito:
        texto = _("{app} ya tiene acceso a tu cuenta de Restream. "
                  "Puedes cerrar esta pestaña.").format(app=APP_NAME)
    else:
        texto = _("No se completó el inicio de sesión en Restream. Puedes "
                  "cerrar esta pestaña y volver a intentarlo desde "
                  "{app}.").format(app=APP_NAME)
    idioma = html.escape(idioma_actual() or "")
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{idioma}">\n'
        f'<head><meta charset="utf-8"><title>{APP_NAME}</title></head>\n'
        f"<body><p>{html.escape(texto)}</p></body>\n"
        "</html>\n"
    ).encode("utf-8")


class _Manejador(http.server.BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/1.0"

    def log_message(self, formato, *argumentos):
        # La línea por defecto trae la ruta con el código a stderr.
        return

    def do_GET(self):
        partes = urlsplit(self.path)
        if partes.path != RUTA_VUELTA:
            self.send_error(404)
            return
        parametros = parse_qs(partes.query)
        estado = (parametros.get("state") or [""])[0]
        if not secrets.compare_digest(estado, self.server.estado):
            self.send_error(400)
            return
        logger.debug("llegó la vuelta de Restream")
        error = (parametros.get("error") or [""])[0]
        codigo = (parametros.get("code") or [""])[0]
        if error or not codigo:
            self.server.cancelado = True
            self._responder(False)
            self.server.terminado.set()
            return
        self.server.codigo = codigo
        self._responder(True)
        self.server.terminado.set()

    def _responder(self, exito):
        contenido = _pagina(exito)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(contenido)))
            self.end_headers()
            self.wfile.write(contenido)
        except OSError:
            pass


class _Servidor(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, direccion, estado):
        self.estado = estado
        self.codigo = None
        self.cancelado = False
        self.terminado = threading.Event()
        super().__init__(direccion, _Manejador)


def _crear_servidor(puertos, estado):
    for puerto in puertos:
        try:
            return _Servidor(("127.0.0.1", puerto), estado)
        except OSError:
            continue
    raise PuertosOcupados()


def esperar_codigo(abrir, plazo=PLAZO, parada=None, puertos=PUERTOS):
    """Abre el navegador y espera el código de vuelta en 127.0.0.1.

    Devuelve `(codigo, redirect_uri)`. Revisa el plazo y la parada entre
    pedido y pedido, con un tiempo de espera corto en el servidor.
    """
    estado = secrets.token_urlsafe(32)
    servidor = _crear_servidor(puertos, estado)
    redirect_uri = (f"http://127.0.0.1:{servidor.server_address[1]}"
                    f"{RUTA_VUELTA}")
    servidor.timeout = INTERVALO
    limite = time.monotonic() + plazo
    try:
        abrir(url_autorizacion(redirect_uri, estado))
        while not servidor.terminado.is_set():
            servidor.handle_request()
            if servidor.terminado.is_set():
                break
            if parada is not None and parada.is_set():
                raise PlazoVencido()
            if time.monotonic() >= limite:
                raise PlazoVencido()
        if servidor.cancelado or servidor.codigo is None:
            raise InicioCancelado()
        return servidor.codigo, redirect_uri
    finally:
        servidor.server_close()


def _post(cliente, url, cuerpo):
    try:
        return cliente.post(url, json=cuerpo, timeout=ESPERA)
    except httpx.HTTPError:
        logger.warning("no se pudo hablar con el servicio de Restream")
        raise FalloServicio() from None


def _leer(respuesta):
    try:
        return respuesta.json()
    except ValueError:
        raise FalloServicio() from None


def _tokens(respuesta):
    datos = _leer(respuesta)
    if respuesta.status_code != 200:
        raise FalloServicio()
    try:
        return sesion.tokens_de_respuesta(datos, time.time())
    except (TypeError, ValueError):
        raise FalloServicio() from None


def canjear(servicio, codigo, redirect_uri, cliente=None):
    """Canjea el código por tokens a través del servicio propio."""
    url = f"{servicio}/exchange"
    cuerpo = {
        "code": codigo,
        "redirect_uri": redirect_uri,
        "client_id": CLIENT_ID,
    }
    if cliente is None:
        with httpx.Client() as propio:
            return _tokens(_post(propio, url, cuerpo))
    return _tokens(_post(cliente, url, cuerpo))


def _renovar_con(cliente, url, cuerpo):
    respuesta = _post(cliente, url, cuerpo)
    datos = _leer(respuesta)
    if isinstance(datos, dict) and datos.get("error") == "invalid_grant":
        raise sesion.RechazoDeConcesion()
    if respuesta.status_code != 200:
        raise FalloServicio()
    try:
        sesion.tokens_de_respuesta(datos, time.time())
    except (TypeError, ValueError):
        raise FalloServicio() from None
    return datos


def renovar(servicio, token_de_renovacion, cliente=None):
    """Renueva el par de tokens a través del servicio propio.

    Devuelve el diccionario de la respuesta y no `Tokens`, porque
    `Sesion.token()` espera el JSON del servidor y lo interpreta con
    `tokens_de_respuesta`.
    """
    url = f"{servicio}/refresh"
    cuerpo = {"refresh_token": token_de_renovacion, "client_id": CLIENT_ID}
    if cliente is None:
        with httpx.Client() as propio:
            return _renovar_con(propio, url, cuerpo)
    return _renovar_con(cliente, url, cuerpo)


def _revocar(cliente, datos):
    try:
        cliente.post(REVOCACION, data=datos, timeout=ESPERA)
    except Exception as error:
        logger.warning("no se pudo revocar el acceso a Restream: %s",
                       type(error).__name__)


def revocar(token_de_renovacion, cliente=None):
    """Pide a Restream que anule el token de renovación; nunca lanza."""
    datos = {"token": token_de_renovacion, "token_type_hint": "refresh_token"}
    if cliente is None:
        with httpx.Client() as propio:
            _revocar(propio, datos)
    else:
        _revocar(cliente, datos)
