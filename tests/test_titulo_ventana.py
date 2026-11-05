"""Título de la ventana principal con el estado de OBS.

Las funciones puras no abren ventanas. Las del cableado usan un marco real y
necesitan wxPython.
"""

from types import SimpleNamespace
import unittest
from unittest import mock

from bellbird.core.config import APP_NAME, APP_VERSION
from bellbird.obs.obs_vigilante import EstadoObs
from bellbird.ui import gui
from bellbird.ui import titulo_ventana
from tests.ventanas_prueba import app_de_prueba, destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


def _estado(transmision=False, grabacion=False, en_pausa=False):
    return EstadoObs(
        {"outputActive": transmision},
        {"outputActive": grabacion, "outputPaused": en_pausa},
        "")


class MarcoFalso:
    def __init__(self, stream="", titulo=None, config=None, estado=None):
        self._titulo_stream = stream
        self._config = {"titulo_estado_obs": False} if config is None else config
        self._obs_vigilante = (None if estado is None
                               else SimpleNamespace(estado=lambda: estado))
        self._titulo = (titulo if titulo is not None
                        else titulo_ventana.componer(stream, ""))
        self.titulos = []

    def GetTitle(self):
        return self._titulo

    def SetTitle(self, texto):
        self._titulo = texto
        self.titulos.append(texto)


class PrefijoEstadoTest(unittest.TestCase):
    def test_sin_dato_no_lleva_prefijo(self):
        self.assertEqual(titulo_ventana.prefijo_estado(None), "")

    def test_sin_salidas_no_lleva_prefijo(self):
        self.assertEqual(titulo_ventana.prefijo_estado(_estado()), "")

    def test_solo_transmision(self):
        self.assertEqual(titulo_ventana.prefijo_estado(_estado(transmision=True)),
                         "(Transmitiendo)")

    def test_solo_grabacion(self):
        self.assertEqual(titulo_ventana.prefijo_estado(_estado(grabacion=True)),
                         "(Grabando)")

    def test_las_dos_salidas(self):
        self.assertEqual(
            titulo_ventana.prefijo_estado(
                _estado(transmision=True, grabacion=True)),
            "(Transmitiendo y grabando)")

    def test_la_grabacion_en_pausa_sigue_diciendo_grabando(self):
        self.assertEqual(
            titulo_ventana.prefijo_estado(
                _estado(grabacion=True, en_pausa=True)),
            "(Grabando)")


class ComponerTest(unittest.TestCase):
    def test_con_titulo_del_video(self):
        self.assertEqual(
            titulo_ventana.componer("Charla", "(Grabando)"),
            f"(Grabando) Charla — {APP_NAME}")

    def test_sin_titulo_usa_la_version(self):
        self.assertEqual(
            titulo_ventana.componer("", "(Grabando)"),
            f"(Grabando) {APP_NAME} v{APP_VERSION}")

    def test_sin_prefijo_deja_el_titulo_de_siempre(self):
        self.assertEqual(titulo_ventana.componer("Charla", ""),
                         f"Charla — {APP_NAME}")


class AplicarTest(unittest.TestCase):
    def test_no_cambia_el_titulo_si_el_texto_es_el_mismo(self):
        marco = MarcoFalso(stream="Charla", titulo=f"Charla — {APP_NAME}")
        titulo_ventana.aplicar(marco)
        self.assertEqual(marco.titulos, [])

    def test_con_la_casilla_desmarcada_no_pone_prefijo_aunque_grabe(self):
        marco = MarcoFalso(
            stream="Charla", titulo=f"Charla — {APP_NAME}",
            config={"titulo_estado_obs": False},
            estado=_estado(grabacion=True))
        titulo_ventana.aplicar(marco)
        self.assertEqual(marco.titulos, [])

    def test_con_la_casilla_marcada_antepone_el_estado(self):
        marco = MarcoFalso(
            stream="Charla", titulo=f"Charla — {APP_NAME}",
            config={"titulo_estado_obs": True},
            estado=_estado(grabacion=True))
        titulo_ventana.aplicar(marco)
        self.assertEqual(marco.titulos,
                         [f"(Grabando) Charla — {APP_NAME}"])

    def test_sin_vigilante_no_pone_prefijo(self):
        marco = MarcoFalso(stream="Charla", titulo=f"Charla — {APP_NAME}",
                           config={"titulo_estado_obs": True})
        titulo_ventana.aplicar(marco)
        self.assertEqual(marco.titulos, [])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class CableadoTest(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()

    def test_el_temporizador_llega_a_aplicar(self):
        marco = wx.Frame(None)
        self.addCleanup(destruir, marco)
        marco._alive = True
        marco._actualizar_sb = lambda: None
        marco._procesar_programado = lambda: None
        marco._avisar_descartes = lambda: None
        with mock.patch.object(titulo_ventana, "aplicar") as aplicar:
            gui.YTChatFrame._on_timer(marco, None)
        aplicar.assert_called_once_with(marco)

    def test_la_casilla_arranca_el_vigilante_sin_componentes_de_estado(self):
        marco = gui.YTChatFrame.__new__(gui.YTChatFrame)
        marco._config = {"estado_toggles": set(), "titulo_estado_obs": True}
        marco._obs_vigilante = None
        with mock.patch.object(gui.obs_vigilante, "VigilanteObs") as clase:
            gui.YTChatFrame._actualizar_vigilante_obs(marco)
        clase.return_value.iniciar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
