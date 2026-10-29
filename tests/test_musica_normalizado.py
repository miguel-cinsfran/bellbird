"""Pruebas del envoltorio de igualación de volumen, sin motor ni ventanas.

Un adaptador falso anota el volumen corregido que recibe `cargar` y las
llamadas a `volumen`: el que suena no cambia cuando entra otro tema.
"""

import unittest

from bellbird.music.modelo import Tema
from bellbird.music.normalizado import Normalizado


class _AdaptadorFalso:
    def __init__(self, volumen=50):
        self.llamadas = []
        self._volumen = volumen

    def cargar(self, tema, ficha, volumen=None):
        self.llamadas.append(("cargar", tema.origen, ficha, volumen))

    def volumen(self, valor):
        self.llamadas.append(("volumen", valor))
        self._volumen = valor

    def fijar_dispositivo(self, identificador):
        self.llamadas.append(("fijar_dispositivo", identificador))

    def tiempo_ms(self):
        self.llamadas.append(("tiempo_ms",))
        return 1234


def _tema(origen="C:/musica/a.mp3"):
    return Tema(origen, "Tema")


class TestNormalizadoCargar(unittest.TestCase):

    def test_el_volumen_corregido_va_en_cargar_sin_tocar_el_actual(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 0.0, volumen=50)
        envuelto.cargar(_tema(), 7)
        self.assertEqual(adaptador.llamadas,
                         [("cargar", "C:/musica/a.mp3", 7, 50)])

    def test_ganancia_positiva_sube(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 6.0, volumen=20)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 1, 25))

    def test_con_volumen_cien_la_ganancia_positiva_supera_cien(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 6.0, volumen=100)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas, [("cargar", "C:/musica/a.mp3",
                                               1, 126)])

    def test_ganancia_negativa_baja(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: -6.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 1, 40))

    def test_ganancia_cero_deja_el_volumen_del_usuario(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 0.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 1, 50))

    def test_apagado_da_el_volumen_del_usuario(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 6.0, volumen=20)
        envuelto.fijar_activo(False)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 1, 20))

    def test_nace_activo(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: -6.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 1, 40))

    def test_ganancia_que_lanza_da_cero_y_el_tema_igual_se_carga(self):
        def _romper(_tema):
            raise RuntimeError("sin caché")

        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, _romper, volumen=50)
        envuelto.cargar(_tema(), 3)
        self.assertEqual(adaptador.llamadas,
                         [("cargar", "C:/musica/a.mp3", 3, 50)])

    def test_cambiar_activo_no_llama_a_volumen_hasta_el_proximo_cargar(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: -6.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        adaptador.llamadas.clear()
        envuelto.fijar_activo(False)
        self.assertEqual(adaptador.llamadas, [])
        envuelto.cargar(_tema(), 2)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 2, 50))

    def test_volumen_cero_da_cero_con_cualquier_ganancia(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 6.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        adaptador.llamadas.clear()
        envuelto.volumen(0)
        self.assertEqual(adaptador.llamadas, [("volumen", 0)])

    def test_volumen_guarda_el_del_usuario_y_aplica_el_efectivo(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: -6.0, volumen=50)
        envuelto.cargar(_tema(), 1)
        adaptador.llamadas.clear()
        envuelto.volumen(80)
        self.assertEqual(adaptador.llamadas, [("volumen", 64)])
        adaptador.llamadas.clear()
        envuelto.fijar_activo(False)
        envuelto.cargar(_tema(), 2)
        self.assertEqual(adaptador.llamadas[0], ("cargar", "C:/musica/a.mp3",
                                                 2, 80))

    def test_delega_fijar_dispositivo_y_tiempo_ms(self):
        adaptador = _AdaptadorFalso()
        envuelto = Normalizado(adaptador, lambda _tema: 0.0, volumen=50)
        envuelto.fijar_dispositivo("altavoces")
        self.assertEqual(envuelto.tiempo_ms(), 1234)
        self.assertEqual(adaptador.llamadas,
                         [("fijar_dispositivo", "altavoces"), ("tiempo_ms",)])


if __name__ == "__main__":
    unittest.main()
