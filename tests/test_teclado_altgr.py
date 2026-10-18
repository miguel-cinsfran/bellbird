"""Pruebas de la consulta de AltGr con el teclado real de Windows."""

import ctypes
import sys
import unittest
from unittest import mock

from ytchat.ui import teclado_altgr


def _distribucion_disponible(identificador: str) -> bool:
    try:
        user32 = ctypes.windll.user32
        user32.LoadKeyboardLayoutW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
        return bool(user32.LoadKeyboardLayoutW(identificador, 0))
    except Exception:
        return False


@unittest.skipUnless(sys.platform == "win32", "Requiere Windows")
class TestCaracterAltgrReal(unittest.TestCase):

    def _exigir_distribucion(self, identificador: str) -> None:
        if not _distribucion_disponible(identificador):
            self.skipTest(
                f"La distribución {identificador} no está en esta máquina")

    def test_q_latinoamericano_escribe_arroba(self):
        self._exigir_distribucion("0000080A")
        self.assertEqual(
            teclado_altgr.caracter_altgr("q", "0000080A"), "@")

    def test_t_no_escribe_nada_en_ninguna_de_las_dos(self):
        for identificador in ("0000080A", "0000040A"):
            self._exigir_distribucion(identificador)
            with self.subTest(distribucion=identificador):
                self.assertEqual(
                    teclado_altgr.caracter_altgr("t", identificador), "")

    def test_e_espanol_escribe_algo(self):
        self._exigir_distribucion("0000040A")
        self.assertNotEqual(
            teclado_altgr.caracter_altgr("e", "0000040A"), "")


class TestCaracterAltgrDobles(unittest.TestCase):

    def test_si_to_unicode_ex_lanza_devuelve_vacio(self):
        falso = mock.Mock()
        falso.ToUnicodeEx.side_effect = OSError("falló")
        with mock.patch.object(teclado_altgr, "_obtener_user32",
                               return_value=falso), \
                mock.patch.object(teclado_altgr.sys, "platform", "win32"):
            self.assertEqual(teclado_altgr.caracter_altgr("q"), "")


if __name__ == "__main__":
    unittest.main()
