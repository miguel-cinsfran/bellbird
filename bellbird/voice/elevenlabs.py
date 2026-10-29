"""Cliente HTTP de ElevenLabs para el motor de voz del lector.

Solo biblioteca estándar: la síntesis es un POST, y las voces y el saldo son
GET, así que `urllib.request` alcanza y no hace falta ninguna dependencia
nueva. Nunca deja salir un error de red crudo: todo se traduce a
`ElevenLabsError` con un `motivo` y una frase en español lista para anunciar,
para que el worker decida el respaldo sin conocer la API.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from bellbird.core import diagnostico
from bellbird.core.idioma import N_, _
from bellbird.voice import escala_voz

logger = diagnostico.obtener_logger(__name__)

_URL_BASE = "https://api.elevenlabs.io"
_URL_TTS = _URL_BASE + "/v1/text-to-speech/{voice_id}?output_format=wav_22050"
_URL_VOCES = _URL_BASE + "/v2/voices?page_size=100"
_URL_SALDO = _URL_BASE + "/v1/user/subscription"

_MODELO = "eleven_flash_v2_5"
_IDIOMA = "es"

MOTIVO_CLAVE = "clave"
MOTIVO_SALDO = "saldo"
MOTIVO_LIMITE = "limite"
MOTIVO_RED = "red"
MOTIVO_OTRO = "otro"

_MSG_CLAVE = N_("La clave de ElevenLabs no es válida.")
_MSG_SALDO = N_("Se acabó el saldo de ElevenLabs.")
_MSG_LIMITE = N_("ElevenLabs está recibiendo demasiadas peticiones.")
_MSG_RED = N_("No se pudo conectar con ElevenLabs.")
# Traductores: {codigo} es el código de error de ElevenLabs.
_MSG_OTRO = N_("ElevenLabs devolvió un error {codigo}.")


class ElevenLabsError(Exception):
    """Fallo al hablar con ElevenLabs, con el motivo para decidir el respaldo."""

    def __init__(self, motivo: str, mensaje: str):
        super().__init__(mensaje)
        self.motivo = motivo


def _error_de_http(exc) -> ElevenLabsError:
    """Traduce un HTTPError a la frase y el motivo que le corresponden."""
    codigo = int(getattr(exc, "code", 0) or 0)
    try:
        cuerpo = (exc.read() or b"").decode("utf-8", "replace")
    except Exception:
        cuerpo = ""
    if codigo == 429:
        return ElevenLabsError(MOTIVO_LIMITE, _(_MSG_LIMITE))
    # 402 es saldo por contrato; 401 trae `quota_exceeded` en el cuerpo cuando
    # en realidad es saldo y no una clave mala.
    if codigo == 402 or (codigo == 401 and "quota_exceeded" in cuerpo):
        return ElevenLabsError(MOTIVO_SALDO, _(_MSG_SALDO))
    if codigo == 401:
        return ElevenLabsError(MOTIVO_CLAVE, _(_MSG_CLAVE))
    return ElevenLabsError(MOTIVO_OTRO, _(_MSG_OTRO).format(codigo=codigo))


class ClienteElevenLabs:
    """Habla con la API de ElevenLabs. `abrir` se inyecta en las pruebas."""

    def __init__(self, clave: str, abrir=urllib.request.urlopen,
                 tiempo: float = 15.0):
        self._clave = clave or ""
        self._abrir = abrir
        self._tiempo = tiempo

    def _pedir(self, peticion) -> bytes:
        try:
            with self._abrir(peticion, timeout=self._tiempo) as respuesta:
                return respuesta.read()
        except urllib.error.HTTPError as exc:
            raise _error_de_http(exc) from exc
        except (urllib.error.URLError, OSError) as exc:
            # URLError cubre DNS, tiempo agotado y sin conexión.
            raise ElevenLabsError(MOTIVO_RED, _(_MSG_RED)) from exc

    def _peticion(self, metodo: str, url: str, cuerpo=None, aceptar=None):
        cabeceras = {"xi-api-key": self._clave}
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode("utf-8")
            cabeceras["Content-Type"] = "application/json"
        if aceptar:
            cabeceras["Accept"] = aceptar
        return urllib.request.Request(url, data=datos, headers=cabeceras,
                                      method=metodo)

    def _json(self, metodo: str, url: str):
        bruto = self._pedir(self._peticion(metodo, url))
        try:
            return json.loads(bruto.decode("utf-8"))
        except Exception as exc:
            raise ElevenLabsError(MOTIVO_OTRO, _(_MSG_OTRO).format(codigo=200)) from exc

    def voces(self) -> list[tuple[str, str]]:
        """Todas las voces (id, nombre), recorriendo las páginas."""
        pares: list[tuple[str, str]] = []
        url = _URL_VOCES
        while url:
            datos = self._json("GET", url)
            for voz in datos.get("voices") or []:
                vid = voz.get("voice_id")
                nombre = voz.get("name")
                if vid and nombre:
                    pares.append((str(vid), str(nombre)))
            token = datos.get("next_page_token")
            if datos.get("has_more") and token:
                url = (f"{_URL_VOCES}&next_page_token="
                       f"{urllib.parse.quote(str(token), safe='')}")
            else:
                url = None
        return pares

    def saldo(self) -> tuple[int, int]:
        """Caracteres usados y límite del período actual."""
        datos = self._json("GET", _URL_SALDO)
        usados = int(datos.get("character_count") or 0)
        limite = int(datos.get("character_limit") or 0)
        return usados, limite

    def sintetizar(self, texto: str, voice_id: str, velocidad_pct: int) -> bytes:
        """Devuelve el WAV de la frase. Lanza `ElevenLabsError` si falla."""
        velocidad = escala_voz.velocidad_a_elevenlabs(velocidad_pct)
        url = _URL_TTS.format(voice_id=urllib.parse.quote(str(voice_id), safe=""))
        cuerpo = {
            "text": texto,
            "model_id": _MODELO,
            "language_code": _IDIOMA,
            "voice_settings": {"speed": velocidad},
        }
        return self._pedir(
            self._peticion("POST", url, cuerpo, aceptar="audio/wav"))
