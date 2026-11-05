"""Manejadores de eventos de TikTok en su módulo propio."""

import asyncio
import types
import unittest
from unittest import mock

from guyrapu.capture import encuestas
from guyrapu.capture import batallas
from guyrapu.capture import metas
from guyrapu.capture import tiktok_manejadores
from guyrapu.capture.tiktok_manejadores import registrar_manejadores
from guyrapu.core.config import (
    TIPO_COFRE, TIPO_ENTRADA, TIPO_ME_GUSTA, TIPO_TEXTO,
)
from guyrapu.core.tipos_mensaje import TIPO_BATALLA, TIPO_META

_TODAS = ("CommentEvent", "GiftEvent", "JoinEvent", "RoomUserSeqEvent",
          "SubscribeEvent", "FollowEvent", "ShareEvent", "EnvelopeEvent",
          "LikeEvent", "PollEvent")
_TODAS_NUEVAS = _TODAS + ("EmoteChatEvent", "QuestionNewEvent",
                          "LivePauseEvent", "LiveUnpauseEvent",
                          "GoalUpdateEvent", "LinkMicBattleEvent",
                          "LinkMicArmiesEvent")


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


class TestEncuestasDeUnaConexionNueva(unittest.TestCase):

    def test_registrar_manejadores_olvida_la_encuesta_anterior(self):
        encuestas.registro.abrir(
            "vieja", "Encuesta vieja", [("pizza", 3)])
        self.assertNotEqual(encuestas.registro.en_curso(), "")
        _registrar(_TODAS)
        self.assertEqual(encuestas.registro.en_curso(), "")

    def test_poll_event_descartado_no_emite_ni_toca_el_registro(self):
        from TikTokLive.events import PollEvent
        from TikTokLiveProto.v3.webcast.model.message import (
            PollOptionInfo, PollStartContent)

        cliente, mod, recibidos, _vistos, _est = _registrar(
            _TODAS_NUEVAS, descartar=lambda evento: True)
        evento = PollEvent(
            poll_id=99,
            start_content=PollStartContent(
                title="¿Qué almorzamos?",
                option_list=[PollOptionInfo(
                    display_content="pizza", votes=0, option_idx=0)]))
        asyncio.run(cliente.manejadores[mod.PollEvent](evento))
        self.assertEqual(recibidos, [])
        self.assertEqual(encuestas.registro.en_curso(), "")


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
             mod.PollEvent, mod.GoalUpdateEvent, mod.LinkMicBattleEvent,
             mod.LinkMicArmiesEvent, mod.LivePauseEvent,
             mod.LiveUnpauseEvent, mod.JoinEvent, mod.RoomUserSeqEvent])

    def test_sin_on_estado_no_registra_pausa_ni_reanudacion(self):
        cliente, mod, _rec, _vis, _est = _registrar(
            _TODAS_NUEVAS, sin_estado=True)
        self.assertNotIn(mod.LivePauseEvent, cliente.manejadores)
        self.assertNotIn(mod.LiveUnpauseEvent, cliente.manejadores)
        self.assertIn(mod.FollowEvent, cliente.manejadores)
        self.assertIn(mod.LikeEvent, cliente.manejadores)


def _modulo_con_metas_y_batallas():
    from TikTokLive.events import (
        GoalUpdateEvent, LinkMicArmiesEvent, LinkMicBattleEvent)
    modulo = types.ModuleType("TikTokLive.events")
    for nombre in ("CommentEvent", "GiftEvent", "JoinEvent",
                   "RoomUserSeqEvent"):
        setattr(modulo, nombre, type(nombre, (), {}))
    modulo.GoalUpdateEvent = GoalUpdateEvent
    modulo.LinkMicBattleEvent = LinkMicBattleEvent
    modulo.LinkMicArmiesEvent = LinkMicArmiesEvent
    return modulo


def _meta_completa():
    from TikTokLive.events import GoalUpdateEvent
    from TikTokLiveProto.v3.webcast.model.gift.model import (
        LiveStreamGoal, LiveStreamSubGoal)
    return GoalUpdateEvent(goal=LiveStreamGoal(
        id_str="g1", description="Viaje",
        sub_goals=[LiveStreamSubGoal(progress=10, target=10)]))


def _meta_en_curso():
    from TikTokLive.events import GoalUpdateEvent
    from TikTokLiveProto.v3.webcast.model.gift.model import (
        LiveStreamGoal, LiveStreamSubGoal)
    return GoalUpdateEvent(goal=LiveStreamGoal(
        id_str="g1", description="Viaje",
        sub_goals=[LiveStreamSubGoal(progress=3, target=10)]))


def _batalla(accion, id_batalla=7):
    from TikTokLive.events import LinkMicBattleEvent
    from TikTokLiveProto.v3.webcast.model.live.match import (
        BattleBaseUserInfo, BattleUserInfo)
    from TikTokLiveProto.v3.webcast.model.message.battle import (
        BattleUserInfoWrapper)
    anfitriones = [
        BattleUserInfoWrapper(value=BattleUserInfo(user=BattleBaseUserInfo(
            user_id=1, nick_name="Ana"))),
        BattleUserInfoWrapper(value=BattleUserInfo(user=BattleBaseUserInfo(
            user_id=2, nick_name="Fulano"))),
    ]
    return LinkMicBattleEvent(battle_id=id_batalla, action=accion,
                              anchors_info=anfitriones)


def _armies(puntajes, id_batalla=7):
    from TikTokLive.events import LinkMicArmiesEvent
    from TikTokLiveProto.v3.webcast.model.message.battle import (
        BattleUserArmies)
    return LinkMicArmiesEvent(
        battle_id=id_batalla,
        armies={ident: BattleUserArmies(hostscore=puntos)
                for ident, puntos in puntajes.items()})


class TestMetasYBatallasEnElCableado(unittest.TestCase):

    def setUp(self):
        metas.registro.reiniciar()
        batallas.registro.reiniciar()

    def _registrar(self, descartar=None):
        cliente = _ClienteFalso()
        modulo = _modulo_con_metas_y_batallas()
        recibidos = []
        registrar_manejadores(
            cliente, modulo,
            on_evento=lambda *a: recibidos.append(a),
            on_espectadores=lambda *a: None, config={},
            descartar=descartar or (lambda evento: False))
        return cliente, modulo, recibidos

    def test_un_evento_real_de_meta_emite_su_tipo(self):
        cliente, modulo, recibidos = self._registrar()
        asyncio.run(cliente.manejadores[modulo.GoalUpdateEvent](
            _meta_completa()))
        self.assertEqual(recibidos[0][2], TIPO_META)

    def test_un_evento_real_de_batalla_emite_su_tipo(self):
        from TikTokLiveProto.v3.webcast.im import LinkMicBattleBattleAction
        cliente, modulo, recibidos = self._registrar()
        asyncio.run(cliente.manejadores[modulo.LinkMicBattleEvent](
            _batalla(LinkMicBattleBattleAction.OPEN)))
        self.assertEqual(recibidos[0][2], TIPO_BATALLA)

    def test_registrar_otra_vez_vacia_los_dos_registros(self):
        from TikTokLiveProto.v3.webcast.im import LinkMicBattleBattleAction
        cliente, modulo, _recibidos = self._registrar()
        asyncio.run(cliente.manejadores[modulo.GoalUpdateEvent](
            _meta_en_curso()))
        asyncio.run(cliente.manejadores[modulo.LinkMicBattleEvent](
            _batalla(LinkMicBattleBattleAction.OPEN)))
        asyncio.run(cliente.manejadores[modulo.LinkMicArmiesEvent](
            _armies({1: 1200, 2: 900})))
        self.assertNotEqual(metas.registro.en_curso(), "")
        self.assertNotEqual(batallas.registro.en_curso(), "")
        self._registrar()
        self.assertEqual(metas.registro.en_curso(), "")
        self.assertEqual(batallas.registro.en_curso(), "")

    def test_un_evento_descartado_no_emite_ni_toca_el_registro(self):
        from TikTokLiveProto.v3.webcast.im import LinkMicBattleBattleAction
        cliente, modulo, recibidos = self._registrar(
            descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[modulo.GoalUpdateEvent](
            _meta_completa()))
        asyncio.run(cliente.manejadores[modulo.LinkMicBattleEvent](
            _batalla(LinkMicBattleBattleAction.OPEN)))
        asyncio.run(cliente.manejadores[modulo.LinkMicArmiesEvent](
            _armies({1: 1200, 2: 900})))
        self.assertEqual(recibidos, [])
        self.assertEqual(metas.registro.en_curso(), "")
        self.assertEqual(batallas.registro.en_curso(), "")


if __name__ == "__main__":
    unittest.main()
