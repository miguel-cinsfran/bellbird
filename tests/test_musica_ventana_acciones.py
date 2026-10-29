"""Pruebas de los diálogos de listas de la ventana de música, sin abrirlos."""

import unittest
from unittest import mock

import wx

from tests.pseudo_prueba import con_pseudo
from bellbird.core.idioma import _
from bellbird.ui import musica_ventana_acciones as acciones


class DobleEntradaTexto:
    """TextEntryDialog falso: captura el mensaje y el título, sin ventana."""

    ultimo = None

    def __init__(self, parent, mensaje, titulo, valor=""):
        self.mensaje = mensaje
        self.titulo = titulo
        self.valor = valor
        DobleEntradaTexto.ultimo = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ShowModal(self):
        return wx.ID_OK

    def GetValue(self):
        return "Mi lista"


class DobleEntradaCancelada(DobleEntradaTexto):
    """TextEntryDialog falso que vuelve como si se hubiera cancelado."""

    def ShowModal(self):
        return wx.ID_CANCEL


class DobleConfirmar:
    """MessageDialog falso: captura el mensaje y el título, sin ventana."""

    respuesta = wx.ID_YES
    ultimo = None

    def __init__(self, parent, mensaje, titulo, estilo):
        self.mensaje = mensaje
        self.titulo = titulo
        self.estilo = estilo
        self.destruida = False
        DobleConfirmar.ultimo = self

    def FindWindow(self, ident):
        return None

    def ShowModal(self):
        return self.respuesta

    def Destroy(self):
        self.destruida = True


class DobleCarpeta:
    """DirDialog falso: captura el mensaje, sin ventana."""

    dialogo = None

    def __init__(self, parent, mensaje, defaultPath=""):
        self.mensaje = mensaje
        self.ruta_defecto = defaultPath
        DobleCarpeta.dialogo = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ShowModal(self):
        return wx.ID_OK

    def GetPath(self):
        return "C:/musica"


class DobleControl:
    """Control falso: solo guarda la carpeta que se le pide."""

    def __init__(self):
        self.cambiada = None

    def _carpeta(self):
        return "C:/vieja"

    def cambiar_carpeta(self, ruta):
        self.cambiada = ruta


class DobleVentana:
    """Ventana falsa: solo arma lo que `_cambiar_carpeta` necesita."""

    def __init__(self):
        self._control = DobleControl()

    def _reload_colecciones(self):
        return None

    def _cargar_fuente(self):
        return None


class TestConstantesAcciones(unittest.TestCase):
    """Las constantes de los diálogos salen marcadas donde se usan."""

    def test_constantes_salen_marcadas(self):
        nombres = ("TITULO", "TITULO_NUEVA", "TITULO_RENOMBRAR",
                   "TEXTO_NOMBRE")
        with con_pseudo():
            for nombre in nombres:
                with self.subTest(nombre=nombre):
                    self.assertTrue(
                        _(getattr(acciones, nombre)).startswith("[¡"),
                        nombre)


class TestDialogosAcciones(unittest.TestCase):
    """Los diálogos muestran el mensaje y el título marcados, sin abrirse."""

    def test_pedir_nombre_muestra_mensaje_y_titulo_marcados(self):
        with mock.patch.object(acciones.wx, "TextEntryDialog",
                               DobleEntradaTexto):
            with con_pseudo():
                nombre = acciones._pedir_nombre(
                    None, _(acciones.TITULO_NUEVA), "Vieja")
        dialogo = DobleEntradaTexto.ultimo
        self.assertEqual(nombre, "Mi lista")
        self.assertTrue(dialogo.mensaje.startswith("[¡"), dialogo.mensaje)
        self.assertTrue(dialogo.titulo.startswith("[¡"), dialogo.titulo)

    def test_pedir_nombre_cancelado_devuelve_none(self):
        with mock.patch.object(acciones.wx, "TextEntryDialog",
                               DobleEntradaCancelada):
            with con_pseudo():
                self.assertIsNone(
                    acciones._pedir_nombre(None, _(acciones.TITULO_NUEVA)))

    def test_confirmar_borrar_muestra_pregunta_y_titulo_marcados(self):
        DobleConfirmar.respuesta = wx.ID_YES
        with mock.patch.object(acciones.wx, "MessageDialog",
                               DobleConfirmar):
            with con_pseudo():
                self.assertTrue(
                    acciones._confirmar_borrar(None, "Rock"))
        dialogo = DobleConfirmar.ultimo
        self.assertTrue(dialogo.mensaje.startswith("[¡"), dialogo.mensaje)
        self.assertIn("Rock", dialogo.mensaje)
        self.assertTrue(dialogo.titulo.startswith("[¡"), dialogo.titulo)
        self.assertTrue(dialogo.destruida)

    def test_confirmar_borrar_con_no_devuelve_falso(self):
        DobleConfirmar.respuesta = wx.ID_NO
        self.addCleanup(setattr, DobleConfirmar, "respuesta", wx.ID_YES)
        with mock.patch.object(acciones.wx, "MessageDialog",
                               DobleConfirmar):
            with con_pseudo():
                self.assertFalse(
                    acciones._confirmar_borrar(None, "Rock"))

    def test_cambiar_carpeta_muestra_mensaje_marcado_y_cambia(self):
        ventana = DobleVentana()
        with mock.patch.object(acciones.wx, "DirDialog", DobleCarpeta):
            with con_pseudo():
                acciones.AccionesVentanaMusica._cambiar_carpeta(ventana)
        dialogo = DobleCarpeta.dialogo
        self.assertTrue(dialogo.mensaje.startswith("[¡"), dialogo.mensaje)
        self.assertEqual(ventana._control.cambiada, "C:/musica")


if __name__ == "__main__":
    unittest.main()
