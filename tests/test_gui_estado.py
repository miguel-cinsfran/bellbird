"""Espectadores y su total en el marco y en la foto para F2."""

import types
import unittest
from unittest import mock

from ytchat.ui import gui
from ytchat.ui import gui_estado


def _marco_falso(metadatos):
    frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
    frame._conectado = True
    frame._es_tiktok = True
    frame._tipo_video = "live"
    frame._titulo_stream = "T"
    frame._metadatos = metadatos
    frame._sc_totales = {}
    frame._mensajes_programados = []
    frame._config = {"silenciar_lectura": False, "programados_activo": False}
    frame._stats = mock.Mock(leidos=0, superchats=0, descartados=0)
    frame._cola = mock.Mock(qsize=mock.Mock(return_value=0))
    frame._worker = mock.Mock(get_rate=mock.Mock(return_value=0),
                              get_volume=mock.Mock(return_value=0))
    frame._obs_vigilante = None
    frame._atajos = {}
    frame._rep_panel = mock.Mock()
    frame._musica = mock.Mock()
    return frame


class TestSetEspectadores(unittest.TestCase):

    def _frame(self):
        return types.SimpleNamespace(_alive=True, _metadatos={})

    def test_guarda_las_dos_cifras(self):
        frame = self._frame()
        gui.YTChatFrame.set_espectadores(frame, 3, 50)
        self.assertEqual(frame._metadatos, {"vistas": 3,
                                           "vistas_total": 50})

    def test_total_none_no_borra_el_total_anterior(self):
        frame = self._frame()
        frame._metadatos = {"vistas": 3, "vistas_total": 50}
        gui.YTChatFrame.set_espectadores(frame, 4)
        self.assertEqual(frame._metadatos, {"vistas": 4,
                                           "vistas_total": 50})


class TestSnapshotEspectadores(unittest.TestCase):

    def test_lleva_el_total(self):
        snap = gui_estado.snapshot_sesion(
            _marco_falso({"vistas": 3, "vistas_total": 50}))
        self.assertEqual(snap.espectadores, 3)
        self.assertEqual(snap.espectadores_total, 50)

    def test_total_no_numerico_queda_en_none(self):
        snap = gui_estado.snapshot_sesion(
            _marco_falso({"vistas": 3, "vistas_total": "muchos"}))
        self.assertEqual(snap.espectadores_total, None)


if __name__ == "__main__":
    unittest.main()
