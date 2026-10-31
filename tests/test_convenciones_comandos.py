"""Convenciones de los comandos de la barra de menús.

La parte pura se prueba con entradas armadas a mano, sin wx. La prueba de
cableado construye el menú real con wx.App: corre siempre en la suite, en
la PC donde no molesta a NVDA. En esta máquina se corre solo la parte
pura, nombrando sus clases.
"""

import unittest

from scripts import convenciones_comandos as cc


def E(ruta, etiqueta, letra="", tecla="", tipo="normal", nivel=1):
    return cc.Entrada(ruta=tuple(ruta), etiqueta=etiqueta, letra=letra,
                      tecla=tecla, tipo=tipo, nivel=nivel)


class TestMayusculas(unittest.TestCase):

    def test_detecta_palabra_con_mayuscula_a_mitad_de_rotulo(self):
        entradas = [E(("Ver",), "Ir a Chat en vivo", "c")]
        self.assertEqual(
            cc.faltas_mayusculas(entradas),
            ["Mayúscula a mitad de rótulo en «Ir a Chat en vivo»: «Chat»"])

    def test_acepta_minusculas_y_siglas_permitidas(self):
        entradas = [E(("Ver",), "Describir la escena de OBS", "o"),
                    E(("Herramientas",), "Actualizar yt-dlp", "a"),
                    E(("Voz",), "Silenciar lectura", "i")]
        self.assertEqual(cc.faltas_mayusculas(entradas), [])


class TestLetrasRepetidas(unittest.TestCase):

    def test_detecta_letra_repetida_entre_hermanos(self):
        entradas = [E(("Ver",), "Ir a Chat en vivo", "c"),
                    E(("Ver",), "Ir a Comentarios", "c")]
        self.assertEqual(
            cc.faltas_letras_repetidas(entradas),
            ["Letra «c» repetida en «Ver»: "
             "«Ir a Chat en vivo» y «Ir a Comentarios»"])

    def test_la_letra_no_distingue_mayusculas(self):
        entradas = [E(("Ver",), "Ir a Chat en vivo", "C"),
                    E(("Ver",), "Ir a Comentarios", "c")]
        self.assertEqual(len(cc.faltas_letras_repetidas(entradas)), 1)

    def test_letras_distintas_pasan(self):
        entradas = [E(("Archivo",), "Conectar", "c"),
                    E(("Archivo",), "Desconectar", "d")]
        self.assertEqual(cc.faltas_letras_repetidas(entradas), [])


class TestProfundidad(unittest.TestCase):

    def test_detecta_nivel_mas_hondo_que_el_submenu(self):
        entradas = [E(("Ver", "Recientes"), "Leer algo", "", "", "normal", 3)]
        self.assertEqual(
            cc.faltas_profundidad(entradas),
            ["Submenú demasiado hondo en «Ver > Recientes»: «Leer algo»"])

    def test_acepta_barra_menu_y_submenu(self):
        entradas = [E((), "Ver", "", "", "menu", 0),
                    E(("Ver",), "Recientes", "", "", "submenu", 1),
                    E(("Ver", "Recientes"), "Leer algo", "", "", "normal", 2)]
        self.assertEqual(cc.faltas_profundidad(entradas), [])


class TestShift(unittest.TestCase):

    def test_detecta_shift_en_ingles_en_la_tecla(self):
        entradas = [E(("Archivo",), "Historial de directos", "h",
                      "Ctrl+Shift+H")]
        self.assertEqual(
            cc.faltas_shift(entradas),
            ["«Shift» en la tecla de «Historial de directos»"])

    def test_acepta_tecla_sin_shift(self):
        entradas = [E(("Archivo",), "Salir", "s", "Alt+F4")]
        self.assertEqual(cc.faltas_shift(entradas), [])


class TestTeclasIngles(unittest.TestCase):

    def test_detecta_nombre_de_tecla_en_ingles(self):
        entradas = [E(("Reproductor",), "Retroceder 1 minuto", "e",
                      "Ctrl+Left")]
        self.assertEqual(
            cc.faltas_teclas_ingles(entradas),
            ["«Left» en la tecla de «Retroceder 1 minuto»"])

    def test_marca_cada_nombre_sin_tocar_los_demas(self):
        entradas = [E(("Música",), "Adelantar 10 segundos", "n",
                      "Ctrl+Alt+Shift+Right")]
        self.assertEqual(
            cc.faltas_teclas_ingles(entradas),
            ["«Right» en la tecla de «Adelantar 10 segundos»"])

    def test_acepta_tecla_sin_nombres_en_ingles(self):
        entradas = [E(("Reproductor",), "Detener reproducción", "t",
                      "Ctrl+D")]
        self.assertEqual(cc.faltas_teclas_ingles(entradas), [])


class TestActivarDesactivar(unittest.TestCase):

    def test_detecta_pareja_activar_desactivar(self):
        entradas = [E(("Transmisión",), "Activar avisos", "a"),
                    E(("Transmisión",), "Desactivar avisos", "d")]
        self.assertEqual(
            cc.faltas_activar_desactivar(entradas),
            ["«Activar avisos» y «Desactivar avisos» "
             "conviven en «Transmisión»"])

    def test_un_solo_activar_pasa(self):
        entradas = [E(("Transmisión",), "Activar avisos", "a"),
                    E(("Transmisión",), "Mostrar OBS", "o")]
        self.assertEqual(cc.faltas_activar_desactivar(entradas), [])


class TestInformativos(unittest.TestCase):

    def test_lista_comandos_con_puntos_suspensivos(self):
        entradas = [E(("Archivo",), "Historial de directos…", "h"),
                    E(("Archivo",), "Salir", "s")]
        self.assertEqual(cc.informativos_puntos(entradas),
                         ["«Historial de directos…» lleva puntos suspensivos"])

    def test_lista_rotulos_largos_sin_contar_articulos(self):
        entradas = [E(("Ver",), "Anunciar autor del último mensaje", "u")]
        self.assertEqual(cc.informativos_largos(entradas),
                         ["«Anunciar autor del último mensaje» tiene 4 palabras"])


FALTAS_CONOCIDAS = [
    "Mayúscula a mitad de rótulo en «Ir a Chat del directo»: «Chat»",
    "Mayúscula a mitad de rótulo en «Ir a Comentarios»: «Comentarios»",
    "Mayúscula a mitad de rótulo en «Ir al Reproductor»: «Reproductor»",
    "Mayúscula a mitad de rótulo en «Super Chats»: «Chats»",
    "«Shift» en la tecla de «Conectar»",
    "«Shift» en la tecla de «Desconectar»",
    "«Shift» en la tecla de «Copiar enlace del directo»",
    "«Shift» en la tecla de «Historial de directos…»",
    "«Shift» en la tecla de «Región anterior»",
    "«Shift» en la tecla de «Ir a la lista del panel actual»",
    "«Shift» en la tecla de «Leer el último mensaje del chat»",
    "«Shift» en la tecla de «Leer el mensaje 2 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 3 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 4 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 5 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 6 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 7 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 8 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 9 desde el final del chat»",
    "«Shift» en la tecla de «Leer el mensaje 10 desde el final del chat»",
    "«Shift» en la tecla de «Preguntar a la IA sobre la imagen…»",
    "«Shift» en la tecla de «Consulta rápida a la IA»",
    "«Shift» en la tecla de «Panel de transmisión…»",
    "«Shift» en la tecla de «Silenciar el micrófono de OBS»",
    "«Shift» en la tecla de «Mostrar OBS»",
    "«Shift» en la tecla de «Avisar cuando OBS no da abasto»",
    "«Shift» en la tecla de «Avisar si el rostro sale del encuadre»",
    "«Shift» en la tecla de «Elegir música…»",
    "«Shift» en la tecla de «Avanzar 10 segundos»",
    "«Shift» en la tecla de «Retroceder 10 segundos»",
    "«Shift» en la tecla de «Administrador de descargas…»",
    "«Shift» en la tecla de «Preferencias…»",
    "«Shift» en la tecla de «Marcar incidencia»",
    "«Enter» en la tecla de "
    "«Enviar mensaje al chat del directo (solo YouTube)…»",
    "«Left» en la tecla de «Retroceder 1 minuto»",
    "«Right» en la tecla de «Avanzar 1 minuto»",
    "«End» en la tecla de «Ir al directo»",
    "«Down» en la tecla de «Bajar volumen del reproductor»",
    "«Up» en la tecla de «Subir volumen del reproductor»",
    "«Space» en la tecla de «Reproducir o pausar»",
    "«Right» en la tecla de «Siguiente canción»",
    "«Left» en la tecla de «Canción anterior»",
    "«Up» en la tecla de «Subir volumen»",
    "«Down» en la tecla de «Bajar volumen»",
    "«Right» en la tecla de «Avanzar 10 segundos»",
    "«Left» en la tecla de «Retroceder 10 segundos»",
]


class TestCableadoMenuReal(unittest.TestCase):

    def test_sin_faltas_nuevas_ni_faltas_que_ya_no_ocurren(self):
        entradas = cc.construir_entradas_reales()
        self.assertEqual(sorted(cc.todas_las_faltas(entradas)),
                         sorted(FALTAS_CONOCIDAS))


if __name__ == "__main__":
    unittest.main()
