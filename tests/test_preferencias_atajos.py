"""Pseudotraducción de la página Atajos de Preferencias.

Abre ventanas.
Comprueba que ningún texto visible propio de la página queda sin pasar
por gettext.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guyrapu.core import config
from guyrapu.ui import gui_preferencias
from guyrapu.voice import motores
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import app_de_prueba, destruir


# Textos que arma otro módulo y esta página solo muestra, con valores de
# fábrica. La nota (`atajos_captura.NOTA_PAGINA`), los títulos de grupo de
# `guyrapu/core/atajos.py` (ATAJOS_GRUPOS) y las etiquetas de los botones
# (`etiqueta_de_accion` y `etiqueta_boton` de `atajos_captura`) ya salen
# marcadas porque esta página las traduce. La comparación es exacta en los
# dos sentidos: falla si aparece un texto nuevo sin envolver y si un
# pendiente ya no está en el recorrido.
PENDIENTES_ATAJOS = ()


# Wrap parte la nota en varias líneas: se comparan los espacios normalizados.
def _normalizar(texto): return " ".join(texto.split())


class TestAtajosSinTextosSinEnvolver(unittest.TestCase):
    def setUp(self):
        self.app = app_de_prueba()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name)
        (self.ruta / "config.ini").write_text(config._CONFIG_FALLBACK,
                                              encoding="utf-8")
        parche = redirigir_rutas(self.ruta)
        parche.__enter__()
        self.addCleanup(parche.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces",
                               return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def _pagina(self, dialogo):
        return next(dialogo.nb.GetPage(i)
                    for i in range(dialogo.nb.GetPageCount())
                    if dialogo.nb.GetPage(i).GetName() == "PagAtajos")

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(self._pagina(dialogo))

        self.assertEqual(sorted(map(_normalizar, sin_marcar)),
                         sorted(map(_normalizar, PENDIENTES_ATAJOS)))


if __name__ == "__main__":
    unittest.main()
