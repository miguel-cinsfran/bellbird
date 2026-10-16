"""Tests del cliente HTTP de ElevenLabs (con `abrir` falso y una prueba real)."""

import io
import json
import unittest
import urllib.error

from ytchat.voice import elevenlabs


class _RespuestaFalsa:
    def __init__(self, cuerpo: bytes, status: int = 200):
        self._cuerpo = cuerpo
        self.status = status

    def read(self):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _abrir_con(cuerpo: bytes, status: int = 200):
    def abrir(peticion, timeout=None):
        return _RespuestaFalsa(cuerpo, status)
    return abrir


def _abrir_que_lanza(exc):
    def abrir(peticion, timeout=None):
        raise exc
    return abrir


def _http_error(codigo: int, cuerpo: bytes = b""):
    return urllib.error.HTTPError("https://api.elevenlabs.io", codigo,
                                  "error", {}, io.BytesIO(cuerpo))


class TestSintetizar(unittest.TestCase):

    def test_la_peticion_lleva_url_cabeceras_y_cuerpo_exactos(self):
        capturadas = []

        def abrir(peticion, timeout=None):
            capturadas.append(peticion)
            return _RespuestaFalsa(b"RIFF....WAVE")

        cliente = elevenlabs.ClienteElevenLabs("mi-clave", abrir=abrir)
        wav = cliente.sintetizar("Hola mundo", "voz-1", 50)

        self.assertEqual(wav, b"RIFF....WAVE")
        self.assertEqual(len(capturadas), 1)
        peticion = capturadas[0]
        self.assertEqual(peticion.get_method(), "POST")
        self.assertIn("/v1/text-to-speech/voz-1", peticion.full_url)
        self.assertIn("output_format=wav_22050", peticion.full_url)
        cabeceras = {k.lower(): v for k, v in peticion.headers.items()}
        self.assertEqual(cabeceras.get("xi-api-key"), "mi-clave")
        self.assertEqual(cabeceras.get("content-type"), "application/json")
        self.assertEqual(cabeceras.get("accept"), "audio/wav")
        cuerpo = json.loads(peticion.data.decode("utf-8"))
        self.assertEqual(cuerpo["text"], "Hola mundo")
        self.assertEqual(cuerpo["model_id"], "eleven_flash_v2_5")
        self.assertEqual(cuerpo["language_code"], "es")
        self.assertEqual(cuerpo["voice_settings"], {"speed": 1.0})

    def test_la_velocidad_usa_la_escala(self):
        capturadas = []

        def abrir(peticion, timeout=None):
            capturadas.append(peticion)
            return _RespuestaFalsa(b"x")

        cliente = elevenlabs.ClienteElevenLabs("k", abrir=abrir)
        cliente.sintetizar("texto", "v", 100)
        cuerpo = json.loads(capturadas[0].data.decode("utf-8"))
        self.assertEqual(cuerpo["voice_settings"]["speed"], 1.2)


class TestVoces(unittest.TestCase):

    def test_recorre_dos_paginas(self):
        paginas = [
            {"voices": [{"voice_id": "a", "name": "Ana"}],
             "has_more": True, "next_page_token": "tok"},
            {"voices": [{"voice_id": "b", "name": "Beto"}],
             "has_more": False},
        ]
        vistas = []

        def abrir(peticion, timeout=None):
            vistas.append(peticion.full_url)
            return _RespuestaFalsa(json.dumps(paginas[len(vistas) - 1]).encode())

        cliente = elevenlabs.ClienteElevenLabs("k", abrir=abrir)
        self.assertEqual(cliente.voces(), [("a", "Ana"), ("b", "Beto")])
        self.assertEqual(len(vistas), 2)
        self.assertIn("page_size=100", vistas[0])
        self.assertIn("next_page_token=tok", vistas[1])

    def test_ignora_voces_sin_id_o_sin_nombre(self):
        def abrir(peticion, timeout=None):
            return _RespuestaFalsa(json.dumps({
                "voices": [{"voice_id": "", "name": "Sin id"},
                           {"voice_id": "b", "name": ""},
                           {"voice_id": "c", "name": "Buena"}],
                "has_more": False,
            }).encode())

        cliente = elevenlabs.ClienteElevenLabs("k", abrir=abrir)
        self.assertEqual(cliente.voces(), [("c", "Buena")])


class TestSaldo(unittest.TestCase):

    def test_devuelve_usados_y_limite(self):
        def abrir(peticion, timeout=None):
            self.assertEqual(peticion.get_method(), "GET")
            self.assertIn("/v1/user/subscription", peticion.full_url)
            return _RespuestaFalsa(json.dumps(
                {"character_count": 120, "character_limit": 30000}).encode())

        cliente = elevenlabs.ClienteElevenLabs("k", abrir=abrir)
        self.assertEqual(cliente.saldo(), (120, 30000))


class TestErrores(unittest.TestCase):

    def _motivo(self, exc):
        cliente = elevenlabs.ClienteElevenLabs("k", abrir=_abrir_que_lanza(exc))
        with self.assertRaises(elevenlabs.ElevenLabsError) as ctx:
            cliente.voces()
        return ctx.exception

    def test_401_sin_quota_es_clave(self):
        exc = self._motivo(_http_error(401, b'{"detail":"unauthorized"}'))
        self.assertEqual(exc.motivo, "clave")
        self.assertEqual(str(exc), "La clave de ElevenLabs no es válida.")

    def test_401_con_quota_es_saldo(self):
        exc = self._motivo(_http_error(401, b'{"detail":{"status":"quota_exceeded"}}'))
        self.assertEqual(exc.motivo, "saldo")
        self.assertEqual(str(exc), "Se acabó el saldo de ElevenLabs.")

    def test_402_es_saldo(self):
        exc = self._motivo(_http_error(402, b""))
        self.assertEqual(exc.motivo, "saldo")
        self.assertEqual(str(exc), "Se acabó el saldo de ElevenLabs.")

    def test_429_es_limite(self):
        exc = self._motivo(_http_error(429, b""))
        self.assertEqual(exc.motivo, "limite")
        self.assertEqual(str(exc),
                         "ElevenLabs está recibiendo demasiadas peticiones.")

    def test_500_es_otro_con_el_codigo(self):
        exc = self._motivo(_http_error(500, b""))
        self.assertEqual(exc.motivo, "otro")
        self.assertEqual(str(exc), "ElevenLabs devolvió un error 500.")

    def test_urlerror_es_red(self):
        exc = self._motivo(urllib.error.URLError("sin ruta al host"))
        self.assertEqual(exc.motivo, "red")
        self.assertEqual(str(exc), "No se pudo conectar con ElevenLabs.")


class TestContraLaRed(unittest.TestCase):
    """Prueba real contra la API: solo puede probar el error de clave."""

    def test_voces_con_clave_inventada(self):
        cliente = elevenlabs.ClienteElevenLabs("clave-inventada-de-prueba",
                                               tiempo=10.0)
        try:
            voces = cliente.voces()
        except elevenlabs.ElevenLabsError as exc:
            if exc.motivo == "red":
                self.skipTest(f"sin conexión a ElevenLabs: {exc}")
            self.assertEqual(exc.motivo, "clave")
            self.assertEqual(str(exc), "La clave de ElevenLabs no es válida.")
        else:
            self.fail(f"con una clave inventada no debería haber voces: {voces!r}")


if __name__ == "__main__":
    unittest.main()
