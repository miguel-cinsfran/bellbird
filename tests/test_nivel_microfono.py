"""Nivel del micrófono a partir de los medidores de OBS. Sin wx."""

import random
import unittest
from dataclasses import FrozenInstanceError

from guyrapu.obs.nivel_microfono import (
    ALTO, BAJO, BIEN, SATURADO, SILENCIO, SIN_MUESTRAS, Nivel,
    frase_de_tramo, nivel_de, sonido_de_tramo)


def _evento(canales, fuente="Mic/Aux"):
    return {"inputs": [{"inputName": fuente, "inputLevelsMul": canales}]}


def _canal(pico):
    return [pico, pico, pico]


class EstadosTest(unittest.TestCase):
    def test_picos_justo_a_los_dos_lados_de_cada_corte(self):
        casos = (
            (0.0009, SILENCIO),
            (0.0011, BAJO),
            (0.09, BAJO),
            (0.11, BIEN),
            (0.34, BIEN),
            (0.36, ALTO),
            (0.94, ALTO),
            (0.95, SATURADO),
        )
        for pico, esperado in casos:
            with self.subTest(pico=pico):
                self.assertEqual(
                    nivel_de([_evento([_canal(pico)])], "Mic/Aux").estado,
                    esperado)

    def test_los_cortes_incluyen_su_valor(self):
        casos = (
            (0.001, BAJO),
            (0.1, BIEN),
            (10 ** (-9 / 20), ALTO),
            (10 ** (-0.5 / 20), SATURADO),
        )
        for pico, esperado in casos:
            with self.subTest(pico=pico):
                self.assertEqual(
                    nivel_de([_evento([_canal(pico)])], "Mic/Aux").estado,
                    esperado)

    def test_un_pico_de_cero_es_silencio(self):
        nivel = nivel_de([_evento([_canal(0.0)])], "Mic/Aux")
        self.assertEqual(nivel.estado, SILENCIO)
        self.assertEqual(nivel.pico_dbfs, float("-inf"))

    def test_con_picos_crecientes_el_estado_nunca_retrocede(self):
        orden = {SILENCIO: 0, BAJO: 1, BIEN: 2, ALTO: 3, SATURADO: 4}
        aleatorio = random.Random(631)
        picos = sorted(aleatorio.random() for _ in range(200))
        anterior = -1
        for pico in picos:
            estado = nivel_de(
                [_evento([_canal(pico)])], "Mic/Aux").estado
            self.assertIn(estado, orden)
            self.assertGreaterEqual(orden[estado], anterior,
                                    f"el pico {pico} dio {estado}")
            anterior = orden[estado]
        self.assertEqual(anterior, orden[SATURADO])


class PicoTest(unittest.TestCase):
    def test_toma_el_mayor_pico_de_todos_los_canales(self):
        eventos = [_evento([[0.0, 0.0, 0.0], [0.0, 0.5, 0.0]])]
        nivel = nivel_de(eventos, "Mic/Aux")
        self.assertEqual(nivel.estado, ALTO)
        self.assertEqual(nivel.pico_dbfs, -6.0)

    def test_toma_el_mayor_pico_de_todas_las_muestras(self):
        eventos = [_evento([_canal(0.0011)]), _evento([_canal(0.5)])]
        self.assertEqual(nivel_de(eventos, "Mic/Aux").estado, ALTO)

    def test_el_pico_se_redondea_a_un_decimal(self):
        nivel = nivel_de([_evento([_canal(0.5)])], "Mic/Aux")
        self.assertEqual(nivel.pico_dbfs, -6.0)
        self.assertEqual(round(nivel.pico_dbfs, 1), nivel.pico_dbfs)

    def test_un_canal_de_un_solo_valor_cuenta_como_muestra(self):
        self.assertEqual(
            nivel_de([_evento([[0.5]])], "Mic/Aux").estado, ALTO)
        self.assertEqual(
            nivel_de([_evento([[0.0]])], "Mic/Aux").estado, SILENCIO)


class FuenteTest(unittest.TestCase):
    def test_los_eventos_de_otra_fuente_no_cuentan(self):
        eventos = [_evento([_canal(0.95)], fuente="Otra")]
        nivel = nivel_de(eventos, "Mic/Aux")
        self.assertEqual(nivel.estado, SIN_MUESTRAS)
        self.assertIsNone(nivel.pico_dbfs)

    def test_la_fuente_busca_su_canal_entre_varias_fuentes(self):
        eventos = [{"inputs": [
            {"inputName": "Otra", "inputLevelsMul": [[0.9, 0.9, 0.9]]},
            {"inputName": "Mic/Aux", "inputLevelsMul": [[0.0, 0.0011, 0.0]]},
        ]}]
        self.assertEqual(nivel_de(eventos, "Mic/Aux").estado, BAJO)


class SinMuestrasTest(unittest.TestCase):
    def test_una_lista_vacia_da_sin_muestras(self):
        nivel = nivel_de([], "Mic/Aux")
        self.assertEqual(nivel.estado, SIN_MUESTRAS)
        self.assertIsNone(nivel.pico_dbfs)

    def test_sin_muestras_es_distinto_de_silencio(self):
        self.assertNotEqual(SIN_MUESTRAS, SILENCIO)
        self.assertEqual(nivel_de([], "Mic/Aux").estado, SIN_MUESTRAS)

    def test_sin_canales_tambien_es_sin_muestras(self):
        self.assertEqual(
            nivel_de([{"inputs": []}], "Mic/Aux").estado, SIN_MUESTRAS)
        self.assertEqual(
            nivel_de([_evento([])], "Mic/Aux").estado, SIN_MUESTRAS)


class FraseDeTramoTest(unittest.TestCase):
    def test_cada_estado_tiene_su_frase(self):
        casos = {
            BIEN: "Nivel correcto.",
            BAJO: "Nivel bajo. Acércate al micrófono o sube su volumen "
                  "en Windows.",
            ALTO: "Nivel alto. Aléjate un poco del micrófono.",
            SATURADO: "El sonido se satura. Aléjate del micrófono o baja su "
                      "volumen en Windows.",
            SILENCIO: "No llega sonido. Revisa que el micrófono esté "
                      "conectado y no silenciado en Windows.",
            SIN_MUESTRAS: "OBS no recibe nada de este micrófono. Revisa que "
                          "esté conectado o elige otro en Elegir micrófono.",
        }
        for estado, esperado in casos.items():
            with self.subTest(estado=estado):
                self.assertEqual(frase_de_tramo(Nivel(estado, -3.0)), esperado)


class SonidoDeTramoTest(unittest.TestCase):
    def test_cada_estado_tiene_su_sonido(self):
        casos = {
            BIEN: "microfono_bien",
            BAJO: "microfono_revisar",
            ALTO: "microfono_revisar",
            SATURADO: "microfono_revisar",
            SILENCIO: "microfono_sin_senal",
            SIN_MUESTRAS: "microfono_sin_senal",
        }
        for estado, esperado in casos.items():
            with self.subTest(estado=estado):
                self.assertEqual(
                    sonido_de_tramo(Nivel(estado, -3.0)), esperado)

    def test_bajo_alto_y_saturado_comparten_sonido(self):
        sonidos = {
            sonido_de_tramo(Nivel(estado, -3.0))
            for estado in (BAJO, ALTO, SATURADO)}
        self.assertEqual(sonidos, {"microfono_revisar"})


class ResultadoTest(unittest.TestCase):
    def test_los_estados_son_las_cadenas_del_diseno(self):
        self.assertEqual(SILENCIO, "silencio")
        self.assertEqual(BAJO, "bajo")
        self.assertEqual(BIEN, "bien")
        self.assertEqual(ALTO, "alto")
        self.assertEqual(SATURADO, "saturado")
        self.assertEqual(SIN_MUESTRAS, "sin_muestras")

    def test_el_resultado_es_inmutable(self):
        nivel = nivel_de([_evento([_canal(0.5)])], "Mic/Aux")
        with self.assertRaises(FrozenInstanceError):
            nivel.estado = SILENCIO


if __name__ == "__main__":
    unittest.main()
