"""Pruebas de la división de música real, sin ventanas ni sonido."""

import inspect
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "qa"))

import escenarios_musica  # noqa: E402
import musica_real  # noqa: E402
import musica_real_cola  # noqa: E402
import musica_real_enlaces  # noqa: E402

ETAPAS = ("a", "b", "c", "d", "e", "f", "f2", "g", "h", "i", "j",
          "k", "l", "m", "n")


class TestSeImportaSinWx(unittest.TestCase):

    def test_los_modulos_no_importan_wx(self):
        codigo = (
            "import sys\n"
            f"sys.path.insert(0, {str(RAIZ)!r})\n"
            f"sys.path.insert(0, {str(RAIZ / 'qa')!r})\n"
            "import musica_real, musica_real_preparar, musica_real_cola\n"
            "import musica_real_enlaces, escenarios_musica\n"
            "assert 'wx' not in sys.modules, 'los módulos importaron wx'\n"
        )
        resultado = subprocess.run([sys.executable, "-B", "-c", codigo],
                                   capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_las_etapas_estan_en_su_modulo(self):
        for nombre in ETAPAS[:11]:
            self.assertTrue(callable(getattr(musica_real_cola,
                                               f"etapa_{nombre}")))
        for nombre in ETAPAS[11:]:
            self.assertTrue(callable(getattr(musica_real_enlaces,
                                               f"etapa_{nombre}")))


class TestFirmaYRegistro(unittest.TestCase):

    def test_mantiene_la_firma_y_el_registro_del_banco(self):
        firma = inspect.signature(escenarios_musica.escenario_musica_real)
        self.assertEqual(list(firma.parameters), ["app", "args", "res"])

        import conducir
        self.assertIs(conducir.ESCENARIOS["musica_real"],
                      escenarios_musica.escenario_musica_real)


class _RecorridoDoble:

    def __init__(self, app, args, res):
        self.app = app
        self.args = args
        self.res = res


def _correr(corta_en=None, revienta_en=None):
    llamadas = []

    def etapa(nombre):
        def correr(rec):
            llamadas.append(nombre)
            if nombre == corta_en:
                raise musica_real._Corte()
            if nombre == revienta_en:
                raise RuntimeError("revienta")
        return correr

    with ExitStack() as pila:
        pila.enter_context(mock.patch.object(
            escenarios_musica, "RecorridoMusica", _RecorridoDoble))
        pila.enter_context(mock.patch.object(
            escenarios_musica, "preparar_origen", return_value=["tema"]))
        pila.enter_context(mock.patch.object(
            escenarios_musica, "preparar_datos"))
        pila.enter_context(mock.patch.object(
            escenarios_musica, "restaurar",
            side_effect=lambda rec: llamadas.append("restaurar")))
        for nombre in ETAPAS:
            pila.enter_context(mock.patch.object(
                escenarios_musica, f"etapa_{nombre}", etapa(nombre)))
        escenarios_musica.escenario_musica_real(
            mock.Mock(), mock.Mock(), mock.Mock())
    return llamadas


class TestOrdenDeEtapas(unittest.TestCase):

    def test_las_etapas_corren_en_orden(self):
        self.assertEqual(_correr(), list(ETAPAS) + ["restaurar"])

    def test_un_corte_de_etapa_restaura_igual(self):
        self.assertEqual(_correr(corta_en="c"),
                         ["a", "b", "c", "restaurar"])

    def test_una_excepcion_de_etapa_restaura_igual(self):
        self.assertEqual(_correr(revienta_en="h"),
                         ["a", "b", "c", "d", "e", "f", "f2", "g", "h",
                          "restaurar"])


if __name__ == "__main__":
    unittest.main()
