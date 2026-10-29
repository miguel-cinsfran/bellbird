"""Pruebas del vigía de la carpeta de música (vigia_carpeta.py).

Usan watchdog de verdad sobre una carpeta temporal, sin dobles y sin wx:
los cambios se hacen en el disco y se espera la llamada a `al_cambiar`.
"""

import os
import tempfile
import threading
import unittest
from pathlib import Path

from bellbird.music.vigia_carpeta import VigiaCarpeta


def _norm(rutas):
    return {os.path.normcase(str(r)) for r in rutas}


class TestVigiaCarpeta(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        (self.raiz / "a.mp3").write_bytes(b"a")
        (self.raiz / "sub").mkdir()
        (self.raiz / "sub" / "b.ogg").write_bytes(b"b")
        self.llamadas = []
        self.llego = threading.Event()
        self.vigia = None

    def tearDown(self):
        if self.vigia is not None:
            self.vigia.parar()
        self.tmp.cleanup()

    def _al_cambiar(self, agregadas, quitadas):
        self.llamadas.append((_norm(agregadas), _norm(quitadas)))
        self.llego.set()

    def _origen(self, *partes):
        return os.path.normcase(os.path.abspath(self.raiz / Path(*partes)))

    def test_una_tanda_con_crear_borrar_mover_y_carpeta_nueva(self):
        self.vigia = VigiaCarpeta(str(self.raiz), self._al_cambiar,
                                   espera_s=0.5)
        self.vigia.arrancar()
        (self.raiz / "c.mp3").write_bytes(b"c")
        (self.raiz / "a.mp3").unlink()
        (self.raiz / "sub2").mkdir()
        (self.raiz / "sub" / "b.ogg").rename(self.raiz / "sub2" / "c.ogg")
        (self.raiz / "pack").mkdir()
        (self.raiz / "pack" / "d.mp3").write_bytes(b"d")
        (self.raiz / "pack" / "e.ogg").write_bytes(b"e")
        (self.raiz / "notas.txt").write_text("no es audio", encoding="utf-8")
        fugaz = self.raiz / "fugaz.mp3"
        fugaz.write_bytes(b"z")
        fugaz.unlink()
        self.assertTrue(self.llego.wait(timeout=8))
        self.llego.clear()
        self.assertFalse(self.llego.wait(timeout=1.5))
        self.assertEqual(len(self.llamadas), 1)
        agregadas, quitadas = self.llamadas[0]
        self.assertEqual(
            agregadas,
            {self._origen("c.mp3"), self._origen("sub2", "c.ogg"),
             self._origen("pack", "d.mp3"), self._origen("pack", "e.ogg")})
        self.assertEqual(
            quitadas,
            {self._origen("a.mp3"), self._origen("sub", "b.ogg")})

    def test_parar_deja_de_llamar(self):
        self.vigia = VigiaCarpeta(str(self.raiz), self._al_cambiar,
                                   espera_s=0.3)
        self.vigia.arrancar()
        self.vigia.parar()
        (self.raiz / "nuevo.mp3").write_bytes(b"n")
        self.assertFalse(self.llego.wait(timeout=1.5))
        self.assertEqual(self.llamadas, [])

    def test_carpeta_inexistente_no_vigila_y_no_lanza(self):
        self.vigia = VigiaCarpeta(str(self.raiz / "no-existe"),
                                   self._al_cambiar, espera_s=0.2)
        self.vigia.arrancar()  # no debe lanzar
        self.assertFalse(self.llego.wait(timeout=1))
        self.assertEqual(self.llamadas, [])

    def test_parar_sin_arrancar_no_lanza(self):
        self.vigia = VigiaCarpeta(str(self.raiz), self._al_cambiar)
        self.vigia.parar()  # no debe lanzar


if __name__ == "__main__":
    unittest.main()
