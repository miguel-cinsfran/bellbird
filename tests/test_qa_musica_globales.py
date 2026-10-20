"""Pruebas del tramo de atajos globales, sin ventanas ni teclas.

Solo cubren lo puro (`se_dijo_desde`, `leer_registro`) y que los dos
módulos importan sin abrir nada. La escena real la corre el banco en la
otra PC.
"""

import importlib.util
import unittest
from pathlib import Path

_QA = Path(__file__).resolve().parent.parent / "qa"


def _cargar(nombre, archivo):
    ruta = _QA / archivo
    paquete = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(paquete)
    paquete.loader.exec_module(modulo)
    return modulo


musica_globales = _cargar("musica_globales_qa", "musica_globales.py")
ventana_ajena = _cargar("ventana_ajena_qa", "ventana_ajena.py")


class TestSeDijoDesde(unittest.TestCase):

    def _anuncios(self):
        return [{"texto": "Música en pausa"},
                {"texto": "Música reanudada"}]

    def test_lo_anterior_al_indice_no_cuenta(self):
        self.assertFalse(musica_globales.se_dijo_desde(
            self._anuncios(), "Música en pausa", desde=1))

    def test_desde_el_indice_si_cuenta(self):
        self.assertTrue(musica_globales.se_dijo_desde(
            self._anuncios(), "Música en pausa", desde=0))

    def test_el_segundo_desde_uno_si_cuenta(self):
        self.assertTrue(musica_globales.se_dijo_desde(
            self._anuncios(), "reanudada", desde=1))

    def test_no_dicho_da_falso(self):
        self.assertFalse(musica_globales.se_dijo_desde(
            self._anuncios(), "Música detenida", desde=0))

    def test_indice_fuera_de_rango_da_falso(self):
        self.assertFalse(musica_globales.se_dijo_desde(
            self._anuncios(), "Música en pausa", desde=9))

    def test_fragmento_vacio_da_falso(self):
        self.assertFalse(musica_globales.se_dijo_desde(
            self._anuncios(), "", desde=0))

    def test_ignora_mayusculas(self):
        self.assertTrue(musica_globales.se_dijo_desde(
            self._anuncios(), "música en PAUSA", desde=0))

    def test_acepta_cadenas_sueltas(self):
        self.assertTrue(musica_globales.se_dijo_desde(
            ["Música en pausa"], "en pausa", desde=0))


class TestLeerRegistro(unittest.TestCase):

    def test_ausente_da_vacio(self):
        import shutil
        import tempfile
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, True)
        self.assertEqual(musica_globales.leer_registro(
            Path(carpeta) / "no_existe.txt"), "")

    def test_vacio_da_vacio(self):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8"):
            pass
        self.addCleanup(os.remove, ruta)
        self.assertEqual(musica_globales.leer_registro(ruta), "")

    def test_devuelve_lo_escrito(self):
        import os
        import tempfile
        fd, ruta = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("qa")
        self.addCleanup(os.remove, ruta)
        self.assertEqual(musica_globales.leer_registro(ruta), "qa")


class TestVentanaAjenaPorTitulo(unittest.TestCase):

    def test_el_titulo_es_el_de_la_ventana_ajena(self):
        self.assertEqual(musica_globales.TITULO_VENTANA_AJENA,
                         ventana_ajena.TITULO)

    def test_hwnd_por_titulo_devuelve_el_hallado(self):
        class Usuario:
            def __init__(self):
                self.pedido = None
            def FindWindowW(self, clase, titulo):
                self.pedido = (clase, titulo)
                return 987
        usuario = Usuario()
        self.assertEqual(musica_globales._hwnd_por_titulo(usuario, "T"), 987)
        self.assertEqual(usuario.pedido, (None, "T"))

    def test_hwnd_por_titulo_sin_ventana_da_none(self):
        class Usuario:
            def FindWindowW(self, clase, titulo):
                return 0
        self.assertIsNone(musica_globales._hwnd_por_titulo(Usuario(), "T"))

    def test_hwnd_por_titulo_si_falla_da_none(self):
        class Usuario:
            def FindWindowW(self, clase, titulo):
                raise OSError("sin Win32")
        self.assertIsNone(musica_globales._hwnd_por_titulo(Usuario(), "T"))

    def test_pid_de_hwnd_devuelve_el_dueno(self):
        import ctypes
        class Usuario:
            def GetWindowThreadProcessId(self, hwnd, ref):
                ctypes.cast(ref, ctypes.POINTER(
                    ctypes.c_ulong)).contents.value = 4321
                return 1
        self.assertEqual(musica_globales._pid_de_hwnd(Usuario(), 987), 4321)

    def test_pid_de_hwnd_si_falla_da_none(self):
        class Usuario:
            def GetWindowThreadProcessId(self, hwnd, ref):
                raise OSError("sin Win32")
        self.assertIsNone(musica_globales._pid_de_hwnd(Usuario(), 987))

    def test_pulsar_alt_manda_abajo_y_arriba(self):
        class Usuario:
            def __init__(self):
                self.pulsadas = []
            def keybd_event(self, tecla, extra, flags, info):
                self.pulsadas.append((tecla, extra, flags, info))
        usuario = Usuario()
        musica_globales._pulsar_alt(usuario)
        self.assertEqual(usuario.pulsadas,
                         [(musica_globales.VK_MENU, 0, 0, 0),
                          (musica_globales.VK_MENU, 0,
                           musica_globales.TECLA_ARRIBA, 0)])

    def test_pedir_cierre_manda_wm_close_a_la_ventana(self):
        posteados = []
        class Usuario:
            def FindWindowW(self, clase, titulo):
                return 987
            def PostMessageW(self, hwnd, mensaje, w, l):
                posteados.append((hwnd, mensaje, w, l))
                return 1
        anterior = musica_globales._usuario32
        musica_globales._usuario32 = lambda: Usuario()
        try:
            musica_globales._pedir_cierre_ventana_ajena()
        finally:
            musica_globales._usuario32 = anterior
        self.assertEqual(posteados,
                         [(987, musica_globales.WM_CLOSE, 0, 0)])

    def test_pedir_cierre_sin_ventana_no_postea(self):
        posteados = []
        class Usuario:
            def FindWindowW(self, clase, titulo):
                return None
            def PostMessageW(self, hwnd, mensaje, w, l):
                posteados.append((hwnd, mensaje, w, l))
                return 1
        anterior = musica_globales._usuario32
        musica_globales._usuario32 = lambda: Usuario()
        try:
            musica_globales._pedir_cierre_ventana_ajena()
        finally:
            musica_globales._usuario32 = anterior
        self.assertEqual(posteados, [])

    def test_traer_al_frente_sin_ventana_da_falso(self):
        self.assertFalse(musica_globales._traer_al_frente(None, 4321))
        self.assertFalse(musica_globales._traer_al_frente(987, None))

    def test_esperar_sin_tiempo_da_nada(self):
        self.assertEqual(musica_globales._esperar_ventana_ajena(segundos=0),
                         (None, None))


class TestImportanSinAbrirNada(unittest.TestCase):

    def test_musica_globales_expone_el_tramo(self):
        self.assertTrue(callable(musica_globales.probar_atajos_globales))
        self.assertTrue(callable(musica_globales.se_dijo_desde))
        self.assertTrue(callable(musica_globales.leer_registro))

    def test_ventana_ajena_expone_su_titulo(self):
        self.assertEqual(ventana_ajena.TITULO, "Ventana ajena de QA")
        self.assertTrue(callable(ventana_ajena.main))

    def test_los_textos_salen_de_la_app(self):
        from ytchat.music import anuncios as anuncios_musica
        self.assertEqual(anuncios_musica.TEXTO_PAUSA, "Música en pausa")
        self.assertEqual(anuncios_musica.TEXTO_REANUDADA,
                         "Música reanudada")
        self.assertIn("cualquier programa",
                      anuncios_musica.TEXTO_ATAJOS_GLOBALES_ACTIVOS)


if __name__ == "__main__":
    unittest.main()
