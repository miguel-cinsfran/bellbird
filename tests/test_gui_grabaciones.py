"""Pruebas de la ventana Grabaciones. Requieren entorno gráfico."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from bellbird.obs import grabaciones
from bellbird.ui import gui_grabaciones
from tests.ventanas_prueba import destruir


class Evento:
    def __init__(self, tecla):
        self._tecla = tecla
        self.saltado = False

    def GetKeyCode(self):
        return self._tecla

    def Skip(self):
        self.saltado = True


class TestVentanaGrabaciones(unittest.TestCase):

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
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

    def _dialogo(self):
        dialogo = gui_grabaciones.GrabacionesDialog(None)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _nombres_en_orden(self, ventana):
        nombres = []
        for hijo in ventana.GetChildren():
            if isinstance(hijo, (wx.ListBox, wx.Button)) and hijo.IsShown():
                nombres.append(hijo.GetName())
            nombres.extend(self._nombres_en_orden(hijo))
        return nombres

    def test_nombres_accesibles_exactos(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo._lista.GetName(), "Grabaciones")
        self.assertEqual([b.GetName() for b in (
            dialogo._btn_abrir, dialogo._btn_carpeta, dialogo._btn_copiar,
            dialogo._btn_eliminar, dialogo._btn_cerrar)],
            ["Abrir", "Abrir carpeta", "Copiar ruta",
             "Eliminar de la lista", "Cerrar"])

    def test_orden_de_tab(self):
        dialogo = self._dialogo()
        self.assertEqual(self._nombres_en_orden(dialogo), [
            "Grabaciones", "Abrir", "Abrir carpeta", "Copiar ruta",
            "Eliminar de la lista", "Cerrar"])

    def test_al_abrir_el_foco_queda_en_la_primera_fila(self):
        grabaciones.anotar(self._archivo("primera.mp4"), ruta=self.ruta,
                           ahora=1000)
        grabaciones.anotar(self._archivo("segunda.mp4"), ruta=self.ruta,
                           ahora=2000)
        dialogo = self._dialogo()
        dialogo.Show()
        self.addCleanup(dialogo.Hide)
        wx.Yield()
        self.assertIs(dialogo.FindFocus(), dialogo._lista)
        self.assertEqual(dialogo._lista.GetSelection(), 0)
        self.assertIn("segunda.mp4", dialogo._lista.GetString(0))

    def test_sin_grabaciones_la_fila_y_las_acciones_lo_dicen(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo._lista.GetCount(), 1)
        self.assertEqual(dialogo._lista.GetString(0),
                         "No hay grabaciones guardadas.")
        for boton_ in (dialogo._btn_abrir, dialogo._btn_carpeta,
                       dialogo._btn_copiar, dialogo._btn_eliminar):
            self.assertTrue(boton_.IsEnabled())
        dialogo._abrir()
        gui_grabaciones.anunciar.assert_called_with(
            "No hay grabaciones guardadas.")

    def test_supr_saca_la_fila_y_deja_el_archivo_en_el_disco(self):
        primero = self._archivo("primero.mp4")
        segundo = self._archivo("segundo.mp4")
        grabaciones.anotar(primero, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(segundo, ruta=self.ruta, ahora=2000)
        dialogo = self._dialogo()
        dialogo.Show()
        self.addCleanup(dialogo.Hide)
        wx.Yield()
        dialogo._lista.SetSelection(0)
        dialogo._on_key(Evento(wx.WXK_DELETE))
        self.assertTrue(segundo.is_file())
        self.assertEqual(dialogo._lista.GetCount(), 1)
        self.assertIn("primero.mp4", dialogo._lista.GetString(0))
        self.assertEqual([e["ruta"] for e in grabaciones.leer(self.ruta)],
                         [str(primero)])
        self.assertIs(dialogo.FindFocus(), dialogo._lista)

    def test_abrir_y_copiar_la_ruta(self):
        archivo = self._archivo("clip.mp4")
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000)
        dialogo = self._dialogo()
        with mock.patch.object(gui_grabaciones.os, "startfile") as startfile:
            dialogo._on_key(Evento(wx.WXK_RETURN))
        startfile.assert_called_once_with(str(archivo))
        dialogo._copiar_ruta()
        gui_grabaciones.copiar_al_portapapeles.assert_called_once_with(
            str(archivo))

    def test_abrir_carpeta_selecciona_el_archivo(self):
        archivo = self._archivo("clip.mp4")
        grabaciones.anotar(archivo, ruta=self.ruta, ahora=1000)
        dialogo = self._dialogo()
        with mock.patch.object(gui_grabaciones.subprocess, "Popen") as abrir:
            dialogo._abrir_carpeta()
        abrir.assert_called_once_with(["explorer", "/select,", str(archivo)])

    def test_abrir_archivo_o_carpeta_que_ya_no_estan_avisa(self):
        dialogo = self._dialogo()
        ruta = str(self.carpeta / "no-existe" / "clip.mp4")
        dialogo._entradas = [{"ruta": ruta}]
        dialogo._lista.Clear()
        dialogo._lista.Append("clip.mp4")
        dialogo._lista.SetSelection(0)
        dialogo._abrir()
        gui_grabaciones.anunciar.assert_called_with(
            "El archivo ya no está disponible.")
        gui_grabaciones.sound_player.reproducir.assert_called_with("error")
        dialogo._abrir_carpeta()
        gui_grabaciones.anunciar.assert_called_with(
            "La carpeta ya no está disponible.")

    def test_lo_borrado_del_disco_no_se_muestra(self):
        queda = self._archivo("queda.mp4")
        borrado = self._archivo("borrado.mp4")
        grabaciones.anotar(queda, ruta=self.ruta, ahora=1000)
        grabaciones.anotar(borrado, ruta=self.ruta, ahora=2000)
        borrado.unlink()
        dialogo = self._dialogo()
        self.assertEqual(dialogo._lista.GetCount(), 1)
        self.assertIn("queda.mp4", dialogo._lista.GetString(0))


if __name__ == "__main__":
    unittest.main()
