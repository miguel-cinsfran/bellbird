"""Pruebas puras de ColaTTS: el orden en que la voz toma los mensajes."""

import queue
import random
import threading
import time
import unittest

from bellbird.voice.cola_tts import ColaTTS


class TestOrdenDeLaCola(unittest.TestCase):

    def test_get_saca_primero_los_adelantados_y_despues_los_normales(self):
        cola = ColaTTS()
        cola.put("normal 1")
        cola.adelantar("adelantado 1")
        cola.put("normal 2")
        cola.adelantar("adelantado 2")
        self.assertEqual([cola.get() for _ in range(4)],
                         ["adelantado 1", "adelantado 2",
                          "normal 1", "normal 2"])

    def test_qsize_cuenta_los_dos_depositos(self):
        cola = ColaTTS()
        cola.put("normal")
        cola.adelantar("adelantado")
        self.assertEqual(cola.qsize(), 2)
        cola.get_nowait()
        self.assertEqual(cola.qsize(), 1)

    def test_adelantar_despierta_un_get_bloqueado_en_otro_hilo(self):
        cola = ColaTTS()
        resultado = []
        hilo = threading.Thread(
            target=lambda: resultado.append(cola.get(timeout=2.0)))
        hilo.start()
        try:
            limite = time.monotonic() + 1.0
            while cola.qsize() == 0 and hilo.is_alive() \
                    and time.monotonic() < limite:
                time.sleep(0.005)
            self.assertTrue(hilo.is_alive())
            cola.adelantar("adelantado")
            hilo.join(2.0)
            self.assertFalse(hilo.is_alive())
            self.assertEqual(resultado, ["adelantado"])
        finally:
            hilo.join(2.0)

    def test_get_nowait_saca_los_normales_antes_que_los_adelantados(self):
        cola = ColaTTS()
        cola.put("normal 1")
        cola.adelantar("adelantado")
        cola.put("normal 2")
        self.assertEqual(cola.get_nowait(), "normal 1")
        self.assertEqual(cola.get_nowait(), "normal 2")
        self.assertEqual(cola.get_nowait(), "adelantado")
        with self.assertRaises(queue.Empty):
            cola.get_nowait()

    def test_vaciar_con_get_nowait_hasta_empty_deja_la_cola_vacia(self):
        cola = ColaTTS()
        cola.put("normal 1")
        cola.adelantar("adelantado")
        cola.put("normal 2")
        vistos = []
        while not cola.empty():
            try:
                vistos.append(cola.get_nowait())
            except queue.Empty:
                break
        self.assertEqual(sorted(vistos),
                         sorted(["normal 1", "normal 2", "adelantado"]))
        self.assertTrue(cola.empty())
        self.assertEqual(cola.qsize(), 0)

    def test_adelantar_con_la_cola_en_maxsize_no_bloquea(self):
        cola = ColaTTS(maxsize=2)
        cola.put("normal 1")
        cola.put("normal 2")
        hilo = threading.Thread(target=lambda: cola.adelantar("adelantado"))
        hilo.start()
        hilo.join(1.0)
        self.assertFalse(hilo.is_alive())
        self.assertEqual(cola.qsize(), 3)


class TestPropiedadDeOrden(unittest.TestCase):

    def test_los_normales_salen_en_el_orden_en_que_entraron(self):
        for semilla in range(50):
            with self.subTest(semilla=semilla):
                azar = random.Random(semilla)
                cola = ColaTTS()
                normales = []
                adelantados = []
                for i in range(20):
                    if azar.random() < 0.5:
                        item = ("normal", i)
                        normales.append(item)
                        cola.put(item)
                    else:
                        item = ("adelantado", i)
                        adelantados.append(item)
                        cola.adelantar(item)
                salida = []
                while not cola.empty():
                    salida.append(cola.get())
                self.assertEqual(salida, adelantados + normales)


class TestCableadoConEncolar(unittest.TestCase):

    def test_el_adelantado_sobrevive_al_descarte_y_sale_primero(self):
        from main import Stats, encolar
        cola = ColaTTS(maxsize=2)
        cola.put({"texto_tts": "normal 1", "autor": ""})
        cola.put({"texto_tts": "normal 2", "autor": ""})
        cola.adelantar({"texto_tts": "reciente", "autor": ""})
        stats = Stats()
        encolar(cola, {"texto_tts": "nuevo", "autor": ""},
                {"estrategia": "limite", "tamanio_maximo": 2}, stats)
        self.assertEqual(stats.descartados, 2)
        self.assertEqual(cola.get()["texto_tts"], "reciente")
        self.assertEqual(cola.get()["texto_tts"], "nuevo")


if __name__ == "__main__":
    unittest.main()
