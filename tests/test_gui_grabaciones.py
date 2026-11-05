"""Pruebas de la lista de grabaciones como panel. Requieren entorno gráfico."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from bellbird.obs import grabaciones
from bellbird.ui import gui_grabaciones
from tests.ventanas_prueba import app_de_prueba, destruir


class Evento:
    def __init__(self, tecla, shift=False):
        self._tecla = tecla
        self._shift = shift
        self.saltado = False

    def GetKeyCode(self):
        return self._tecla

    def ShiftDown(self):
        return self._shift

    def Skip(self):
        self.saltado = True


class TestPanelGrabaciones(unittest.TestCase):

    def setUp(self):
        self.app = app_de_prueba()
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name)
        self.ruta = self.carpeta / "grabaciones.json"
        parche = mock.patch.object(grabaciones.paths, "grabaciones",
                                   return_value=self.ruta)
        parche.start()
        self.addCleanup(parche.stop)
        for parche in (
                mock.patch.object(gui_grabaciones, "anunciar"),
                mock.patch.object(gui_grabaciones.sound_player, "reproducir"),
                mock.patch.object(gui_grabaciones, "copiar_al_portapapeles")):
            parche.start()
            self.addCleanup(parche.stop)

    def _archivo(self, nombre, bytes_=16):
        ruta = self.carpeta / nombre
        ruta.write_bytes(b"x" * bytes_)
        return ruta

    def _panel(self):
        padre = wx.Frame(None)
        self.addCleanup(destruir, padre)
        panel = gui_grabaciones.PanelGrabaciones(padre)
        self.addCleanup(destruir, panel)
        return panel

    def test_nombres_accesibles_exactos(self):
        panel = self._panel()
        self.assertEqual(panel._lista.GetName(), "Grabaciones y clips")

    def test_orden_de_tab(self):
        panel = self._panel()
        self.assertEqual([panel._lista.GetName()], ["Grabaciones y clips"])

    def test_poblar_deja_la_primera_fila_seleccionada(self):
        grabaciones.anotar(self._archivo("primera.mp4"), ruta=self.ruta,
                           ahora=1000)
        grabaciones.anotar(self._archivo("segunda.mp4"), ruta=self.ruta,
                           ahora=2000)
        panel = self._panel()
        self.assertEqual(panel._lista.GetSelection(), 0)
        self.assertIn("segunda.mp4", panel._lista.GetString(0))

    def test_una_fila_de_clip_dice_clip(self):
        archivo = self._archivo("clip.mp4", 2 * 1024 * 1024)
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000, tipo="clip")
        panel = self._panel()
        fila = panel._lista.GetString(0)
        self.assertTrue(fila.startswith("Clip, clip.mp4, "))
        self.assertTrue(fila.endswith("2 MB"))

    def test_sin_grabaciones_la_fila_y_las_acciones_lo_dicen(self):
        panel = self._panel()
        self.assertEqual(panel._lista.GetCount(), 1)
        self.assertEqual(panel._lista.GetString(0),
                         "No hay grabaciones ni clips guardados.")
        panel._abrir()
        gui_grabaciones.anunciar.assert_called_with(
            "No hay grabaciones ni clips guardados.")

    def test_supr_saca_la_fila_y_deja_el_archivo_en_el_disco(self):
        primero = self._archivo("primero.mp4")
        segundo = self._archivo("segundo.mp4")
        grabaciones.anotar(primero, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(segundo, ruta=self.ruta, ahora=2000)
        panel = self._panel()
        panel._lista.SetSelection(0)
        panel._on_key(Evento(wx.WXK_DELETE))
        self.assertTrue(segundo.is_file())
        self.assertEqual(panel._lista.GetCount(), 1)
        self.assertIn("primero.mp4", panel._lista.GetString(0))
        self.assertEqual([e["ruta"] for e in grabaciones.leer(self.ruta)],
                         [str(primero)])
        self.assertIs(panel.FindFocus(), panel._lista)

    def test_abrir_y_copiar_la_ruta(self):
        archivo = self._archivo("clip.mp4")
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000)
        panel = self._panel()
        with mock.patch.object(gui_grabaciones.os, "startfile") as startfile:
            panel._on_key(Evento(wx.WXK_RETURN))
        startfile.assert_called_once_with(str(archivo))
        panel._copiar_ruta()
        gui_grabaciones.copiar_al_portapapeles.assert_called_once_with(
            str(archivo))

    def test_la_tecla_aplicaciones_abre_el_menu_con_las_cuatro_acciones(self):
        panel = self._panel()
        etiquetas = []

        def popup(menu):
            etiquetas.extend(item.GetItemLabelText()
                             for item in menu.GetMenuItems())

        with mock.patch.object(panel._lista, "PopupMenu",
                               side_effect=popup) as mostrar:
            panel._on_key(Evento(wx.WXK_WINDOWS_MENU))
        mostrar.assert_called_once()
        self.assertEqual(etiquetas, ["Abrir", "Abrir carpeta", "Copiar ruta",
                                     "Eliminar de la lista"])

    def test_mayus_f10_abre_el_mismo_menu(self):
        panel = self._panel()
        with mock.patch.object(panel, "_mostrar_menu") as mostrar:
            panel._on_key(Evento(wx.WXK_F10, shift=True))
        mostrar.assert_called_once_with()

    def test_abrir_carpeta_selecciona_el_archivo(self):
        archivo = self._archivo("clip.mp4")
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000)
        panel = self._panel()
        with mock.patch.object(gui_grabaciones.subprocess, "Popen") as abrir:
            panel._abrir_carpeta()
        abrir.assert_called_once_with(["explorer", "/select,", str(archivo)])

    def test_abrir_archivo_o_carpeta_que_ya_no_estan_avisa(self):
        panel = self._panel()
        ruta = str(self.carpeta / "no-existe" / "clip.mp4")
        panel._entradas = [{"ruta": ruta}]
        panel._lista.Clear()
        panel._lista.Append("clip.mp4")
        panel._lista.SetSelection(0)
        panel._abrir()
        gui_grabaciones.anunciar.assert_called_with(
            "El archivo ya no está disponible.")
        gui_grabaciones.sound_player.reproducir.assert_called_with("error")
        panel._abrir_carpeta()
        gui_grabaciones.anunciar.assert_called_with(
            "La carpeta ya no está disponible.")

    def test_lo_borrado_del_disco_no_se_muestra(self):
        queda = self._archivo("queda.mp4")
        borrado = self._archivo("borrado.mp4")
        grabaciones.anotar(queda, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(borrado, ruta=self.ruta, ahora=2000)
        borrado.unlink()
        panel = self._panel()
        self.assertEqual(panel._lista.GetCount(), 1)
        self.assertIn("queda.mp4", panel._lista.GetString(0))


if __name__ == "__main__":
    unittest.main()
