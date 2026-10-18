"""Pruebas del motor compartido de libVLC (`ytchat.player.motor_vlc`)."""

import sys
import threading
import time
import types
import unittest
from types import SimpleNamespace
from unittest import mock

from ytchat.player import motor_vlc


_MONOTONIC_REAL = time.monotonic


class RelojMonotonic:
    def __init__(self, primero, despues):
        self._llamadas = 0
        self._primero = primero
        self._despues = despues
        self._hilo = threading.get_ident()
        self._real = _MONOTONIC_REAL

    def __call__(self):
        if threading.get_ident() != self._hilo:
            return self._real()
        self._llamadas += 1
        return self._primero if self._llamadas == 1 else self._despues


class _BaseMotorVlc(unittest.TestCase):
    """Aísla el estado de módulo: cada prueba arranca sin binding ni instancia."""

    def setUp(self):
        self._guardado = (motor_vlc._modulo, motor_vlc._inst, motor_vlc._preparado)
        motor_vlc._modulo = None
        motor_vlc._inst = None
        motor_vlc._preparado = False

    def tearDown(self):
        motor_vlc._modulo, motor_vlc._inst, motor_vlc._preparado = self._guardado


class TestInstancia(_BaseMotorVlc):

    def test_crea_una_vez_y_usa_args(self):
        creada = object()
        fabricar = mock.Mock(return_value=creada)
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=fabricar)):
            primera = motor_vlc.instancia()
            segunda = motor_vlc.instancia()
        self.assertIs(primera, creada)
        self.assertIs(segunda, creada)
        fabricar.assert_called_once_with(*motor_vlc.ARGS)

    def test_varios_hilos_comparten_una_sola_creacion(self):
        creada = object()
        entro = threading.Event()
        liberar = threading.Event()

        def fabricar(*_):
            entro.set()
            liberar.wait(5)
            return creada

        fabricar_mock = mock.Mock(side_effect=fabricar)
        resultados = []
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=fabricar_mock)):
            hilos = [
                threading.Thread(target=lambda: resultados.append(motor_vlc.instancia()))
                for _ in range(4)
            ]
            for hilo in hilos:
                hilo.start()
            self.assertTrue(entro.wait(5), "Instance no llegó a llamarse")
            liberar.set()
            for hilo in hilos:
                hilo.join(5)
        self.assertEqual(fabricar_mock.call_count, 1)
        self.assertEqual(len(resultados), 4)
        self.assertTrue(all(resultado is creada for resultado in resultados))

    def test_no_recuerda_el_fallo_al_lanzar(self):
        falla = mock.Mock(side_effect=RuntimeError("boom"))
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=falla)):
            self.assertIsNone(motor_vlc.instancia())
        creada = object()
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=mock.Mock(return_value=creada))):
            self.assertIs(motor_vlc.instancia(), creada)

    def test_no_recuerda_el_none(self):
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=mock.Mock(return_value=None))):
            self.assertIsNone(motor_vlc.instancia())
        creada = object()
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=mock.Mock(return_value=creada))):
            self.assertIs(motor_vlc.instancia(), creada)

    def test_sin_cargar_devuelve_none_sin_instanciar(self):
        fabricar = mock.Mock()
        with mock.patch.object(motor_vlc, "cargar", return_value=False), \
                mock.patch.object(motor_vlc, "_modulo",
                                  SimpleNamespace(Instance=fabricar)):
            self.assertIsNone(motor_vlc.instancia())
        fabricar.assert_not_called()


class TestModulo(_BaseMotorVlc):

    def test_none_antes_de_cargar_y_el_binding_despues(self):
        self.assertIsNone(motor_vlc.modulo())
        binding = types.SimpleNamespace(nombre="vlc")
        with mock.patch.object(motor_vlc, "preparar"), \
                mock.patch.dict(sys.modules, {"vlc": binding}):
            self.assertTrue(motor_vlc.cargar())
        self.assertIs(motor_vlc.modulo(), binding)


class TestTramos(_BaseMotorVlc):

    def test_preparar_dll_registra_su_tramo(self):
        reloj = RelojMonotonic(1.0, 1.25)
        with mock.patch.object(motor_vlc, "carpeta_empaquetada", return_value=None), \
                mock.patch.object(motor_vlc.time, "monotonic", side_effect=reloj), \
                mock.patch.object(motor_vlc.diagnostico.logger, "info") as registrar:
            motor_vlc.preparar()
        registrar.assert_any_call(
            "VLC_PRECALENTAMIENTO tramo=%s ms=%.0f", "preparar_dll", 250)
        self.assertEqual(sum(llamada.args[1] == "preparar_dll"
                             for llamada in registrar.call_args_list), 1)

    def test_importar_modulo_registra_su_tramo(self):
        reloj = RelojMonotonic(2.0, 2.5)
        with mock.patch.object(motor_vlc, "preparar"), \
                mock.patch.object(motor_vlc.time, "monotonic", side_effect=reloj), \
                mock.patch.object(motor_vlc.diagnostico.logger, "info") as registrar, \
                mock.patch.dict(sys.modules, {"vlc": types.SimpleNamespace()}):
            self.assertTrue(motor_vlc.cargar())
        registrar.assert_any_call(
            "VLC_PRECALENTAMIENTO tramo=%s ms=%.0f", "importar_modulo", 500)
        self.assertEqual(sum(llamada.args[1] == "importar_modulo"
                             for llamada in registrar.call_args_list), 1)

    def test_crear_instancia_registra_su_tramo(self):
        instancia = object()
        reloj = RelojMonotonic(3.0, 3.75)
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "_modulo",
                                  types.SimpleNamespace(Instance=lambda *_: instancia)), \
                mock.patch.object(motor_vlc.time, "monotonic", side_effect=reloj), \
                mock.patch.object(motor_vlc.diagnostico.logger, "info") as registrar:
            self.assertIs(motor_vlc.instancia(), instancia)
        registrar.assert_any_call(
            "VLC_PRECALENTAMIENTO tramo=%s ms=%.0f", "crear_instancia", 750)
        self.assertEqual(sum(llamada.args[1] == "crear_instancia"
                             for llamada in registrar.call_args_list), 1)


class TestCableado(unittest.TestCase):

    def test_panel_toma_la_instancia_compartida(self):
        from ytchat.player import reproductor
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._inst = None
        panel._listo = True
        compartida = object()
        with mock.patch.object(motor_vlc, "instancia", return_value=compartida) as pedir:
            self.assertTrue(panel._asegurar_instancia())
        pedir.assert_called_once_with()
        self.assertIs(panel._inst, compartida)

    def test_panel_sin_reproductor_no_pide_la_instancia(self):
        from ytchat.player import reproductor
        panel = reproductor.ReproductorPanel.__new__(reproductor.ReproductorPanel)
        panel._inst = None
        panel._listo = False
        with mock.patch.object(motor_vlc, "instancia") as pedir:
            self.assertFalse(panel._asegurar_instancia())
        pedir.assert_not_called()

    def test_autocomprobacion_pide_la_instancia_compartida(self):
        from ytchat.core import autocomprobacion
        compartida = object()
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "instancia", return_value=compartida) as pedir:
            autocomprobacion._vlc()
        pedir.assert_called_once_with()

    def test_autocomprobacion_avisa_si_no_carga(self):
        from ytchat.core import autocomprobacion
        with mock.patch.object(motor_vlc, "cargar", return_value=False):
            with self.assertRaises(RuntimeError) as error:
                autocomprobacion._vlc()
        self.assertIn("no se pudo cargar libVLC", str(error.exception))

    def test_autocomprobacion_avisa_si_la_instancia_sale_vacia(self):
        from ytchat.core import autocomprobacion
        with mock.patch.object(motor_vlc, "cargar", return_value=True), \
                mock.patch.object(motor_vlc, "instancia", return_value=None):
            with self.assertRaises(RuntimeError) as error:
                autocomprobacion._vlc()
        self.assertIn("la instancia de VLC salió vacía", str(error.exception))


class TestReal(_BaseMotorVlc):

    def test_instancia_real_y_media_player(self):
        try:
            import vlc  # noqa: F401
        except Exception as exc:
            self.skipTest(f"python-vlc no está disponible: {exc}")
        if not motor_vlc.cargar():
            self.skipTest("no se pudo cargar libVLC en esta máquina")
        instancia = motor_vlc.instancia()
        self.assertIsNotNone(instancia)
        self.assertIs(motor_vlc.instancia(), instancia)
        player = instancia.media_player_new()
        self.assertIsNotNone(player)
        player.release()


if __name__ == "__main__":
    unittest.main()
