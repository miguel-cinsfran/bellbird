"""Pegamento wx de los avisos de progreso de descargas.

Un temporizador de nivel de módulo lee la lista del gestor y anuncia lo que
corresponde aunque el Administrador de descargas esté cerrado.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import wx

from bellbird.ui import aviso_progreso


def _item(ident, progreso, nombre=""):
    url = f"https://ejemplo/{ident}"
    return SimpleNamespace(id=ident, progreso=progreso, estado="descargando",
                           procesando=False, nombre=nombre or url, url=url)


class PruebasAvisoProgreso(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        aviso_progreso._temporizador = None
        aviso_progreso._anunciador = None
        self.addCleanup(self._parar)

    def _parar(self):
        if aviso_progreso._temporizador is not None:
            aviso_progreso._temporizador.Stop()
        aviso_progreso._temporizador = None
        aviso_progreso._anunciador = None

    def _gestor(self, lista):
        doble = mock.Mock()
        doble.lista.return_value = lista
        parche = mock.patch.object(aviso_progreso, "gestor", return_value=doble)
        parche.start()
        self.addCleanup(parche.stop)
        return doble

    def _opcion(self, activa):
        parche = mock.patch.object(
            aviso_progreso.cfg, "obtener_opciones_descarga",
            return_value={"anunciar_progreso": activa})
        parche.start()
        self.addCleanup(parche.stop)

    def test_con_la_opcion_activa_anuncia_y_suena_el_avance(self):
        self._gestor([_item("a", 0.0)])
        self._opcion(True)
        aviso_progreso.vigilar()
        with mock.patch.object(aviso_progreso, "anunciar") as anunciar, \
                mock.patch.object(aviso_progreso._snd, "reproducir") as sonar, \
                mock.patch.object(aviso_progreso.time, "monotonic",
                                  side_effect=[0.0, 1.0]):
            aviso_progreso._latido()
            aviso_progreso.gestor().lista.return_value = [_item("a", 10.0)]
            aviso_progreso._latido()
        anunciar.assert_called_once_with("10 por ciento")
        sonar.assert_called_once_with("descarga_avance")

    def test_con_la_opcion_apagada_no_anuncia_ni_suena(self):
        self._gestor([_item("a", 10.0)])
        self._opcion(False)
        aviso_progreso.vigilar()
        with mock.patch.object(aviso_progreso, "anunciar") as anunciar, \
                mock.patch.object(aviso_progreso._snd, "reproducir") as sonar:
            aviso_progreso._latido()
        anunciar.assert_not_called()
        sonar.assert_not_called()
        self.assertIsNone(aviso_progreso._anunciador)

    def test_sin_descargas_en_curso_no_lee_la_configuracion(self):
        self._gestor([SimpleNamespace(id="a", estado="completado",
                                      progreso=100.0)])
        with mock.patch.object(
                aviso_progreso.cfg, "obtener_opciones_descarga") as obtener:
            aviso_progreso._latido()
        obtener.assert_not_called()

    def test_dos_avisos_en_la_misma_vuelta_dan_un_anuncio_y_un_sonido(self):
        self._gestor([_item("a", 0.0, nombre="Uno"),
                      _item("b", 0.0, nombre="Dos")])
        self._opcion(True)
        aviso_progreso.vigilar()
        with mock.patch.object(aviso_progreso, "anunciar") as anunciar, \
                mock.patch.object(aviso_progreso._snd, "reproducir") as sonar, \
                mock.patch.object(aviso_progreso.time, "monotonic",
                                  side_effect=[0.0, 1.0]):
            aviso_progreso._latido()
            aviso_progreso.gestor().lista.return_value = [
                _item("a", 10.0, nombre="Uno"),
                _item("b", 10.0, nombre="Dos")]
            aviso_progreso._latido()
        anunciar.assert_called_once_with(
            "Uno: 10 por ciento. Dos: 10 por ciento")
        sonar.assert_called_once_with("descarga_avance")

    def test_vigilar_dos_veces_deja_un_solo_temporizador(self):
        self._opcion(False)
        aviso_progreso.vigilar()
        primero = aviso_progreso._temporizador
        aviso_progreso.vigilar()
        self.assertIs(aviso_progreso._temporizador, primero)
        self.assertTrue(primero.IsRunning())


if __name__ == "__main__":
    unittest.main()
