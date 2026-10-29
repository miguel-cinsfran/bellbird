"""Cableado de «Abrir carpeta de registros» del menú Ayuda.

Sin ventanas: se llama a `abrir_carpeta_registros` con un frame de mentira
y dobles de `os.startfile` y `wx.MessageBox`. No se corre con wx.App.
"""

import unittest
from pathlib import Path
from unittest import mock

from ytchat.ui import gui_menu


class TestAbrirCarpetaRegistros(unittest.TestCase):

    def test_abre_la_carpeta_de_datos(self):
        frame = mock.Mock()
        with mock.patch.object(gui_menu.os, "startfile") as iniciar, \
             mock.patch.object(gui_menu.paths, "carpeta_datos",
                               return_value=Path("X")):
            gui_menu.abrir_carpeta_registros(frame)
        iniciar.assert_called_once_with(str(Path("X")))

    def test_si_falla_muestra_el_mensaje_con_titulo(self):
        frame = mock.Mock()
        with mock.patch.object(gui_menu.os, "startfile",
                               side_effect=OSError("falla")), \
             mock.patch.object(gui_menu.paths, "carpeta_datos",
                               return_value=Path("X")), \
             mock.patch.object(gui_menu.wx, "MessageBox") as mensaje:
            gui_menu.abrir_carpeta_registros(frame)
        mensaje.assert_called_once_with(
            "No se pudo abrir la carpeta de registros:\n\nfalla",
            "Carpeta de registros",
            gui_menu.wx.OK | gui_menu.wx.ICON_ERROR, frame)


if __name__ == "__main__":
    unittest.main()
