"""Tests de obs_salida con secuencias de muestras y reloj falso."""

import threading
import unittest

from ytchat.obs import obs_salida
from ytchat.obs.obs_salida import (
    esperar_salida, evaluar_inicio, frase_salida, problema_en_directo)


def muestra(activa=True, bytes_=0, reconectando=False, perdidos=0,
            totales=0):
    return {"outputActive": activa, "outputBytes": bytes_,
            "outputReconnecting": reconectando,
            "outputSkippedFrames": perdidos, "outputTotalFrames": totales}


class ClienteFalso:
    def __init__(self, muestras):
        self.muestras = list(muestras)
        self.llamadas = 0

    def pedir(self, tipo, datos=None, parada=None):
        assert tipo == "GetStreamStatus"
        self.llamadas += 1
        indice = min(self.llamadas - 1, len(self.muestras) - 1)
        return {"responseData": dict(self.muestras[indice])}


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.siestecitas = []

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.siestecitas.append(segundos)
        self.ahora += segundos


class EvaluarInicioTest(unittest.TestCase):
    def test_enviando_cuando_crecen_los_bytes(self):
        self.assertEqual(evaluar_inicio(
            [muestra(True, 100), muestra(True, 250)]), "enviando")

    def test_enviando_solo_si_hay_dos_seguidas(self):
        self.assertEqual(evaluar_inicio([muestra(True, 100)]), "esperando")
        self.assertEqual(evaluar_inicio(
            [muestra(True, 100), muestra(True, 100)]), "esperando")

    def test_reconectando_en_la_ultima(self):
        self.assertEqual(evaluar_inicio(
            [muestra(True, 100), muestra(True, 100, reconectando=True)]),
            "reconectando")

    def test_sin_salida_si_ninguna_activa(self):
        self.assertEqual(evaluar_inicio(
            [muestra(False), muestra(False)]), "sin_salida")
        self.assertEqual(evaluar_inicio([]), "sin_salida")

    def test_esperando_activa_sin_crecer(self):
        self.assertEqual(evaluar_inicio(
            [muestra(True, 100), muestra(True, 100)]), "esperando")


class EsperarSalidaTest(unittest.TestCase):
    def esperar(self, cliente, **extras):
        reloj = RelojFalso()
        extras.setdefault("dormir", reloj.dormir)
        extras.setdefault("reloj", reloj.reloj)
        return esperar_salida(cliente, **extras), reloj

    def test_devuelve_enviando_en_cuanto_crece(self):
        cliente = ClienteFalso([muestra(True, 10), muestra(True, 40)])
        veredicto, _ = self.esperar(cliente, limite=20.0, intervalo=1.0)
        self.assertEqual(veredicto, "enviando")
        self.assertEqual(cliente.llamadas, 2)

    def test_corta_por_limite_con_el_ultimo_veredicto(self):
        cliente = ClienteFalso([muestra(True, 10)] * 50)
        veredicto, reloj = self.esperar(cliente, limite=3.0, intervalo=1.0)
        self.assertEqual(veredicto, "esperando")
        self.assertGreaterEqual(reloj.ahora, 3.0)

    def test_limite_sin_salida(self):
        cliente = ClienteFalso([muestra(False)] * 50)
        veredicto, _ = self.esperar(cliente, limite=2.0, intervalo=1.0)
        self.assertEqual(veredicto, "sin_salida")

    def test_parada_devuelve_lo_ultimo(self):
        cliente = ClienteFalso([muestra(True, 10)] * 50)
        parada = threading.Event()
        reloj = RelojFalso()

        def dormir(segundos):
            parada.set()
            reloj.dormir(segundos)

        veredicto = esperar_salida(cliente, parada=parada, limite=30.0,
                                   intervalo=1.0, dormir=dormir,
                                   reloj=reloj.reloj)
        self.assertEqual(veredicto, "esperando")


class FraseSalidaTest(unittest.TestCase):
    def test_frases_exactas(self):
        self.assertEqual(frase_salida("enviando", "TikTok"),
                         "OBS está enviando la señal a Restream.")
        self.assertEqual(frase_salida("enviando", "YouTube"),
                         "OBS está enviando la señal a YouTube.")
        self.assertEqual(
            frase_salida("reconectando", "TikTok"),
            "OBS no logra conectar con Restream y está reintentando. "
            "Revisa internet.")
        self.assertEqual(frase_salida("sin_salida", "TikTok"),
                         "OBS no empezó a transmitir.")
        self.assertEqual(frase_salida("esperando", "YouTube"),
                         "OBS todavía no confirma que la señal salga.")


class ProblemaEnDirectoTest(unittest.TestCase):
    def test_reconectando(self):
        self.assertEqual(
            problema_en_directo(muestra(True, 10), muestra(True, 10, True)),
            "Se cortó la conexión con el servicio, OBS está reconectando.")

    def test_cuadros_perdidos_mas_del_cinco_por_ciento(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=60, totales=1100)
        self.assertEqual(problema_en_directo(anterior, actual),
                         "Se están perdiendo cuadros: 60 por ciento. "
                         "La red va lenta.")

    def test_pocos_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=1, totales=1010)
        self.assertIsNone(problema_en_directo(anterior, actual))

    def test_menos_de_treinta_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=10, totales=1010)
        self.assertIsNone(problema_en_directo(anterior, actual))

    def test_seis_por_ciento_con_cien_cuadros_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=6, totales=1100)
        self.assertEqual(problema_en_directo(anterior, actual),
                         "Se están perdiendo cuadros: 6 por ciento. "
                         "La red va lenta.")

    def test_cuatro_por_ciento_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=4, totales=1100)
        self.assertIsNone(problema_en_directo(anterior, actual))

    def test_cincuenta_por_ciento_con_veinte_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=10, totales=1020)
        self.assertIsNone(problema_en_directo(anterior, actual))

    def test_sin_novedad_da_none(self):
        self.assertIsNone(problema_en_directo(muestra(True, 10),
                                              muestra(True, 20)))


if __name__ == "__main__":
    unittest.main()
