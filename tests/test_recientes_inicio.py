"""Lista de directos recientes de la pantalla sin conexión.

P1 a P4 con un historial temporal real, la reconexión con la URL al pulsar
Intro, la visibilidad al mostrar y ocultar la zona, y el orden de Tab.
Las pruebas puras no crean ventanas; las de ventana solo corren en la otra
PC con `herramientas/oficina.py modulos --arbol`.
"""

import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bellbird.core import config  # primero: abre la cadena sin circular
from bellbird.core import historial
from bellbird.ui import recientes_inicio


def _entrada(plataforma, clave, fecha, url=None):
    return {
        "plataforma": plataforma, "clave": clave,
        "url": url or f"https://ejemplo/{clave}",
        "titulo": f"Título {clave}", "canal": f"Canal {clave}",
        "fecha": fecha, "directo": False,
    }


class TestEntradasRecientes(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "historial.json"

    def _guardar(self, entradas):
        historial.guardar(self.ruta, entradas)

    def test_diez_de_doce_del_mas_nuevo_al_mas_viejo(self):
        entradas = [
            _entrada("youtube" if i % 2 else "tiktok", f"clave-{i:02d}",
                     f"2026-03-{i + 1:02d}T10:00:00")
            for i in range(12)
        ]
        self._guardar(list(reversed(entradas)))
        recientes = recientes_inicio.entradas_recientes(self.ruta)
        self.assertEqual(10, len(recientes))
        self.assertEqual(
            [f"clave-{i:02d}" for i in range(11, 1, -1)],
            [e["clave"] for e in recientes])

    def test_ordena_por_fecha_mezclando_plataformas(self):
        vieja = _entrada("youtube", "vieja", "2026-01-05T10:00:00")
        nueva = _entrada("tiktok", "nueva", "2026-02-05T10:00:00")
        media = _entrada("youtube", "media", "2026-01-20T10:00:00")
        self._guardar([vieja, nueva, media])
        recientes = recientes_inicio.entradas_recientes(self.ruta)
        self.assertEqual(["nueva", "media", "vieja"],
                         [e["clave"] for e in recientes])

    def test_fila_lleva_prefijo_de_plataforma(self):
        youtube = _entrada("youtube", "yt", "2026-01-05T10:00:00")
        tiktok = _entrada("tiktok", "tk", "2026-02-05T10:00:00")
        fila_yt = recientes_inicio.texto_reciente(youtube)
        fila_tk = recientes_inicio.texto_reciente(tiktok)
        self.assertTrue(fila_yt.startswith("YouTube: "))
        self.assertTrue(fila_tk.startswith("TikTok: "))
        self.assertIn(historial.etiqueta(youtube), fila_yt)
        self.assertIn(historial.etiqueta(tiktok), fila_tk)

    def test_sin_historial_da_vacio(self):
        self._guardar([])
        self.assertEqual([], recientes_inicio.entradas_recientes(self.ruta))

    def test_ruta_inexistente_da_vacio(self):
        self.assertEqual(
            [], recientes_inicio.entradas_recientes(self.ruta))


class TestRecientesVentana(unittest.TestCase):
    """Necesita ventana real: solo corre en la otra PC."""

    def setUp(self):
        import wx
        self.wx = wx
        self.app = wx.App.Get() or wx.App(False)
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "historial.json"

    def _entradas(self, total=12):
        return [
            _entrada("youtube" if i % 2 else "tiktok", f"clave-{i:02d}",
                     f"2026-03-{i + 1:02d}T10:00:00")
            for i in range(total)
        ]

    def _marco(self, entradas):
        from tests.ventanas_prueba import destruir
        historial.guardar(self.ruta, entradas)
        marco = self.wx.Frame(None)
        self.addCleanup(destruir, marco)
        panel = self.wx.Panel(marco)
        sizer = self.wx.BoxSizer(self.wx.VERTICAL)
        panel.SetSizer(sizer)
        zona = self.wx.Panel(panel, name="ZonaContenido")
        sizer.Add(zona, 1, self.wx.EXPAND)
        zona.Hide()
        al_conectar = mock.Mock()
        recientes = recientes_inicio.armar(
            panel, sizer, zona, al_conectar, ruta=self.ruta)
        marco.ShowWithoutActivating()
        self.wx.Yield()
        return marco, panel, sizer, zona, recientes, al_conectar

    def test_con_historial_muestra_rotulo_lista_y_primera_fila(self):
        marco, panel, sizer, zona, recientes, _ = self._marco(self._entradas())
        self.assertTrue(recientes.caja.IsShown())
        self.assertEqual("&Directos recientes:", recientes.rotulo.GetLabel())
        self.assertEqual("Directos recientes", recientes.lista.GetName())
        self.assertEqual(10, recientes.lista.GetCount())
        self.assertEqual(0, recientes.lista.GetSelection())
        self.assertTrue(
            recientes.lista.GetString(0).startswith(("YouTube: ", "TikTok: ")))

    def test_intro_conecta_con_la_url_de_la_fila(self):
        _m, _p, _s, _z, recientes, al_conectar = self._marco(self._entradas(3))
        recientes.lista.SetSelection(1)
        evento = mock.Mock()
        evento.GetKeyCode.return_value = self.wx.WXK_RETURN
        recientes.al_tecla(evento)
        esperada = recientes.entradas[1]["url"]
        al_conectar.assert_called_once_with(esperada)
        evento.Skip.assert_not_called()

    def test_otra_tecla_se_deja_pasar(self):
        _m, _p, _s, _z, recientes, al_conectar = self._marco(self._entradas(3))
        evento = mock.Mock()
        evento.GetKeyCode.return_value = ord("a")
        recientes.al_tecla(evento)
        al_conectar.assert_not_called()
        evento.Skip.assert_called_once_with()

    def test_zona_visible_oculta_y_zona_oculta_muestra(self):
        marco, panel, sizer, zona, recientes, _ = self._marco(self._entradas(3))
        self.assertTrue(recientes.caja.IsShown())
        zona.Show()
        self.wx.Yield()
        self.assertFalse(recientes.caja.IsShown())
        zona.Hide()
        self.wx.Yield()
        self.assertTrue(recientes.caja.IsShown())
        self.assertEqual(3, recientes.lista.GetCount())

    def test_sin_historial_no_muestra_ni_lista_ni_rotulo(self):
        _m, _p, _s, _z, recientes, _c = self._marco([])
        self.assertFalse(recientes.caja.IsShown())
        self.assertEqual(0, recientes.lista.GetCount())

    def test_al_desconectar_recarga_con_el_historial_al_dia(self):
        marco, panel, sizer, zona, recientes, _ = self._marco(self._entradas(2))
        self.assertEqual(2, recientes.lista.GetCount())
        historial.guardar(self.ruta, self._entradas(5))
        zona.Show()
        self.wx.Yield()
        zona.Hide()
        self.wx.Yield()
        self.assertTrue(recientes.caja.IsShown())
        self.assertEqual(5, recientes.lista.GetCount())

    def test_abrir_historial_usa_la_misma_ruta_y_funcion(self):
        _m, _p, _s, _z, recientes, al_conectar = self._marco(self._entradas(1))
        with mock.patch(
                "bellbird.ui.gui_historial.abrir_historial") as abrir:
            recientes.abrir_historial()
        self.assertEqual(1, abrir.call_count)
        _args, _kwargs = abrir.call_args
        self.assertEqual((self.ruta, al_conectar), (_args[1], _args[2]))

    def test_on_historial_delega_en_la_lista(self):
        from bellbird.ui import gui
        marco = gui.YTChatFrame.__new__(gui.YTChatFrame)
        marco._inicio = mock.Mock()
        marco._on_historial()
        marco._inicio.abrir_historial.assert_called_once_with()


class TestOrdenTabDesconectada(unittest.TestCase):
    """La lista cierra el Tab sin conexión: enlace, Conectar, Transmitir, lista."""

    def setUp(self):
        import wx
        self.wx = wx
        self.app = wx.App.Get() or wx.App(False)

    def _ventana(self):
        from bellbird.ui import gui
        from tests.ventanas_prueba import destruir
        configuracion = {
            "atajos_raw": {}, "filtro_activo": "todos",
            "mostrar_botones_reproductor": False, "mostrar_metadatos": True,
            "mostrar_total_superchats": True, "overlay_activo": False,
            "programados_activo": False,
        }
        stats = SimpleNamespace(leidos=0, superchats=0, descartados=0)
        worker = SimpleNamespace(get_rate=lambda: 0, get_volume=lambda: 100)
        with mock.patch.object(gui.diagnostico, "crear_hilo"):
            marco = gui.YTChatFrame(None, configuracion, queue.Queue(),
                                    stats, worker,
                                    __import__("threading").Event())
        self.addCleanup(destruir, marco)
        marco.ShowWithoutActivating()
        self.wx.Yield()
        return marco

    def test_lista_al_final_sin_conexion(self):
        from tests.rutas_temporales import redirigir_rutas
        with redirigir_rutas("."):
            marco = self._ventana()
            self.assertFalse(marco._zona.IsShown())
            hijos = marco._panel_principal.GetChildren()
            nombres = [h.GetName() for h in hijos]
            self.assertIn(marco._inicio.caja.GetName(), nombres)
            sizer = marco._panel_principal.GetSizer()
            orden = [sizer.GetItem(i).GetWindow()
                     for i in range(sizer.GetItemCount())]
            self.assertLess(orden.index(marco._inicio.caja),
                            orden.index(marco._zona))

    def test_lista_oculta_al_conectar(self):
        marco = self._ventana()
        marco._mostrar_zona(True)
        self.wx.Yield()
        self.assertFalse(marco._inicio.caja.IsShown())
        marco._mostrar_zona(False)
        self.wx.Yield()

    def test_intro_en_recientes_cablea_la_reconexion(self):
        # Cableado ventana real: con historial temporal de una entrada y sin
        # conexión, Intro sobre la lista deja la URL en el campo y programa
        # la conexión. Si gui.py pasa otra función a armar, txt_url queda
        # vacío y CallAfter no recibe _on_conectar.
        from bellbird.ui import gui
        from bellbird.ui import recientes_inicio
        entrada = {
            "plataforma": "youtube", "clave": "abcdefghijk",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "titulo": "Título", "canal": "Canal",
            "fecha": "2026-03-01T10:00:00", "directo": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "historial.json"
            historial.guardar(ruta, [entrada])
            with mock.patch.object(recientes_inicio.paths, "historial_lives",
                                   return_value=ruta):
                marco = self._ventana()
            self.assertEqual(1, marco._inicio.lista.GetCount())
            evento = mock.Mock()
            evento.GetKeyCode.return_value = self.wx.WXK_RETURN
            with mock.patch.object(gui.wx, "CallAfter") as diferir:
                marco._inicio.al_tecla(evento)
            self.assertEqual(entrada["url"], marco.txt_url.GetValue())
            diferir.assert_called_once_with(marco._on_conectar, None)


if __name__ == "__main__":
    unittest.main()
