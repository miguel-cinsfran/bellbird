"""Pruebas de los avisos diferidos: sin wx real, con dobles."""

import unittest
from types import SimpleNamespace
from unittest import mock

from bellbird.ui import aviso_diferido


def _frame(conectado=False, transmitiendo=False):
    return SimpleNamespace(
        _conectado=conectado,
        _supervisar_transmision=lambda accion: transmitiendo)


def _ventana(mostrada=True, modal=False):
    ventana = mock.Mock()
    ventana.IsShown.return_value = mostrada
    ventana.IsModal.return_value = modal
    return ventana


class TestOcupado(unittest.TestCase):

    def test_solo_todo_falso_es_libre(self):
        for conectado in (False, True):
            for transmitiendo in (False, True):
                for modal in (False, True):
                    with self.subTest(conectado=conectado,
                                      transmitiendo=transmitiendo,
                                      modal=modal):
                        esperado = conectado or transmitiendo or modal
                        self.assertEqual(
                            esperado,
                            aviso_diferido.ocupado(
                                conectado, transmitiendo, modal))


class TestEstaOcupado(unittest.TestCase):

    def _sin_modales(self):
        return mock.patch.object(
            aviso_diferido.wx, "GetTopLevelWindows", return_value=[])

    def test_libre_sin_conexion_ni_transmision_ni_modales(self):
        with self._sin_modales():
            self.assertFalse(
                aviso_diferido.esta_ocupado(_frame()))

    def test_conectado_ocupa(self):
        with self._sin_modales():
            self.assertTrue(
                aviso_diferido.esta_ocupado(_frame(conectado=True)))

    def test_transmitiendo_ocupa(self):
        with self._sin_modales():
            self.assertTrue(
                aviso_diferido.esta_ocupado(_frame(transmitiendo=True)))

    def test_modal_abierto_ocupa(self):
        frame = _frame()
        with mock.patch.object(
                aviso_diferido.wx, "GetTopLevelWindows",
                return_value=[_ventana(mostrada=True, modal=True)]):
            self.assertTrue(aviso_diferido.esta_ocupado(frame))

    def test_ventana_no_modal_no_ocupa(self):
        with mock.patch.object(
                aviso_diferido.wx, "GetTopLevelWindows",
                return_value=[_ventana(mostrada=True, modal=False)]):
            self.assertFalse(
                aviso_diferido.esta_ocupado(_frame()))

    def test_modal_oculto_no_ocupa(self):
        with mock.patch.object(
                aviso_diferido.wx, "GetTopLevelWindows",
                return_value=[_ventana(mostrada=False, modal=True)]):
            self.assertFalse(
                aviso_diferido.esta_ocupado(_frame()))

    def test_el_propio_frame_no_cuenta_como_modal(self):
        frame = _frame()
        frame.IsShown = mock.Mock(return_value=True)
        frame.IsModal = mock.Mock(return_value=True)
        with mock.patch.object(
                aviso_diferido.wx, "GetTopLevelWindows",
                return_value=[frame]):
            self.assertFalse(aviso_diferido.esta_ocupado(frame))

    def test_si_preguntar_transmision_falla_ocupa(self):
        frame = SimpleNamespace(_conectado=False,
                                _supervisar_transmision=mock.Mock(
                                    side_effect=RuntimeError("boom")))
        with self._sin_modales():
            self.assertTrue(aviso_diferido.esta_ocupado(frame))

    def test_si_listar_ventanas_falla_ocupa(self):
        with mock.patch.object(
                aviso_diferido.wx, "GetTopLevelWindows",
                side_effect=RuntimeError("boom")):
            self.assertTrue(aviso_diferido.esta_ocupado(_frame()))


class TestCuandoLibre(unittest.TestCase):

    def test_ocupado_reprograma_con_30000_y_no_llama(self):
        llamadas = []
        with mock.patch.object(
                aviso_diferido, "esta_ocupado", return_value=True), \
                mock.patch.object(aviso_diferido.wx, "CallLater") as programar:
            aviso_diferido.cuando_libre(
                _frame(conectado=True),
                lambda: llamadas.append("llamada"))
        programa_args, _ = programar.call_args
        self.assertEqual(30000, programa_args[0])
        self.assertEqual([], llamadas)

    def test_reprogramado_vuelve_a_intentar_hasta_abrir(self):
        llamadas = []
        pendientes = []
        frame = _frame()
        with mock.patch.object(
                aviso_diferido, "esta_ocupado",
                side_effect=[True, False]), \
                mock.patch.object(
                    aviso_diferido.wx, "CallLater",
                    side_effect=lambda ms, fn: pendientes.append((ms, fn))):
            aviso_diferido.cuando_libre(
                frame, llamadas.append, "abierta")
            self.assertEqual([], llamadas)
            self.assertEqual(1, len(pendientes))
            pendientes[0][1]()
        self.assertEqual(["abierta"], llamadas)

    def test_libre_llama_una_vez(self):
        llamadas = []
        with mock.patch.object(
                aviso_diferido, "esta_ocupado", return_value=False), \
                mock.patch.object(aviso_diferido.wx, "CallLater") as programar:
            aviso_diferido.cuando_libre(_frame(), llamadas.append, "x")
        programar.assert_not_called()
        self.assertEqual(["x"], llamadas)

    def test_frame_destruido_no_hace_nada(self):
        for muerto in (None,
                       SimpleNamespace(_conectado=False,
                                       _supervisar_transmision=lambda a: False,
                                       _alive=False)):
            with self.subTest(muerto=muerto):
                funcion = mock.Mock()
                with mock.patch.object(
                        aviso_diferido.wx, "CallLater") as programar:
                    aviso_diferido.cuando_libre(muerto, funcion)
                funcion.assert_not_called()
                programar.assert_not_called()

    def test_excepcion_de_la_funcion_no_sube(self):
        def rota():
            raise RuntimeError("boom")
        with mock.patch.object(
                aviso_diferido, "esta_ocupado", return_value=False), \
                mock.patch.object(aviso_diferido, "logger"):
            aviso_diferido.cuando_libre(_frame(), rota)


if __name__ == "__main__":
    unittest.main()
