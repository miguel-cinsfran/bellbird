"""Prueba real del resguardo de claves de IA en Windows."""

import os
import unittest

from ytchat.ai import claves

PREFIJO_PRUEBA = "Bellbird/ia-prueba/"


@unittest.skipUnless(os.name == "nt", "solo Windows")
class PruebaClaves(unittest.TestCase):
    def test_guardar_y_leer_devuelve_la_misma(self):
        proveedor = "prueba-lectura"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        texto = "clave con ñ, tildes áéí y \U0001F511"
        claves.guardar(proveedor, texto, prefijo=PREFIJO_PRUEBA)
        self.assertEqual(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA),
                         texto)

    def test_guardar_dos_veces_deja_la_segunda(self):
        proveedor = "prueba-reemplazo"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        claves.guardar(proveedor, "primera", prefijo=PREFIJO_PRUEBA)
        claves.guardar(proveedor, "segunda", prefijo=PREFIJO_PRUEBA)
        self.assertEqual(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA),
                         "segunda")

    def test_leer_y_borrar_lo_inexistente(self):
        proveedor = "prueba-ausente"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        self.assertIsNone(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA))
        self.assertFalse(claves.borrar(proveedor, prefijo=PREFIJO_PRUEBA))

    def test_borrar_lo_existente(self):
        proveedor = "prueba-borrado"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        claves.guardar(proveedor, "temporal", prefijo=PREFIJO_PRUEBA)
        self.assertTrue(claves.borrar(proveedor, prefijo=PREFIJO_PRUEBA))
        self.assertIsNone(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA))

    def test_clave_con_bordes_vuelve_sin_ellos(self):
        proveedor = "prueba-bordes"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        claves.guardar(proveedor, "  secreta  ", prefijo=PREFIJO_PRUEBA)
        self.assertEqual(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA),
                         "secreta")

    def test_claves_no_admitidas_dan_valor(self):
        proveedor = "prueba-limites"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        for texto in ("", "   ", "a" * 1281):
            with self.subTest(texto=texto[:8]):
                with self.assertRaises(ValueError):
                    claves.guardar(proveedor, texto,
                                   prefijo=PREFIJO_PRUEBA)
        self.assertIsNone(claves.leer(proveedor, prefijo=PREFIJO_PRUEBA))
        for malo in ("", "con/barra"):
            with self.subTest(malo=malo):
                with self.assertRaises(ValueError):
                    claves.guardar(malo, "temporal",
                                   prefijo=PREFIJO_PRUEBA)
                with self.assertRaises(ValueError):
                    claves.leer(malo, prefijo=PREFIJO_PRUEBA)
                with self.assertRaises(ValueError):
                    claves.borrar(malo, prefijo=PREFIJO_PRUEBA)

    def test_prefijo_de_prueba_no_toca_el_real(self):
        proveedor = "prueba-aislada"
        self.addCleanup(claves.borrar, proveedor, PREFIJO_PRUEBA)
        claves.guardar(proveedor, "temporal", prefijo=PREFIJO_PRUEBA)
        self.assertIsNone(claves.leer(proveedor))


if __name__ == "__main__":
    unittest.main()
