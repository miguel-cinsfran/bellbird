"""Pruebas de la ventana de actualización de yt-dlp.

La lógica corre sin ventanas con una ventana falsa; la pseudotraducción de
la ventana real la corre el advisor en la otra PC. El texto final lo arma
`ytchat/downloads/ytdlp_bin.py`: pasa tal cual, sin marcar.
"""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir
from ytchat.ui import gui_actualizar_ytdlp as ventana_ytdlp

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class VentanaFalsa:
    """Doble de DialogoActualizacion: no abre nada en pantalla."""

    def __init__(self):
        self._cerrado = False
        self._cancelado = mock.Mock()
        self._cancelado.is_set.return_value = False
        self.mostrada = False
        self.elevada = False
        self.estados = []
        self.progresos = []
        self.valores = []
        self.txt_estado = mock.Mock()
        self.txt_estado.SetValue.side_effect = self.valores.append
        self.btn_cerrar = mock.Mock()

    @property
    def cerrado(self):
        return self._cerrado

    @property
    def cancelado(self):
        return self._cancelado

    def Show(self):
        self.mostrada = True

    def Raise(self):
        self.elevada = True

    def estado(self, texto):
        self.estados.append(texto)

    def progreso(self, porcentaje):
        self.progresos.append(porcentaje)

    def en_hilo_principal(self, funcion, *args):
        funcion(*args)

    def cerrar(self):
        self._cerrado = True
        self._cancelado.is_set.return_value = True


def _hilo_inmediato(objetivo, _nombre):
    hilo = mock.Mock()
    hilo.start.side_effect = lambda: objetivo()
    return hilo


class TestVentanaYtdlp(unittest.TestCase):
    """La lógica, sin ventanas: corre acá."""

    def _abrir(self, actualizar):
        from ytchat.downloads import ytdlp_bin
        ventanas = []

        def fabrica(padre, titulo):
            ventana = VentanaFalsa()
            ventana.titulo = titulo
            ventanas.append(ventana)
            return ventana

        frame = mock.Mock()
        frame._ventana_actualizar_ytdlp = None
        with mock.patch("ytchat.ui.gui_actualizacion.DialogoActualizacion",
                        side_effect=fabrica), \
                mock.patch.object(ytdlp_bin, "actualizar_ytdlp",
                                  side_effect=actualizar), \
                mock.patch("ytchat.core.diagnostico.crear_hilo",
                           side_effect=_hilo_inmediato):
            ventana_ytdlp.abrir_ventana_actualizacion(frame)
        return frame, ventanas[0]

    def test_abre_busca_y_pasa_el_texto_ajeno(self):
        def actualizar(avisar=None, progreso=None, cancelar=None):
            return ("ya_al_dia", "1.0", "1.0")

        with con_pseudo(), \
                mock.patch("ytchat.ui.gui_actualizacion.anunciar"):
            _frame, ventana = self._abrir(actualizar)
        self.assertTrue(ventana.mostrada)
        self.assertEqual(ventana.titulo, "[¡Actualizar yt-dlp!]")
        self.assertEqual(ventana.estados[0],
                         "[¡Buscando la última versión de yt-dlp.!]")
        self.assertIn("Ya tienes yt-dlp al día, versión 1.0.",
                      ventana.estados)
        self.assertEqual(ventana.progresos, [100])

    def test_aviso_y_progreso_propios_salen_marcados(self):
        def actualizar(avisar=None, progreso=None, cancelar=None):
            avisar("2.0")
            progreso(40, 0, 0)
            return ("ya_al_dia", "1.0", "1.0")

        with con_pseudo(), \
                mock.patch("ytchat.ui.gui_actualizacion.anunciar"):
            _frame, ventana = self._abrir(actualizar)
        self.assertIn("[¡Hay una versión nueva de yt-dlp, la 2.0. "
                      "Descargando.!]", ventana.estados)
        self.assertIn(40, ventana.progresos)
        self.assertIn("[¡Descargando yt-dlp: 40 por ciento!]",
                      ventana.valores)

    def test_segunda_apertura_enfoca_la_ya_abierta(self):
        def actualizar(avisar=None, progreso=None, cancelar=None):
            return ("ya_al_dia", "1.0", "1.0")

        frame, ventana = self._abrir(actualizar)
        self.assertFalse(ventana.elevada)
        with mock.patch("ytchat.ui.gui_actualizacion.DialogoActualizacion",
                        side_effect=AssertionError("no debe crear otra")), \
                mock.patch("ytchat.core.diagnostico.crear_hilo",
                           side_effect=_hilo_inmediato):
            ventana_ytdlp.abrir_ventana_actualizacion(frame)
        self.assertTrue(ventana.elevada)
        ventana.btn_cerrar.SetFocus.assert_called()

    def test_ventana_cerrada_permite_abrir_otra(self):
        def actualizar(avisar=None, progreso=None, cancelar=None):
            return ("ya_al_dia", "1.0", "1.0")

        frame, ventana = self._abrir(actualizar)
        ventana.cerrar()
        frame2, ventana2 = self._abrir(actualizar)
        self.assertIsNot(ventana, ventana2)
        self.assertTrue(ventana2.mostrada)


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoVentanaYtdlp(unittest.TestCase):
    """Pseudotraducción de la ventana real: la corre el advisor."""

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        from ytchat.downloads import ytdlp_bin

        def actualizar(avisar=None, progreso=None, cancelar=None):
            avisar("2.0")
            progreso(40, 0, 0)
            return ("ya_al_dia", "1.0", "1.0")

        frame = wx.Frame(None)
        self.addCleanup(destruir, frame)
        with con_pseudo(), \
                mock.patch.object(ytdlp_bin, "actualizar_ytdlp",
                                  side_effect=actualizar), \
                mock.patch("ytchat.core.diagnostico.crear_hilo",
                           side_effect=_hilo_inmediato), \
                mock.patch("ytchat.ui.gui_actualizacion.anunciar"):
            ventana_ytdlp.abrir_ventana_actualizacion(frame)
            ventana = frame._ventana_actualizar_ytdlp
            self.addCleanup(destruir, ventana)
            sin_marcar = textos_sin_marcar(ventana)
        self.assertEqual([], sin_marcar)


if __name__ == "__main__":
    unittest.main()
