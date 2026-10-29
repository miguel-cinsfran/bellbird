"""Tests de obs_salida con secuencias de muestras y reloj falso."""

import threading
import unittest

from tests.pseudo_prueba import con_pseudo
from bellbird.core.idioma import _
from bellbird.obs import obs_salida
from bellbird.obs.obs_salida import (
    esperar_salida, evaluar_inicio, frase_salida, problemas_en_directo)


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


class ProblemasEnDirectoTest(unittest.TestCase):
    def test_reconectando(self):
        self.assertEqual(
            problemas_en_directo(muestra(True, 10), muestra(True, 10, True)),
            [("reconexion",
              "Se perdió la conexión con el servicio. OBS está reconectando.")])

    def test_vuelta_cuando_deja_de_reconectar(self):
        self.assertEqual(
            problemas_en_directo(muestra(True, 10, reconectando=True),
                                 muestra(True, 10, reconectando=False)),
            [("vuelta", "La conexión con el servicio volvió.")])

    def test_vuelta_no_avisa_si_la_transmision_no_esta_activa(self):
        self.assertEqual(
            problemas_en_directo(muestra(True, 10, reconectando=True),
                                 muestra(False, 10)), [])

    def test_cuadros_perdidos_mas_del_cinco_por_ciento(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=60, totales=1100)
        self.assertEqual(problemas_en_directo(anterior, actual),
                         [("red", "Se están perdiendo cuadros: 60 por ciento. "
                                  "La red va lenta.")])

    def test_pocos_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=1, totales=1010)
        self.assertEqual(problemas_en_directo(anterior, actual), [])

    def test_menos_de_treinta_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=10, totales=1010)
        self.assertEqual(problemas_en_directo(anterior, actual), [])

    def test_seis_por_ciento_con_cien_cuadros_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=6, totales=1100)
        self.assertEqual(problemas_en_directo(anterior, actual),
                         [("red", "Se están perdiendo cuadros: 6 por ciento. "
                                  "La red va lenta.")])

    def test_cuatro_por_ciento_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=4, totales=1100)
        self.assertEqual(problemas_en_directo(anterior, actual), [])

    def test_cincuenta_por_ciento_con_veinte_cuadros_no_avisa(self):
        anterior = muestra(True, 10, perdidos=0, totales=1000)
        actual = muestra(True, 20, perdidos=10, totales=1020)
        self.assertEqual(problemas_en_directo(anterior, actual), [])

    def test_contador_reiniciado_no_avisa(self):
        anterior = muestra(True, 10, perdidos=100, totales=2000)
        actual = muestra(True, 20, perdidos=0, totales=0)
        self.assertEqual(problemas_en_directo(anterior, actual), [])

    def test_sin_novedad_da_lista_vacia(self):
        self.assertEqual(problemas_en_directo(muestra(True, 10),
                                              muestra(True, 20)), [])

    def test_sobrecarga_usa_el_mayor_de_codificacion_y_dibujo(self):
        avisos = problemas_en_directo(
            muestra(True, 10), muestra(True, 20),
            estadisticas_anterior={"outputSkippedFrames": 0,
                                   "outputTotalFrames": 1000,
                                   "renderSkippedFrames": 0,
                                   "renderTotalFrames": 1000},
            estadisticas={"outputSkippedFrames": 400,
                          "outputTotalFrames": 2000,
                          "renderSkippedFrames": 10,
                          "renderTotalFrames": 1100})
        self.assertEqual(avisos, [("sobrecarga",
            "OBS no da abasto: se pierde el 40 por ciento de los cuadros.")])

    def test_sobrecarga_toma_el_dibujo_cuando_supera_al_codificado(self):
        avisos = problemas_en_directo(
            muestra(True, 10), muestra(True, 20),
            estadisticas_anterior={"outputSkippedFrames": 0,
                                   "outputTotalFrames": 1000,
                                   "renderSkippedFrames": 0,
                                   "renderTotalFrames": 1000},
            estadisticas={"outputSkippedFrames": 30,
                          "outputTotalFrames": 2000,
                          "renderSkippedFrames": 20,
                          "renderTotalFrames": 1100})
        self.assertEqual(avisos, [("sobrecarga",
            "OBS no da abasto: se pierde el 20 por ciento de los cuadros.")])

    def test_sobrecarga_bajo_umbral_en_los_dos_no_avisa(self):
        avisos = problemas_en_directo(
            muestra(True, 10), muestra(True, 20),
            estadisticas_anterior={"outputSkippedFrames": 0,
                                   "outputTotalFrames": 1000,
                                   "renderSkippedFrames": 0,
                                   "renderTotalFrames": 1000},
            estadisticas={"outputSkippedFrames": 40,
                          "outputTotalFrames": 2000,
                          "renderSkippedFrames": 40,
                          "renderTotalFrames": 2000})
        self.assertEqual(avisos, [])

    def test_sobrecarga_nunca_devuelve_mas_de_un_aviso(self):
        for output_total, output_perdidos, render_total, render_perdidos in (
                (1000, 400, 100, 10),
                (1000, 30, 100, 20),
                (1000, 500, 100, 500),
                (0, 0, 0, 0),
                (1000, 0, 100, 50)):
            with self.subTest(estadisticas=(output_total, output_perdidos,
                                            render_total, render_perdidos)):
                avisos = problemas_en_directo(
                    muestra(True, 10), muestra(True, 20),
                    estadisticas_anterior={"outputSkippedFrames": 0,
                                           "outputTotalFrames": 1000,
                                           "renderSkippedFrames": 0,
                                           "renderTotalFrames": 1000},
                    estadisticas={
                        "outputSkippedFrames": output_perdidos,
                        "outputTotalFrames": 1000 + output_total,
                        "renderSkippedFrames": render_perdidos,
                        "renderTotalFrames": 1000 + render_total})
                self.assertLessEqual(
                    [tipo for tipo, _ in avisos].count("sobrecarga"), 1)

    def test_estadisticas_que_faltan_no_avisan_de_equipo(self):
        self.assertEqual(problemas_en_directo(
            muestra(True, 10), muestra(True, 20), None, None), [])
        self.assertEqual(problemas_en_directo(
            muestra(True, 10), muestra(True, 20),
            {"outputSkippedFrames": 0, "outputTotalFrames": 1000,
             "renderSkippedFrames": 0, "renderTotalFrames": 1000}, None), [])

    def test_contador_de_estadisticas_reiniciado_no_avisa(self):
        avisos = problemas_en_directo(
            muestra(True, 10), muestra(True, 20),
            estadisticas_anterior={"outputSkippedFrames": 500,
                                   "outputTotalFrames": 2000,
                                   "renderSkippedFrames": 0,
                                   "renderTotalFrames": 1000},
            estadisticas={"outputSkippedFrames": 0, "outputTotalFrames": 0,
                          "renderSkippedFrames": 0, "renderTotalFrames": 0})
        self.assertEqual(avisos, [])

    def test_varios_problemas_en_la_misma_muestra(self):
        avisos = problemas_en_directo(
            muestra(True, 10, perdidos=0, totales=1000),
            muestra(True, 20, perdidos=60, totales=1100),
            estadisticas_anterior={"outputSkippedFrames": 0,
                                   "outputTotalFrames": 1000,
                                   "renderSkippedFrames": 0,
                                   "renderTotalFrames": 1000},
            estadisticas={"outputSkippedFrames": 400,
                          "outputTotalFrames": 2000,
                          "renderSkippedFrames": 0,
                          "renderTotalFrames": 1000})
        self.assertEqual([tipo for tipo, _ in avisos], ["red", "sobrecarga"])


class TestPseudoSalida(unittest.TestCase):
    """Pseudotraducción de los textos de `obs_salida`.

    Sin ventanas: llama a las funciones bajo `con_pseudo()` y exige cada
    frase propia marcada, con los datos de ejemplo presentes.
    """

    def test_frase_salida_marca_los_cuatro_veredictos(self):
        with con_pseudo():
            for veredicto in ("enviando", "reconectando", "sin_salida",
                              "esperando"):
                with self.subTest(veredicto=veredicto):
                    frase = obs_salida.frase_salida(veredicto, "TikTok")
                    self.assertTrue(frase.startswith("[¡"), frase)
                    if veredicto in ("enviando", "reconectando"):
                        self.assertIn("Restream", frase)

    def test_problemas_marcan_los_cuatro_avisos(self):
        with con_pseudo():
            reconexion = problemas_en_directo(
                muestra(True, 10), muestra(True, 10, reconectando=True))
            self.assertTrue(reconexion[0][1].startswith("[¡"), reconexion)
            vuelta = problemas_en_directo(
                muestra(True, 10, reconectando=True),
                muestra(True, 10, reconectando=False))
            self.assertTrue(vuelta[0][1].startswith("[¡"), vuelta)
            red = problemas_en_directo(
                muestra(True, 10, perdidos=0, totales=1000),
                muestra(True, 20, perdidos=60, totales=1100))
            self.assertTrue(red[0][1].startswith("[¡"), red)
            self.assertIn("60", red[0][1])
            sobrecarga = problemas_en_directo(
                muestra(True, 10), muestra(True, 20),
                estadisticas_anterior={"outputSkippedFrames": 0,
                                       "outputTotalFrames": 1000,
                                       "renderSkippedFrames": 0,
                                       "renderTotalFrames": 1000},
                estadisticas={"outputSkippedFrames": 400,
                              "outputTotalFrames": 2000,
                              "renderSkippedFrames": 0,
                              "renderTotalFrames": 1000})
            self.assertTrue(sobrecarga[0][1].startswith("[¡"), sobrecarga)
            self.assertIn("40", sobrecarga[0][1])

    def test_constantes_marcadas_se_traducen_al_usarse(self):
        with con_pseudo():
            self.assertTrue(_(obs_salida._FRASE_RECONEXION).startswith("[¡"))
            self.assertTrue(_(obs_salida._FRASE_VUELTA).startswith("[¡"))


if __name__ == "__main__":
    unittest.main()
