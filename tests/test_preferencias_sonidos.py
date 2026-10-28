"""Pruebas de la página Sonidos (con wx: las corre el advisor en otra PC).

Usan un sounds.ini temporal real, nunca el de datos.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wx

from ytchat.core import paths
from ytchat.core.eventos_sonido import EVENTOS
from ytchat.ui import preferencias_sonidos
from ytchat.ui.preferencias_sonidos import PaginaSonidos


class TestPaginaSonidos(unittest.TestCase):
    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "sounds.ini"
        self.ruta.write_text("[sonidos]\nvolumen = 0.7\ntema = default\n",
                             encoding="utf-8")
        parche = mock.patch.object(preferencias_sonidos.paths, "sounds_ini",
                                    return_value=self.ruta)
        self.addCleanup(parche.stop)
        parche.start()
        self.libro = wx.Notebook(wx.Frame(None), name="LibroPrueba")
        self.addCleanup(self.libro.GetParent().Destroy)
        self.pagina = PaginaSonidos()
        self.panel = self.pagina.construir(self.libro)

    def test_lista_con_59_filas_marcadas(self):
        self.assertEqual(self.pagina._lista.GetItemCount(), 59)
        self.assertEqual(self.pagina._lista.GetItemCount(), len(EVENTOS))
        for indice in range(59):
            self.assertTrue(self.pagina._lista.IsItemChecked(indice))

    def test_destildar_y_guardar_escribe_la_linea_vacia_y_recarga(self):
        self.pagina._lista.CheckItem(0, False)
        with mock.patch.object(preferencias_sonidos._snd, "cargar") as cargar, \
                mock.patch.object(preferencias_sonidos.cfg, "cargar_sonidos",
                                   return_value={"eventos": {}}) as fabrica:
            self.assertTrue(self.pagina.guardar())
            fabrica.assert_called_once_with()
            cargar.assert_called_once_with({"eventos": {}})
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertIn(f"{EVENTOS[0]} =", texto)

    def test_sin_cambios_no_escribe(self):
        with mock.patch.object(preferencias_sonidos.archivos,
                               "escribir_texto_atomico") as escribir:
            self.assertTrue(self.pagina.guardar())
            escribir.assert_not_called()

    def test_boton_llama_con_la_ruta_del_tema(self):
        self.pagina._lista.SetItemState(
            1, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
        with mock.patch.object(preferencias_sonidos._snd,
                               "reproducir_archivo") as oir:
            self.pagina._on_oir(None)
            oir.assert_called_once()
            ruta = str(oir.call_args.args[0])
            self.assertTrue(ruta.endswith(f"{EVENTOS[1]}.wav"))

    def test_sin_fila_elegida_no_hace_nada(self):
        self.pagina._lista.Select(0, False)
        with mock.patch.object(preferencias_sonidos._snd,
                               "reproducir_archivo") as oir:
            self.pagina._on_oir(None)
            oir.assert_not_called()

    def test_rotulo_con_mnemonico_antes_de_la_lista(self):
        rotulos = [c for c in self.panel.GetChildren()
                   if isinstance(c, wx.StaticText)]
        self.assertIn("&Sonidos:", [r.GetLabel() for r in rotulos])

    def test_primera_fila_elegida_al_cargar(self):
        self.assertEqual(self.pagina._lista.GetFirstSelected(), 0)
        with mock.patch.object(preferencias_sonidos._snd,
                               "reproducir_archivo") as oir:
            self.pagina._on_oir(None)
            oir.assert_called_once()
            ruta = str(oir.call_args.args[0])
            self.assertTrue(ruta.endswith(f"{EVENTOS[0]}.wav"))

    def test_columna_sigue_el_ancho_de_la_lista(self):
        lista = self.pagina._lista
        lista.SetSize((500, 300))
        lista.SendSizeEvent()
        self.assertEqual(lista.GetColumnWidth(0),
                         lista.GetClientSize().width)

    def test_mnemonicos_no_chocan_con_guardar(self):
        letras = []
        for control in self.panel.GetChildren():
            etiqueta = control.GetLabel() if hasattr(control, "GetLabel") else ""
            if "&" in etiqueta:
                letras.append(etiqueta.split("&", 1)[1][:1].lower())
        self.assertEqual(len(letras), len(set(letras)), letras)
        self.assertNotIn("g", letras)
        self.assertNotIn("c", letras)


if __name__ == "__main__":
    unittest.main()
