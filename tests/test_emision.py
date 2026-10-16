"""Pruebas de la emisión de YouTube con dobles (sin red ni API real)."""

import threading
import unittest
from datetime import datetime
from unittest import mock

from ytchat.obs import obs_cliente
from ytchat.obs.obs_destinos import Destino
from ytchat.youtube import emision
from ytchat.youtube.emision import (
    EmisionError, chat_legible, cuerpo_emision, error_de_miniatura,
    esperar_en_vivo, etiquetas_de_texto, preparar_en_youtube,
    titulo_por_defecto, url_video,
)


class TestChatLegible(unittest.TestCase):

    def test_publico_se_lee(self):
        self.assertTrue(chat_legible("public"))

    def test_no_listado_se_lee(self):
        self.assertTrue(chat_legible("unlisted"))

    def test_privado_no_se_lee(self):
        self.assertFalse(chat_legible("private"))


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
        self.assertFalse(cuerpo["contentDetails"]["enableAutoStop"])

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

    def test_latencia_ninos_y_dvr(self):
        cuerpo = cuerpo_emision("Hola", "", "public",
                                "2026-10-14T20:00:00Z", latencia="ultraLow",
                                ninos=True, dvr=False)
        self.assertEqual(cuerpo["contentDetails"]["latencyPreference"],
                         "ultraLow")
        self.assertTrue(cuerpo["status"]["selfDeclaredMadeForKids"])
        self.assertFalse(cuerpo["contentDetails"]["enableDvr"])

    def test_latencia_desconocida_cae_a_normal(self):
        cuerpo = cuerpo_emision("Hola", "", "public",
                                "2026-10-14T20:00:00Z", latencia="turbo")
        self.assertEqual(cuerpo["contentDetails"]["latencyPreference"],
                         "normal")

    def test_opciones_por_defecto(self):
        cuerpo = cuerpo_emision("Hola", "", "public",
                                "2026-10-14T20:00:00Z")
        self.assertEqual(cuerpo["contentDetails"]["latencyPreference"],
                         "normal")
        self.assertFalse(cuerpo["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(cuerpo["contentDetails"]["enableDvr"])


class TestEtiquetasDeTexto(unittest.TestCase):

    def test_separa_limpia_y_saca_vacias(self):
        self.assertEqual(etiquetas_de_texto(" uno , dos ,, tres "),
                         ["uno", "dos", "tres"])

    def test_sin_repetidas_ignorando_mayusculas(self):
        self.assertEqual(etiquetas_de_texto("Uno, uno, UNO, dos"),
                         ["Uno", "dos"])

    def test_vacio_y_none(self):
        self.assertEqual(etiquetas_de_texto(""), [])
        self.assertEqual(etiquetas_de_texto(None), [])

    def test_corta_al_pasar_el_limite(self):
        self.assertEqual(etiquetas_de_texto("a" * 300 + ", " + "b" * 300),
                         ["a" * 300])

    def test_justo_en_el_limite_entra(self):
        self.assertEqual(etiquetas_de_texto("a" * 250 + ", " + "b" * 250),
                         ["a" * 250, "b" * 250])


class TestErrorDeMiniatura(unittest.TestCase):

    def test_jpg_png_y_mayusculas(self):
        for ruta in ("foto.jpg", "foto.png", "foto.JPEG", "FOTO.PNG"):
            with self.subTest(ruta=ruta):
                self.assertIsNone(
                    error_de_miniatura(ruta, tamanio=lambda _r: 100))

    def test_vacia(self):
        self.assertEqual(error_de_miniatura(""),
                         "No se encontró el archivo de la miniatura.")

    def test_extension(self):
        self.assertEqual(
            error_de_miniatura("foto.gif", tamanio=lambda _r: 10),
            "La miniatura tiene que ser JPG o PNG.")

    def test_no_existe(self):
        def revienta(_ruta):
            raise OSError("no está")
        self.assertEqual(error_de_miniatura("foto.jpg", tamanio=revienta),
                         "No se encontró el archivo de la miniatura.")

    def test_pasa_de_2mb(self):
        self.assertEqual(
            error_de_miniatura("foto.png",
                               tamanio=lambda _r: 2 * 1024 * 1024 + 1),
            "La miniatura pasa de 2 MB.")

    def test_justo_2mb_entra(self):
        self.assertIsNone(
            error_de_miniatura("foto.png",
                               tamanio=lambda _r: 2 * 1024 * 1024))


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
        self.orden = []

    def flujo_reutilizable(self):
        if "flujo" in self.fallos:
            raise self.fallos["flujo"]
        return self.flujo

    def crear_emision(self, cuerpo):
        if "crear" in self.fallos:
            raise self.fallos["crear"]
        self.orden.append("crear")
        self.cuerpo = cuerpo
        return self.id_video

    def vincular_emision(self, id_video, id_flujo):
        if "vincular" in self.fallos:
            raise self.fallos["vincular"]
        self.orden.append("vincular")
        self.vinculada = (id_video, id_flujo)

    def borrar_emision(self, id_video):
        self.borradas.append(id_video)
        if "borrar" in self.fallos:
            raise self.fallos["borrar"]

    def token_actualizado(self):
        return self.token

    def actualizar_categoria_y_etiquetas(self, id_video, titulo, descripcion,
                                         categoria, etiquetas):
        if "categoria" in self.fallos:
            raise self.fallos["categoria"]
        self.orden.append("categoria")
        self.categoria_etiquetas = (id_video, titulo, descripcion, categoria,
                                    etiquetas)

    def poner_miniatura(self, id_video, ruta):
        if "miniatura" in self.fallos:
            raise self.fallos["miniatura"]
        self.orden.append("miniatura")
        self.miniatura = (id_video, ruta)


class ErrorHttp403(Exception):
    def __init__(self):
        super().__init__("HttpError 403: Forbidden")
        self.resp = type("Resp", (), {"status": 403})()


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


class TestPrepararExtras(unittest.TestCase):

    def _correr(self, cliente_yt, extras=None, avisar=None):
        return preparar_en_youtube(
            cliente_yt, "obs", {}, preparar_destino=lambda *a, **k: None,
            extras=extras, avisar=avisar)

    def test_aplica_categoria_etiquetas_y_miniatura(self):
        cliente_yt = ClienteYTFalso()
        avisos = []
        extras = {"categoria": "20", "etiquetas": ["uno", "dos"],
                  "miniatura": "foto.jpg", "titulo": "T",
                  "descripcion": "D"}
        self.assertEqual(self._correr(cliente_yt, extras, avisos.append),
                         "vid123")
        self.assertEqual(cliente_yt.categoria_etiquetas,
                         ("vid123", "T", "D", "20", ["uno", "dos"]))
        self.assertEqual(cliente_yt.miniatura, ("vid123", "foto.jpg"))
        self.assertEqual(cliente_yt.orden,
                         ["crear", "vincular", "categoria", "miniatura"])
        self.assertEqual(avisos, [])

    def test_sin_extras_no_llama_a_nada(self):
        cliente_yt = ClienteYTFalso()
        self.assertEqual(self._correr(cliente_yt), "vid123")
        self.assertFalse(getattr(cliente_yt, "categoria_etiquetas", None))
        self.assertFalse(getattr(cliente_yt, "miniatura", None))

    def test_fallo_de_categoria_avisa_y_sigue_con_la_miniatura(self):
        cliente_yt = ClienteYTFalso(
            fallos={"categoria": RuntimeError("quotaExceeded")})
        avisos = []
        extras = {"categoria": "20", "etiquetas": [], "miniatura": "foto.jpg",
                  "titulo": "T", "descripcion": "D"}
        self.assertEqual(self._correr(cliente_yt, extras, avisos.append),
                         "vid123")
        self.assertEqual(cliente_yt.borradas, [])
        self.assertEqual(cliente_yt.miniatura, ("vid123", "foto.jpg"))
        self.assertTrue(any("categoría y las etiquetas" in a
                            for a in avisos))

    def test_fallo_403_de_miniatura_avisa_y_no_borra(self):
        cliente_yt = ClienteYTFalso(
            fallos={"miniatura": ErrorHttp403()})
        avisos = []
        extras = {"categoria": "", "etiquetas": [], "miniatura": "foto.jpg",
                  "titulo": "T", "descripcion": "D"}
        self.assertEqual(self._correr(cliente_yt, extras, avisos.append),
                         "vid123")
        self.assertEqual(cliente_yt.borradas, [])
        self.assertEqual(avisos, [
            "YouTube no aceptó la miniatura: el canal tiene que estar "
            "verificado por teléfono."])


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


class TestFinalizarEnYoutube(unittest.TestCase):

    def _cliente(self, estado):
        cliente = mock.Mock()
        cliente.estado_emision.return_value = estado
        return cliente

    def test_al_aire_finaliza(self):
        for estado in ("live", "liveStarting", "testing"):
            with self.subTest(estado=estado):
                cliente = self._cliente(estado)
                self.assertTrue(
                    emision.finalizar_en_youtube(cliente, "vid123"))
                cliente.estado_emision.assert_called_once_with("vid123")
                cliente.finalizar_emision.assert_called_once_with(
                    "vid123")
                cliente.borrar_emision.assert_not_called()

    def test_sin_salir_borra(self):
        for estado in ("created", "ready"):
            with self.subTest(estado=estado):
                cliente = self._cliente(estado)
                self.assertTrue(
                    emision.finalizar_en_youtube(cliente, "vid123"))
                cliente.borrar_emision.assert_called_once_with("vid123")
                cliente.finalizar_emision.assert_not_called()

    def test_terminada_o_ausente_no_hace_nada(self):
        for estado in ("complete", "revoked", ""):
            with self.subTest(estado=estado):
                cliente = self._cliente(estado)
                self.assertTrue(
                    emision.finalizar_en_youtube(cliente, "vid123"))
                cliente.finalizar_emision.assert_not_called()
                cliente.borrar_emision.assert_not_called()

    def test_excepcion_sale(self):
        cliente = mock.Mock()
        cliente.estado_emision.side_effect = RuntimeError("falla de red")
        with self.assertRaises(RuntimeError):
            emision.finalizar_en_youtube(cliente, "vid123")
        cliente.finalizar_emision.assert_not_called()
        cliente.borrar_emision.assert_not_called()


class TestGanchosYoutube(unittest.TestCase):

    def test_preparar_llama_a_preparar_en_youtube(self):
        cliente_yt = mock.Mock()
        cuerpo = {"snippet": {"title": "Hola"}}
        parada = threading.Event()
        preparar, _esperar, _finalizar = emision.ganchos_youtube(
            cliente_yt, cuerpo, guardar_token="guardar")
        with mock.patch.object(emision, "preparar_en_youtube",
                               return_value="vid123") as preparar_en:
            devuelto = preparar("obs", parada)
        self.assertEqual(devuelto, "vid123")
        preparar_en.assert_called_once_with(
            cliente_yt, "obs", cuerpo, parada=parada,
            guardar_token="guardar", extras=None, avisar=None)

    def test_preparar_pasa_extras_y_avisar(self):
        cliente_yt = mock.Mock()
        cuerpo = {"snippet": {"title": "Hola"}}
        parada = threading.Event()
        extras = {"categoria": "20"}
        avisar = mock.Mock()
        preparar, _esperar, _finalizar = emision.ganchos_youtube(
            cliente_yt, cuerpo, guardar_token=None, extras=extras,
            avisar=avisar)
        with mock.patch.object(emision, "preparar_en_youtube",
                               return_value="vid123") as preparar_en:
            preparar("obs", parada)
        preparar_en.assert_called_once_with(
            cliente_yt, "obs", cuerpo, parada=parada,
            guardar_token=None, extras=extras, avisar=avisar)

    def test_esperar_llama_a_esperar_en_vivo(self):
        cliente_yt = mock.Mock()
        _preparar, esperar, _finalizar = emision.ganchos_youtube(
            cliente_yt, {}, guardar_token=None)
        parada = threading.Event()
        with mock.patch.object(emision, "esperar_en_vivo",
                               return_value=True) as esperar_en:
            visto = esperar("vid123", parada, 30.0)
        self.assertTrue(visto)
        esperar_en.assert_called_once_with(
            cliente_yt.estado_emision, "vid123", parada, limite=30.0)

    def test_finalizar_llama_a_finalizar_en_youtube(self):
        cliente_yt = mock.Mock()
        _preparar, _esperar, finalizar = emision.ganchos_youtube(
            cliente_yt, {}, guardar_token=None)
        with mock.patch.object(emision, "finalizar_en_youtube",
                               return_value=True) as finalizar_en:
            devuelto = finalizar("vid123")
        self.assertTrue(devuelto)
        finalizar_en.assert_called_once_with(cliente_yt, "vid123")

    def test_finalizar_guarda_el_token_renovado(self):
        cliente_yt = mock.Mock()
        cliente_yt.token_actualizado.return_value = "nuevo-token"
        guardados = []
        _preparar, _esperar, finalizar = emision.ganchos_youtube(
            cliente_yt, {}, guardar_token=guardados.append)
        with mock.patch.object(emision, "finalizar_en_youtube",
                               return_value=True):
            finalizar("vid123")
        self.assertEqual(guardados, ["nuevo-token"])


if __name__ == "__main__":
    unittest.main()
