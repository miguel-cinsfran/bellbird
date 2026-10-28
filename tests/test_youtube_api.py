"""Tests de los parsers puros de youtube_api (sin red ni libs de Google)."""

import unittest
import sys
import types
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.youtube.youtube_api import (
    ClienteYouTube, FRASE_MINiatura_SIN_VERIFICAR, normalizar_comentario,
    parsear_pagina_comentarios, comentarios_desactivados, es_error_403,
    mensaje_error_api, mensaje_error_miniatura,
)


class ServicioFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta

    def videos(self):
        return self

    def channels(self):
        return self

    def list(self, **kwargs):
        self.parametros = kwargs
        return self

    def execute(self):
        return self.respuesta


class TestDetallesDirecto(unittest.TestCase):

    def cliente(self, respuesta):
        cliente = ClienteYouTube({"api_key": "clave"})
        cliente._svc_lectura = ServicioFalso(respuesta)
        return cliente

    def test_respuesta_completa(self):
        cliente = self.cliente({"items": [{"liveStreamingDetails": {
            "concurrentViewers": "30",
            "actualStartTime": "2026-08-27T14:03:12Z",
        }}]})
        self.assertEqual(cliente.detalles_directo("abc"), {
            "espectadores": 30, "comienzo": "2026-08-27T14:03:12Z"})

    def test_respuesta_sin_espectadores(self):
        cliente = self.cliente({"items": [{"liveStreamingDetails": {
            "actualStartTime": "2026-08-27T14:03:12Z",
        }}]})
        self.assertEqual(cliente.detalles_directo("abc"), {
            "espectadores": None, "comienzo": "2026-08-27T14:03:12Z"})

    def test_respuesta_vacia(self):
        cliente = self.cliente({"items": []})
        self.assertEqual(cliente.detalles_directo("abc"), {
            "espectadores": None, "comienzo": ""})


class TestDatosChatDirecto(unittest.TestCase):

    def cliente(self, respuesta):
        cliente = ClienteYouTube({"api_key": "clave"})
        cliente._svc_lectura = ServicioFalso(respuesta)
        return cliente

    def test_sin_video(self):
        self.assertEqual(self.cliente({"items": []}).datos_chat_directo("abc"), {
            "hay_video": False, "hay_directo": False, "live_chat_id": "",
            "canal_id": ""})

    def test_video_que_no_es_directo(self):
        self.assertEqual(self.cliente({"items": [{}]}).datos_chat_directo("abc"), {
            "hay_video": True, "hay_directo": False, "live_chat_id": "",
            "canal_id": ""})

    def test_directo_con_chat(self):
        self.assertEqual(self.cliente({"items": [{"liveStreamingDetails": {
            "activeLiveChatId": "chat"}}]}).datos_chat_directo("abc"), {
            "hay_video": True, "hay_directo": True, "live_chat_id": "chat",
            "canal_id": ""})

    def test_devuelve_el_canal_del_directo(self):
        self.assertEqual(self.cliente({"items": [
            {"snippet": {"channelId": "UCpropio"},
             "liveStreamingDetails": {"activeLiveChatId": "chat"}},
        ]}).datos_chat_directo("abc"), {
            "hay_video": True, "hay_directo": True, "live_chat_id": "chat",
            "canal_id": "UCpropio"})

    def test_pide_el_snippet_en_la_misma_llamada(self):
        servicio = ServicioFalso({"items": []})
        cliente = ClienteYouTube({"api_key": "clave"})
        cliente._svc_lectura = servicio
        cliente.datos_chat_directo("abc")
        self.assertIn("snippet", servicio.parametros.get("part", ""))

    def test_resolvedor_conserva_el_id(self):
        self.assertEqual(self.cliente({"items": [{"liveStreamingDetails": {
            "activeLiveChatId": "chat"}}]}).resolver_live_chat_id("abc"), "chat")


class TestIdCanalPropio(unittest.TestCase):

    def cliente(self, respuesta):
        cliente = ClienteYouTube({"token": "{}"})
        cliente._svc_escritura = ServicioFalso(respuesta)
        return cliente

    def test_devuelve_el_id_del_canal_de_la_sesion(self):
        cliente = self.cliente({"items": [{"id": "UCpropio"}]})
        self.assertEqual(cliente.id_canal_propio(), "UCpropio")

    def test_sin_items_devuelve_vacio(self):
        self.assertEqual(self.cliente({"items": []}).id_canal_propio(), "")

    def test_pide_los_canales_propios(self):
        servicio = ServicioFalso({"items": [{"id": "UCpropio"}]})
        cliente = ClienteYouTube({"token": "{}"})
        cliente._svc_escritura = servicio
        cliente.id_canal_propio()
        self.assertTrue(servicio.parametros.get("mine"))
        self.assertEqual(servicio.parametros.get("part"), "id")


class TestNormalizarComentario(unittest.TestCase):

    def test_basico(self):
        c = normalizar_comentario({
            "authorDisplayName": "Ana",
            "textOriginal": "hola",
            "likeCount": 5,
            "publishedAt": "2026-01-01T00:00:00Z",
            "authorChannelId": {"value": "UCabc"},
        }, comment_id="x1")
        self.assertEqual(c.autor, "Ana")
        self.assertEqual(c.texto, "hola")
        self.assertEqual(c.likes, 5)
        self.assertEqual(c.autor_canal_id, "UCabc")
        self.assertEqual(c.comment_id, "x1")
        self.assertFalse(c.es_respuesta)

    def test_campos_faltantes(self):
        c = normalizar_comentario({})
        self.assertEqual(c.autor, "Usuario")
        self.assertEqual(c.texto, "")
        self.assertEqual(c.likes, 0)
        self.assertEqual(c.autor_canal_id, "")

    def test_likecount_invalido(self):
        c = normalizar_comentario({"likeCount": "no-numero"})
        self.assertEqual(c.likes, 0)

    def test_textdisplay_como_respaldo(self):
        c = normalizar_comentario({"textDisplay": "<b>hola</b>"})
        self.assertEqual(c.texto, "<b>hola</b>")

    def test_canal_como_string(self):
        c = normalizar_comentario({"authorChannelId": "UCxyz"})
        self.assertEqual(c.autor_canal_id, "UCxyz")


class TestParsearPagina(unittest.TestCase):

    def _resp(self):
        return {
            "items": [{
                "snippet": {
                    "totalReplyCount": 1,
                    "topLevelComment": {
                        "id": "top1",
                        "snippet": {"authorDisplayName": "Ana", "textOriginal": "hola",
                                    "likeCount": 3},
                    },
                },
                "replies": {"comments": [{
                    "id": "rep1",
                    "snippet": {"authorDisplayName": "Beto", "textOriginal": "que tal"},
                }]},
            }],
            "nextPageToken": "NEXT",
        }

    def test_intercala_respuestas(self):
        coms, nxt = parsear_pagina_comentarios(self._resp())
        self.assertEqual(nxt, "NEXT")
        self.assertEqual(len(coms), 2)
        self.assertEqual(coms[0].autor, "Ana")
        self.assertEqual(coms[0].respuestas, 1)
        self.assertFalse(coms[0].es_respuesta)
        self.assertEqual(coms[1].autor, "Beto")
        self.assertTrue(coms[1].es_respuesta)

    def test_excluir_respuestas(self):
        coms, _ = parsear_pagina_comentarios(self._resp(), incluir_respuestas=False)
        self.assertEqual(len(coms), 1)
        self.assertEqual(coms[0].autor, "Ana")

    def test_respuesta_conserva_id_para_responder(self):
        coms, _ = parsear_pagina_comentarios(self._resp())
        self.assertEqual(coms[0].comment_id, "top1")
        self.assertEqual(coms[1].comment_id, "rep1")

    def test_pagina_vacia(self):
        coms, nxt = parsear_pagina_comentarios({})
        self.assertEqual(coms, [])
        self.assertEqual(nxt, "")


class TestMensajeError(unittest.TestCase):

    def test_quota(self):
        self.assertIn("cuota", mensaje_error_api("The request cannot be completed: quotaExceeded"))

    def test_comentarios_desactivados(self):
        self.assertIn("desactivados", mensaje_error_api("commentsDisabled"))

    def test_reconoce_comentarios_desactivados(self):
        self.assertTrue(comentarios_desactivados("commentsDisabled"))
        self.assertTrue(comentarios_desactivados("Disabled comments"))
        self.assertFalse(comentarios_desactivados("videoNotFound"))

    def test_video_no_encontrado(self):
        self.assertIn("vídeo", mensaje_error_api("videoNotFound"))

    def test_sin_permiso(self):
        self.assertIn("permiso", mensaje_error_api("insufficientPermissions"))

    def test_prohibido_con_directos_no_activados_avisa_de_activarlos(self):
        texto = ("403 Forbidden: liveStreamingNotEnabled: "
                 "el directo no está activado")
        self.assertIn("directos activados", mensaje_error_api(texto))

    def test_generico(self):
        self.assertIn("Error de la API", mensaje_error_api("algo raro"))


class TestErrorDeMiniaturaMensajes(unittest.TestCase):

    def test_403_con_resp_status(self):
        exc = mock.Mock()
        exc.resp.status = 403
        self.assertTrue(es_error_403(exc))

    def test_403_con_status_code(self):
        exc = mock.Mock(spec=[])
        exc.status_code = 403
        self.assertTrue(es_error_403(exc))

    def test_403_por_texto(self):
        self.assertTrue(es_error_403(RuntimeError("403 Forbidden")))
        self.assertTrue(es_error_403(RuntimeError("algo forbidden")))

    def test_otro_error_no_es_403(self):
        self.assertFalse(es_error_403(RuntimeError("videoNotFound")))

    def test_mensaje_403_es_la_frase_del_canal(self):
        self.assertEqual(mensaje_error_miniatura(RuntimeError("forbidden")),
                         FRASE_MINiatura_SIN_VERIFICAR)

    def test_otro_error_se_traduce(self):
        self.assertIn("No se pudo poner la miniatura",
                      mensaje_error_miniatura(RuntimeError("videoNotFound")))


class TestPseudoMensajes(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_errores_de_api_van_marcados(self):
        casos = ("Tu sesión", "quotaExceeded", "commentsDisabled",
                 "videoNotFound", "keyInvalid", "liveStreamingNotEnabled",
                 "insufficientPermissions", "liveChatNotFound",
                 "rate limit alcanzado", "algo raro")
        with con_pseudo():
            marcados = [mensaje_error_api(caso) for caso in casos]
            marcados.append(
                mensaje_error_miniatura(RuntimeError("forbidden")))
            marcados.append(
                mensaje_error_miniatura(RuntimeError("videoNotFound")))
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)

    def test_autor_y_titulo_por_defecto_van_marcados(self):
        with con_pseudo():
            autor = normalizar_comentario({}).autor
        self.assertTrue(autor.startswith("[¡"), autor)

    def test_lista_sin_titulo_va_marcada(self):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioListasFalso([{"items": [
            {"id": "PL1", "snippet": {"title": ""}},
        ]}])
        cliente._svc_escritura = servicio
        with con_pseudo():
            listas = cliente.listas_del_canal()
        self.assertEqual(len(listas), 1)
        self.assertTrue(listas[0][1].startswith("[¡"), listas)


class ServicioFlujosFalso:
    def __init__(self, flujos):
        self.flujos = flujos
        self.parametros = {}

    def liveStreams(self):
        return self

    def list(self, **kwargs):
        self.parametros = kwargs
        return self

    def execute(self):
        return {"items": self.flujos}


def flujo(titulo, reutilizable=True, servidor="rtmp://a.rtmp.youtube.com/live2",
          clave="clave", id_flujo="flujo-1"):
    return {"id": id_flujo, "snippet": {"title": titulo},
            "contentDetails": {"isReusable": reutilizable},
            "cdn": {"ingestionInfo": {"ingestionAddress": servidor,
                                      "streamName": clave}}}


class TestClaveEmision(unittest.TestCase):

    def cliente(self, flujos):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioFlujosFalso(flujos)
        cliente._svc_escritura = servicio
        return cliente, servicio

    def test_prefiere_default_entre_reutilizables(self):
        cliente, _ = self.cliente([
            flujo("Otro", clave="otra"),
            flujo("Default stream key", clave="elegida"),
        ])
        self.assertEqual(cliente.clave_emision(),
                         ("rtmp://a.rtmp.youtube.com/live2", "elegida"))

    def test_ignora_los_no_reutilizables(self):
        cliente, _ = self.cliente([
            flujo("Ajena", reutilizable=False, clave="ajena"),
            flujo("Mía", clave="mia"),
        ])
        self.assertEqual(cliente.clave_emision(),
                         ("rtmp://a.rtmp.youtube.com/live2", "mia"))

    def test_sin_reutilizables_devuelve_none(self):
        cliente, _ = self.cliente([flujo("Ajena", reutilizable=False)])
        self.assertIsNone(cliente.clave_emision())
        cliente_vacio, _ = self.cliente([])
        self.assertIsNone(cliente_vacio.clave_emision())

    def test_sin_campos_de_ingesta_devuelve_none(self):
        cliente, _ = self.cliente([{"snippet": {"title": "Default stream key"},
                                    "contentDetails": {"isReusable": True},
                                    "cdn": {}}])
        self.assertIsNone(cliente.clave_emision())

    def test_pide_los_flujos_propios(self):
        cliente, servicio = self.cliente([flujo("Default stream key")])
        cliente.clave_emision()
        self.assertTrue(servicio.parametros.get("mine"))
        self.assertIn("contentDetails", servicio.parametros.get("part", ""))


class TestFlujoReutilizable(unittest.TestCase):

    def cliente(self, flujos):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioFlujosFalso(flujos)
        cliente._svc_escritura = servicio
        return cliente, servicio

    def test_devuelve_id_servidor_y_clave(self):
        cliente, _ = self.cliente([
            flujo("Otro", clave="otra", id_flujo="flujo-otra"),
            flujo("Default stream key", clave="elegida",
                  id_flujo="flujo-elegida"),
        ])
        self.assertEqual(cliente.flujo_reutilizable(),
                         ("flujo-elegida",
                          "rtmp://a.rtmp.youtube.com/live2", "elegida"))

    def test_saltea_flujos_sin_id(self):
        sin_id = {"snippet": {"title": "Default stream key"},
                  "contentDetails": {"isReusable": True},
                  "cdn": {"ingestionInfo": {
                      "ingestionAddress": "rtmp://a.rtmp.youtube.com/live2",
                      "streamName": "clave"}}}
        cliente, _ = self.cliente([sin_id])
        self.assertIsNone(cliente.flujo_reutilizable())

    def test_sin_reutilizables_devuelve_none(self):
        cliente, _ = self.cliente([flujo("Ajena", reutilizable=False,
                                        id_flujo="flujo-ajena")])
        self.assertIsNone(cliente.flujo_reutilizable())

    def test_clave_emision_usa_el_flujo(self):
        cliente, _ = self.cliente([
            flujo("Default stream key", clave="elegida",
                  id_flujo="flujo-elegida"),
        ])
        self.assertEqual(cliente.clave_emision(),
                         ("rtmp://a.rtmp.youtube.com/live2", "elegida"))


class ServicioEmisionFalso:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.metodo = ""
        self.parametros = {}

    def liveBroadcasts(self):
        return self

    def insert(self, **kwargs):
        self.metodo = "insert"
        self.parametros = kwargs
        return self

    def bind(self, **kwargs):
        self.metodo = "bind"
        self.parametros = kwargs
        return self

    def list(self, **kwargs):
        self.metodo = "list"
        self.parametros = kwargs
        return self

    def delete(self, **kwargs):
        self.metodo = "delete"
        self.parametros = kwargs
        return self

    def transition(self, **kwargs):
        self.metodo = "transition"
        self.parametros = kwargs
        return self

    def execute(self):
        return self.respuesta


class TestEmisionApi(unittest.TestCase):

    def cliente(self, respuesta):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioEmisionFalso(respuesta)
        cliente._svc_escritura = servicio
        return cliente, servicio

    def test_crear_emision_devuelve_el_id(self):
        cliente, servicio = self.cliente({"id": "vid123"})
        cuerpo = {"snippet": {"title": "Hola"}}
        self.assertEqual(cliente.crear_emision(cuerpo), "vid123")
        self.assertEqual(servicio.metodo, "insert")
        self.assertEqual(
            servicio.parametros.get("part"), "snippet,status,contentDetails")
        self.assertEqual(servicio.parametros.get("body"), cuerpo)

    def test_vincular_emision_manda_los_parametros(self):
        cliente, servicio = self.cliente({})
        cliente.vincular_emision("vid123", "flujo-1")
        self.assertEqual(servicio.metodo, "bind")
        self.assertEqual(servicio.parametros.get("id"), "vid123")
        self.assertEqual(servicio.parametros.get("part"), "id,contentDetails")
        self.assertEqual(servicio.parametros.get("streamId"), "flujo-1")

    def test_estado_emision_devuelve_el_ciclo(self):
        cliente, servicio = self.cliente(
            {"items": [{"status": {"lifeCycleStatus": "live"}}]})
        self.assertEqual(cliente.estado_emision("vid123"), "live")
        self.assertEqual(servicio.metodo, "list")
        self.assertEqual(servicio.parametros.get("part"), "status")
        self.assertEqual(servicio.parametros.get("id"), "vid123")

    def test_estado_emision_sin_items_devuelve_vacio(self):
        cliente, _ = self.cliente({"items": []})
        self.assertEqual(cliente.estado_emision("vid123"), "")

    def test_borrar_emision_manda_el_id(self):
        cliente, servicio = self.cliente({})
        cliente.borrar_emision("vid123")
        self.assertEqual(servicio.metodo, "delete")
        self.assertEqual(servicio.parametros.get("id"), "vid123")

    def test_finalizar_emision_pasa_a_terminada(self):
        cliente, servicio = self.cliente({})
        cliente.finalizar_emision("vid123")
        self.assertEqual(servicio.metodo, "transition")
        self.assertEqual(
            servicio.parametros.get("broadcastStatus"), "complete")
        self.assertEqual(servicio.parametros.get("id"), "vid123")
        self.assertEqual(servicio.parametros.get("part"), "status")

    def test_emisiones_activas_pide_las_activas(self):
        cliente, servicio = self.cliente({"items": []})
        self.assertEqual(cliente.emisiones_activas(), [])
        self.assertEqual(servicio.metodo, "list")
        self.assertEqual(
            servicio.parametros.get("broadcastStatus"), "active")
        self.assertEqual(
            servicio.parametros.get("broadcastType"), "all")
        self.assertEqual(
            servicio.parametros.get("part"), "id,contentDetails,status,snippet")

    def test_emisiones_activas_devuelve_id_flujo_y_titulo(self):
        cliente, _servicio = self.cliente({"items": [
            {"id": "vid1",
             "contentDetails": {"boundStreamId": "flujo-1"},
             "snippet": {"title": "Charla"}},
            {"id": "vid2",
             "contentDetails": {"boundStreamId": "flujo-2"},
             "snippet": {"title": "Música"}},
            {"contentDetails": {"boundStreamId": "sin-id"},
             "snippet": {"title": "Sin id"}},
        ]})
        self.assertEqual(cliente.emisiones_activas(),
                         [("vid1", "flujo-1", "Charla"),
                          ("vid2", "flujo-2", "Música")])

    def test_emisiones_activas_sin_titulo_devuelve_vacio(self):
        cliente, _servicio = self.cliente({"items": [
            {"id": "vid1",
             "contentDetails": {"boundStreamId": "flujo-1"}},
        ]})
        self.assertEqual(cliente.emisiones_activas(),
                         [("vid1", "flujo-1", "")])

    def test_directos_no_activados(self):
        self.assertIn("directos activados",
                      mensaje_error_api("liveStreamingNotEnabled: algo"))


class ServicioOpcionesFalso:
    def __init__(self, video_items=None):
        self.video_items = video_items or []
        self.list_kwargs = {}
        self.update_kwargs = {}
        self.set_kwargs = {}

    def videos(self):
        return self

    def thumbnails(self):
        return self

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return self

    def update(self, **kwargs):
        self.update_kwargs = kwargs
        return self

    def set(self, **kwargs):
        self.set_kwargs = kwargs
        return self

    def execute(self):
        return {"items": self.video_items}


class TestOpcionesVideo(unittest.TestCase):

    def cliente(self, video_items=None):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioOpcionesFalso(video_items)
        cliente._svc_escritura = servicio
        return cliente, servicio

    def test_actualizar_manda_titulo_categoria_y_etiquetas(self):
        cliente, servicio = self.cliente()
        cliente.actualizar_categoria_y_etiquetas(
            "vid123", "Título", "Descripción", "20", ["uno", "dos"])
        self.assertEqual(servicio.update_kwargs.get("part"), "snippet")
        cuerpo = servicio.update_kwargs.get("body")
        self.assertEqual(cuerpo["id"], "vid123")
        self.assertEqual(cuerpo["snippet"]["title"], "Título")
        self.assertEqual(cuerpo["snippet"]["description"], "Descripción")
        self.assertEqual(cuerpo["snippet"]["categoryId"], "20")
        self.assertEqual(cuerpo["snippet"]["tags"], ["uno", "dos"])
        self.assertEqual(servicio.list_kwargs, {})

    def test_categoria_vacia_la_lee_del_video(self):
        cliente, servicio = self.cliente([{"snippet": {"categoryId": "24"}}])
        cliente.actualizar_categoria_y_etiquetas(
            "vid123", "Título", "Descripción", "", ["uno"])
        self.assertEqual(servicio.list_kwargs.get("part"), "snippet")
        self.assertEqual(servicio.list_kwargs.get("id"), "vid123")
        self.assertEqual(servicio.update_kwargs["body"]["snippet"]["categoryId"],
                         "24")

    def test_categoria_vacia_sin_video_queda_vacia(self):
        cliente, servicio = self.cliente([])
        cliente.actualizar_categoria_y_etiquetas(
            "vid123", "T", "D", "", [])
        self.assertEqual(servicio.update_kwargs["body"]["snippet"]["categoryId"],
                         "")

    def test_poner_miniatura_png(self):
        cliente, servicio = self.cliente()
        with mock.patch("googleapiclient.http.MediaFileUpload") as media:
            cliente.poner_miniatura("vid123", "foto.png")
        media.assert_called_once_with("foto.png", mimetype="image/png")
        self.assertEqual(servicio.set_kwargs.get("videoId"), "vid123")
        self.assertIs(servicio.set_kwargs.get("media_body"),
                      media.return_value)

    def test_poner_miniatura_jpg_por_defecto(self):
        cliente, _servicio = self.cliente()
        with mock.patch("googleapiclient.http.MediaFileUpload") as media:
            cliente.poner_miniatura("vid123", "foto.jpg")
        media.assert_called_once_with("foto.jpg", mimetype="image/jpeg")


class ServicioListasFalso:
    def __init__(self, paginas=None, insert_respuesta=None):
        self.paginas = list(paginas or [])
        self.insert_respuesta = insert_respuesta or {}
        self.list_kwargs = []
        self.insert_kwargs = {}
        self._pendiente = None

    def playlists(self):
        return self

    def playlistItems(self):
        return self

    def list(self, **kwargs):
        self.list_kwargs.append(kwargs)
        self._pendiente = (self.paginas.pop(0) if self.paginas
                           else {"items": []})
        return self

    def insert(self, **kwargs):
        self.insert_kwargs = kwargs
        self._pendiente = self.insert_respuesta
        return self

    def execute(self):
        return self._pendiente


class TestListasDelCanal(unittest.TestCase):

    def cliente(self, paginas=None, insert_respuesta=None):
        cliente = ClienteYouTube({"token": "{}"})
        servicio = ServicioListasFalso(paginas, insert_respuesta)
        cliente._svc_escritura = servicio
        return cliente, servicio

    def test_devuelve_los_pares_en_orden(self):
        cliente, servicio = self.cliente([{"items": [
            {"id": "PL1", "snippet": {"title": "Música"}},
            {"id": "PL2", "snippet": {"title": "Charla"}},
        ]}])
        self.assertEqual(cliente.listas_del_canal(),
                         [("PL1", "Música"), ("PL2", "Charla")])
        self.assertTrue(servicio.list_kwargs[0].get("mine"))
        self.assertEqual(servicio.list_kwargs[0].get("part"), "snippet")
        self.assertEqual(servicio.list_kwargs[0].get("maxResults"), 50)

    def test_sigue_next_page_token(self):
        cliente, servicio = self.cliente([
            {"items": [{"id": "PL1", "snippet": {"title": "Uno"}}],
             "nextPageToken": "NEXT"},
            {"items": [{"id": "PL2", "snippet": {"title": "Dos"}}]},
        ])
        self.assertEqual(cliente.listas_del_canal(),
                         [("PL1", "Uno"), ("PL2", "Dos")])
        self.assertEqual(len(servicio.list_kwargs), 2)
        self.assertNotIn("pageToken", servicio.list_kwargs[0])
        self.assertEqual(servicio.list_kwargs[1].get("pageToken"), "NEXT")

    def test_para_en_cuatro_paginas(self):
        paginas = [
            {"items": [{"id": f"PL{i}", "snippet": {"title": "T"}}],
             "nextPageToken": "NEXT"}
            for i in range(6)
        ]
        cliente, servicio = self.cliente(paginas)
        listas = cliente.listas_del_canal()
        self.assertEqual(len(servicio.list_kwargs), 4)
        self.assertEqual([id_ for id_, _t in listas],
                         ["PL0", "PL1", "PL2", "PL3"])

    def test_item_sin_id_se_descarta(self):
        cliente, _servicio = self.cliente([{"items": [
            {"snippet": {"title": "Sin id"}},
            {"id": "PL1", "snippet": {"title": "Con id"}},
        ]}])
        self.assertEqual(cliente.listas_del_canal(), [("PL1", "Con id")])

    def test_titulo_vacio_queda_sin_titulo(self):
        cliente, _servicio = self.cliente([{"items": [
            {"id": "PL1", "snippet": {"title": ""}},
            {"id": "PL2"},
        ]}])
        self.assertEqual(cliente.listas_del_canal(),
                         [("PL1", "Sin título"), ("PL2", "Sin título")])

    def test_sin_listas_devuelve_vacio(self):
        cliente, _servicio = self.cliente([{"items": []}])
        self.assertEqual(cliente.listas_del_canal(), [])

    def test_agregar_a_lista_manda_el_cuerpo_exacto(self):
        cliente, servicio = self.cliente(insert_respuesta={})
        cliente.agregar_a_lista("PL123", "vid123")
        self.assertEqual(servicio.insert_kwargs.get("part"), "snippet")
        self.assertEqual(servicio.insert_kwargs.get("body"), {
            "snippet": {
                "playlistId": "PL123",
                "resourceId": {"kind": "youtube#video", "videoId": "vid123"},
            },
        })


class TestCableadoChatDirecto(unittest.TestCase):
    def test_entrega_la_causa_a_la_interfaz(self):
        import main
        llamadas = []
        frame = types.SimpleNamespace(
            _alive=True, set_live_chat_id=lambda *args: llamadas.append(args))
        cliente = mock.Mock(datos_chat_directo=mock.Mock(return_value={
            "hay_video": True, "hay_directo": True, "live_chat_id": ""}))
        modulos = {
            "ytchat.youtube.credenciales": types.SimpleNamespace(hay_lectura=lambda: True,
                                                      hay_sesion=lambda: False,
                                                      cargar=lambda: {},
                                                      efectivas=lambda *a, **k: {}),
            "ytchat.youtube.youtube_api": types.SimpleNamespace(
                google_disponible=lambda: True, ClienteYouTube=lambda _: cliente),
            "ytchat.ui.gui": types.SimpleNamespace(_gui_frame=frame),
            "wx": types.SimpleNamespace(CallAfter=lambda funcion, *args: funcion(*args)),
        }
        # `from ytchat.x import y` mira primero el atributo del paquete:
        # sin estos parches usaría el módulo real si otra prueba ya lo importó.
        from ytchat import ui as _paquete_ui, youtube as _paquete_youtube
        with mock.patch.dict(sys.modules, modulos), \
                mock.patch.object(_paquete_youtube, "credenciales",
                                  modulos["ytchat.youtube.credenciales"],
                                  create=True), \
                mock.patch.object(_paquete_youtube, "youtube_api",
                                  modulos["ytchat.youtube.youtube_api"],
                                  create=True), \
                mock.patch.object(_paquete_ui, "gui",
                                  modulos["ytchat.ui.gui"],
                                  create=True):
            main._resolver_live_chat_id("abc")
        self.assertEqual(llamadas, [("", "chat_desactivado", "abc", False)])

    def test_resolver_live_chat_id_usa_credenciales_efectivas(self):
        import main
        construidos = []
        llamadas = []
        frame = types.SimpleNamespace(
            _alive=True, set_live_chat_id=lambda *args: llamadas.append(args))
        cliente = mock.Mock(datos_chat_directo=mock.Mock(return_value={
            "hay_video": True, "hay_directo": True, "live_chat_id": ""}))

        def cliente_registra(credenciales):
            construidos.append(credenciales)
            return cliente

        modulos = {
            "ytchat.youtube.credenciales": types.SimpleNamespace(
                hay_lectura=lambda: True,
                hay_sesion=lambda: False,
                cargar=lambda: {"origen": "cargar"},
                efectivas=lambda *a, **k: {"origen": "efectivas"}),
            "ytchat.youtube.youtube_api": types.SimpleNamespace(
                google_disponible=lambda: True, ClienteYouTube=cliente_registra),
            "ytchat.ui.gui": types.SimpleNamespace(_gui_frame=frame),
            "wx": types.SimpleNamespace(CallAfter=lambda funcion, *args: funcion(*args)),
        }
        # `from ytchat.x import y` mira primero el atributo del paquete:
        # sin estos parches usaría el módulo real si otra prueba ya lo importó.
        from ytchat import ui as _paquete_ui, youtube as _paquete_youtube
        with mock.patch.dict(sys.modules, modulos), \
                mock.patch.object(_paquete_youtube, "credenciales",
                                  modulos["ytchat.youtube.credenciales"],
                                  create=True), \
                mock.patch.object(_paquete_youtube, "youtube_api",
                                  modulos["ytchat.youtube.youtube_api"],
                                  create=True), \
                mock.patch.object(_paquete_ui, "gui",
                                  modulos["ytchat.ui.gui"],
                                  create=True):
            main._resolver_live_chat_id("abc")
        self.assertEqual(construidos, [{"origen": "efectivas"}])

    def _resolver_con(self, datos, sesion, canal_propio="UCpropio",
                      falla_datos=False):
        import main
        llamadas = []
        frame = types.SimpleNamespace(
            _alive=True, set_live_chat_id=lambda *args: llamadas.append(args))
        cliente = mock.Mock()
        if falla_datos:
            cliente.datos_chat_directo = mock.Mock(side_effect=RuntimeError("caído"))
        else:
            cliente.datos_chat_directo = mock.Mock(return_value=datos)
        cliente.id_canal_propio = mock.Mock(return_value=canal_propio)
        modulos = {
            "ytchat.youtube.credenciales": types.SimpleNamespace(
                hay_lectura=lambda: True,
                hay_sesion=lambda: sesion,
                cargar=lambda: {},
                efectivas=lambda *a, **k: {}),
            "ytchat.youtube.youtube_api": types.SimpleNamespace(
                google_disponible=lambda: True, ClienteYouTube=lambda _: cliente),
            "ytchat.ui.gui": types.SimpleNamespace(_gui_frame=frame),
            "wx": types.SimpleNamespace(CallAfter=lambda funcion, *args: funcion(*args)),
        }
        from ytchat import ui as _paquete_ui, youtube as _paquete_youtube
        with mock.patch.dict(sys.modules, modulos), \
                mock.patch.object(_paquete_youtube, "credenciales",
                                  modulos["ytchat.youtube.credenciales"],
                                  create=True), \
                mock.patch.object(_paquete_youtube, "youtube_api",
                                  modulos["ytchat.youtube.youtube_api"],
                                  create=True), \
                mock.patch.object(_paquete_ui, "gui",
                                  modulos["ytchat.ui.gui"],
                                  create=True):
            main._resolver_live_chat_id("abc")
        return llamadas, cliente

    def _datos(self, canal_id):
        return {"hay_video": True, "hay_directo": True, "live_chat_id": "chat",
                "canal_id": canal_id}

    def test_directo_propio_cuando_coincide_el_canal(self):
        llamadas, cliente = self._resolver_con(self._datos("UCpropio"), True)
        self.assertEqual(len(llamadas), 1)
        self.assertEqual(llamadas[0][0], "chat")
        self.assertEqual(llamadas[0][2], "abc")
        self.assertTrue(llamadas[0][3])
        self.assertEqual(cliente.id_canal_propio.call_count, 1)

    def test_directo_ajeno_cuando_difiere_el_canal(self):
        llamadas, cliente = self._resolver_con(self._datos("UCotro"), True,
                                               canal_propio="UCpropio")
        self.assertEqual(llamadas[0][0], "chat")
        self.assertFalse(llamadas[0][3])

    def test_sin_sesion_no_pide_el_canal_propio(self):
        llamadas, cliente = self._resolver_con(self._datos("UCpropio"), False)
        cliente.id_canal_propio.assert_not_called()
        self.assertFalse(llamadas[0][3])

    def test_si_la_api_falla_propio_queda_en_falso(self):
        llamadas, _cliente = self._resolver_con(self._datos("UCpropio"), True,
                                                falla_datos=True)
        self.assertEqual(len(llamadas), 1)
        self.assertFalse(llamadas[0][3])


if __name__ == "__main__":
    unittest.main()
