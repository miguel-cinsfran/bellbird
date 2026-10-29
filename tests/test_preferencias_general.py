"""Pseudotraducción de la página General de Preferencias.

Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
Comprueba que ningún texto visible de la página queda sin pasar por
gettext.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.core import config
from bellbird.core import idioma
from bellbird.ui import gui, gui_preferencias, preferencias_general
from bellbird.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir


class TestGeneralSinTextosSinEnvolver(unittest.TestCase):
    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pagina(self, dialogo):
        return next(dialogo.nb.GetPage(i)
                    for i in range(dialogo.nb.GetPageCount())
                    if dialogo.nb.GetPage(i).GetName() == "PagGeneral")

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(self._pagina(dialogo))

        # Los nombres de los idiomas van en su propio idioma y no se
        # traducen: la excepción sale de `NOMBRES_IDIOMA`, no va a mano.
        esperados = [nombre for _valor, nombre in idioma.idiomas_disponibles()
                     if nombre in idioma.NOMBRES_IDIOMA.values()]
        self.assertEqual(sorted(sin_marcar), sorted(esperados))


class _CuadroFalso:
    def __init__(self, *args, **kwargs):
        self.respuesta = gui.wx.ID_NO
        self.etiquetas = None
        self.escape = None
        self.destruido = False

    def SetYesNoLabels(self, si, no):
        self.etiquetas = (si, no)

    def SetEscapeId(self, identificador):
        self.escape = identificador

    def ShowModal(self):
        return self.respuesta

    def Destroy(self):
        self.destruido = True


class TestReinicioPorIdioma(unittest.TestCase):
    """Cuadro de reinicio y relanzado de la aplicación.

    Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
    """

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()

    def test_reiniciar_ahora_es_el_boton_de_fabrica(self):
        cuadro = _CuadroFalso()
        captados = {}

        def fabrica(*args, **kwargs):
            captados["args"] = args
            captados["kwargs"] = kwargs
            return cuadro

        with mock.patch.object(preferencias_general.wx, "MessageDialog",
                               side_effect=fabrica):
            preferencias_general.ofrecer_reinicio(None)
        estilo = (captados["args"][3] if len(captados["args"]) > 3
                  else captados["kwargs"].get("style", 0))
        self.assertTrue(estilo & gui.wx.YES_NO)
        self.assertFalse(estilo & gui.wx.NO_DEFAULT)

    def test_mas_tarde_no_programa_el_reinicio(self):
        cuadro = _CuadroFalso()
        with mock.patch.object(preferencias_general.wx, "MessageDialog",
                               return_value=cuadro), \
                mock.patch.object(preferencias_general.wx, "CallAfter") as llamar:
            self.assertFalse(preferencias_general.ofrecer_reinicio(None))
        llamar.assert_not_called()
        self.assertEqual(cuadro.etiquetas, ("&Reiniciar ahora", "&Más tarde"))
        self.assertEqual(cuadro.escape, gui.wx.ID_NO)
        self.assertTrue(cuadro.destruido)

    def test_reiniciar_ahora_programa_el_reinicio(self):
        cuadro = _CuadroFalso()
        cuadro.respuesta = gui.wx.ID_YES
        padre = object()
        with mock.patch.object(preferencias_general.wx, "MessageDialog",
                               return_value=cuadro), \
                mock.patch.object(preferencias_general.wx, "CallAfter") as llamar:
            self.assertTrue(preferencias_general.ofrecer_reinicio(padre))
        llamar.assert_called_once_with(preferencias_general._reiniciar, padre)

    def test_close_devuelve_falso_cuando_el_cierre_se_veta(self):
        marco = gui.wx.Frame(None)
        self.addCleanup(marco.Destroy)

        def vetar(evento):
            evento.Veto()

        marco.Bind(gui.wx.EVT_CLOSE, vetar)
        self.assertFalse(marco.Close())

    def test_reiniciar_lanza_y_cierra(self):
        padre = mock.Mock()
        padre.Close.return_value = True
        proceso = mock.Mock()
        orden = ["Bellbird.exe", "--esperar-pid", "9"]
        with mock.patch.object(preferencias_general.instancia, "orden_reabrir",
                               return_value=orden) as armar, \
                mock.patch.object(preferencias_general.subprocess, "Popen",
                                  return_value=proceso) as lanzar:
            preferencias_general._reiniciar(padre)
        armar.assert_called_once_with(os.getpid())
        lanzar.assert_called_once_with(
            orden,
            creationflags=getattr(preferencias_general.subprocess,
                                  "CREATE_NO_WINDOW", 0),
            close_fds=True)
        padre.Close.assert_called_once_with()
        proceso.terminate.assert_not_called()

    def test_cierre_vetado_termina_lo_lanzado(self):
        padre = mock.Mock()
        padre.Close.return_value = False
        proceso = mock.Mock()
        with mock.patch.object(preferencias_general.instancia, "orden_reabrir",
                               return_value=["Bellbird.exe"]), \
                mock.patch.object(preferencias_general.subprocess, "Popen",
                                  return_value=proceso):
            preferencias_general._reiniciar(padre)
        proceso.terminate.assert_called_once_with()


def _dialogo_falso(cambiar_idioma):
    class DialogoFalso:
        def __init__(self, parent, config):
            self._config = config
            self.avisos = []

        def ShowModal(self):
            if cambiar_idioma:
                self._config["idioma"] = "en"
            return gui.wx.ID_OK

        def hubo_cambios(self):
            return True

        def Destroy(self):
            pass

    return DialogoFalso


class TestCuadroSoloSiCambiaElIdioma(unittest.TestCase):
    """`abrir_preferencias` decide el cuadro comparando el idioma.

    Abre ventanas: la corre el advisor en la otra PC, no se corre acá.
    """

    def setUp(self):
        self.app = gui.wx.App(False) if not gui.wx.App.Get() else gui.wx.App.Get()

    def test_el_cuadro_aparece_solo_si_cambio_el_idioma(self):
        for cambiar, esperado in ((True, 1), (False, 0)):
            with self.subTest(cambiar=cambiar):
                with mock.patch.object(
                        gui_preferencias, "PreferenciasDialog",
                        _dialogo_falso(cambiar)), \
                        mock.patch.object(
                            gui_preferencias, "ofrecer_reinicio") as ofrecer:
                    gui_preferencias.abrir_preferencias(None, {"idioma": "es"})
                self.assertEqual(ofrecer.call_count, esperado)


if __name__ == "__main__":
    unittest.main()
