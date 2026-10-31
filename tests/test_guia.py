"""Pruebas de la guía de encuadre con pitidos.

Lógica pura, sin wx ni sonido: cada lado y altura, el espejo, el
centrado, sin rostro y que el intervalo no crece al acercarse. Al final,
los once `.wav` reales de `sounds/guia/`: existen, son estéreo y los de
un lado llevan el otro canal en silencio.
"""

import unittest
import wave
from pathlib import Path

from bellbird.camera import encuadre, guia


ANCHO = 320
ALTO = 240


def _rostro(centro_x, ojos_y):
    """Un rostro con el centro horizontal y la altura de ojos pedidos."""
    ancho, alto = 80.0, 100.0
    x = centro_x * ANCHO - ancho / 2
    ojos = ojos_y * ALTO
    return encuadre.Rostro(
        x=x, y=20.0, ancho=ancho, alto=alto,
        ojo_izquierda=(x + 20.0, ojos), ojo_derecha=(x + 60.0, ojos),
        nariz=(x + 40.0, ojos + 20.0), confianza=0.99)


class TestLado(unittest.TestCase):

    def test_a_la_izquierda_pide_izquierda(self):
        pulso = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.lado, "izquierda")

    def test_a_la_derecha_pide_derecha(self):
        pulso = guia.pulso(_rostro(0.8, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.lado, "derecha")

    def test_al_centro_no_pide_lado(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.lado, "centro")

    def test_usa_los_umbrales_de_encuadre(self):
        cerca_izquierda = encuadre.UMBRAL_IZQUIERDA - 0.01
        casi_centro = encuadre.UMBRAL_IZQUIERDA + 0.01
        self.assertEqual(
            guia.pulso(_rostro(cerca_izquierda, 0.35), ANCHO, ALTO).lado,
            "izquierda")
        self.assertEqual(
            guia.pulso(_rostro(casi_centro, 0.35), ANCHO, ALTO).lado,
            "centro")


class TestEspejo(unittest.TestCase):

    def test_sin_espejo_pide_el_lado_de_la_imagen(self):
        pulso = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO, espejo=False)
        self.assertEqual(pulso.lado, "izquierda")

    def test_con_espejo_pide_el_lado_contrario(self):
        pulso = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO, espejo=True)
        self.assertEqual(pulso.lado, "derecha")

    def test_el_centro_no_cambia_con_espejo(self):
        sin = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO, espejo=False)
        con = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO, espejo=True)
        self.assertEqual((sin.lado, sin.altura), (con.lado, con.altura))


class TestAltura(unittest.TestCase):

    def test_ojos_altos_piden_bajar(self):
        pulso = guia.pulso(_rostro(0.5, 0.1), ANCHO, ALTO)
        self.assertEqual(pulso.altura, "abajo")

    def test_ojos_bajos_piden_subir(self):
        pulso = guia.pulso(_rostro(0.5, 0.6), ANCHO, ALTO)
        self.assertEqual(pulso.altura, "arriba")

    def test_ojos_medios_no_piden_altura(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.altura, "medio")

    def test_usa_los_umbrales_de_encuadre(self):
        alto = encuadre.OJO_ALTO - 0.01
        medio = encuadre.OJO_ALTO + 0.01
        self.assertEqual(
            guia.pulso(_rostro(0.5, alto), ANCHO, ALTO).altura, "abajo")
        self.assertEqual(
            guia.pulso(_rostro(0.5, medio), ANCHO, ALTO).altura, "medio")


class TestCentrado(unittest.TestCase):

    def test_centrado_en_los_dos_ejes(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual((pulso.lado, pulso.altura), ("centro", "medio"))

    def test_centrado_lleva_el_intervalo_minimo(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.intervalo, 0.2)


class TestSinRostro(unittest.TestCase):

    def test_sin_rostro_el_lado_es_ninguno(self):
        pulso = guia.pulso(None, ANCHO, ALTO)
        self.assertEqual(pulso.lado, "ninguno")


class TestIntervalo(unittest.TestCase):

    def test_acotado_entre_minimo_y_maximo(self):
        lejos = guia.pulso(_rostro(0.0, 0.0), ANCHO, ALTO)
        centro = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertGreaterEqual(lejos.intervalo, 0.2)
        self.assertLessEqual(lejos.intervalo, 0.9)
        self.assertGreaterEqual(centro.intervalo, 0.2)
        self.assertLessEqual(centro.intervalo, 0.9)

    def test_no_crece_al_acercarse_al_objetivo(self):
        pasos = [(0.05, 0.05), (0.2, 0.15), (0.35, 0.25),
                 (0.45, 0.32), (0.5, 0.35)]
        intervalos = [guia.pulso(_rostro(x, y), ANCHO, ALTO).intervalo
                      for x, y in pasos]
        for anterior, siguiente in zip(intervalos, intervalos[1:]):
            self.assertGreaterEqual(anterior, siguiente)

    def test_mas_lejos_mas_espaciado(self):
        cerca = guia.pulso(_rostro(0.45, 0.32), ANCHO, ALTO)
        lejos = guia.pulso(_rostro(0.1, 0.1), ANCHO, ALTO)
        self.assertGreater(lejos.intervalo, cerca.intervalo)


class TestDecidir(unittest.TestCase):

    def test_pitido_lleva_el_nombre_del_wav(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0),
                         ("pitido", "izquierda_medio.wav"))

    def test_antes_del_intervalo_no_hay_pitido(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        guia.decidir(marcha, tono, 1.0)
        self.assertEqual(guia.decidir(marcha, tono, 1.1), ("nada", None))

    def test_despues_de_1_5_s_centrada_termina(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0)[0], "pitido")
        self.assertEqual(guia.decidir(marcha, tono, 2.5), ("lista", None))

    def test_un_cuadro_fuera_corta_la_racha(self):
        marcha = guia.Marcha(inicio=0.0)
        centro = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        fuera = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        guia.decidir(marcha, centro, 1.0)
        guia.decidir(marcha, fuera, 2.0)
        self.assertEqual(guia.decidir(marcha, centro, 3.6)[0], "pitido")


class TestWavsReales(unittest.TestCase):
    """Los once `.wav` de la guía, generados por `scripts/sound_gen.py`."""

    NOMBRES = [f"{lado}_{altura}.wav"
               for lado in ("izquierda", "centro", "derecha")
               for altura in ("arriba", "medio", "abajo")]
    NOMBRES = NOMBRES + ["listo.wav", "sin_rostro.wav"]

    def _carpeta(self):
        from bellbird.core import paths
        return paths.carpeta_guia()

    def test_existen_los_once(self):
        faltan = [nombre for nombre in self.NOMBRES
                  if not (self._carpeta() / nombre).is_file()]
        self.assertEqual(faltan, [])

    def _canales(self, nombre):
        with wave.open(str(self._carpeta() / nombre), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 2, nombre)
            cuadros = wav.readframes(wav.getnframes())
        izquierdos = [int.from_bytes(cuadros[i:i + 2], "little", signed=True)
                      for i in range(0, len(cuadros), 4)]
        derechos = [int.from_bytes(cuadros[i:i + 2], "little", signed=True)
                    for i in range(2, len(cuadros), 4)]
        return izquierdos, derechos

    def test_izquierda_suena_solo_por_la_izquierda(self):
        for altura in ("arriba", "medio", "abajo"):
            with self.subTest(altura=altura):
                izquierdos, derechos = self._canales(
                    f"izquierda_{altura}.wav")
                self.assertTrue(any(izquierdos))
                self.assertFalse(any(derechos))

    def test_derecha_suena_solo_por_la_derecha(self):
        for altura in ("arriba", "medio", "abajo"):
            with self.subTest(altura=altura):
                izquierdos, derechos = self._canales(
                    f"derecha_{altura}.wav")
                self.assertFalse(any(izquierdos))
                self.assertTrue(any(derechos))

    def test_centro_suena_por_los_dos(self):
        for altura in ("arriba", "medio", "abajo"):
            with self.subTest(altura=altura):
                izquierdos, derechos = self._canales(
                    f"centro_{altura}.wav")
                self.assertTrue(any(izquierdos))
                self.assertTrue(any(derechos))

    def test_los_pitidos_duran_unos_80_ms(self):
        for lado in ("izquierda", "centro", "derecha"):
            for altura in ("arriba", "medio", "abajo"):
                nombre = f"{lado}_{altura}.wav"
                with self.subTest(nombre=nombre), \
                        wave.open(str(self._carpeta() / nombre), "rb") as wav:
                    duracion = wav.getnframes() / wav.getframerate()
                    self.assertAlmostEqual(duracion, 0.08, delta=0.03)


if __name__ == "__main__":
    unittest.main()
