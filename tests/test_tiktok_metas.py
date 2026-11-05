"""Lectura de `GoalUpdateEvent` de TikTokLive hacia el registro de metas.

Construye los eventos con sus clases reales: una meta que avanza sin
cumplirse no anuncia y queda para F2; al cumplirse anuncia una sola vez.
"""

import unittest

from TikTokLive.events import GoalUpdateEvent
from TikTokLiveProto.v3.webcast.model.gift.model import (
    LiveStreamGoal,
    LiveStreamSubGoal,
)

from bellbird.capture import metas
from bellbird.capture import tiktok_metas
from bellbird.core.tipos_mensaje import TIPO_META


def _meta(descripcion="100 rosas para el viaje", submetas=((340, 500),),
          id_meta="g1"):
    return GoalUpdateEvent(goal=LiveStreamGoal(
        id_str=id_meta,
        description=descripcion,
        sub_goals=[LiveStreamSubGoal(id_str=f"s{i}", progress=progreso,
                                     target=objetivo)
                   for i, (progreso, objetivo) in enumerate(submetas)]))


class TestProcesarMetas(unittest.TestCase):

    def setUp(self):
        tiktok_metas.reiniciar()

    def _procesar(self, evento):
        recibidos = []
        tiktok_metas.procesar(evento, lambda *a: recibidos.append(a))
        return recibidos

    def test_avanza_sin_cumplirse_no_anuncia_y_queda_en_f2(self):
        self.assertEqual(self._procesar(_meta()), [])
        self.assertEqual(
            metas.registro.en_curso(),
            "Meta: 100 rosas para el viaje, 340 de 500")

    def test_al_cumplirse_anuncia_su_tipo(self):
        self.assertEqual(self._procesar(_meta(submetas=((500, 500),))), [(
            "", "Meta cumplida: 100 rosas para el viaje", TIPO_META, "", "")])

    def test_cumplida_repetida_no_vuelve_a_anunciar(self):
        self._procesar(_meta(submetas=((500, 500),)))
        self.assertEqual(self._procesar(_meta(submetas=((500, 500),))), [])

    def test_sin_descripcion_solo_dice_meta_cumplida(self):
        recibidos = self._procesar(
            _meta(descripcion="", submetas=((10, 10),)))
        self.assertEqual(recibidos[0][1], "Meta cumplida")

    def test_reiniciar_olvida_la_meta(self):
        self._procesar(_meta())
        tiktok_metas.reiniciar()
        self.assertEqual(metas.registro.en_curso(), "")


if __name__ == "__main__":
    unittest.main()
