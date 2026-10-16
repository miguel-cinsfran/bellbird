"""Eventos nuevos de TikTok (seguir, compartir, cofre, me gusta) e historial.

Cubre la lógica pura (`tramo_regalo` vive en test_sonidos_eventos), el
cableado de los manejadores nuevos, el envoltorio de `is_history` con
objetos REALES de la librería, los textos que se leen y el sonido en la GUI.
"""

import asyncio
import inspect
import queue
import sys
import threading
import types
import unittest
from unittest import mock

import main
from ytchat.capture import tiktok_captura
from ytchat.capture.tiktok_captura import (
    debe_pasar_me_gusta, es_historico, _envolver_marcador_historico,
)
from ytchat.core import sonidos_eventos
from ytchat.core.config import (
    TIPO_TEXTO, TIPO_SUPERCHAT, TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE,
    TIPO_ME_GUSTA,
)

_NOMBRES_EVENTOS = (
    "ConnectEvent", "CommentEvent", "GiftEvent", "DisconnectEvent",
    "LiveEndEvent", "RoomUserSeqEvent", "JoinEvent", "SubscribeEvent",
    "FollowEvent", "ShareEvent", "EnvelopeEvent", "LikeEvent",
)


def _config_minima(**extras):
    base = {
        "usuarios_silenciados": [], "palabras_silenciadas": [],
        "silenciados_ocultar": set(), "silenciados_runtime": set(),
        "silenciar_lectura": False, "limpiar_emojis": False,
        "eliminar_urls": False, "max_longitud_mensaje": 200,
        "umbral_solo_nombre": 0, "formato_prefijo": "nombre_mensaje",
        "estrategia": "todas", "tamanio_maximo": 10,
    }
    base.update(extras)
    return base


class TestDebePasarMeGusta(unittest.TestCase):
    def test_el_primero_pasa(self):
        self.assertTrue(debe_pasar_me_gusta(None, 100.0))

    def test_segundo_dentro_de_3_segundos_no_pasa(self):
        self.assertFalse(debe_pasar_me_gusta(100.0, 101.5))

    def test_en_la_frontera_exacta_pasa(self):
        self.assertTrue(debe_pasar_me_gusta(100.0, 103.0))

    def test_despues_del_intervalo_pasa(self):
        self.assertTrue(debe_pasar_me_gusta(100.0, 103.1))

    def test_intervalo_personalizado(self):
        self.assertFalse(debe_pasar_me_gusta(100.0, 104.0, intervalo=5.0))
        self.assertTrue(debe_pasar_me_gusta(100.0, 105.0, intervalo=5.0))


class TestEsHistorico(unittest.TestCase):
    def test_sin_marca_no_es_historico(self):
        self.assertFalse(es_historico(types.SimpleNamespace()))

    def test_con_marca_si(self):
        ev = types.SimpleNamespace()
        ev._ytchat_historico = True
        self.assertTrue(es_historico(ev))

    def test_nunca_lanza(self):
        self.assertFalse(es_historico(None))


class _ClienteFalso:
    room_info = {}

    def __init__(self):
        self.manejadores = {}
        self.conexion_kwargs = {}

    def on(self, evento):
        def decorar(func):
            self.manejadores[evento] = func
            return func
        return decorar

    async def connect(self, **kwargs):
        self.conexion_kwargs.update(kwargs)

    async def disconnect(self):
        pass


def _modulos_falsos(cliente):
    mod_eventos = types.ModuleType("TikTokLive.events")
    for nombre in _NOMBRES_EVENTOS:
        setattr(mod_eventos, nombre, type(nombre, (), {}))
    mod_tiktok = types.ModuleType("TikTokLive")
    mod_tiktok.TikTokLiveClient = lambda unique_id: cliente
    mod_tiktok.events = mod_eventos
    return mod_tiktok, mod_eventos


class TestManejadoresNuevos(unittest.TestCase):
    CONECTADO = 1750000000.0

    def _sesion(self, recibidos, anunciar_entradas=False):
        cliente = _ClienteFalso()
        mod_tiktok, mod_eventos = _modulos_falsos(cliente)
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: recibidos.append(a),
                lambda *a: None, lambda d: None, None,
                anunciar_entradas=anunciar_entradas)
        self.assertIsNone(error)
        with mock.patch("time.time", return_value=self.CONECTADO):
            asyncio.run(cliente.manejadores[mod_eventos.ConnectEvent](
                mod_eventos.ConnectEvent()))
        return cliente, mod_eventos

    def _evento(self, creado_ms):
        comun = types.SimpleNamespace(create_time=creado_ms)
        autor = types.SimpleNamespace(nick_name="Pepe", id="1")
        return types.SimpleNamespace(common=comun, user_info=autor)

    def test_seguir_compartir_cofre_llegan_con_su_tipo(self):
        recibidos = []
        cliente, mod_eventos = self._sesion(recibidos)
        ahora_ms = (self.CONECTADO + 1) * 1000
        for nombre_clase, tipo in (("FollowEvent", TIPO_SEGUIR),
                                   ("ShareEvent", TIPO_COMPARTIR),
                                   ("EnvelopeEvent", TIPO_COFRE)):
            asyncio.run(cliente.manejadores[
                getattr(mod_eventos, nombre_clase)](self._evento(ahora_ms)))
        self.assertEqual([r[2] for r in recibidos],
                         [TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE])
        self.assertEqual(recibidos[0][0], "Pepe")

    def test_varios_me_gusta_seguidos_producen_uno_solo(self):
        recibidos = []
        cliente, mod_eventos = self._sesion(recibidos)
        ahora_ms = (self.CONECTADO + 1) * 1000
        for _ in range(3):
            asyncio.run(cliente.manejadores[mod_eventos.LikeEvent](
                self._evento(ahora_ms)))
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][2], TIPO_ME_GUSTA)

    def test_manejador_nuevo_descarta_historico_y_previo(self):
        recibidos = []
        cliente, mod_eventos = self._sesion(recibidos)
        historico = self._evento((self.CONECTADO + 1) * 1000)
        historico._ytchat_historico = True
        asyncio.run(cliente.manejadores[mod_eventos.FollowEvent](historico))
        previo = self._evento((self.CONECTADO - 10) * 1000)
        asyncio.run(cliente.manejadores[mod_eventos.FollowEvent](previo))
        self.assertEqual(recibidos, [])
        nuevo = self._evento((self.CONECTADO + 1) * 1000)
        asyncio.run(cliente.manejadores[mod_eventos.FollowEvent](nuevo))
        self.assertEqual(len(recibidos), 1)

    def test_suscripcion_y_entrada_tambien_descartan_historico(self):
        recibidos = []
        cliente, mod_eventos = self._sesion(
            recibidos, anunciar_entradas=True)
        for nombre_clase in ("SubscribeEvent", "JoinEvent"):
            historico = self._evento((self.CONECTADO + 1) * 1000)
            historico._ytchat_historico = True
            asyncio.run(cliente.manejadores[
                getattr(mod_eventos, nombre_clase)](historico))
        self.assertEqual(recibidos, [])


class TestEnvoltorioHistoricoReal(unittest.TestCase):
    """El envoltorio con el método REAL del cliente y sobres REALES de
    TikTokLiveProto: solo el comentario no histórico llega a `on_evento`."""

    def _comentarios_reales(self):
        from TikTokLive import TikTokLiveClient
        from TikTokLiveProto.v3.webcast.model import message as mm
        from TikTokLiveProto.v3.webcast.shared import message as sm
        cliente = TikTokLiveClient(unique_id="prueba_historico")
        _envolver_marcador_historico(cliente)

        async def _parsear(historico):
            carga = mm.WebcastChatMessage(content="hola").SerializeToString()
            sobre = sm.BaseProtoMessage(
                method="WebcastChatMessage", payload=carga,
                is_history=historico)
            eventos = await cliente._parse_webcast_response_message(
                sm.ProtoMessageFetchResult(), sobre)
            return [e for e in eventos
                    if type(e).__name__ == "CommentEvent"]

        return (asyncio.run(_parsear(True))[0],
                asyncio.run(_parsear(False))[0])

    def test_solo_el_no_historico_llega_a_on_evento(self):
        historico, nuevo = self._comentarios_reales()
        self.assertTrue(es_historico(historico))
        self.assertFalse(es_historico(nuevo))
        # Encadenado al manejador de comentarios de _sesion (cliente falso).
        recibidos = []
        cliente = _ClienteFalso()
        mod_tiktok, mod_eventos = _modulos_falsos(cliente)
        parada = threading.Event()
        parada.set()
        with mock.patch.dict(sys.modules, {"TikTokLive": mod_tiktok,
                                           "TikTokLive.events": mod_eventos}):
            error = tiktok_captura._sesion(
                "pepe", parada, lambda *a: recibidos.append(a),
                lambda *a: None, lambda d: None, None)
        self.assertIsNone(error)
        manejador = cliente.manejadores[mod_eventos.CommentEvent]
        asyncio.run(manejador(historico))
        self.assertEqual(recibidos, [])
        asyncio.run(manejador(nuevo))
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][1], "hola")

    def test_sin_metodo_no_rompe_la_captura(self):
        _envolver_marcador_historico(types.SimpleNamespace())
        _envolver_marcador_historico(None)

    def test_llamada_por_nombre_como_la_libreria(self):
        # TikTokLive 6.6.6 llama SIEMPRE con argumentos por nombre
        # (webcast_response=, webcast_response_message=): el envoltorio
        # tiene que aceptar esa llamada y marcar igual que por posición.
        from TikTokLive import TikTokLiveClient
        from TikTokLiveProto.v3.webcast.model import message as mm
        from TikTokLiveProto.v3.webcast.shared import message as sm
        cliente = TikTokLiveClient(unique_id="prueba_historico_kw")
        _envolver_marcador_historico(cliente)

        async def _parsear(historico):
            carga = mm.WebcastChatMessage(content="hola").SerializeToString()
            sobre = sm.BaseProtoMessage(
                method="WebcastChatMessage", payload=carga,
                is_history=historico)
            eventos = await cliente._parse_webcast_response_message(
                webcast_response=sm.ProtoMessageFetchResult(),
                webcast_response_message=sobre)
            comentarios = [e for e in eventos
                           if type(e).__name__ == "CommentEvent"]
            self.assertEqual(len(comentarios), 1)
            return comentarios[0]

        historico = asyncio.run(_parsear(True))
        nuevo = asyncio.run(_parsear(False))
        self.assertTrue(es_historico(historico))
        self.assertFalse(es_historico(nuevo))

    def test_contrato_libreria_llama_por_nombre(self):
        # Si la librería deja de llamar con webcast_response_message=,
        # el envoltorio por nombre quedaría desactualizado: avisar.
        from TikTokLive.client.client import TikTokLiveClient
        fuente = inspect.getsource(
            TikTokLiveClient._parse_webcast_response)
        self.assertIn("_parse_webcast_response_message(", fuente)
        self.assertIn("webcast_response_message=", fuente)

    def test_marca_que_falla_devuelve_eventos_igual(self):
        # Un evento que no acepta atributos nuevos (lanza KeyError al
        # anotar): el envoltorio devuelve los eventos del original.
        class _EventoQueExplota:
            def __setattr__(self, nombre, valor):
                if nombre == "_ytchat_historico":
                    raise KeyError("no acepta marcas")
                object.__setattr__(self, nombre, valor)

        evento = _EventoQueExplota()

        async def _original(*args, **kwargs):
            return [evento]

        cliente = types.SimpleNamespace(
            _parse_webcast_response_message=_original)
        _envolver_marcador_historico(cliente)
        eventos = asyncio.run(
            cliente._parse_webcast_response_message(
                webcast_response=object(),
                webcast_response_message=types.SimpleNamespace(
                    is_history=True)))
        self.assertEqual(eventos, [evento])

    def test_rama_sincrona_por_nombre_y_con_fallo(self):
        # La rama síncrona acepta la llamada por nombre y también
        # degrada a los eventos sin marcar si anotar falla.
        def _original(*args, **kwargs):
            return ["ev"]

        cliente = types.SimpleNamespace(
            _parse_webcast_response_message=_original)
        _envolver_marcador_historico(cliente)
        self.assertFalse(asyncio.iscoroutinefunction(
            cliente._parse_webcast_response_message))
        eventos = cliente._parse_webcast_response_message(
            webcast_response=object(),
            webcast_response_message=types.SimpleNamespace(
                is_history=True))
        self.assertEqual(eventos, ["ev"])
        with mock.patch.object(tiktok_captura, "_marcar_historicos",
                               side_effect=KeyError("falla al marcar")):
            cliente2 = types.SimpleNamespace(
                _parse_webcast_response_message=_original)
            _envolver_marcador_historico(cliente2)
            eventos2 = cliente2._parse_webcast_response_message(
                webcast_response=object(),
                webcast_response_message=types.SimpleNamespace(
                    is_history=True))
            self.assertEqual(eventos2, ["ev"])


class TestTextosEntranteNuevos(unittest.TestCase):
    def _leer_tts(self, tipo):
        cola = queue.Queue()
        main.procesar_entrante("Ana", "", tipo, "", "canal", cola,
                               _config_minima(), main.Stats(),
                               on_message=lambda *a, **k: None)
        return cola.get_nowait()["texto_tts"]

    def test_seguir_compartir_cofre(self):
        self.assertEqual(self._leer_tts(TIPO_SEGUIR), "Ana sigue el canal")
        self.assertEqual(self._leer_tts(TIPO_COMPARTIR),
                         "Ana compartió el directo")
        self.assertEqual(self._leer_tts(TIPO_COFRE), "Ana envió un cofre")

    def test_eventos_nuevos_usan_voz_de_eventos_con_multivoz(self):
        for tipo in (TIPO_SEGUIR, TIPO_COMPARTIR, TIPO_COFRE):
            cola = queue.Queue()
            main.procesar_entrante(
                "Ana", "", tipo, "", "canal", cola,
                _config_minima(multivoz=True, voz_eventos="Microsoft Pablo"),
                main.Stats(), on_message=lambda *a, **k: None)
            self.assertEqual(cola.get_nowait()["voz"], "Microsoft Pablo")

    def test_sin_voz_de_eventos_no_marca_voz(self):
        cola = queue.Queue()
        main.procesar_entrante(
            "Ana", "", TIPO_SEGUIR, "", "canal", cola,
            _config_minima(multivoz=True, voz_eventos=""),
            main.Stats(), on_message=lambda *a, **k: None)
        self.assertNotIn("voz", cola.get_nowait())

    def test_importante_en_superchat_y_moderador(self):
        cola = queue.Queue()
        main.procesar_entrante("Ana", "hola", TIPO_SUPERCHAT, "$5", "canal",
                               cola, _config_minima(), main.Stats(),
                               on_message=lambda *a, **k: None)
        self.assertTrue(cola.get_nowait().get("importante"))
        cola_mod = queue.Queue()
        main.procesar_entrante("Mod", "hola", TIPO_TEXTO, "", "canal",
                               cola_mod, _config_minima(), main.Stats(),
                               on_message=lambda *a, **k: None,
                               rol=sonidos_eventos.ROL_MODERADOR)
        self.assertTrue(cola_mod.get_nowait().get("importante"))

    def test_mensaje_comun_no_es_importante(self):
        cola = queue.Queue()
        main.procesar_entrante("Ana", "hola", TIPO_TEXTO, "", "canal", cola,
                               _config_minima(), main.Stats(),
                               on_message=lambda *a, **k: None)
        self.assertNotIn("importante", cola.get_nowait())

    def test_me_gusta_avisa_a_la_gui_pero_no_se_lee(self):
        cola = queue.Queue()
        avisos = []
        main.procesar_entrante(
            "Ana", "", TIPO_ME_GUSTA, "", "canal", cola,
            _config_minima(), main.Stats(),
            on_message=lambda *a, **k: avisos.append(a))
        self.assertEqual(len(avisos), 1)
        self.assertTrue(cola.empty())


class TestGuiMeGustaYRegalo(unittest.TestCase):
    def _frame(self):
        from ytchat.ui import gui
        from ytchat.ui.lista_chat import ListaChat
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        frame._chat = ListaChat(max_items=500)
        frame._pendientes = []
        frame._pendientes_timer = None
        frame._filtro = None
        frame._config = {"limpiar_emojis": True}
        frame._autor_esta_oculto = lambda autor: False
        frame._sumar_superchat = mock.Mock()
        frame.lb_chat = mock.Mock()
        return frame

    def _procesar(self, frame, registro):
        from ytchat.ui import gui
        with mock.patch.object(gui._snd, "reproducir") as reproducir:
            visible = frame._procesar_mensaje_chat(registro)
        return visible, reproducir.call_args.args[0]

    def _registro(self, **extras):
        from ytchat.ui.lista_chat import MensajeChat
        base = {"plataforma": "tiktok", "autor": "Ana", "identificador": "C",
                "texto": "", "hora": "12:00", "tipo": TIPO_ME_GUSTA,
                "monto": "", "rol": ""}
        base.update(extras)
        return MensajeChat(**base)

    def test_me_gusta_suena_y_no_agrega_fila(self):
        frame = self._frame()
        visible, sonido = self._procesar(frame, self._registro())
        self.assertEqual(sonido, "me_gusta")
        self.assertFalse(visible)
        frame.lb_chat.Append.assert_not_called()

    def test_regalo_de_1500_diamantes_suena_grande_y_suma(self):
        frame = self._frame()
        visible, sonido = self._procesar(
            frame, self._registro(tipo=TIPO_SUPERCHAT,
                                  monto="1500 diamantes"))
        self.assertEqual(sonido, "regalo_grande")
        frame._sumar_superchat.assert_called_once_with("1500 diamantes")


if __name__ == "__main__":
    unittest.main()
