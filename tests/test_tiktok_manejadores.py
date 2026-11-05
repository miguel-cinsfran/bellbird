"""Manejadores de eventos de TikTok en su módulo propio."""

import asyncio
import types
import unittest
from unittest import mock

from bellbird.capture import tiktok_manejadores
from bellbird.capture.tiktok_manejadores import registrar_manejadores
from bellbird.core.config import (
    TIPO_COFRE, TIPO_ENTRADA, TIPO_ME_GUSTA, TIPO_TEXTO,
)

_TODAS = ("CommentEvent", "GiftEvent", "JoinEvent", "RoomUserSeqEvent",
          "SubscribeEvent", "FollowEvent", "ShareEvent", "EnvelopeEvent",
          "LikeEvent")
_TODAS_NUEVAS = _TODAS + ("EmoteChatEvent", "QuestionNewEvent",
                          "LivePauseEvent", "LiveUnpauseEvent")


class _ClienteFalso:
    def __init__(self):
        self.manejadores = {}

    def on(self, evento):
        def decorar(func):
            self.manejadores[evento] = func
            return func
        return decorar


def _modulo(nombres):
    mod = types.ModuleType("TikTokLive.events")
    for nombre in nombres:
        setattr(mod, nombre, type(nombre, (), {}))
    return mod


def _registrar(nombres, evento_entrada="mostrar", descartar=None,
                 on_estado=None, sin_estado=False, config=None):
    cliente = _ClienteFalso()
    mod = _modulo(nombres)
    recibidos = []
    vistos = []
    estados = []
    estado = None if sin_estado else (
        on_estado or (lambda *a: estados.append(a)))
    opciones = {"evento_entrada": evento_entrada}
    opciones.update(config or {})
    registrar_manejadores(
        cliente, mod, on_evento=lambda *a: recibidos.append(a),
        on_espectadores=lambda *a: vistos.append(a),
        config=opciones,
        descartar=(descartar or (lambda evento: False)),
        on_estado=estado)
    return cliente, mod, recibidos, vistos, estados


def _evento_comentario(texto="hola"):
    autor = types.SimpleNamespace(nick_name="Pepe", id="1")
    return types.SimpleNamespace(comment=texto, user_info=autor)


class TestRegistrarManejadores(unittest.TestCase):
    def test_registra_uno_por_clase_presente(self):
        cliente, mod, _recibidos, _vistos, _estados = _registrar(_TODAS)
        for nombre in _TODAS:
            self.assertIn(getattr(mod, nombre), cliente.manejadores)

    def test_no_registra_las_ausentes(self):
        obligatorias = ("CommentEvent", "GiftEvent", "JoinEvent",
                        "RoomUserSeqEvent")
        cliente, mod, _recibidos, _vistos, _estados = _registrar(
            obligatorias)
        self.assertEqual(
            set(cliente.manejadores),
            {getattr(mod, nombre) for nombre in obligatorias})

    def test_suscripcion_por_subnotify_cuando_no_hay_subscribe(self):
        nombres = ("CommentEvent", "GiftEvent", "JoinEvent",
                   "RoomUserSeqEvent", "SubNotifyEvent")
        cliente, mod, _recibidos, _vistos, _estados = _registrar(nombres)
        self.assertIn(mod.SubNotifyEvent, cliente.manejadores)

    def test_join_se_registra_aunque_el_evento_de_entrada_este_desactivado(self):
        for modo in ("principal", "ocultar"):
            with self.subTest(modo=modo):
                cliente, mod, _rec, _vis, _est = _registrar(
                    _TODAS, evento_entrada=modo)
                self.assertIn(mod.JoinEvent, cliente.manejadores)

    def test_descartar_true_bloquea_el_comentario(self):
        cliente, mod, recibidos, _vistos, _estados = _registrar(
            _TODAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.CommentEvent](
            _evento_comentario()))
        self.assertEqual(recibidos, [])

    def test_descartar_false_deja_pasar_el_comentario(self):
        cliente, mod, recibidos, _vistos, _estados = _registrar(_TODAS)
        asyncio.run(cliente.manejadores[mod.CommentEvent](
            _evento_comentario("hola")))
        self.assertEqual(len(recibidos), 1)
        self.assertIn("hola", recibidos[0][1])

    def test_conteo_no_usa_descartar(self):
        cliente, mod, _recibidos, vistos, _estados = _registrar(
            _TODAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.RoomUserSeqEvent](
            types.SimpleNamespace(total=3, total_user=50)))
        self.assertEqual(vistos, [(3, 50)])


def _evento_sticker(cuantos=1):
    autor = types.SimpleNamespace(nick_name="Ana", id="1")
    return types.SimpleNamespace(
        emote_list=[object()] * cuantos, user_info=autor)


def _evento_pregunta(texto="¿qué juego es?"):
    autor = types.SimpleNamespace(nick_name="Ana", id="1")
    datos = types.SimpleNamespace(content=texto, user_info=autor)
    return types.SimpleNamespace(data=datos)


def _evento_me_gusta(count=15):
    autor = types.SimpleNamespace(nick_name="Ana", id="1")
    return types.SimpleNamespace(count=count, user_info=autor)


def _evento_entrada(nombre, ident):
    autor = types.SimpleNamespace(nick_name=nombre, id=ident)
    return types.SimpleNamespace(user_info=autor)


class TestStickersYPreguntas(unittest.TestCase):
    def test_sticker_uno_se_lee_como_sticker(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        asyncio.run(cliente.manejadores[mod.EmoteChatEvent](
            _evento_sticker(1)))
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana")
        self.assertEqual(recibidos[0][1], "sticker")
        self.assertEqual(recibidos[0][2], TIPO_TEXTO)

    def test_sticker_varios_con_numero(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        asyncio.run(cliente.manejadores[mod.EmoteChatEvent](
            _evento_sticker(3)))
        self.assertEqual(recibidos[0][1], "3 stickers")
        self.assertEqual(recibidos[0][2], TIPO_TEXTO)

    def test_sticker_sin_lista_se_lee_como_sticker(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        asyncio.run(cliente.manejadores[mod.EmoteChatEvent](
            _evento_sticker(0)))
        self.assertEqual(recibidos[0][1], "sticker")

    def test_sticker_respeta_descartar(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.EmoteChatEvent](
            _evento_sticker(1)))
        self.assertEqual(recibidos, [])

    def test_pregunta_se_lee_con_prefijo(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        asyncio.run(cliente.manejadores[mod.QuestionNewEvent](
            _evento_pregunta("  ¿qué juego es?  ")))
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana")
        self.assertEqual(recibidos[0][1], "Pregunta: ¿qué juego es?")
        self.assertEqual(recibidos[0][2], TIPO_TEXTO)

    def test_pregunta_sin_data_no_llama(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        asyncio.run(cliente.manejadores[mod.QuestionNewEvent](
            types.SimpleNamespace()))
        self.assertEqual(recibidos, [])

    def test_pregunta_sin_content_no_llama(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        autor = types.SimpleNamespace(nick_name="Ana", id="1")
        evento = types.SimpleNamespace(
            data=types.SimpleNamespace(content="   ", user_info=autor))
        asyncio.run(cliente.manejadores[mod.QuestionNewEvent](evento))
        self.assertEqual(recibidos, [])

    def test_pregunta_respeta_descartar(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.QuestionNewEvent](
            _evento_pregunta()))
        self.assertEqual(recibidos, [])


def _inundar(cliente, mod, cantidad=15, veces=3, reloj=1000.0):
    with mock.patch.object(tiktok_manejadores.time, "monotonic",
                           return_value=reloj):
        for _ in range(veces):
            asyncio.run(cliente.manejadores[mod.LikeEvent](
                _evento_me_gusta(cantidad)))
    return reloj


def _vaciar_con_conteo(cliente, mod, reloj):
    with mock.patch.object(tiktok_manejadores.time, "monotonic",
                           return_value=reloj):
        asyncio.run(cliente.manejadores[mod.RoomUserSeqEvent](
            types.SimpleNamespace(total=3, total_user=50)))


class TestMeGustaAgrupado(unittest.TestCase):
    def test_rafaga_de_una_persona_da_una_sola_llamada_con_el_total(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        reloj = _inundar(cliente, mod, cantidad=15, veces=3)
        self.assertEqual(recibidos, [])
        _vaciar_con_conteo(cliente, mod, reloj + 10.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana")
        self.assertEqual(recibidos[0][2], TIPO_ME_GUSTA)
        self.assertEqual(recibidos[0][3], "45")
        self.assertEqual(recibidos[0][4], "1")

    def test_count_invalido_cuenta_uno(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        with mock.patch.object(tiktok_manejadores.time, "monotonic",
                               return_value=1000.0):
            asyncio.run(cliente.manejadores[mod.LikeEvent](
                _evento_me_gusta(0)))
            asyncio.run(cliente.manejadores[mod.LikeEvent](
                _evento_me_gusta("hola")))
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][3], "2")

    def test_me_gusta_respeta_descartar(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, descartar=lambda evento: True)
        _inundar(cliente, mod)
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(recibidos, [])

    def test_conteo_tambien_avisa_sus_numeros(self):
        cliente, mod, _recibidos, vistos, _est = _registrar(_TODAS_NUEVAS)
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(vistos, [(3, 50)])


class TestEntradasAgrupadas(unittest.TestCase):
    def _entrar(self, cliente, mod, nombre, ident, reloj):
        with mock.patch.object(tiktok_manejadores.time, "monotonic",
                               return_value=reloj):
            asyncio.run(cliente.manejadores[mod.JoinEvent](
                _evento_entrada(nombre, ident)))

    def test_tres_entradas_dentro_de_la_ventana_salen_en_una_fila(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        for indice, nombre in enumerate(("Ana", "Beto", "Caro")):
            self._entrar(cliente, mod, nombre, str(indice + 1), 1000.0)
        self.assertEqual(recibidos, [])
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana, Beto y Caro")
        self.assertEqual(recibidos[0][2], TIPO_ENTRADA)
        self.assertEqual(recibidos[0][3], "3")

    def test_agrupar_entradas_desmarcado_emite_cada_una_al_llegar(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, config={"tiktok_agrupar_entradas": False})
        for indice, nombre in enumerate(("Ana", "Beto", "Caro")):
            self._entrar(cliente, mod, nombre, str(indice + 1), 1000.0)
        self.assertEqual(len(recibidos), 3)
        self.assertEqual([r[0] for r in recibidos], ["Ana", "Beto", "Caro"])
        self.assertEqual([r[3] for r in recibidos], ["", "", ""])

    def test_una_persona_silenciada_no_aparece_y_las_demas_siguen(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, config={"usuarios_silenciados": ["beto"]})
        for indice, nombre in enumerate(("Ana", "Beto", "Caro")):
            self._entrar(cliente, mod, nombre, str(indice + 1), 1000.0)
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana y Caro")
        self.assertEqual(recibidos[0][2], TIPO_ENTRADA)
        self.assertEqual(recibidos[0][3], "2")

    def test_una_persona_oculta_en_la_sesion_tampoco_aparece(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS,
            config={"silenciados_runtime": {"beto"}})
        for indice, nombre in enumerate(("Ana", "Beto", "Caro")):
            self._entrar(cliente, mod, nombre, str(indice + 1), 1000.0)
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana y Caro")
        self.assertEqual(recibidos[0][3], "2")

    def test_la_ventana_de_entradas_no_usa_los_segundos_de_me_gusta(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS,
            config={"tiktok_segundos_entradas": 1,
                    "tiktok_segundos_me_gusta": 60})
        for indice, nombre in enumerate(("Ana", "Beto")):
            self._entrar(cliente, mod, nombre, str(indice + 1), 1000.0)
        _vaciar_con_conteo(cliente, mod, 1002.0)
        self.assertEqual(len(recibidos), 1)
        self.assertEqual(recibidos[0][0], "Ana y Beto")
        self.assertEqual(recibidos[0][3], "2")

    def test_una_sola_persona_conserva_la_fila_y_su_autor(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        self._entrar(cliente, mod, "Ana", "1", 1000.0)
        _vaciar_con_conteo(cliente, mod, 1010.0)
        self.assertEqual(recibidos, [("Ana", "", TIPO_ENTRADA, "", "1")])


class TestMeGustaSinAgrupar(unittest.TestCase):
    def test_agrupar_me_gusta_desmarcado_emite_cada_uno_al_llegar(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, config={"tiktok_agrupar_me_gusta": False})
        with mock.patch.object(tiktok_manejadores.time, "monotonic",
                               return_value=1000.0):
            asyncio.run(cliente.manejadores[mod.LikeEvent](
                _evento_me_gusta(15)))
            asyncio.run(cliente.manejadores[mod.LikeEvent](
                _evento_me_gusta(15)))
        self.assertEqual(len(recibidos), 2)
        self.assertEqual([r[2] for r in recibidos],
                         [TIPO_ME_GUSTA, TIPO_ME_GUSTA])
        self.assertEqual([r[3] for r in recibidos], ["15", "15"])


class TestCofreConRemitente(unittest.TestCase):
    """El cofre se anuncia con el nombre de quien lo envió, si viene."""

    def _cofre(self):
        cliente, mod, recibidos, _vistos, _est = _registrar(_TODAS_NUEVAS)
        return cliente, mod, recibidos

    def test_entrega_el_nombre_del_remitente_del_cofre(self):
        from TikTokLive.events import EnvelopeEvent
        from TikTokLiveProto.v3.webcast.model.message.redenvelope import (
            MessageRedEnvelopInfo)
        cliente, mod, recibidos = self._cofre()
        evento = EnvelopeEvent(envelope_info=MessageRedEnvelopInfo(
            send_user_name="Ana", send_user_id="7"))
        asyncio.run(cliente.manejadores[mod.EnvelopeEvent](evento))
        self.assertEqual(recibidos, [("Ana", "", TIPO_COFRE, "", "7")])

    def test_sin_nombre_usa_el_autor_del_evento(self):
        from TikTokLive.events import EnvelopeEvent
        from TikTokLiveProto.v3.webcast.model.message.redenvelope import (
            MessageRedEnvelopInfo)
        cliente, mod, recibidos = self._cofre()
        evento = EnvelopeEvent(envelope_info=MessageRedEnvelopInfo())
        asyncio.run(cliente.manejadores[mod.EnvelopeEvent](evento))
        self.assertEqual(recibidos, [("Usuario", "", TIPO_COFRE, "", "")])

    def test_sin_envelope_info_usa_el_autor_del_evento(self):
        from TikTokLive.events import EnvelopeEvent
        cliente, mod, recibidos = self._cofre()
        asyncio.run(cliente.manejadores[mod.EnvelopeEvent](EnvelopeEvent()))
        self.assertEqual(recibidos, [("Usuario", "", TIPO_COFRE, "", "")])


class TestPausaDirecto(unittest.TestCase):
    def test_pausa_y_reanudacion_llaman_on_estado(self):
        estados = []
        cliente, mod, _rec, _vis, _est = _registrar(
            _TODAS_NUEVAS, on_estado=lambda *a: estados.append(a))
        asyncio.run(cliente.manejadores[mod.LivePauseEvent](
            types.SimpleNamespace()))
        asyncio.run(cliente.manejadores[mod.LiveUnpauseEvent](
            types.SimpleNamespace()))
        self.assertEqual(estados, [
            ("directo_pausado", "El directo de TikTok está en pausa."),
            ("directo_reanudado", "El directo de TikTok continúa."),
        ])

    def test_pausa_respeta_descartar(self):
        estados = []
        cliente, mod, _rec, _vis, _est = _registrar(
            _TODAS_NUEVAS, descartar=lambda evento: True,
            on_estado=lambda *a: estados.append(a))
        asyncio.run(cliente.manejadores[mod.LivePauseEvent](
            types.SimpleNamespace()))
        self.assertEqual(estados, [])

    def test_no_registra_pausa_si_falta_la_clase(self):
        nombres = ("CommentEvent", "GiftEvent", "JoinEvent",
                   "RoomUserSeqEvent")
        cliente, mod, _rec, _vis, estados = _registrar(nombres)
        self.assertEqual(estados, [])


class TestOrdenDeRegistro(unittest.TestCase):
    def test_registra_las_clases_en_orden_con_todo_presente(self):
        cliente, mod, _rec, _vis, _est = _registrar(_TODAS_NUEVAS)
        self.assertEqual(
            list(cliente.manejadores),
            [mod.CommentEvent, mod.GiftEvent, mod.SubscribeEvent,
             mod.FollowEvent, mod.ShareEvent, mod.EnvelopeEvent,
             mod.LikeEvent, mod.EmoteChatEvent, mod.QuestionNewEvent,
             mod.LivePauseEvent, mod.LiveUnpauseEvent, mod.JoinEvent,
             mod.RoomUserSeqEvent])

    def test_sin_on_estado_no_registra_pausa_ni_reanudacion(self):
        cliente, mod, _rec, _vis, _est = _registrar(
            _TODAS_NUEVAS, sin_estado=True)
        self.assertNotIn(mod.LivePauseEvent, cliente.manejadores)
        self.assertNotIn(mod.LiveUnpauseEvent, cliente.manejadores)
        self.assertIn(mod.FollowEvent, cliente.manejadores)
        self.assertIn(mod.LikeEvent, cliente.manejadores)


if __name__ == "__main__":
    unittest.main()
