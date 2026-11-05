"""Pruebas de la guía de encuadre con pitidos.

Lógica pura, sin wx ni sonido: cada lado y altura, el espejo, el
centrado, sin rostro, el paneo y la nota continuos y que el intervalo no
crece al acercarse. Al final, los dos `.wav` fijos de `sounds/guia/`.
"""

import unittest
import wave

from guyrapu.camera import encuadre, guia


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


class TestPaneo(unittest.TestCase):

    def test_el_paneo_coincide_con_el_lado_y_es_proporcional(self):
        for espejo in (False, True):
            for paso in range(101):
                centro_x = paso / 100
                pulso = guia.pulso(
                    _rostro(centro_x, 0.35), ANCHO, ALTO, espejo=espejo)
                valor = max(-1.0, min(1.0, (centro_x - 0.5) / 0.3))
                if espejo:
                    valor = -valor
                with self.subTest(espejo=espejo, centro_x=centro_x):
                    self.assertAlmostEqual(pulso.paneo, valor, places=6)
                    if pulso.lado == "izquierda":
                        self.assertLess(pulso.paneo, 0)
                    elif pulso.lado == "derecha":
                        self.assertGreater(pulso.paneo, 0)
                    else:
                        self.assertLessEqual(abs(pulso.paneo), 0.4 + 1e-9)

    def test_mas_lejos_del_centro_mas_a_ese_lado(self):
        cerca = guia.pulso(_rostro(0.4, 0.35), ANCHO, ALTO)
        lejos = guia.pulso(_rostro(0.1, 0.35), ANCHO, ALTO)
        self.assertLess(lejos.paneo, cerca.paneo)


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


class TestFrecuencia(unittest.TestCase):

    def test_la_nota_no_baja_al_bajar_los_ojos(self):
        for espejo in (False, True):
            frecuencias = [
                guia.pulso(_rostro(0.5, paso / 100), ANCHO, ALTO,
                           espejo=espejo).frecuencia
                for paso in range(101)]
            with self.subTest(espejo=espejo):
                for anterior, siguiente in zip(frecuencias, frecuencias[1:]):
                    self.assertLessEqual(anterior, siguiente)

    def test_los_topes_de_la_nota(self):
        self.assertAlmostEqual(
            guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO).frecuencia, 440.0)
        self.assertAlmostEqual(
            guia.pulso(_rostro(0.5, 0.6), ANCHO, ALTO).frecuencia, 880.0)
        self.assertAlmostEqual(
            guia.pulso(_rostro(0.5, 0.1), ANCHO, ALTO).frecuencia, 220.0)


class TestCentrado(unittest.TestCase):

    def test_centrado_en_los_dos_ejes(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual((pulso.lado, pulso.altura), ("centro", "medio"))

    def test_centrado_lleva_el_intervalo_minimo(self):
        pulso = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(pulso.intervalo, 0.08)


class TestSinRostro(unittest.TestCase):

    def test_sin_rostro_el_lado_es_ninguno(self):
        pulso = guia.pulso(None, ANCHO, ALTO)
        self.assertEqual(pulso.lado, "ninguno")


class TestIntervalo(unittest.TestCase):

    def test_acotado_entre_los_dos_topes(self):
        centro = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        lejos = guia.pulso(_rostro(0.0, 1.0), ANCHO, ALTO)
        self.assertEqual(centro.intervalo, 0.08)
        self.assertEqual(lejos.intervalo, 0.6)

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

    def test_pitido_lleva_el_pulso(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0), ("pitido", tono))

    def test_antes_del_intervalo_no_hay_pitido(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        guia.decidir(marcha, tono, 1.0)
        self.assertEqual(guia.decidir(marcha, tono, 1.1), ("nada", None))

    def test_en_la_zona_suena_el_tono_centrado_cada_cuadro(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0), ("centro", None))
        self.assertEqual(guia.decidir(marcha, tono, 2.0), ("centro", None))

    def test_al_salir_de_la_zona_vuelven_los_pitidos(self):
        marcha = guia.Marcha(inicio=0.0)
        centro = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        fuera = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        guia.decidir(marcha, centro, 1.0)
        self.assertEqual(guia.decidir(marcha, fuera, 1.1)[0], "pitido")

    def test_sin_rostro_avisa_cada_un_segundo(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(None, ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0),
                         ("sin_rostro", None))
        self.assertEqual(guia.decidir(marcha, tono, 1.5), ("nada", None))
        self.assertEqual(guia.decidir(marcha, tono, 2.1),
                         ("sin_rostro", None))

    def test_despues_de_1_5_s_centrada_termina(self):
        marcha = guia.Marcha(inicio=0.0)
        tono = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        self.assertEqual(guia.decidir(marcha, tono, 1.0)[0], "centro")
        self.assertEqual(guia.decidir(marcha, tono, 2.5), ("lista", None))

    def test_un_cuadro_fuera_corta_la_racha(self):
        marcha = guia.Marcha(inicio=0.0)
        centro = guia.pulso(_rostro(0.5, 0.35), ANCHO, ALTO)
        fuera = guia.pulso(_rostro(0.2, 0.35), ANCHO, ALTO)
        guia.decidir(marcha, centro, 1.0)
        guia.decidir(marcha, fuera, 2.0)
        self.assertEqual(guia.decidir(marcha, centro, 3.6)[0], "centro")


class TestWavsReales(unittest.TestCase):
    """Los dos `.wav` fijos de la guía, generados por `scripts/sound_gen.py`."""

    NOMBRES = ["listo.wav", "sin_rostro.wav"]

    def _carpeta(self):
        from guyrapu.core import paths
        return paths.carpeta_guia()

    def test_existen_los_dos(self):
        faltan = [nombre for nombre in self.NOMBRES
                  if not (self._carpeta() / nombre).is_file()]
        self.assertEqual(faltan, [])

    def test_son_estereo(self):
        for nombre in self.NOMBRES:
            with self.subTest(nombre=nombre), \
                    wave.open(str(self._carpeta() / nombre), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 2, nombre)


if __name__ == "__main__":
    unittest.main()
