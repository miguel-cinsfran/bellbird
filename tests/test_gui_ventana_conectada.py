"""Ventana principal conectada a 860x700: chat y vídeo visibles.

Abren ventanas: las corre el advisor en la otra PC, no se corren acá. Con
el rediseño del encargo (interruptor a la fila del volumen, «Mensaje:» a
la izquierda del campo y proporción que cede el vídeo con mínimo 110),
la lista muestra al menos 6 filas y el vídeo conserva al menos 100 px.
"""

import queue
import unittest
from types import SimpleNamespace
from unittest import mock

from bellbird.player import reproductor
from bellbird.ui import gui
from tests.ventanas_prueba import destruir


class TestVentanaConectadaFabrica(unittest.TestCase):
    # Con ventana: las corre el advisor en la otra PC. No correr aquí.

    def setUp(self):
        self.app = gui.wx.App.Get() or gui.wx.App(False)

    def _ventana(self):
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": True,
            "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False, "tamanio_fuente_chat": 12,
        }
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100)
        with mock.patch.object(gui.diagnostico, "crear_hilo"), \
                mock.patch.object(reproductor, "disponible",
                                  return_value=True):
            frame = gui.YTChatFrame(None, configuracion, queue.Queue(),
                                    stats, worker,
                                    __import__("threading").Event())
        self.addCleanup(destruir, frame)
        return frame

    def _medir(self, frame):
        frame._mostrar_zona(True)
        frame.SetSize((gui.ANCHO_DEFECTO, gui.ALTO_DEFECTO))
        gui.wx.Yield()
        frame.Layout()
        gui.wx.Yield()
        for i in range(50):
            frame.lb_chat.Append(f"Autor {i}: mensaje de prueba {i}")
        gui.wx.Yield()
        datos = {
            "marco": tuple(frame.GetSize()),
            "cliente": tuple(frame.GetClientSize()),
            "cuaderno": tuple(frame.nb.GetSize()),
            "lista": tuple(frame.lb_chat.GetSize()),
            "filas": frame.lb_chat.GetCountPerPage(),
            "video": tuple(frame._rep_panel._video.GetSize()),
            "min_rep": tuple(frame._rep_panel.GetSizer().GetMinSize()),
        }
        return datos

    def test_lista_muestra_al_menos_seis_filas(self):
        frame = self._ventana()
        datos = self._medir(frame)
        self.assertGreaterEqual(
            datos["filas"], 6,
            f"filas={datos['filas']} marco={datos['marco']} "
            f"cuaderno={datos['cuaderno']} lista={datos['lista']}")

    def test_video_conserva_al_menos_100_de_alto(self):
        frame = self._ventana()
        datos = self._medir(frame)
        self.assertGreaterEqual(
            datos["video"][1], 100,
            f"video={datos['video']} min_rep={datos['min_rep']} "
            f"marco={datos['marco']} cuaderno={datos['cuaderno']}")


if __name__ == "__main__":
    unittest.main()
