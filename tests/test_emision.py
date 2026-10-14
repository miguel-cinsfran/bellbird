"""Pruebas de la emisión de YouTube con dobles (sin red ni API real)."""

import threading
import unittest
from datetime import datetime
from unittest import mock

from ytchat.obs import obs_cliente
from ytchat.obs.obs_destinos import Destino
from ytchat.youtube import emision
from ytchat.youtube.emision import (
    EmisionError, cuerpo_emision, esperar_en_vivo, preparar_en_youtube,
    titulo_por_defecto, url_video,
)


class TestCuerpoEmision(unittest.TestCase):

    def test_basico(self):
        cuerpo = cuerpo_emision(" Hola ", " Mundo ", "unlisted",
                                "2026-10-14T20:00:00Z")
        self.assertEqual(cuerpo["snippet"]["title"], "Hola")
        self.assertEqual(cuerpo["snippet"]["description"], "Mundo")
        self.assertEqual(cuerpo["snippet"]["scheduledStartTime"],
                         "2026-10-14T20:00:00Z")
        self.assertEqual(cuerpo["status"]["privacyStatus"], "unlisted")
        self.assertFalse(cuerpo["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(
            cuerpo["contentDetails"]["enableAutoStart"])
        self.assertTrue(cuerpo["contentDetails"]["enableAutoStop"])

    def test_recorta_titulo_y_descripcion(self):
        cuerpo = cuerpo_emision("x" * 150, "y" * 6000, "public",
                                "2026-10-14T20:00:00Z")
        self.assertEqual(len(cuerpo["snippet"]["title"]), 100)
        self.assertEqual(len(cuerpo["snippet"]["description"]), 5000)

    def test_titulo_vacio(self):
        with self.assertRaises(EmisionError) as contexto:
            cuerpo_emision("   ", "algo", "unlisted",
                           "2026-10-14T20:00:00Z")
        self.assertEqual(str(contexto.exception),
                         "Falta el título del directo.")

    def test_privacidad_invalida(self):
        with self.assertRaises(ValueError):
            cuerpo_emision("Hola", "", "solo-yo",
                           "2026-10-14T20:00:00Z")


class TestTituloYUrl(unittest.TestCase):

    def test_titulo_por_defecto(self):
        self.assertEqual(titulo_por_defecto(datetime(2026, 10, 14)),
                         "Directo del 14/10/2026")

    def test_url_video(self):
        self.assertEqual(url_video("abc123"),
                         "https://www.youtube.com/watch?v=abc123")


class ClienteYTFalso:
    def __init__(self, flujo=("flujo-1", "rtmp://servidor", "clave"),
                 id_video="vid123", token=None, fallos=None):
        self.flujo = flujo
        self.id_video = id_video
        self.token = token
        self.fallos = fallos or {}
        self.borradas = []

    def flujo_reutilizable(self):
        if "flujo" in self.fallos:
            raise self.fallos["flujo"]
        return self.flujo

    def crear_emision(self, cuerpo):
        if "crear" in self.fallos:
            raise self.fallos["crear"]
        self.cuerpo = cuerpo
        return self.id_video

    def vincular_emision(self, id_video, id_flujo):
        if "vincular" in self.fallos:
            raise self.fallos["vincular"]
        self.vinculada = (id_video, id_flujo)

    def borrar_emision(self, id_video):
        self.borradas.append(id_video)
        if "borrar" in self.fallos:
            raise self.fallos["borrar"]

    def token_actualizado(self):
        return self.token


class TestPrepararEnYoutube(unittest.TestCase):

    def test_camino_feliz(self):
        cliente_yt = ClienteYTFalso()
        pedidos = []

        def preparar_destino(cliente_obs, destino, parada=None):
            pedidos.append((cliente_obs, destino, parada))

        parada = threading.Event()
        cuerpo = {"snippet": {"title": "Hola"}}
        devuelto = preparar_en_youtube(
            cliente_yt, "obs", cuerpo, parada=parada,
            preparar_destino=preparar_destino)
        self.assertEqual(devuelto, "vid123")
        self.assertEqual(pedidos, [(
            "obs", Destino("YouTube", "rtmp://servidor", "clave"),
            parada)])
        self.assertEqual(cliente_yt.vinculada, ("vid123", "flujo-1"))
        self.assertEqual(cliente_yt.borradas, [])

    def test_sin_flujo_reutilizable(self):
        cliente_yt = ClienteYTFalso(flujo=None)
        with self.assertRaises(EmisionError) as contexto:
            preparar_en_youtube(cliente_yt, "obs", {},
                                preparar_destino=lambda *a, **k: None)
        self.assertIn("reutilizable", str(contexto.exception))
        self.assertEqual(cliente_yt.borradas, [])

    def test_fallo_en_vincular_borra_la_emision(self):
        cliente_yt = ClienteYTFalso(fallos={"vincular": RuntimeError("boom")})
        with self.assertRaises(EmisionError):
            preparar_en_youtube(cliente_yt, "obs", {},
                                preparar_destino=lambda *a, **k: None)
        self.assertEqual(cliente_yt.borradas, ["vid123"])

    def test_fallo_en_preparar_borra_la_emision(self):
        cliente_yt = ClienteYTFalso()

        def preparar_roto(cliente_obs, destino, parada=None):
            raise obs_cliente.ObsError("OBS no aplicó el destino.")

        with self.assertRaises(obs_cliente.ObsError):
            preparar_en_youtube(cliente_yt, "obs", {},
                                preparar_destino=preparar_roto)
        self.assertEqual(cliente_yt.borradas, ["vid123"])

    def test_fallo_al_borrar_no_tapa_el_original(self):
        cliente_yt = ClienteYTFalso(fallos={"vincular": RuntimeError("boom"),
                                           "borrar": RuntimeError("otro")})
        with self.assertRaises(EmisionError) as contexto:
            preparar_en_youtube(cliente_yt, "obs", {},
                                preparar_destino=lambda *a, **k: None)
        self.assertIn("boom", str(contexto.exception))
        self.assertEqual(cliente_yt.borradas, ["vid123"])

    def test_error_de_la_api_sale_traducido(self):
        cliente_yt = ClienteYTFalso(
            fallos={"crear": RuntimeError("quotaExceeded: basta")})
        with self.assertRaises(EmisionError) as contexto:
            preparar_en_youtube(cliente_yt, "obs", {},
                                preparar_destino=lambda *a, **k: None)
        self.assertIn("cuota", str(contexto.exception).lower())

    def test_guardar_token_con_token_nuevo(self):
        guardados = []
        cliente_yt = ClienteYTFalso(token="nuevo-token")
        preparar_en_youtube(
            cliente_yt, "obs", {},
            preparar_destino=lambda *a, **k: None,
            guardar_token=guardados.append)
        self.assertEqual(guardados, ["nuevo-token"])

    def test_guardar_token_tambien_si_algo_falla(self):
        guardados = []
        cliente_yt = ClienteYTFalso(token="nuevo-token",
                                    fallos={"vincular":
                                            RuntimeError("boom")})
        with self.assertRaises(EmisionError):
            preparar_en_youtube(
                cliente_yt, "obs", {},
                preparar_destino=lambda *a, **k: None,
                guardar_token=guardados.append)
        self.assertEqual(guardados, ["nuevo-token"])


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.ahora += segundos


class TestEsperarEnVivo(unittest.TestCase):

    def test_en_vivo_a_la_tercera(self):
        reloj = RelojFalso()
        estados = iter(["ready", "testing", "live"])
        visto = esperar_en_vivo(lambda _id: next(estados), "vid",
                                cada=5.0, limite=120.0,
                                dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertTrue(visto)
        self.assertEqual(reloj.ahora, 10.0)

    def test_limite_agotado(self):
        reloj = RelojFalso()
        visto = esperar_en_vivo(lambda _id: "ready", "vid",
                                cada=5.0, limite=12.0,
                                dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertFalse(visto)

    def test_parada(self):
        reloj = RelojFalso()
        parada = threading.Event()
        llamadas = []

        def consultar(id_video):
            llamadas.append(id_video)
            parada.set()
            return "ready"

        visto = esperar_en_vivo(consultar, "vid", parada=parada,
                                dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertFalse(visto)

    def test_excepcion_no_corta(self):
        reloj = RelojFalso()
        intentos = []

        def consultar(id_video):
            intentos.append(id_video)
            if len(intentos) < 3:
                raise RuntimeError("falla de red")
            return "live"

        visto = esperar_en_vivo(consultar, "vid",
                                dormir=reloj.dormir, reloj=reloj.reloj)
        self.assertTrue(visto)
        self.assertEqual(len(intentos), 3)


class TestGanchosYoutube(unittest.TestCase):

    def test_preparar_llama_a_preparar_en_youtube(self):
        cliente_yt = mock.Mock()
        cuerpo = {"snippet": {"title": "Hola"}}
        parada = threading.Event()
        preparar, _esperar = emision.ganchos_youtube(
            cliente_yt, cuerpo, guardar_token="guardar")
        with mock.patch.object(emision, "preparar_en_youtube",
                               return_value="vid123") as preparar_en:
            devuelto = preparar("obs", parada)
        self.assertEqual(devuelto, "vid123")
        preparar_en.assert_called_once_with(
            cliente_yt, "obs", cuerpo, parada=parada,
            guardar_token="guardar")

    def test_esperar_llama_a_esperar_en_vivo(self):
        cliente_yt = mock.Mock()
        _preparar, esperar = emision.ganchos_youtube(
            cliente_yt, {}, guardar_token=None)
        parada = threading.Event()
        with mock.patch.object(emision, "esperar_en_vivo",
                               return_value=True) as esperar_en:
            visto = esperar("vid123", parada, 30.0)
        self.assertTrue(visto)
        esperar_en.assert_called_once_with(
            cliente_yt.estado_emision, "vid123", parada, limite=30.0)


if __name__ == "__main__":
    unittest.main()
