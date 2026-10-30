"""Pruebas de que construir.bat no borra carpetas versionadas."""

import fnmatch
import re
import subprocess
import unittest
from pathlib import Path


def _carpetas_versionadas(base):
    salida = subprocess.run(
        ["git", "ls-files"], cwd=str(base),
        capture_output=True, text=True, check=True,
    )
    carpetas = set()
    for linea in salida.stdout.splitlines():
        nombre = linea.strip()
        if not nombre:
            continue
        primero = nombre.split("/")[0]
        if (base / primero).is_dir():
            carpetas.add(primero)
    return sorted(carpetas)


def _objetivo_rmdir(linea):
    patron_for = re.search(
        r'for\s+/d\s+%%\w+\s+in\s*\(\s*"([^"]+)"', linea, re.IGNORECASE,
    )
    posicion = linea.lower().find("rmdir")
    if posicion < 0:
        return None
    detras = linea[posicion + len("rmdir"):]
    citado = re.search(r'"([^"]+)"', detras)
    if citado and "%%" in citado.group(1) and patron_for:
        return patron_for.group(1)
    if citado:
        return citado.group(1)
    if patron_for and "%%" in detras:
        return patron_for.group(1)
    return None


class TestConstruirLimpieza(unittest.TestCase):

    def test_ningun_rmdir_apunta_a_carpeta_versionada(self):
        base = Path(__file__).parents[1]
        lineas = (base / "construir.bat").read_text(encoding="utf-8").splitlines()
        carpetas = _carpetas_versionadas(base)
        self.assertTrue(carpetas)
        for numero, linea in enumerate(lineas, 1):
            if "rmdir" not in linea.lower():
                continue
            objetivo = _objetivo_rmdir(linea)
            if objetivo is None:
                continue
            if objetivo.upper().startswith("%OUT%"):
                continue
            for carpeta in carpetas:
                coincide = fnmatch.fnmatchcase(carpeta.lower(), objetivo.lower())
                self.assertFalse(
                    coincide,
                    f"construir.bat:{numero} borra {objetivo!r} "
                    f"que coincide con la carpeta versionada {carpeta!r}",
                )


if __name__ == "__main__":
    unittest.main()
