"""Pruebas del reparto de mediciones entre trabajos simultáneos.

Módulo puro, sin ffmpeg ni ventanas: las mediciones son funciones falsas
que anotan cuántas corren a la vez.
"""

import threading
import time
import unittest
from unittest import mock

from guyrapu.music import medicion_paralela


class TestTrabajosDeMedicion(unittest.TestCase):

    def test_la_mitad_de_los_nucleos_con_tope_de_cuatro(self):
        casos = {None: 1, 1: 1, 2: 1, 4: 2, 8: 4, 32: 4}
        for nucleos, esperado in casos.items():
            with self.subTest(nucleos=nucleos):
                self.assertEqual(
                    medicion_paralela.trabajos_de_medicion(nucleos),
                    esperado)


class TestMedirEnParalelo(unittest.TestCase):

    def test_no_pasa_de_los_trabajos_pedidos(self):
        activos = 0
        maximo = 0
        candado = threading.Lock()

        def _medir(elemento):
            nonlocal activos, maximo
            with candado:
                activos += 1
                maximo = max(maximo, activos)
            time.sleep(0.02)
            with candado:
                activos -= 1
            return elemento

        resultados = list(medicion_paralela.medir_en_paralelo(
            range(10), _medir, lambda: True, 3))
        self.assertEqual(maximo, 3)
        self.assertLessEqual(maximo, 3)
        self.assertEqual(sorted(e[0] for e in resultados), list(range(10)))

    def test_detener_deja_de_enviar_y_entrega_lo_enviado(self):
        trabajos = 3
        enviados = []
        entregas = [0]
        candado = threading.Lock()

        def _medir(elemento):
            with candado:
                enviados.append(elemento)
            return elemento * 2

        def _seguir():
            return entregas[0] < 2

        resultados = []
        for elemento, resultado in medicion_paralela.medir_en_paralelo(
                range(100), _medir, _seguir, trabajos):
            resultados.append((elemento, resultado))
            entregas[0] += 1
        self.assertLess(len(enviados), 100)
        self.assertLessEqual(len(enviados), trabajos + 2)
        self.assertEqual(sorted(e[0] for e in resultados), sorted(enviados))
        self.assertEqual(sorted(e[1] for e in resultados),
                         sorted(e * 2 for e in enviados))

    def test_un_error_se_entrega_como_none_y_sigue(self):
        def _medir(elemento):
            if elemento == "malo":
                raise ValueError("no se pudo medir")
            return elemento

        with mock.patch.object(medicion_paralela, "logger") as logger:
            resultados = dict(medicion_paralela.medir_en_paralelo(
                ["a", "malo", "c"], _medir, lambda: True, 2))
        self.assertIsNone(resultados["malo"])
        self.assertEqual(resultados["a"], "a")
        self.assertEqual(resultados["c"], "c")
        logger.exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
