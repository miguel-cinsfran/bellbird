"""Pruebas de las capturas del banco de QA, casi todas puras.

Las clases `TestNombres`, `TestDedup`, `TestIndice`, `TestColores` y
`TestArgumentosCapturas` no abren ventanas y corren en cualquier PC. La
clase `TestCapturaWx` sí crea un `wx.Frame` de verdad y la corre el
advisor en la otra PC; acá NO se corre.
"""

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

_QA = Path(__file__).resolve().parent.parent / "qa"


def _cargar(nombre, archivo):
    ruta = _QA / archivo
    paquete = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(paquete)
    paquete.loader.exec_module(modulo)
    return modulo


capturas = _cargar("capturas_qa", "capturas.py")
conducir = _cargar("conducir_qa", "conducir.py")


class TestNombres(unittest.TestCase):

    def test_pliega_tildes_y_espacios(self):
        self.assertEqual(capturas.plegar("Gestor de descargas"),
                         "gestor_de_descargas")
        self.assertEqual(capturas.plegar("Música"), "musica")

    def test_pliega_simbolos(self):
        self.assertEqual(capturas.plegar("¡Hola, qué tal!"), "hola_que_tal")

    def test_nombre_base_con_numero(self):
        self.assertEqual(capturas.nombre_base(3, "chat", "Gestor de descargas"),
                         "03_chat_gestor_de_descargas")

    def test_titulos_largos_se_recortan(self):
        base = capturas.nombre_base(1, "x", "a" * 100)
        self.assertEqual(base, "01_x_" + "a" * capturas.LIMITE_TITULO)
        pagina = capturas.nombre_pagina("01_x_y", 2, "b" * 100)
        self.assertTrue(pagina.endswith("b" * capturas.LIMITE_PESTANA))

    def test_nombre_pagina_con_numero_y_pestana(self):
        self.assertEqual(capturas.nombre_pagina("03_musica_musica", 2,
                                                "Biblioteca"),
                         "03_musica_musica_p02_biblioteca")


class TestDedup(unittest.TestCase):

    def test_el_mismo_titulo_y_escenario_va_una_vez(self):
        registro = capturas.RegistroCapturas("donde-sea")
        primera = registro.reservar("chat", "Preferencias")
        self.assertIsNotNone(primera)
        self.assertIsNone(registro.reservar("chat", "Preferencias"))
        self.assertIsNone(registro.reservar("CHAT", "preferencias"))

    def test_otro_escenario_captura_de_nuevo(self):
        registro = capturas.RegistroCapturas("donde-sea")
        self.assertIsNotNone(registro.reservar("chat", "Música"))
        segunda = registro.reservar("musica", "Música")
        self.assertIsNotNone(segunda)
        self.assertNotEqual(registro.reservar("x", "Y")[0], segunda[0])

    def test_la_variante_distigue(self):
        registro = capturas.RegistroCapturas("donde-sea")
        self.assertIsNotNone(registro.reservar("m", "Música"))
        self.assertIsNotNone(
            registro.reservar("m", "Música", extra="cola visible"))
        self.assertIsNone(
            registro.reservar("m", "Música", extra="cola visible"))


class TestIndice(unittest.TestCase):

    def test_renglon_ok_trae_todo(self):
        linea = capturas.linea_ok(3, "03_chat_principal.png", "chat",
                                  "YTChat", "", (800, 600), (400, 300))
        for pedazo in ("03", "03_chat_principal.png", "chat", "YTChat",
                       "800x600", "400x300"):
            self.assertIn(pedazo, linea)

    def test_renglon_fallo_trae_motivo(self):
        linea = capturas.linea_fallo(4, "chat", "Música", "PrintWindow falso")
        self.assertIn("FALLIDA", linea)
        self.assertIn("PrintWindow falso", linea)

    def test_indice_con_seccion_no_capturado(self):
        registro = capturas.RegistroCapturas("donde-sea")
        registro.anotar_ok(1, "01_a.png", "chat", "T", "", (1, 1), None)
        texto = registro.indice_texto()
        self.assertIn("01_a.png", texto)
        self.assertIn("No capturado", texto)

    def test_carpeta_por_defecto_con_fecha_y_hora(self):
        import datetime
        texto = capturas.carpeta_por_defecto(
            datetime.datetime(2026, 10, 20, 15, 4))
        self.assertEqual(texto, "2026-10-20_15-04")


class TestColores(unittest.TestCase):

    def test_bgra_a_rgb_da_vuelta_azul_y_rojo(self):
        crudos = bytes([10, 20, 30, 255, 0, 0, 255, 0])
        self.assertEqual(capturas.bgra_a_rgb(crudos),
                         bytes([30, 20, 10, 255, 0, 0]))

    def test_bgra_incompletos_rechazados(self):
        with self.assertRaises(ValueError):
            capturas.bgra_a_rgb(bytes([1, 2, 3]))

    def test_todo_negro_con_pixeles_en_cero(self):
        self.assertTrue(capturas.es_todo_negro(bytes([0, 0, 0, 0, 0, 0])))

    def test_no_todo_negro_con_un_byte_encendido(self):
        self.assertFalse(capturas.es_todo_negro(bytes([0, 0, 1, 0, 0, 0])))

    def test_vacio_no_es_todo_negro(self):
        self.assertFalse(capturas.es_todo_negro(b""))


class TestArgumentosCapturas(unittest.TestCase):

    def test_sin_la_opcion_no_hay_captor(self):
        self.assertIsNone(conducir._argumentos([]).capturas)

    def test_la_opcion_sola_pide_carpeta_automatica(self):
        self.assertEqual(conducir._argumentos(["--capturas"]).capturas,
                         "__auto__")

    def test_la_opcion_acepta_carpeta(self):
        args = conducir._argumentos(["--capturas", "mi/carpeta"])
        self.assertEqual(args.capturas, "mi/carpeta")

    def _aplicacion(self, respuesta=None, error=None):
        app = mock.Mock()
        app.llamadas = []
        def _pedir(op, **extra):
            app.llamadas.append((op, extra))
            if error is not None:
                raise error
            return respuesta
        app.pedir.side_effect = _pedir
        return app

    def test_sin_captor_no_hay_como_pedir(self):
        app = self._aplicacion()
        self.assertFalse(hasattr(conducir._argumentos([]), "captor"))

    def test_el_fallo_de_la_sonda_no_levanta(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            captor = conducir.Captor(Path(base) / "c")
            app = self._aplicacion(error=RuntimeError("mute"))
            self.assertFalse(captor.capturar(app, "chat", "Principal"))
            self.assertEqual(len(app.llamadas), 1)
            self.assertIn("FALLIDA", captor.registro.indice_texto())

    def test_la_duplicada_no_vuelve_a_pedir(self):
        import tempfile
        respuesta = {"ok": True, "datos": {"archivos": [{
            "archivo": "01_chat_principal.png", "titulo": "Principal",
            "pestana": "", "ancho": 800, "alto": 600,
            "minimo": [400, 300]}]}}
        with tempfile.TemporaryDirectory() as base:
            captor = conducir.Captor(Path(base) / "c")
            app = self._aplicacion(respuesta=respuesta)
            self.assertTrue(captor.capturar(app, "chat", "Principal"))
            self.assertFalse(captor.capturar(app, "chat", "Principal"))
            self.assertEqual(len(app.llamadas), 1)


class TestCapturaWx(unittest.TestCase):
    """Captura de verdad sobre un `wx.Frame`. La corre el advisor."""

    @classmethod
    def setUpClass(cls):
        try:
            import wx as _wx
        except ImportError:
            raise unittest.SkipTest("sin wx en esta PC")
        cls.wx = _wx
        cls.sonda = _cargar("sonda_qa", "sonda.py")
        app = _wx.App()
        cls.app = app
        marco = _wx.Frame(None, title="Prueba de captura",
                          size=(160, 120))
        panel = _wx.Panel(marco)
        panel.SetBackgroundColour(_wx.Colour(11, 22, 33))
        marco.ShowWithoutActivating()
        cls.sonda._dejar_pintar(marco)
        cls.marco = marco

    @classmethod
    def tearDownClass(cls):
        try:
            cls.marco.Destroy()
        except Exception:
            pass

    def test_el_png_existe_y_mide_lo_mismo(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            destino = Path(base) / "prueba.png"
            ancho, alto = self.sonda._guardar_png(self.marco, destino)
            self.assertTrue(destino.is_file())
            imagen = self.wx.Image(str(destino))
            self.assertEqual((imagen.GetWidth(), imagen.GetHeight()),
                             (ancho, alto))
            esperado = self.marco.GetSize()
            self.assertEqual((ancho, alto),
                             (esperado.GetWidth(), esperado.GetHeight()))

    def test_el_centro_tiene_el_color_del_panel(self):
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            destino = Path(base) / "prueba.png"
            ancho, alto = self.sonda._guardar_png(self.marco, destino)
            imagen = self.wx.Image(str(destino))
            rojo = imagen.GetRed(ancho // 2, alto // 2)
            verde = imagen.GetGreen(ancho // 2, alto // 2)
            azul = imagen.GetBlue(ancho // 2, alto // 2)
            self.assertEqual((rojo, verde, azul), (11, 22, 33))


if __name__ == "__main__":
    unittest.main()
