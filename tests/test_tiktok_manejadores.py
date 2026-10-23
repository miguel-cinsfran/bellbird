"""Manejadores de eventos de TikTok en su módulo propio."""

import asyncio
import types
import unittest

from ytchat.capture.tiktok_manejadores import registrar_manejadores

_TODAS = ("CommentEvent", "GiftEvent", "JoinEvent", "RoomUserSeqEvent",
          "SubscribeEvent", "FollowEvent", "ShareEvent", "EnvelopeEvent",
          "LikeEvent")


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


def _registrar(nombres, anunciar_entradas=True, descartar=None):
    cliente = _ClienteFalso()
    mod = _modulo(nombres)
    recibidos = []
    vistos = []
    registrar_manejadores(
        cliente, mod, on_evento=lambda *a: recibidos.append(a),
        on_espectadores=lambda *a: vistos.append(a),
        anunciar_entradas=anunciar_entradas,
        descartar=(descartar or (lambda evento: False)))
    return cliente, mod, recibidos, vistos


def _evento_comentario(texto="hola"):
    autor = types.SimpleNamespace(nick_name="Pepe", id="1")
    return types.SimpleNamespace(comment=texto, user_info=autor)


class TestRegistrarManejadores(unittest.TestCase):
    def test_registra_uno_por_clase_presente(self):
        cliente, mod, _recibidos, _vistos = _registrar(_TODAS)
        for nombre in _TODAS:
            self.assertIn(getattr(mod, nombre), cliente.manejadores)

    def test_no_registra_las_ausentes(self):
        obligatorias = ("CommentEvent", "GiftEvent", "JoinEvent",
                        "RoomUserSeqEvent")
        cliente, mod, _recibidos, _vistos = _registrar(obligatorias)
        self.assertEqual(
            set(cliente.manejadores),
            {getattr(mod, nombre) for nombre in obligatorias})

    def test_suscripcion_por_subnotify_cuando_no_hay_subscribe(self):
        nombres = ("CommentEvent", "GiftEvent", "JoinEvent",
                   "RoomUserSeqEvent", "SubNotifyEvent")
        cliente, mod, _recibidos, _vistos = _registrar(nombres)
        self.assertIn(mod.SubNotifyEvent, cliente.manejadores)

    def test_join_solo_con_anunciar_entradas(self):
        cliente, mod, _rec, _vis = _registrar(_TODAS, anunciar_entradas=True)
        self.assertIn(mod.JoinEvent, cliente.manejadores)
        cliente2, mod2, _r2, _v2 = _registrar(_TODAS, anunciar_entradas=False)
        self.assertNotIn(mod2.JoinEvent, cliente2.manejadores)

    def test_descartar_true_bloquea_el_comentario(self):
        cliente, mod, recibidos, _vistos = _registrar(
            _TODAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.CommentEvent](
            _evento_comentario()))
        self.assertEqual(recibidos, [])

    def test_descartar_false_deja_pasar_el_comentario(self):
        cliente, mod, recibidos, _vistos = _registrar(_TODAS)
        asyncio.run(cliente.manejadores[mod.CommentEvent](
            _evento_comentario("hola")))
        self.assertEqual(len(recibidos), 1)
        self.assertIn("hola", recibidos[0][1])

    def test_conteo_no_usa_descartar(self):
        cliente, mod, _recibidos, vistos = _registrar(
            _TODAS, descartar=lambda evento: True)
        asyncio.run(cliente.manejadores[mod.RoomUserSeqEvent](
            types.SimpleNamespace(total=3, total_user=50)))
        self.assertEqual(vistos, [(3, 50)])


if __name__ == "__main__":
    unittest.main()
