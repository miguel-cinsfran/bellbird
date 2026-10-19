"""Pruebas de los textos de la ventana de música (vista.py), sin wx."""

import unittest
from unittest import mock

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


class TestEtiquetasMostrar(unittest.TestCase):

    def test_primero_la_carpeta_y_despues_las_listas(self):
        self.assertEqual(vista.etiquetas_mostrar(["Rock", "Jazz"]),
                         ["Temas de la carpeta", "Lista: Rock",
                          "Lista: Jazz"])

    def test_sin_listas_solo_la_carpeta(self):
        self.assertEqual(vista.etiquetas_mostrar([]),
                         ["Temas de la carpeta"])


class TestFiltroDeListas(unittest.TestCase):

    def test_sin_texto_devuelve_todos(self):
        temas = (_tema(1), _tema(2))
        self.assertEqual(vista.filtrar_lista(temas, ""), temas)

    def test_busca_en_titulo_artista_y_album(self):
        temas = (
            _tema(1),
            _tema(2, artista="Ana"),
            _tema(3, album="Verano"),
        )
        self.assertEqual([t.titulo for t in vista.filtrar_lista(temas, "ana")],
                         ["Tema 2"])
        self.assertEqual([t.titulo for t in vista.filtrar_lista(temas, "vera")],
                         ["Tema 3"])

    def test_ignora_mayusculas_y_tildes(self):
        temas = (_tema(1, artista="José"),)
        self.assertEqual(vista.filtrar_lista(temas, "JOSE"), temas)

    def test_sin_coincidencias(self):
        self.assertEqual(vista.filtrar_lista((_tema(1),), "zzz"), ())

    def test_filtro_de_la_carpeta_delega_en_biblioteca(self):
        biblio = mock.Mock()
        biblio.temas.return_value = (_tema(1), _tema(2))
        biblio.buscar.return_value = (_tema(2),)
        self.assertEqual(vista.filtrar_biblioteca(biblio, ""),
                         (_tema(1), _tema(2)))
        biblio.buscar.assert_not_called()
        self.assertEqual(vista.filtrar_biblioteca(biblio, "dos"),
                         (_tema(2),))
        biblio.buscar.assert_called_once_with("dos")

    def test_filtrar_fuente_elige_segun_la_biblioteca(self):
        biblio = mock.Mock()
        biblio.temas.return_value = (_tema(1),)
        biblio.buscar.return_value = ()
        self.assertEqual(vista.filtrar_fuente((_tema(2),), "", biblio),
                         (_tema(1),))
        self.assertEqual(vista.filtrar_fuente((_tema(2),), "", None),
                         (_tema(2),))


class TestTextoCoincidencias(unittest.TestCase):

    def test_ninguno(self):
        self.assertEqual(vista.texto_coincidencias(0), "Ningún tema coincide")

    def test_uno(self):
        self.assertEqual(vista.texto_coincidencias(1), "1 tema coincide")

    def test_varios(self):
        self.assertEqual(vista.texto_coincidencias(8), "8 temas coinciden")

    def test_negativo_cuenta_como_ninguno(self):
        self.assertEqual(vista.texto_coincidencias(-1),
                         "Ningún tema coincide")


class TestIndiceTrasRefrescar(unittest.TestCase):

    def test_conserva_el_mismo_indice(self):
        self.assertEqual(vista.indice_seleccion_tras_refrescar(2, 5), 2)

    def test_recorta_al_total(self):
        self.assertEqual(vista.indice_seleccion_tras_refrescar(8, 5), 4)

    def test_sin_seleccion(self):
        self.assertEqual(vista.indice_seleccion_tras_refrescar(None, 5), -1)

    def test_seleccion_negativa(self):
        self.assertEqual(vista.indice_seleccion_tras_refrescar(-1, 5), -1)

    def test_sin_filas(self):
        self.assertEqual(vista.indice_seleccion_tras_refrescar(0, 0), -1)


class TestAyudas(unittest.TestCase):

    def test_biblioteca_de_la_carpeta(self):
        self.assertEqual(
            vista.ayuda_biblioteca(False),
            "Intro reproduce ahora, Mayús más Intro a continuación, "
            "Control más Intro al final, tecla de aplicaciones para más "
            "opciones")

    def test_biblioteca_de_una_lista_suma_suprimir(self):
        self.assertEqual(
            vista.ayuda_biblioteca(True),
            vista.ayuda_biblioteca(False) + ", Suprimir quita de la lista")

    def test_cola(self):
        self.assertEqual(
            vista.ayuda_cola(),
            "Intro reproduce, Suprimir quita, Alt más flechas mueve, "
            "tecla de aplicaciones para más opciones")

    def test_buscar(self):
        self.assertEqual(
            vista.ayuda_buscar(),
            "Escribe para filtrar, flecha abajo va a los temas, "
            "Escape borra la búsqueda")


if __name__ == "__main__":
    unittest.main()
