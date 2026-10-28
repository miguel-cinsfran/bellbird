"""Pruebas de identificación segura de la ventana del smoke."""

import os
import sys
import unittest
from types import SimpleNamespace

from scripts.smoke_test import (RAIZ, _MINIMO_CONTROLES, _MUTEX_INSTANCIA,
                                _recorrer, arbol_sigue_vivo,
                                es_descendiente, hay_otra_instancia_abierta,
                                interactivos_sin_nombre, mapa_padres_procesos,
                                mensaje_fallo_controles, mensaje_fallo_ventana,
                                ventana_es_de_la_aplicacion)


class VentanaEsDeLaAplicacionTest(unittest.TestCase):

    def test_acepta_titulo_y_python(self):
        self.assertTrue(ventana_es_de_la_aplicacion("Bellbird v2.5.1", "python.exe"))

    def test_acepta_ejecutable_de_la_app(self):
        self.assertTrue(ventana_es_de_la_aplicacion("Bellbird v2.5.1", "bellbird.exe"))

    def test_rechaza_proceso_viejo(self):
        self.assertFalse(ventana_es_de_la_aplicacion("Bellbird v2.5.1", "ytchattts.exe"))

    def test_rechaza_explorador_con_titulo_correcto(self):
        self.assertFalse(ventana_es_de_la_aplicacion(
            "Bellbird - para probar", "explorer.exe"))

    def test_rechaza_titulo_distinto_con_proceso_correcto(self):
        self.assertFalse(ventana_es_de_la_aplicacion("Otra ventana", "python.exe"))

    def test_rechaza_titulo_viejo(self):
        self.assertFalse(ventana_es_de_la_aplicacion("YTChat TTS v2.5.1", "python.exe"))

    def test_compara_el_proceso_sin_mayusculas(self):
        self.assertTrue(ventana_es_de_la_aplicacion("Bellbird v2.5.1", "PYTHONW.EXE"))


class MutexInstanciaTest(unittest.TestCase):

    @unittest.skipUnless(sys.platform == "win32",
                         "OpenMutexW solo existe en Windows")
    def test_detecta_un_mutex_real_y_deja_de_verlo_al_cerrarlo(self):
        import ctypes
        import uuid

        nombre = f"YTChatTTS_Prueba_{os.getpid()}_{uuid.uuid4().hex}"
        self.assertFalse(hay_otra_instancia_abierta(nombre))

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                          ctypes.c_wchar_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.CreateMutexW(None, False, nombre)
        self.assertTrue(handle)
        try:
            self.assertTrue(hay_otra_instancia_abierta(nombre))
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))

        self.assertFalse(hay_otra_instancia_abierta(nombre))

    def test_el_nombre_coincide_con_el_de_main(self):
        with open(os.path.join(RAIZ, "main.py"), encoding="utf-8") as archivo:
            fuente = archivo.read()

        self.assertIn(_MUTEX_INSTANCIA, fuente)


class InteractivosSinNombreTest(unittest.TestCase):

    def test_devuelve_solo_los_interactivos_sin_nombre(self):
        controles = [
            ("Button", ""),
            ("Edit", "Escribir mensaje"),
            ("Text", ""),
            ("Pane", ""),
            ("List", ""),
        ]

        self.assertEqual(interactivos_sin_nombre(controles), ["Button", "List"])

    def test_ignora_interactivo_con_nombre(self):
        self.assertEqual(interactivos_sin_nombre([("CheckBox", "Activar")]), [])

    def test_ignora_no_interactivo_sin_nombre(self):
        self.assertEqual(interactivos_sin_nombre([("Text", "")]), [])

    def test_acepta_lista_vacia(self):
        self.assertEqual(interactivos_sin_nombre([]), [])


class MinimoControlesTest(unittest.TestCase):

    def test_el_piso_es_veinte(self):
        self.assertEqual(_MINIMO_CONTROLES, 20)

    def test_diecinueve_controles_no_alcanzan(self):
        self.assertIsNotNone(mensaje_fallo_controles(19))

    def test_veinte_controles_alcanzan(self):
        self.assertIsNone(mensaje_fallo_controles(20))

    def test_el_caso_del_defecto_falla(self):
        mensaje = mensaje_fallo_controles(6)

        self.assertIsNotNone(mensaje)
        self.assertIn("6", mensaje)
        self.assertIn(str(_MINIMO_CONTROLES), mensaje)


class ElementoFalso:
    def __init__(self, tipo, nombre, descendientes=()):
        self._info = SimpleNamespace(control_type=tipo, name=nombre)
        self._descendientes = list(descendientes)

    @property
    def element_info(self):
        return self._info

    def descendants(self):
        return self._descendientes


class ElementoConInfoFallido(ElementoFalso):

    @property
    def element_info(self):
        raise RuntimeError("información inaccesible")


class ElementoConDescendientesFallidos(ElementoFalso):

    def descendants(self):
        raise RuntimeError("árbol inaccesible")


class RecorrerTest(unittest.TestCase):

    def test_devuelve_raiz_y_descendientes_en_orden(self):
        boton = ElementoFalso("Button", "Conectar")
        texto = ElementoFalso("Text", "Estado")
        raiz = ElementoFalso("Window", "YTChat TTS", [boton, texto])

        self.assertEqual(_recorrer(raiz), [
            ("Window", "YTChat TTS"),
            ("Button", "Conectar"),
            ("Text", "Estado"),
        ])

    def test_salta_descendiente_cuya_informacion_falla(self):
        boton = ElementoFalso("Button", "Conectar")
        raro = ElementoConInfoFallido("Edit", "")
        raiz = ElementoFalso("Window", "YTChat TTS", [raro, boton])

        self.assertEqual(_recorrer(raiz), [
            ("Window", "YTChat TTS"),
            ("Button", "Conectar"),
        ])

    def test_devuelve_lista_vacia_si_no_puede_recorrer_descendientes(self):
        raiz = ElementoConDescendientesFallidos("Window", "YTChat TTS")

        self.assertEqual(_recorrer(raiz), [])

    def test_quita_espacios_del_nombre(self):
        raiz = ElementoFalso("Window", "   ")

        self.assertEqual(_recorrer(raiz), [("Window", "")])


class EsDescendienteTest(unittest.TestCase):

    def test_la_raizmisma_es_del_arbol(self):
        self.assertTrue(es_descendiente(100, 100, {}))

    def test_hijo_directo(self):
        self.assertTrue(es_descendiente(101, 100, {101: 100}))

    def test_nieto(self):
        self.assertTrue(es_descendiente(102, 100, {101: 100, 102: 101}))

    def test_proceso_ajeno(self):
        self.assertFalse(es_descendiente(201, 100, {201: 200, 101: 100}))

    def test_pid_sin_entrada_en_el_mapa(self):
        self.assertFalse(es_descendiente(999, 100, {101: 100}))

    def test_ciclo_en_el_mapa_no_se_cuelga(self):
        self.assertFalse(es_descendiente(1, 99, {1: 2, 2: 1}))


class MensajeFalloVentanaTest(unittest.TestCase):

    def test_proceso_terminado(self):
        mensaje = mensaje_fallo_ventana(False, [])

        self.assertEqual(mensaje, "la aplicación terminó sin abrir la ventana")

    def test_proceso_vivo_sigue_arrancando(self):
        mensaje = mensaje_fallo_ventana(True, [])

        self.assertEqual(mensaje, "la ventana no apareció en 40 s y la "
                                 "aplicación sigue arrancando")

    def test_proceso_vivo_con_ventanas_ajenas(self):
        mensaje = mensaje_fallo_ventana(True, ["explorer.exe", "proceso 1234"])

        self.assertIn("sigue arrancando", mensaje)
        self.assertIn("explorer.exe", mensaje)
        self.assertIn("proceso 1234", mensaje)


class ArbolSigueVivoTest(unittest.TestCase):

    def test_raiz_en_la_foto(self):
        self.assertTrue(arbol_sigue_vivo(100, {100: 1, 101: 100}))

    def test_solo_un_descendiente_vivo(self):
        self.assertTrue(arbol_sigue_vivo(100, {101: 100, 102: 101}))

    def test_arbol_muerto(self):
        self.assertFalse(arbol_sigue_vivo(100, {200: 1, 201: 200}))

    def test_sin_foto_supone_vivo(self):
        self.assertTrue(arbol_sigue_vivo(100, {}))


class MapaPadresProcesosTest(unittest.TestCase):

    def test_el_mapa_real_trae_al_propio_interprete(self):
        mapa = mapa_padres_procesos()

        self.assertIn(os.getpid(), mapa)
        self.assertEqual(mapa[os.getpid()], os.getppid())
