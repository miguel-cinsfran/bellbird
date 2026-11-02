"""Cuadro del estado de la sesión en una lista, para recorrer con flechas."""

import unittest
from unittest import mock

from tests.ventanas_prueba import destruir

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

try:
    from bellbird.ui import dialogo_estado
    _HAY_DIALOGO = True
except ImportError:
    dialogo_estado = None  # type: ignore
    _HAY_DIALOGO = False


@unittest.skipUnless(_HAY_WX and _HAY_DIALOGO, "wxPython no está instalado")
class TestDialogoEstado(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()
        self.dialogo = dialogo_estado.DialogoEstado(None, ["Uno", "Dos"])
        self.addCleanup(destruir, self.dialogo)

    def test_titulo_lista_y_nombres_exactos(self):
        self.assertEqual(self.dialogo.GetTitle(), "Estado de la sesión")
        self.assertEqual(
            [self.dialogo.lista.GetString(i)
             for i in range(self.dialogo.lista.GetCount())],
            ["Uno", "Dos"])
        self.assertEqual(self.dialogo.lista.GetName(), "Estado de la sesión")
        self.assertEqual(self.dialogo.btn_cerrar.GetName(), "Cerrar")

    def test_foco_en_la_lista_y_orden_de_tab_lista_cerrar(self):
        self.dialogo.Show()
        try:
            self.assertIs(wx.Window.FindFocus(), self.dialogo.lista)
        finally:
            self.dialogo.Hide()
        orden = [c for c in self.dialogo.panel.GetChildren()
                 if c in (self.dialogo.lista, self.dialogo.btn_cerrar)]
        self.assertEqual(orden, [self.dialogo.lista,
                                 self.dialogo.btn_cerrar])
        self.assertEqual(self.dialogo.GetEscapeId(), wx.ID_CANCEL)
        self.assertEqual(self.dialogo.btn_cerrar.GetId(), wx.ID_CANCEL)

    def test_sin_lineas_queda_un_solo_texto(self):
        dialogo = dialogo_estado.DialogoEstado(None, [])
        self.addCleanup(destruir, dialogo)
        self.assertEqual(dialogo.lista.GetCount(), 1)
        self.assertEqual(dialogo.lista.GetString(0),
                         "Sin información de estado.")

    def test_las_lineas_son_una_foto_del_momento(self):
        lineas = ["Uno"]
        dialogo = dialogo_estado.DialogoEstado(None, lineas)
        self.addCleanup(destruir, dialogo)
        lineas.append("Dos")
        self.assertEqual(dialogo.lista.GetCount(), 1)
        self.assertEqual(dialogo.lista.GetString(0), "Uno")


@unittest.skipUnless(_HAY_WX and _HAY_DIALOGO, "wxPython no está instalado")
class TestAbrirEstado(unittest.TestCase):

    def setUp(self):
        self.app = wx.App() if not wx.App.Get() else wx.App.Get()

    def test_cierra_y_devuelve_el_foco_anterior(self):
        padre = mock.Mock()
        anterior = mock.Mock()
        with mock.patch.object(dialogo_estado, "_ventana_con_foco",
                               return_value=anterior), \
                mock.patch.object(dialogo_estado, "DialogoEstado") as clase:
            dialogo_estado.abrir_estado(padre, ["Uno"])
        clase.return_value.ShowModal.assert_called_once_with()
        clase.return_value.Destroy.assert_called_once_with()
        anterior.SetFocus.assert_called_once_with()
        padre.SetFocus.assert_not_called()

    def test_sin_foco_anterior_enfoca_la_ventana_principal(self):
        padre = mock.Mock()
        with mock.patch.object(dialogo_estado, "_ventana_con_foco",
                               return_value=None), \
                mock.patch.object(dialogo_estado, "DialogoEstado"):
            dialogo_estado.abrir_estado(padre, ["Uno"])
        padre.SetFocus.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
