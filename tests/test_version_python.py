"""La suite corre con la versión de Python que fija .python-version."""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_VERSION = RAIZ / ".python-version"


class VersionPythonTest(unittest.TestCase):
    def test_la_suite_corre_con_la_version_del_repositorio(self):
        esperada = ARCHIVO_VERSION.read_text(encoding="utf-8").strip()
        actual = "%d.%d" % sys.version_info[:2]
        self.assertEqual(
            actual,
            esperada,
            "La suite corre con Python %s y .python-version pide %s"
            % (actual, esperada),
        )
