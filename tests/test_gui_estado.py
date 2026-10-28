"""Espectadores y su total en el marco y en la foto para F2."""

import types
import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.ui import gui
from ytchat.ui import gui_estado
from ytchat.ui.sesion_conectada import SesionConectada


def _marco_falso(metadatos):
    frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
    frame._conectado = True
    frame.sesion = SesionConectada(es_tiktok=True, tipo_video="live")
    frame._titulo_stream = "T"
    frame._metadatos = metadatos
    frame._sc_totales = {}
    frame.programador = gui.programados.ProgramadorMensajes([])
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


class TestTotalAportesTexto(unittest.TestCase):

    def test_una_divisa(self):
        frame = types.SimpleNamespace(_sc_totales={"€": 15.5})
        self.assertEqual(gui_estado.total_aportes_texto(frame), "€15.50")

    def test_dos_divisas(self):
        frame = types.SimpleNamespace(_sc_totales={"€": 15.0, "$": 10.0})
        self.assertEqual(gui_estado.total_aportes_texto(frame), "€15, $10")


class TestFormatoTotalSc(unittest.TestCase):

    def _frame(self, totales):
        return types.SimpleNamespace(
            _stats=types.SimpleNamespace(superchats=3),
            _sc_totales=totales)

    def test_sin_totales(self):
        self.assertEqual(
            gui.YTChatFrame._formato_total_sc(self._frame({})), "SC: 3")

    def test_una_divisa(self):
        self.assertEqual(
            gui.YTChatFrame._formato_total_sc(self._frame({"€": 15.5})),
            "SC: 3 (€15.50)")

    def test_dos_divisas(self):
        self.assertEqual(
            gui.YTChatFrame._formato_total_sc(
                self._frame({"€": 15.0, "$": 10.0})),
            "SC: 3 (€15, $10)")


def _hilo_inmediato(objetivo, _nombre):
    hilo = mock.Mock()
    hilo.start.side_effect = lambda: objetivo()
    return hilo


class TestPseudoAnuncios(unittest.TestCase):
    """Pseudotraducción de los anuncios de estado, sin ventanas: corre acá."""

    def test_estado_sin_info_sale_marcado(self):
        frame = types.SimpleNamespace(_config={},
                                      _snapshot_sesion=lambda: "SNAP")
        captados = []
        with con_pseudo(), \
                mock.patch.object(gui.estado_sesion, "formatear_estado",
                                  return_value=""), \
                mock.patch.object(gui, "anunciar", captados.append):
            gui_estado.anunciar_estado(frame)
        self.assertEqual(captados, ["[¡Sin información de estado.!]"])

    def test_autor_sale_marcado(self):
        for ultimo, esperado in (
                ("Ana", "[¡Último mensaje leído de Ana!]"),
                ("", "[¡Todavía no se leyó ningún mensaje.!]")):
            with self.subTest(ultimo=ultimo):
                trabajador = mock.Mock()
                trabajador.ultimo_autor.return_value = ultimo
                frame = types.SimpleNamespace(_worker=trabajador)
                captados = []
                with con_pseudo(), \
                        mock.patch.object(gui, "anunciar", captados.append):
                    gui_estado.anunciar_autor(frame)
                self.assertEqual(captados, [esperado])

    def test_escena_sin_obs_sale_marcada(self):
        frame = types.SimpleNamespace(_descripcion_escena_en_curso=False)
        captados = []
        with con_pseudo(), \
                mock.patch.object(gui.obs_activacion,
                                  "obs_esta_en_ejecucion",
                                  return_value=False), \
                mock.patch.object(gui, "anunciar", captados.append):
            gui_estado.describir_escena(frame)
        self.assertEqual(captados, ["[¡OBS no está abierto.!]"])

    def test_escena_pasa_el_texto_ajeno_tal_cual(self):
        gestor = mock.Mock()
        gestor.descripcion_escena.return_value = "Escena: Principal"
        frame = types.SimpleNamespace(
            _descripcion_escena_en_curso=False,
            _anunciar_descripcion_escena=mock.Mock())
        with mock.patch.object(gui.obs_activacion,
                               "obs_esta_en_ejecucion",
                               return_value=True), \
                mock.patch.object(gui, "GestorPanelObs",
                                  return_value=gestor), \
                mock.patch.object(gui.diagnostico, "crear_hilo",
                                  side_effect=_hilo_inmediato), \
                mock.patch.object(gui.wx, "CallAfter",
                                  side_effect=lambda f, *a: f(*a)):
            gui_estado.describir_escena(frame)
        frame._anunciar_descripcion_escena.assert_called_once_with(
            "Escena: Principal")


if __name__ == "__main__":
    unittest.main()
