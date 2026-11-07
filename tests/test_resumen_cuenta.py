"""Pruebas del resumen de Cuenta y de la fila de un perfil de Restream.

Es lógica pura: no abre ventanas ni sale a la red.
"""

import unittest
from types import SimpleNamespace

from guyrapu.restream import resumen_cuenta
from guyrapu.restream.perfiles import Perfil


def _canal(identificador, texto, activo=True):
    return SimpleNamespace(id=identificador, texto=texto, activo=activo)


def _perfil(nombre="Canal", canales=(1,), orientacion="horizontal"):
    return Perfil(nombre=nombre, canales=canales, orientacion=orientacion)


class TestResumenCuenta(unittest.TestCase):

    def test_sin_cuenta_dice_el_texto_largo(self):
        self.assertEqual(
            "Sin cuenta de Restream conectada. Restream transmite a varias "
            "plataformas a la vez: conecta la cuenta para elegir los destinos "
            "y armar perfiles.",
            resumen_cuenta.resumen(False, "", [], 0))

    def test_con_cuenta_dice_nombre_cantidades_y_plurales(self):
        destinos = [_canal(1, "TikTok: uno"), _canal(2, "YouTube: dos",
                                                     activo=False)]
        self.assertEqual(
            "Cuenta conectada: Ana.\n2 destinos, 1 activo. 3 perfiles.",
            resumen_cuenta.resumen(True, "Ana", destinos, 3))

    def test_con_cuenta_singulares(self):
        self.assertEqual(
            "Cuenta conectada: Ana.\n1 destino, 1 activo. 1 perfil.",
            resumen_cuenta.resumen(
                True, "Ana", [_canal(1, "TikTok: uno")], 1))

    def test_sin_nombre_no_inventa_uno(self):
        self.assertEqual(
            "Cuenta de Restream conectada.\n1 destino, 1 activo. 1 perfil.",
            resumen_cuenta.resumen(
                True, "", [_canal(1, "TikTok: uno")], 1))

    def test_sin_destinos_dice_el_paso_que_falta(self):
        self.assertEqual(
            "Cuenta conectada: Ana.\n0 destinos, 0 activos. 0 perfiles.\n"
            "Todavía no hay destinos. Agrégalos en la pestaña Destinos.",
            resumen_cuenta.resumen(True, "Ana", [], 0))

    def test_con_destinos_y_sin_perfiles_dice_el_paso_que_falta(self):
        self.assertEqual(
            "Cuenta conectada: Ana.\n1 destino, 1 activo. 0 perfiles.\n"
            "Todavía no hay perfiles. Créalos en la pestaña Perfiles.",
            resumen_cuenta.resumen(
                True, "Ana", [_canal(1, "TikTok: uno")], 0))

    def test_con_destinos_y_perfiles_no_dice_ningun_paso(self):
        texto = resumen_cuenta.resumen(
            True, "Ana", [_canal(1, "TikTok: uno")], 1)
        self.assertNotIn("Todavía no hay", texto)

    def test_suma_la_linea_de_youtube_y_los_errores(self):
        texto = resumen_cuenta.resumen(
            True, "Ana", [_canal(1, "TikTok: uno")], 1,
            youtube="YouTube en Restream: uno.",
            errores=("No se pudieron leer los destinos.", ""))
        self.assertEqual(
            "Cuenta conectada: Ana.\n1 destino, 1 activo. 1 perfil.\n"
            "YouTube en Restream: uno.\n"
            "No se pudieron leer los destinos.",
            texto)


class TestFilaPerfil(unittest.TestCase):

    def test_nombra_los_destinos_en_orden(self):
        perfil = _perfil(canales=(1, 2))
        self.assertEqual(
            "Canal, horizontal: TikTok: uno, YouTube: dos",
            resumen_cuenta.fila_perfil(
                perfil, {1: "TikTok: uno", 2: "YouTube: dos"}, True))

    def test_sin_destinos_lo_dice(self):
        self.assertEqual(
            "Canal, vertical, sin destinos",
            resumen_cuenta.fila_perfil(
                _perfil(orientacion="vertical", canales=()), {}, True))

    def test_un_destino_faltante(self):
        self.assertEqual(
            "Canal, horizontal: TikTok: uno, falta un destino",
            resumen_cuenta.fila_perfil(
                _perfil(canales=(1, 2)), {1: "TikTok: uno"}, True))

    def test_dos_destinos_faltantes(self):
        self.assertEqual(
            "Canal, horizontal: TikTok: uno, faltan 2 destinos",
            resumen_cuenta.fila_perfil(
                _perfil(canales=(1, 2, 3)), {1: "TikTok: uno"}, True))

    def test_sin_destinos_leidos_no_cuenta_faltantes(self):
        self.assertEqual(
            "Canal, horizontal",
            resumen_cuenta.fila_perfil(_perfil(canales=(1, 2)), {}, False))

    def test_todos_los_destinos_faltantes(self):
        self.assertEqual(
            "Canal, horizontal, faltan 2 destinos",
            resumen_cuenta.fila_perfil(_perfil(canales=(1, 2)), {}, True))


if __name__ == "__main__":
    unittest.main()
