"""Pruebas de los textos de la ventana de música (vista.py), sin wx."""

import unittest

from ytchat.music import vista
from ytchat.music.modelo import EstadoMusica, Tema


def _tema(n, **campos):
    return Tema(f"C:/musica/tema{n}.mp3", f"Tema {n}", **campos)


def _estado(cola=(), posicion=None, pausado=False, terminado=False):
    return EstadoMusica(tuple(cola), posicion, pausado, terminado, 100, False)


class TestFilasTemas(unittest.TestCase):

    def test_una_fila_por_tema_en_orden(self):
        filas = vista.filas_temas([_tema(1), _tema(2)], False)
        self.assertEqual(filas, ["Tema 1", "Tema 2"])

    def test_lista_vacia(self):
        self.assertEqual(vista.filas_temas([], False), [])

    def test_incluye_el_artista_si_lo_pide(self):
        filas = vista.filas_temas([_tema(1, artista="Ana")], True)
        self.assertEqual(filas, ["Tema 1, de Ana"])

    def test_sin_artista_aunque_lo_tenga(self):
        filas = vista.filas_temas([_tema(1, artista="Ana")], False)
        self.assertEqual(filas, ["Tema 1"])


class TestFilasCola(unittest.TestCase):

    def test_numera_desde_uno(self):
        estado = _estado([_tema(1), _tema(2)], posicion=None)
        self.assertEqual(vista.filas_cola(estado, False),
                         ["1. Tema 1", "2. Tema 2"])

    def test_la_actual_lleva_sonando(self):
        estado = _estado([_tema(1), _tema(2)], posicion=1)
        self.assertEqual(vista.filas_cola(estado, False),
                         ["1. Tema 1", "Sonando: 2. Tema 2"])

    def test_la_actual_en_pausa(self):
        estado = _estado([_tema(1), _tema(2)], posicion=0, pausado=True)
        self.assertEqual(vista.filas_cola(estado, False),
                         ["En pausa: 1. Tema 1", "2. Tema 2"])

    def test_terminada_no_marca_ninguna(self):
        estado = _estado([_tema(1)], posicion=0, terminado=True)
        self.assertEqual(vista.filas_cola(estado, False), ["1. Tema 1"])

    def test_cola_vacia(self):
        self.assertEqual(vista.filas_cola(_estado(), False), [])

    def test_incluye_el_artista_si_lo_pide(self):
        estado = _estado([_tema(1, artista="Ana")], posicion=0)
        self.assertEqual(vista.filas_cola(estado, True),
                         ["Sonando: 1. Tema 1, de Ana"])


class TestTextoResumen(unittest.TestCase):

    def test_sin_busqueda(self):
        self.assertEqual(vista.texto_resumen(120, 120, False),
                         "120 temas en la carpeta")

    def test_sin_busqueda_singular(self):
        self.assertEqual(vista.texto_resumen(1, 1, False),
                         "1 tema en la carpeta")

    def test_sin_busqueda_cero(self):
        self.assertEqual(vista.texto_resumen(0, 0, False),
                         "0 temas en la carpeta")

    def test_buscando(self):
        self.assertEqual(vista.texto_resumen(120, 8, True),
                         "8 de 120 temas")

    def test_buscando_singular_total(self):
        self.assertEqual(vista.texto_resumen(1, 1, True),
                         "1 de 1 tema")

    def test_buscando_un_resultado_de_muchos(self):
        self.assertEqual(vista.texto_resumen(120, 1, True),
                         "1 de 120 temas")

    def test_buscando_sin_resultados(self):
        self.assertEqual(vista.texto_resumen(120, 0, True),
                         "0 de 120 temas")


if __name__ == "__main__":
    unittest.main()
