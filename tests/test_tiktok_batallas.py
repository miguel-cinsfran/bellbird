"""Lectura de `LinkMicBattleEvent` y `LinkMicArmiesEvent` de TikTokLive.

Construye los eventos con sus clases reales: el comienzo y el fin se
anuncian una vez con su tipo y los puntajes, las demás etapas no anuncian
y las armies solo actualizan los puntajes de F2.
"""

import queue
import unittest

import main
from TikTokLive.events import LinkMicArmiesEvent, LinkMicBattleEvent
from TikTokLiveProto.v3.webcast.im import LinkMicBattleBattleAction
from TikTokLiveProto.v3.webcast.model.live.match import (
    BattleBaseUserInfo,
    BattleUserInfo,
)
from TikTokLiveProto.v3.webcast.model.message.battle import (
    BattleResult,
    BattleUserArmies,
    BattleUserInfoWrapper,
)

from guyrapu.capture import batallas
from guyrapu.capture import tiktok_batallas
from guyrapu.core.tipos_mensaje import TIPO_BATALLA, TIPO_BATALLA_FIN


def _anfitrion(ident, nombre):
    return BattleUserInfoWrapper(value=BattleUserInfo(
        user=BattleBaseUserInfo(user_id=ident, nick_name=nombre)))


def _batalla(accion, anfitriones=(("Ana", 1), ("Fulano", 2)),
             puntajes=None, id_batalla=7):
    return LinkMicBattleEvent(
        battle_id=id_batalla,
        action=accion,
        anchors_info=[_anfitrion(ident, nombre)
                      for nombre, ident in anfitriones],
        battle_result={ident: BattleResult(score=puntos)
                       for ident, puntos in (puntajes or {}).items()})


def _armies(puntajes, id_batalla=7):
    return LinkMicArmiesEvent(
        battle_id=id_batalla,
        armies={ident: BattleUserArmies(hostscore=puntos)
                for ident, puntos in puntajes.items()})


class TestProcesarBatallas(unittest.TestCase):

    def setUp(self):
        tiktok_batallas.reiniciar()

    def _procesar(self, evento):
        recibidos = []
        tiktok_batallas.procesar(evento, lambda *a: recibidos.append(a))
        return recibidos

    def test_open_anuncia_el_comienzo(self):
        recibidos = self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        self.assertEqual(recibidos, [(
            "", "Batalla: Ana contra Fulano", TIPO_BATALLA, "", "")])

    def test_open_repetido_no_vuelve_a_anunciar(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        self.assertEqual(
            self._procesar(_batalla(LinkMicBattleBattleAction.OPEN)), [])

    def test_fin_anuncia_los_puntajes(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        recibidos = self._procesar(_batalla(
            LinkMicBattleBattleAction.FINISH,
            puntajes={1: 3200, 2: 2800}))
        self.assertEqual(recibidos, [(
            "", "Batalla terminada: Ana con 3200 puntos, Fulano con 2800 "
            "puntos", TIPO_BATALLA_FIN, "", "")])

    def test_cut_short_tambien_anuncia_el_fin(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        recibidos = self._procesar(_batalla(
            LinkMicBattleBattleAction.LINK_MIC_BATTLE_BATTLE_ACTION_CUT_SHORT,
            puntajes={1: 10, 2: 5}))
        self.assertEqual(recibidos[0][2], TIPO_BATALLA_FIN)

    def test_fin_repetido_no_vuelve_a_anunciar(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        fin = _batalla(LinkMicBattleBattleAction.FINISH,
                       puntajes={1: 3200, 2: 2800})
        self._procesar(fin)
        self.assertEqual(self._procesar(fin), [])

    def test_fin_sin_comienzo_se_anuncia_igual(self):
        recibidos = self._procesar(_batalla(
            LinkMicBattleBattleAction.FINISH,
            puntajes={1: 3200, 2: 2800}))
        self.assertEqual(recibidos[0][2], TIPO_BATALLA_FIN)

    def test_invite_no_anuncia(self):
        self.assertEqual(
            self._procesar(_batalla(LinkMicBattleBattleAction.INVITE)), [])

    def test_armies_cambia_los_puntajes_de_f2_sin_anunciar(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        tiktok_batallas.procesar_armies(_armies({1: 1200, 2: 900}))
        self.assertEqual(
            batallas.registro.en_curso(),
            "Batalla en curso: Ana 1200 puntos, Fulano 900 puntos")

    def test_reiniciar_olvida_la_batalla(self):
        self._procesar(_batalla(LinkMicBattleBattleAction.OPEN))
        tiktok_batallas.reiniciar()
        self.assertEqual(batallas.registro.en_curso(), "")


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


class TestModoOcultarEnElCableado(unittest.TestCase):

    def test_ocultar_no_deja_pasar_ni_el_comienzo_ni_el_fin(self):
        for tipo in (TIPO_BATALLA, TIPO_BATALLA_FIN):
            with self.subTest(tipo=tipo):
                recibidos = []
                cola = queue.Queue()
                main.procesar_entrante(
                    "", "Batalla", tipo, "", "", cola,
                    _config_minima(evento_batalla="ocultar"), main.Stats(),
                    on_message=lambda *a, **k: recibidos.append(a))
                self.assertEqual(recibidos, [])
                self.assertTrue(cola.empty())


if __name__ == "__main__":
    unittest.main()
