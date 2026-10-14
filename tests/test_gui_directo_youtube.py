"""Pruebas del diálogo de datos del directo de YouTube.

TestResultadoDirecto no crea ventanas y se corre aquí. TestDialogoDirectoVentana
crea un wx.Dialog de verdad: NO correr en esta máquina (abre ventanas); las
corre el dueño.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.ui import gui_directo_youtube as directo
from ytchat.youtube.emision import (
    ETIQUETAS_PRIVACIDAD,
    PRIVACIDADES,
    EmisionError,
    titulo_por_defecto,
)


class TestResultadoDirecto(unittest.TestCase):
    # Lógica pura del diálogo, sin ventanas.

    def test_titulo_vacio_falla_como_cuerpo_emision(self):
        with self.assertRaises(EmisionError) as contexto:
            directo.resultado_directo("   ", "algo", "unlisted")
        self.assertEqual(str(contexto.exception),
                         "Falta el título del directo.")

    def test_recorta_titulo_a_cien(self):
        datos = directo.resultado_directo("x" * 150, "", "public")
        self.assertEqual(len(datos["titulo"]), 100)

    def test_privacidad_invalida_cae_a_no_listado(self):
        datos = directo.resultado_directo("Hola", "", "solo-yo")
        self.assertEqual(datos["privacidad"], "unlisted")

    def test_devuelve_los_tres_valores(self):
        datos = directo.resultado_directo("Hola", "línea1\nlínea2", "private")
        self.assertEqual(datos, {"titulo": "Hola",
                                 "descripcion": "línea1\nlínea2",
                                 "privacidad": "private"})


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoDirectoVentana(unittest.TestCase):
    # Con ventana: las corre el dueño. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, **kwargs):
        dialogo = directo.DialogoDirectoYoutube(None, **kwargs)
        self.addCleanup(dialogo.Destroy)
        return dialogo

    def test_titulo_vacio_usa_el_por_defecto_seleccionado(self):
        from datetime import datetime
        dialogo = self._dialogo(titulo="")
        self.assertEqual(dialogo.txt_titulo.GetValue(),
                         titulo_por_defecto(datetime.now()))
        inicio, fin = dialogo.txt_titulo.GetSelection()
        self.assertEqual((inicio, fin),
                         (0, len(dialogo.txt_titulo.GetValue())))

    def test_titulo_limitado_a_100_caracteres(self):
        with mock.patch.object(wx.TextCtrl, "SetMaxLength") as maximo:
            dialogo = self._dialogo(titulo="Hola")
        maximo.assert_called_once_with(100)

    def test_nombres_accesibles_y_rotulos(self):
        dialogo = self._dialogo(titulo="Hola", descripcion="d",
                                privacidad="public")
        self.assertEqual(dialogo.txt_titulo.GetName(), "Título del directo")
        self.assertEqual(dialogo.txt_descripcion.GetName(),
                         "Descripción del directo")
        self.assertEqual(dialogo.cho_privacidad.GetName(), "Privacidad")
        textos = [h.GetLabel() for h in dialogo.GetChildren()
                  if isinstance(h, wx.StaticText)]
        self.assertIn("Título:", textos)
        self.assertIn("Descripción, opcional:", textos)
        self.assertIn("Privacidad:", textos)

    def test_orden_de_tab_y_privacidad(self):
        dialogo = self._dialogo(titulo="Hola", privacidad="private")
        orden = [h.GetName() for h in dialogo.GetChildren()
                 if h.GetName() in ("Título del directo",
                                    "Descripción del directo", "Privacidad")]
        self.assertEqual(orden, ["Título del directo",
                                 "Descripción del directo", "Privacidad"])
        self.assertEqual(
            [dialogo.cho_privacidad.GetString(i)
             for i in range(dialogo.cho_privacidad.GetCount())],
            [ETIQUETAS_PRIVACIDAD[p] for p in PRIVACIDADES])
        self.assertEqual(dialogo.cho_privacidad.GetSelection(),
                         PRIVACIDADES.index("private"))
        estilo = dialogo.txt_descripcion.GetWindowStyle()
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertFalse(estilo & wx.TE_PROCESS_TAB)

    def test_botones_y_foco(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertEqual(dialogo.btn_crear.GetLabel(), "&Crear directo")
        self.assertEqual(dialogo.btn_crear.GetId(), wx.ID_OK)
        self.assertEqual(dialogo.btn_cancelar.GetLabel(), "C&ancelar")
        self.assertEqual(dialogo.btn_cancelar.GetId(), wx.ID_CANCEL)
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_crear_con_titulo_vacio_anuncia_y_sigue_abierto(self):
        dialogo = self._dialogo(titulo="Hola")
        dialogo.txt_titulo.SetValue("   ")
        with mock.patch.object(directo, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_crear(mock.Mock())
        anunciar.assert_called_once_with("Falta el título del directo.")
        fin.assert_not_called()
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_pedir_datos_devuelve_dict_y_none(self):
        dialogo = self._dialogo(titulo="Hola")
        with mock.patch.object(directo, "DialogoDirectoYoutube",
                               return_value=dialogo), \
                mock.patch.object(dialogo, "Destroy"):
            dialogo._datos = {"titulo": "Hola", "descripcion": "",
                              "privacidad": "unlisted"}
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_OK):
                self.assertEqual(
                    directo.pedir_datos_directo(None, "Hola", "", "unlisted"),
                    {"titulo": "Hola", "descripcion": "",
                     "privacidad": "unlisted"})
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_CANCEL):
                self.assertIsNone(
                    directo.pedir_datos_directo(None, "Hola", "", "unlisted"))


if __name__ == "__main__":
    unittest.main()
