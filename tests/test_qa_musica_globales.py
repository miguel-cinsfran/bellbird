"""Pruebas del tramo de atajos globales, sin ventanas ni teclas.

Solo cubren lo puro (`se_dijo_desde`, `leer_registro`,
`tomados_de_fallo`, `traducir_atajo_a_teclas`, `PASOS`,
`_resolver_activacion`) y que los dos módulos importan sin abrir nada.
La escena real la corre el banco.
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


class TestTomadosDeFallo(unittest.TestCase):

    def _anuncio(self, lista):
        from bellbird.music import anuncios as anuncios_musica
        return anuncios_musica.TEXTO_ATAJOS_GLOBALES_FALLO.format(
            lista=lista)

    def test_extrae_varias(self):
        anuncio = self._anuncio("Ctrl+Alt+Espacio, Ctrl+Alt+Flecha derecha")
        self.assertEqual(musica_globales.tomados_de_fallo(anuncio),
                         ["Ctrl+Alt+Espacio", "Ctrl+Alt+Flecha derecha"])

    def test_extrae_una_sola(self):
        self.assertEqual(musica_globales.tomados_de_fallo(
            self._anuncio("Ctrl+Alt+Espacio")), ["Ctrl+Alt+Espacio"])

    def test_reconoce_la_de_que_suena(self):
        from bellbird.ui.atajos_captura import atajo_legible
        nombre = atajo_legible("ctrl+alt+t")
        tomados = musica_globales.tomados_de_fallo(
            self._anuncio(f"Ctrl+Alt+Espacio, {nombre}"))
        self.assertIn(nombre, tomados)

    def test_sin_anuncio_de_fallo_da_vacia(self):
        self.assertEqual(musica_globales.tomados_de_fallo(
            "Atajos de música activos en cualquier aplicación"), [])

    def test_vacio_da_vacia(self):
        self.assertEqual(musica_globales.tomados_de_fallo(""), [])
        self.assertEqual(musica_globales.tomados_de_fallo(None), [])

    def test_acepta_dict_de_la_sonda(self):
        self.assertEqual(musica_globales.tomados_de_fallo(
            {"texto": self._anuncio("Ctrl+Alt+T")}), ["Ctrl+Alt+T"])


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
        self.assertTrue(callable(musica_globales.tomados_de_fallo))

    def test_la_tecla_y_el_prefijo_salen_de_las_constantes(self):
        from bellbird.music import anuncios as anuncios_musica
        from bellbird.ui.atajos_captura import atajo_legible
        self.assertEqual(musica_globales.TECLA_QUE_SUENA, "^%t")
        self.assertEqual(musica_globales.NOMBRE_QUE_SUENA,
                         atajo_legible("ctrl+alt+t"))
        self.assertEqual(musica_globales.PREFIJO_QUE_SUENA,
                         anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")[0])
        self.assertTrue(musica_globales.PREFIJO_QUE_SUENA)

    def test_ventana_ajena_expone_su_titulo(self):
        self.assertEqual(ventana_ajena.TITULO, "Ventana ajena de QA")
        self.assertTrue(callable(ventana_ajena.main))

    def test_los_textos_salen_de_la_app(self):
        from bellbird.music import anuncios as anuncios_musica
        self.assertEqual(anuncios_musica.TEXTO_PAUSA, "Música en pausa")
        self.assertEqual(anuncios_musica.TEXTO_REANUDADA,
                         "Música reanudada")
        self.assertIn("cualquier aplicación",
                      anuncios_musica.TEXTO_ATAJOS_GLOBALES_ACTIVOS)


class TestTraducirAtajoATeclas(unittest.TestCase):

    def test_letra(self):
        self.assertEqual(
            musica_globales.traducir_atajo_a_teclas("ctrl+alt+t"), "^%t")

    def test_espacio(self):
        self.assertEqual(
            musica_globales.traducir_atajo_a_teclas("ctrl+alt+space"),
            "^%{SPACE}")

    def test_flecha(self):
        self.assertEqual(
            musica_globales.traducir_atajo_a_teclas("ctrl+alt+right"),
            "^%{RIGHT}")

    def test_mayus(self):
        self.assertEqual(
            musica_globales.traducir_atajo_a_teclas("ctrl+alt+shift+left"),
            "^%+{LEFT}")

    def test_acepta_otro_orden_y_mayusculas(self):
        self.assertEqual(
            musica_globales.traducir_atajo_a_teclas("Alt+Ctrl+A"), "^%a")

    def test_formato_que_no_corresponde_da_none(self):
        for texto in ("", None, "ctrl+t", "ctrl+alt+f5", "ctrl+shift+t",
                      "ctrl+alt+shift+up", "ctrl+alt+left+right"):
            self.assertIsNone(
                musica_globales.traducir_atajo_a_teclas(texto))


class TestTablaDePasos(unittest.TestCase):

    def test_toda_accion_aparece(self):
        from bellbird.ui.atajos_globales import ACCIONES
        en_tabla = {paso.accion for paso in musica_globales.PASOS}
        faltan = [accion for accion in ACCIONES if accion not in en_tabla]
        self.assertEqual(faltan, [])

    def test_teclas_son_la_traduccion_de_fabrica(self):
        from bellbird.core import config_predeterminada
        for paso in musica_globales.PASOS:
            fabrica = config_predeterminada.obtener(
                "atajos", paso.accion, "")
            self.assertEqual(
                paso.teclas,
                musica_globales.traducir_atajo_a_teclas(fabrica))
            self.assertTrue(paso.teclas)

    def test_esperados_salen_de_las_constantes(self):
        from bellbird.music import anuncios as anuncios_musica
        from bellbird.music import anuncios_teclas
        permitidos = {
            anuncios_musica.TEXTO_QUE_SUENA.split("{nombre}")[0],
            anuncios_musica.TEXTO_PAUSA,
            anuncios_musica.TEXTO_REANUDADA,
            anuncios_musica.TEXTO_DETENIDA,
            anuncios_musica.TEXTO_ALEATORIO_ON,
            anuncios_musica.TEXTO_ALEATORIO_OFF,
            anuncios_musica.TEXTO_REPETIR_TODO,
            anuncios_musica.TEXTO_REPETIR_TEMA,
            anuncios_musica.TEXTO_REPETIR_NO,
            anuncios_teclas.TEXTO_SILENCIADA,
            anuncios_teclas.TEXTO_RESTAURADA,
        }
        vistos = 0
        for paso in musica_globales.PASOS:
            if paso.esperado is None:
                continue
            vistos += 1
            self.assertTrue(paso.esperado)
            self.assertIn(paso.esperado, permitidos)
        self.assertTrue(vistos)
        self.assertTrue(any(paso.esperado is None
                            for paso in musica_globales.PASOS))

    def test_volumen_acepta_cualquier_anuncio_nuevo(self):
        pasos = [paso for paso in musica_globales.PASOS
                 if paso.accion in ("musica_vol_mas", "musica_vol_menos")]
        self.assertEqual(len(pasos), 2)
        for paso in pasos:
            self.assertIsNone(paso.esperado)

    def test_interruptores_quedan_como_estaban(self):
        from collections import Counter
        veces = Counter(paso.accion for paso in musica_globales.PASOS)
        self.assertEqual(veces["musica_silenciar"] % 2, 0)
        self.assertEqual(veces["musica_aleatorio"] % 2, 0)
        self.assertEqual(veces["musica_repetir"] % 3, 0)
        self.assertGreater(veces["musica_repetir"], 0)

    def test_repetir_sigue_el_ciclo_de_la_app(self):
        from bellbird.music import anuncios as anuncios_musica
        ciclo = [paso.esperado for paso in musica_globales.PASOS
                 if paso.accion == "musica_repetir"]
        self.assertEqual(ciclo, [anuncios_musica.TEXTO_REPETIR_TODO,
                                 anuncios_musica.TEXTO_REPETIR_TEMA,
                                 anuncios_musica.TEXTO_REPETIR_NO])

    def test_empieza_diciendo_y_termina_sonando(self):
        pasos = musica_globales.PASOS
        self.assertEqual(pasos[0].accion, "musica_que_suena")
        self.assertEqual(pasos[-1].accion, "musica_play")
        self.assertIsNone(pasos[-1].esperado)


class TestResolverActivacionConTomadas(unittest.TestCase):

    def _res(self):
        class Res:
            def __init__(self):
                self.fallos = []
                self.notas = []
                self.no_probados = []
            def fallo(self, texto):
                self.fallos.append(texto)
            def nota(self, texto):
                self.notas.append(texto)
            def no_probado(self, texto):
                self.no_probados.append(texto)
        return Res()

    def _propia_con_fallo(self, lista):
        from bellbird.music import anuncios as anuncios_musica
        anuncio = anuncios_musica.TEXTO_ATAJOS_GLOBALES_FALLO.format(
            lista=lista)
        class Propia:
            anuncios = [{"texto": anuncio}]
        return Propia()

    def test_tomada_de_musica_es_fallo_y_sigue(self):
        from bellbird.music import anuncios as anuncios_musica
        from bellbird.ui.atajos_captura import atajo_legible
        nombre = atajo_legible("ctrl+alt+right")
        res = self._res()
        sigue = musica_globales._resolver_activacion(
            self._propia_con_fallo(nombre), res, 0,
            anuncios_musica.TEXTO_ATAJOS_GLOBALES_ACTIVOS)
        self.assertTrue(sigue)
        self.assertEqual(len(res.fallos), 1)
        self.assertIn(nombre, res.fallos[0])
        self.assertEqual(res.no_probados, [])

    def test_tomada_de_que_suena_tambien_es_fallo_y_sigue(self):
        from bellbird.music import anuncios as anuncios_musica
        nombre = musica_globales.NOMBRE_QUE_SUENA
        res = self._res()
        sigue = musica_globales._resolver_activacion(
            self._propia_con_fallo(nombre), res, 0,
            anuncios_musica.TEXTO_ATAJOS_GLOBALES_ACTIVOS)
        self.assertTrue(sigue)
        self.assertEqual(len(res.fallos), 1)
        self.assertIn(nombre, res.fallos[0])
        self.assertEqual(res.no_probados, [])


if __name__ == "__main__":
    unittest.main()
