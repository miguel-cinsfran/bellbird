"""Pruebas del lector de pantalla por Prism, con contexto falso."""

import sys
import unittest
from unittest import mock

from prism import BackendId, PrismError
from prism.common import PrismNotImplementedError

from ytchat.voice import lector


class BackendFalso:

    def __init__(self, nombre, falla_voz=False, error_braille=None):
        self.name = nombre
        self.hablado = []
        self.brailleado = []
        self._falla_voz = falla_voz
        self._error_braille = error_braille

    def speak(self, texto, interrupt=False):
        if self._falla_voz:
            raise PrismError("el lector se cayó")
        self.hablado.append((texto, interrupt))

    def braille(self, texto):
        if self._error_braille is not None:
            raise self._error_braille
        self.brailleado.append(texto)


class ContextoFalso:

    def __init__(self, crear):
        self.creados = []
        self._crear = crear

    def create(self, identificador):
        self.creados.append(identificador)
        return self._crear(identificador)


class RelojFalso:

    def __init__(self, t=0.0):
        self.t = t

    def monotonic(self):
        return self.t

    def avanzar(self, segundos):
        self.t += segundos


def _solo(nombre_backend, backend):
    def crear(identificador):
        if identificador.name == nombre_backend:
            return backend
        raise PrismError("no disponible")
    return crear


def _no_disponible(identificador):
    raise PrismError("no disponible")


def _nombres_pedidos(contexto):
    return [identificador.name for identificador in contexto.creados]


class TestDeteccion(unittest.TestCase):

    def test_elige_el_primer_lector_en_orden_sin_pedir_motores_de_voz(self):
        backend = BackendFalso("JAWS")
        contexto = ContextoFalso(_solo("JAWS", backend))

        obj = lector.Lector(fabrica_contexto=lambda: contexto)

        self.assertEqual(_nombres_pedidos(contexto), ["NVDA", "JAWS"])
        self.assertEqual(_nombres_pedidos(contexto), list(lector.LECTORES[:2]))
        self.assertEqual(obj.nombre(), "JAWS")
        for prohibido in ("ONE_CORE", "SAPI", "UIA"):
            self.assertNotIn(prohibido, _nombres_pedidos(contexto))

    def test_la_lista_de_lectores_no_trae_motores_de_voz(self):
        for prohibido in ("ONE_CORE", "SAPI", "UIA"):
            self.assertNotIn(prohibido, lector.LECTORES)

    def test_los_ids_pedidos_son_los_de_la_lista_de_lectores(self):
        contexto = ContextoFalso(_no_disponible)
        lector.Lector(fabrica_contexto=lambda: contexto)
        self.assertEqual(_nombres_pedidos(contexto), list(lector.LECTORES))
        self.assertEqual(
            [identificador for identificador in contexto.creados],
            [getattr(BackendId, nombre) for nombre in lector.LECTORES])


class TestReintentoYRecuperacion(unittest.TestCase):

    def test_sin_lector_es_noop_y_reintenta_cada_cinco_segundos(self):
        reloj = RelojFalso(0.0)
        contexto = ContextoFalso(_no_disponible)
        obj = lector.Lector(fabrica_contexto=lambda: contexto, reloj=reloj.monotonic)
        self.assertEqual(len(contexto.creados), len(lector.LECTORES))
        contexto.creados.clear()

        obj.speak("hola")
        self.assertEqual(contexto.creados, [])

        reloj.avanzar(lector.REINTENTO_S - 0.1)
        obj.speak("hola")
        self.assertEqual(contexto.creados, [])

        reloj.avanzar(0.1)
        obj.speak("hola")
        self.assertEqual(len(contexto.creados), len(lector.LECTORES))

    def test_reintenta_una_sola_vez_en_un_backend_nuevo(self):
        caido = BackendFalso("NVDA", falla_voz=True)
        nuevo = BackendFalso("NVDA")
        llamadas = []

        def crear(identificador):
            if identificador.name != "NVDA":
                raise PrismError("no disponible")
            llamadas.append(identificador)
            return caido if len(llamadas) == 1 else nuevo

        contexto = ContextoFalso(crear)
        obj = lector.Lector(fabrica_contexto=lambda: contexto)

        obj.speak("hola", interrupt=True)

        self.assertEqual(nuevo.hablado, [("hola", True)])
        self.assertEqual(caido.hablado, [])
        self.assertEqual(len(llamadas), 2)

    def test_no_reintenta_mas_de_una_vez_aunque_el_nuevo_tambien_falle(self):
        caidos = []

        def crear(identificador):
            if identificador.name != "NVDA":
                raise PrismError("no disponible")
            backend = BackendFalso("NVDA", falla_voz=True)
            caidos.append(backend)
            return backend

        contexto = ContextoFalso(crear)
        obj = lector.Lector(fabrica_contexto=lambda: contexto)

        with mock.patch.object(lector.logger, "warning") as registrar:
            obj.speak("hola")

        self.assertEqual(len(caidos), 2)
        registrar.assert_called()

    def test_sin_backend_el_braille_es_noop_y_no_detecta(self):
        contexto = ContextoFalso(_no_disponible)
        obj = lector.Lector(fabrica_contexto=lambda: contexto)
        contexto.creados.clear()

        obj.braille("hola")

        self.assertEqual(contexto.creados, [])


class TestTexto(unittest.TestCase):

    def _lector_con(self, backend):
        contexto = ContextoFalso(_solo(backend.name, backend))
        return lector.Lector(fabrica_contexto=lambda: contexto)

    def test_texto_vacio_o_de_espacios_no_llega_al_backend(self):
        backend = BackendFalso("NVDA")
        obj = self._lector_con(backend)

        obj.speak("")
        obj.speak("   ")
        obj.braille("")
        obj.braille("  ")

        self.assertEqual(backend.hablado, [])
        self.assertEqual(backend.brailleado, [])

    def test_quita_el_caracter_nulo(self):
        backend = BackendFalso("NVDA")
        obj = self._lector_con(backend)

        obj.speak("ho\x00la")
        obj.braille("bra\x00ille")

        self.assertEqual(backend.hablado, [("hola", False)])
        self.assertEqual(backend.brailleado, ["braille"])

    def test_braille_sin_implementacion_no_relanza(self):
        backend = BackendFalso(
            "NVDA", error_braille=PrismNotImplementedError("sin braille"))
        obj = self._lector_con(backend)

        obj.braille("hola")

        self.assertEqual(backend.brailleado, [])


class TestSinPrism(unittest.TestCase):

    def test_sin_prism_queda_inactivo_con_una_sola_advertencia(self):
        with mock.patch.dict(sys.modules, {"prism": None}), \
                mock.patch.object(lector.logger, "warning") as registrar:
            obj = lector.Lector()
            obj.speak("hola")
            obj.braille("hola")
            self.assertIsNone(obj.nombre())

        registrar.assert_called_once()


class TestPrismReal(unittest.TestCase):

    def test_el_lector_real_se_construye_y_el_texto_vacio_no_suena(self):
        obj = lector.Lector()
        nombre = obj.nombre()
        self.assertTrue(nombre is None or isinstance(nombre, str))
        obj.speak("")
