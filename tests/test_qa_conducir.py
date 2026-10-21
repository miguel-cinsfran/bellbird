"""Pruebas de la lógica pura del banco de QA, sin abrir ventanas ni la app.

Se importa `qa/conducir.py` como `tests/test_qa_directo_real.py` importa el
suyo: por ruta, para no depender de que `qa/` sea un paquete. Importarlo no
arranca nada; la aplicación solo se levanta desde `main()`.
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_RUTA = Path(__file__).resolve().parent.parent / "qa" / "conducir.py"
_paquete = importlib.util.spec_from_file_location("conducir_qa", _RUTA)
conducir = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(conducir)


class TestDebeCerrarObsAlFinal(unittest.TestCase):

    def test_no_estaba_y_lo_abrio_el_banco_se_cierra(self):
        self.assertTrue(conducir.debe_cerrar_obs_al_final(False, True))

    def test_estaba_abierto_antes_no_se_toca(self):
        self.assertFalse(conducir.debe_cerrar_obs_al_final(True, True))

    def test_no_estaba_y_no_hay_nada_no_hace_nada(self):
        self.assertFalse(conducir.debe_cerrar_obs_al_final(False, False))

    def test_estaba_y_ya_no_esta_no_hace_nada(self):
        self.assertFalse(conducir.debe_cerrar_obs_al_final(True, False))


class TestLimpiarSentinelObs(unittest.TestCase):

    def test_borra_las_marcas_run_y_respeta_lo_demas(self):
        with tempfile.TemporaryDirectory() as base:
            centinela = os.path.join(base, "obs-studio", ".sentinel")
            os.makedirs(centinela)
            for nombre in ("run_1", "run_2"):
                with open(os.path.join(centinela, nombre), "w"):
                    pass
            otro = os.path.join(centinela, "no-es-marca")
            with open(otro, "w"):
                pass

            with mock.patch.dict(os.environ, {"APPDATA": base}):
                borrados = conducir.limpiar_sentinel_obs()

            self.assertEqual(borrados, 2)
            self.assertFalse(os.path.exists(os.path.join(centinela, "run_1")))
            self.assertFalse(os.path.exists(os.path.join(centinela, "run_2")))
            self.assertTrue(os.path.exists(otro))

    def test_sin_appdata_no_borra_nada(self):
        entorno = {k: v for k, v in os.environ.items() if k != "APPDATA"}
        with mock.patch.dict(os.environ, entorno, clear=True):
            self.assertEqual(conducir.limpiar_sentinel_obs(), 0)


class TestVueltasTabTransmision(unittest.TestCase):

    def test_alcanza_los_28_controles_con_margen(self):
        self.assertGreaterEqual(conducir.VUELTAS_TAB_TRANSMISION, 28 + 10)


class TestSuperficiesQa(unittest.TestCase):

    def test_no_queda_modulo_de_interfaz_sin_escenario(self):
        self.assertEqual(conducir.superficies_sin_escenario(), [])

    def test_cada_clave_de_superficies_existe_en_el_disco(self):
        raiz = Path(__file__).resolve().parent.parent
        faltan = [
            nombre for nombre in conducir.SUPERFICIES
            if not (raiz / "ytchat" / "ui" / nombre).is_file()
            and not (raiz / "ytchat" / "player" / nombre).is_file()
        ]
        self.assertEqual(faltan, [])

    def test_declara_los_modulos_de_interfaz_de_la_musica(self):
        for nombre in ("musica_ventana.py", "musica_ventana_acciones.py",
                       "musica_menus.py", "musica_dialogo_enlace.py"):
            self.assertEqual(conducir.SUPERFICIES.get(nombre), "musica")

    def test_declara_los_modulos_de_interfaz_de_la_ia(self):
        for nombre in ("ia_ventana.py", "ia_agregar_captura.py"):
            self.assertEqual(conducir.SUPERFICIES.get(nombre), "ia")


class TestTodosCubreLosEscenarios(unittest.TestCase):

    def test_toda_escena_esta_en_todos_o_fuera_de_todos(self):
        self.assertEqual(set(conducir.ESCENARIOS),
                         set(conducir.EN_TODOS) | set(conducir.FUERA_DE_TODOS))


if __name__ == "__main__":
    unittest.main()
