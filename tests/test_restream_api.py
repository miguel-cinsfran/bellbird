"""Pruebas de lo que se le pide a la API REST de Restream."""

import os
import unittest
from unittest import mock

import httpx

from bellbird.restream import api


TOKEN = "token-secreto-de-prueba"
ID_EVENTO = "fa2f5c54-4de5-4118-a4b0-925c648c49d6"
ID_HISTORIA = "0b6b1f7e-2f34-4d0a-9c11-4c3f7d2a5e10"

PLATAFORMAS = [
    {"id": 1, "name": "Twitch"},
    {"id": 5, "name": "Youtube"},
    {"id": 37, "name": "Facebook"},
    {"id": 67, "name": "TikTok"},
]

CANALES = [
    {"id": 10, "platformId": 67, "channelUrl": "https://tiktok.com/@uno",
     "displayName": "szeiryugaming"},
    {"id": 11, "platformId": 5, "channelUrl": "https://youtube.com/@dos",
     "displayName": "dos"},
    {"id": 12, "platformId": 1, "channelUrl": "https://twitch.tv/tres",
     "displayName": "tres"},
    {"id": 13, "platformId": 37, "channelUrl": "https://facebook.com/cuatro",
     "displayName": "cuatro"},
]

CANALES_ACTUALES = [
    {"id": 10, "streamingPlatformId": 67, "embedUrl": "https://embed/uno",
     "url": "https://tiktok.com/@uno", "identifier": "uno",
     "displayName": "szeiryuGaming", "enabled": True},
    {"id": 11, "streamingPlatformId": 5, "embedUrl": "https://embed/dos",
     "url": "https://youtube.com/@dos", "identifier": "dos",
     "displayName": "dos", "enabled": False},
]

PERFIL = {
    "id": 1,
    "username": "manolopez643_96db9af7",
    "email": "manu@example.com",
}


def _sin_red(_pedido):
    raise httpx.ConnectError("sin red")


class TestCanales(unittest.TestCase):

    def setUp(self):
        self._cache = mock.patch.object(api, "_PLATAFORMAS", None)
        self._cache.start()
        self.addCleanup(self._cache.stop)

    def _cliente(self, manejar):
        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        return cliente

    def test_p4_lee_los_canales_y_los_ordena(self):
        pedidos = []

        def manejar(pedido):
            pedidos.append(pedido)
            if pedido.url.path == "/v2/platform/all":
                return httpx.Response(200, json=PLATAFORMAS)
            if pedido.url.path == "/v2/user/channel/all":
                return httpx.Response(200, json=CANALES)
            return httpx.Response(404)

        resultado = api.canales(TOKEN, self._cliente(manejar))

        self.assertEqual(
            [(13, 37, "Facebook", "cuatro", "https://facebook.com/cuatro"),
             (10, 67, "TikTok", "szeiryugaming", "https://tiktok.com/@uno"),
             (12, 1, "Twitch", "tres", "https://twitch.tv/tres"),
             (11, 5, "YouTube", "dos", "https://youtube.com/@dos")],
            [(canal.id, canal.plataforma_id, canal.plataforma, canal.nombre,
              canal.url) for canal in resultado])
        self.assertEqual([True, True, True, True],
                         [canal.activo for canal in resultado])
        self.assertEqual(
            ["Facebook: cuatro", "TikTok: szeiryugaming",
             "Twitch: tres", "YouTube: dos"],
            [canal.texto for canal in resultado])

        pedido = [p for p in pedidos
                  if p.url.path == "/v2/user/channel/all"][0]
        self.assertEqual(pedido.headers["authorization"], f"Bearer {TOKEN}")
        publicas = [p for p in pedidos if p.url.path == "/v2/platform/all"]
        self.assertEqual(len(publicas), 1)
        self.assertNotIn("authorization", publicas[0].headers)

    def test_p4_la_forma_de_channel_all_trae_la_plataforma_y_si_esta_activo(
            self):
        def manejar(pedido):
            if pedido.url.path == "/v2/platform/all":
                return httpx.Response(200, json=PLATAFORMAS)
            if pedido.url.path == "/v2/user/channel/all":
                return httpx.Response(200, json=CANALES_ACTUALES)
            return httpx.Response(404)

        resultado = api.canales(TOKEN, self._cliente(manejar))

        self.assertEqual(
            [(10, 67, "TikTok", "szeiryuGaming",
              "https://tiktok.com/@uno", True),
             (11, 5, "YouTube", "dos", "https://youtube.com/@dos", False)],
            [(canal.id, canal.plataforma_id, canal.plataforma, canal.nombre,
              canal.url, canal.activo) for canal in resultado])
        self.assertEqual(["TikTok: szeiryuGaming", "YouTube: dos"],
                         [canal.texto for canal in resultado])

    def test_p4_salta_la_entrada_rota_y_cae_a_la_url(self):
        def manejar(pedido):
            if pedido.url.path == "/v2/platform/all":
                return httpx.Response(200, json=PLATAFORMAS)
            return httpx.Response(200, json=[
                {"id": "no-es-entero", "platformId": 67,
                 "displayName": "roto", "channelUrl": "https://x"},
                {"platformId": 67, "displayName": "sin id",
                 "channelUrl": "https://x"},
                {"id": 7, "platformId": 67, "displayName": "",
                 "channelUrl": "https://tiktok.com/@siete"},
            ])

        resultado = api.canales(TOKEN, self._cliente(manejar))

        self.assertEqual([7], [canal.id for canal in resultado])
        self.assertEqual("https://tiktok.com/@siete", resultado[0].nombre)
        self.assertEqual("https://tiktok.com/@siete", resultado[0].url)

    def test_p5_la_lista_publica_corrige_youtube_y_se_lee_una_vez(self):
        pedidos = []

        def manejar(pedido):
            pedidos.append(pedido)
            return httpx.Response(200, json=PLATAFORMAS)

        mapa = api.plataformas(self._cliente(manejar))
        self.assertEqual("YouTube", mapa[5])
        self.assertEqual("Twitch", mapa[1])
        self.assertEqual("TikTok", mapa[67])
        self.assertEqual(mapa, api.plataformas(self._cliente(manejar)))
        self.assertEqual(1, len(pedidos))

    def test_p5_una_plataforma_desconocida_se_muestra_como_plataforma_id(self):
        def manejar(pedido):
            if pedido.url.path == "/v2/platform/all":
                return httpx.Response(200, json=PLATAFORMAS)
            return httpx.Response(200, json=[
                {"id": 7, "platformId": 999, "displayName": "raro",
                 "channelUrl": "https://x"},
            ])

        resultado = api.canales(TOKEN, self._cliente(manejar))

        self.assertEqual("Plataforma 999", resultado[0].plataforma)
        self.assertEqual("Plataforma 999: raro", resultado[0].texto)

    def test_p6_cualquier_fallo_es_error_propio_sin_el_token(self):
        def sin_json(_pedido):
            return httpx.Response(200, text="no es json")

        casos = {
            "401": lambda pedido: httpx.Response(401, json={"error": "x"}),
            "sin red": _sin_red,
            "sin json": sin_json,
        }
        for nombre, respuesta in casos.items():
            with self.subTest(caso=nombre):
                def manejar(pedido):
                    if pedido.url.path == "/v2/platform/all":
                        return httpx.Response(200, json=PLATAFORMAS)
                    return respuesta(pedido)

                with self.assertLogs(api.logger, level="WARNING") as registro:
                    with self.assertRaises(api.ErrorApi) as contexto:
                        api.canales(TOKEN, self._cliente(manejar))

                self.assertIn("destinos", str(contexto.exception).lower())
                self.assertNotIn(TOKEN, str(contexto.exception))
                self.assertNotIn(TOKEN, "\n".join(registro.output))


class TestPerfil(unittest.TestCase):

    def _cliente(self, manejar):
        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        return cliente

    def test_perfil_lee_correo_y_usuario(self):
        visto = {}

        def manejar(pedido):
            visto["ruta"] = pedido.url.path
            visto["autorizacion"] = pedido.headers.get("authorization")
            return httpx.Response(200, json=PERFIL)

        datos = api.perfil(TOKEN, self._cliente(manejar))

        self.assertEqual("/v2/user/profile", visto["ruta"])
        self.assertEqual(f"Bearer {TOKEN}", visto["autorizacion"])
        self.assertEqual("manu@example.com", datos.correo)
        self.assertEqual("manolopez643_96db9af7", datos.usuario)

    def test_perfil_sin_correo_deja_el_correo_vacio(self):
        def manejar(_pedido):
            return httpx.Response(200, json={
                "id": 1, "username": "manolopez643_96db9af7"})

        datos = api.perfil(TOKEN, self._cliente(manejar))

        self.assertEqual("", datos.correo)
        self.assertEqual("manolopez643_96db9af7", datos.usuario)

    def test_perfil_fuera_de_200_es_error_propio_sin_el_token(self):
        def manejar(_pedido):
            return httpx.Response(401, json={"error": "x"})

        with self.assertLogs(api.logger, level="WARNING"):
            with self.assertRaises(api.ErrorApi) as contexto:
                api.perfil(TOKEN, self._cliente(manejar))

        self.assertNotIn(TOKEN, str(contexto.exception))


class TestEliminarCanal(unittest.TestCase):

    def _cliente(self, manejar):
        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        return cliente

    def test_eliminar_canal_manda_delete_y_acepta_2xx(self):
        visto = {}

        def manejar(pedido):
            visto["metodo"] = pedido.method
            visto["url"] = str(pedido.url)
            visto["autorizacion"] = pedido.headers.get("authorization")
            return httpx.Response(204)

        api.eliminar_canal(TOKEN, 10, self._cliente(manejar))

        self.assertEqual("DELETE", visto["metodo"])
        self.assertEqual("https://api.restream.io/v2/user/channels/10",
                         visto["url"])
        self.assertEqual(f"Bearer {TOKEN}", visto["autorizacion"])

    def test_eliminar_canal_fuera_de_2xx_es_error_propio_sin_el_token(self):
        def manejar(_pedido):
            return httpx.Response(404, json={"error": "x"})

        with self.assertLogs(api.logger, level="WARNING"):
            with self.assertRaises(api.ErrorApi) as contexto:
                api.eliminar_canal(TOKEN, 10, self._cliente(manejar))

        self.assertNotIn(TOKEN, str(contexto.exception))


class TestEventos(unittest.TestCase):

    def _cliente(self, manejar):
        cliente = httpx.Client(transport=httpx.MockTransport(manejar))
        self.addCleanup(cliente.close)
        return cliente

    def test_pide_la_ruta_de_cada_tipo_y_su_token(self):
        from bellbird.restream.eventos import TIPO_EN_DIRECTO, TIPO_HISTORIAL, TIPO_PROXIMOS

        rutas = {
            TIPO_PROXIMOS:
                "https://api.restream.io/v2/user/events/upcoming?source=2",
            TIPO_EN_DIRECTO:
                "https://api.restream.io/v2/user/events/in-progress",
            TIPO_HISTORIAL:
                "https://api.restream.io/v2/user/events/history?page=1&limit=50",
        }
        for tipo, esperada in rutas.items():
            with self.subTest(tipo=tipo):
                visto = {}

                def manejar(pedido):
                    visto["url"] = str(pedido.url)
                    visto["autorizacion"] = pedido.headers.get("authorization")
                    return httpx.Response(200, json=[
                        {"id": ID_EVENTO, "status": "upcoming",
                         "title": "Charla", "destinations": []}])

                leidos = api.eventos(TOKEN, tipo, self._cliente(manejar))

                self.assertEqual(esperada, visto["url"])
                self.assertEqual(f"Bearer {TOKEN}",
                                 visto["autorizacion"])
                self.assertEqual([ID_EVENTO],
                                 [evento.id for evento in leidos])

    def test_el_historial_llega_con_items(self):
        def manejar(_pedido):
            return httpx.Response(200, json={
                "items": [{"id": ID_HISTORIA, "status": "finished",
                           "title": "Terminada", "destinations": []}],
                "pagination": {"page": 1},
            })

        leidos = api.eventos(TOKEN, "historial", self._cliente(manejar))

        self.assertEqual([ID_HISTORIA],
                         [evento.id for evento in leidos])

    def test_estadisticas_pide_el_evento_y_lee_el_total(self):
        visto = {}

        def manejar(pedido):
            visto["url"] = str(pedido.url)
            return httpx.Response(200, json={
                "total": {"mean": 3, "max": 8, "viewsTotal": 20,
                          "watchedTime": 90},
                "byChannel": {},
            })

        leidas = api.estadisticas(TOKEN, ID_EVENTO, self._cliente(manejar))

        self.assertEqual(
            "https://api.restream.io/v2/user/events/"
            f"{ID_EVENTO}/analytics/viewers",
            visto["url"])
        self.assertEqual(3, leidas.promedio)
        self.assertEqual(8, leidas.maximo)
        self.assertEqual(20, leidas.vistas)
        self.assertEqual(90, leidas.tiempo_visto)

    def test_un_fallo_es_error_propio_sin_el_token(self):
        def manejar(_pedido):
            return httpx.Response(500, json={"error": "x"})

        with self.assertLogs(api.logger, level="WARNING"):
            with self.assertRaises(api.ErrorApi) as contexto:
                api.eventos(TOKEN, "proximos", self._cliente(manejar))

        self.assertNotIn(TOKEN, str(contexto.exception))


@unittest.skipUnless(os.environ.get("BELLBIRD_PRUEBAS_CON_RED") == "1",
                     "necesita la cuenta real de Restream")
class TestContraRestreamReal(unittest.TestCase):

    def test_perfil_y_canales_de_verdad(self):
        from bellbird.restream import cuenta

        token = cuenta.sesion().token()
        if not token:
            self.skipTest("no hay una cuenta de Restream conectada")

        datos = api.perfil(token)
        canales = api.canales(token)

        self.assertIsInstance(datos.correo, str)
        self.assertIsInstance(datos.usuario, str)
        self.assertIsInstance(canales, list)

    def test_los_tres_tipos_de_eventos_y_sus_estadisticas(self):
        from bellbird.restream import cuenta
        from bellbird.restream.eventos import (
            TIPO_EN_DIRECTO, TIPO_HISTORIAL, TIPO_PROXIMOS)

        token = cuenta.sesion().token()
        if not token:
            self.skipTest("no hay una cuenta de Restream conectada")

        cabeceras = {"Authorization": f"Bearer {token}"}
        for tipo in (TIPO_PROXIMOS, TIPO_EN_DIRECTO, TIPO_HISTORIAL):
            with self.subTest(tipo=tipo):
                crudo = api._leer(
                    api._pedir(None, api.EVENTOS[tipo], cabeceras))
                if isinstance(crudo, dict):
                    crudo = crudo.get("items")
                self.assertIsInstance(crudo, list)
                leidos = api.eventos(token, tipo)
                self.assertEqual(
                    len(crudo), len(leidos),
                    f"{tipo}: la API trajo {len(crudo)} eventos crudos y "
                    f"se leyeron {len(leidos)}")
                for evento in leidos:
                    self.assertIsInstance(evento.id, str)
                    self.assertTrue(evento.id)

        historial = api.eventos(token, TIPO_HISTORIAL)
        self.assertTrue(historial, "la cuenta no tiene eventos terminados")

        leidas = api.estadisticas(token, historial[0].id)
        self.assertGreaterEqual(leidas.vistas, 0)
        self.assertGreaterEqual(leidas.tiempo_visto, 0)


if __name__ == "__main__":
    unittest.main()
