"""Pruebas de los avisos de música (anuncios.py), sin wx ni VLC."""

import unittest

from scripts import sound_gen
from ytchat.core import config
from ytchat.music import anuncios
from ytchat.music.modelo import (
    AVANZO,
    COLA_VACIA,
    ERROR_MOTOR,
    FIN_LISTA,
    INICIO_LISTA,
    OK,
    REINICIADO,
    SIN_TEMA,
    TEMA_FALLIDO,
    VOLUMEN_INVALIDO,
    EstadoMusica,
    Resultado,
    Tema,
)


def _tema(n, **campos):
    return Tema(f"C:/musica/tema{n}.mp3", f"Tema {n}", **campos)


def _estado(cola=(), posicion=None, pausado=False, terminado=False):
    return EstadoMusica(tuple(cola), posicion, pausado, terminado, 100, False)


def _resultado(codigo, cola=(), posicion=None, pausado=False, terminado=False,
               tema=None, ok=True):
    return Resultado(ok, codigo, _estado(cola, posicion, pausado, terminado), tema)


class TestNombreTema(unittest.TestCase):

    def test_sin_artista_es_el_titulo(self):
        self.assertEqual(anuncios.nombre_tema(_tema(1), False), "Tema 1")

    def test_con_artista_y_la_casilla_marcada(self):
        self.assertEqual(
            anuncios.nombre_tema(_tema(1, artista="Ana"), True),
            "Tema 1, de Ana")

    def test_con_artista_y_la_casilla_apagada(self):
        self.assertEqual(
            anuncios.nombre_tema(_tema(1, artista="Ana"), False), "Tema 1")

    def test_titulo_vacio_usa_el_archivo_sin_extension(self):
        tema = Tema(r"C:\musica\cancion.mp3", "")
        self.assertEqual(anuncios.nombre_tema(tema, True), "cancion")

    def test_titulo_vacio_de_un_enlace_usa_el_origen(self):
        tema = Tema("https://ejemplo.test/v.mp3", "")
        self.assertEqual(anuncios.nombre_tema(tema, True),
                         "https://ejemplo.test/v.mp3")


class TestAvisoAutomatico(unittest.TestCase):

    def test_avanzo_con_titulo_y_sonido(self):
        r = _resultado(AVANZO, cola=[_tema(1), _tema(2)], posicion=1)
        aviso = anuncios.aviso_automatico(r, True, True, False)
        self.assertEqual(aviso.texto, "Tema 2")
        self.assertEqual(aviso.sonido, "musica_tema")

    def test_avanzo_solo_sonido(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_automatico(r, True, False, False)
        self.assertEqual(aviso.texto, "")
        self.assertEqual(aviso.sonido, "musica_tema")

    def test_avanzo_solo_titulo(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, True, False)
        self.assertEqual(aviso.texto, "Tema 1")
        self.assertIsNone(aviso.sonido)

    def test_avanzo_con_las_dos_casillas_apagadas_no_avisa(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        self.assertIsNone(anuncios.aviso_automatico(r, False, False, False))

    def test_avanzo_incluye_el_artista_si_lo_pide(self):
        r = _resultado(AVANZO, cola=[_tema(1, artista="Ana")], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, True, True)
        self.assertEqual(aviso.texto, "Tema 1, de Ana")

    def test_fin_lista_siempre_avisa(self):
        r = _resultado(FIN_LISTA)
        aviso = anuncios.aviso_automatico(r, False, False, False)
        self.assertEqual(aviso.texto, "Fin de la lista de música")
        self.assertEqual(aviso.sonido, "musica_fin")

    def test_tema_fallido_siempre_avisa_sin_artista(self):
        r = _resultado(TEMA_FALLIDO, tema=_tema(3, artista="Ana"))
        aviso = anuncios.aviso_automatico(r, False, False, True)
        self.assertEqual(
            aviso.texto,
            "No se pudo reproducir: Tema 3. Se pasa al siguiente")
        self.assertEqual(aviso.sonido, "musica_fallo")

    def test_otro_codigo_no_avisa(self):
        for codigo in (OK, SIN_TEMA, COLA_VACIA, INICIO_LISTA,
                       VOLUMEN_INVALIDO, ERROR_MOTOR, "desconocido"):
            with self.subTest(codigo=codigo):
                r = _resultado(codigo)
                self.assertIsNone(
                    anuncios.aviso_automatico(r, True, True, True))


class TestAvisoAccion(unittest.TestCase):

    def test_siguiente_ok_dice_el_tema_nuevo(self):
        r = _resultado(OK, cola=[_tema(1), _tema(2)], posicion=1)
        aviso = anuncios.aviso_accion("siguiente", r, False)
        self.assertEqual(aviso.texto, "Tema 2")
        self.assertIsNone(aviso.sonido)

    def test_anterior_ok_dice_el_tema_nuevo(self):
        r = _resultado(OK, cola=[_tema(1), _tema(2)], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False)
        self.assertEqual(aviso.texto, "Tema 1")

    def test_siguiente_fin_de_lista(self):
        aviso = anuncios.aviso_accion("siguiente", _resultado(FIN_LISTA), False)
        self.assertEqual(aviso.texto, "Último tema de la lista")

    def test_anterior_inicio_de_lista(self):
        aviso = anuncios.aviso_accion("anterior", _resultado(INICIO_LISTA), False)
        self.assertEqual(aviso.texto, "Primer tema de la lista")

    def test_anterior_reiniciado_dice_desde_el_comienzo(self):
        r = _resultado(REINICIADO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False)
        self.assertEqual(aviso.texto, "Desde el comienzo")
        self.assertIsNone(aviso.sonido)

    def test_pausa_ok_en_pausa(self):
        r = _resultado(OK, cola=[_tema(1)], posicion=0, pausado=True)
        self.assertEqual(anuncios.aviso_accion("pausa", r, False).texto,
                         "Música en pausa")

    def test_pausa_ok_reanudada(self):
        r = _resultado(OK, cola=[_tema(1)], posicion=0, pausado=False)
        self.assertEqual(anuncios.aviso_accion("pausa", r, False).texto,
                         "Música reanudada")

    def test_detener_ok(self):
        self.assertEqual(anuncios.aviso_accion("detener", _resultado(OK), False).texto,
                         "Música detenida")

    def test_cualquier_accion_sin_tema(self):
        for accion in ("siguiente", "anterior", "pausa", "detener", "reproducir"):
            with self.subTest(accion=accion):
                aviso = anuncios.aviso_accion(accion, _resultado(SIN_TEMA), False)
                self.assertEqual(aviso.texto, "No hay música sonando")

    def test_cualquier_accion_con_cola_vacia(self):
        aviso = anuncios.aviso_accion("reproducir", _resultado(COLA_VACIA), False)
        self.assertEqual(aviso.texto, "No hay temas para reproducir")

    def test_error_motor_con_tema_lleva_sonido_de_error(self):
        r = _resultado(ERROR_MOTOR, tema=_tema(4), ok=False)
        aviso = anuncios.aviso_accion("reproducir", r, False)
        self.assertEqual(aviso.texto, "No se pudo reproducir: Tema 4")
        self.assertEqual(aviso.sonido, "error")

    def test_error_motor_sin_tema(self):
        r = _resultado(ERROR_MOTOR, ok=False)
        aviso = anuncios.aviso_accion("detener", r, False)
        self.assertEqual(aviso.texto, "No se pudo usar el motor de música")
        self.assertEqual(aviso.sonido, "error")

    def test_reproducir_ok_dice_el_tema_que_empezo(self):
        r = _resultado(OK, cola=[_tema(5)], posicion=0)
        self.assertEqual(anuncios.aviso_accion("reproducir", r, False).texto,
                         "Tema 5")

    def test_reproducir_ok_usa_el_tema_del_resultado(self):
        r = _resultado(OK, cola=[_tema(5)], posicion=0, tema=_tema(9))
        self.assertEqual(anuncios.aviso_accion("reproducir", r, False).texto,
                         "Tema 9")

    def test_otra_combinacion_no_dice_nada(self):
        aviso = anuncios.aviso_accion("desconocida", _resultado(OK), False)
        self.assertEqual(aviso.texto, "")
        self.assertIsNone(aviso.sonido)


class TestOtrosAvisos(unittest.TestCase):

    def test_que_suena_sin_tema(self):
        aviso = anuncios.aviso_que_suena(_estado(), False)
        self.assertEqual(aviso.texto, "No hay música sonando")

    def test_que_suena_con_lista_terminada(self):
        estado = _estado([_tema(1)], 0, terminado=True)
        aviso = anuncios.aviso_que_suena(estado, False)
        self.assertEqual(aviso.texto, "No hay música sonando")

    def test_que_suena_sonando(self):
        estado = _estado([_tema(1), _tema(2)], 0)
        aviso = anuncios.aviso_que_suena(estado, False)
        self.assertEqual(aviso.texto, "Sonando: Tema 1. Tema 1 de 2")

    def test_que_suena_en_pausa(self):
        estado = _estado([_tema(1), _tema(2)], 1, pausado=True)
        aviso = anuncios.aviso_que_suena(estado, False)
        self.assertEqual(aviso.texto, "En pausa: Tema 2. Tema 2 de 2")

    def test_que_suena_con_artista(self):
        estado = _estado([_tema(1, artista="Ana")], 0)
        aviso = anuncios.aviso_que_suena(estado, True)
        self.assertEqual(aviso.texto, "Sonando: Tema 1, de Ana. Tema 1 de 1")

    def test_aleatorio_activado(self):
        self.assertEqual(anuncios.aviso_aleatorio(True).texto,
                         "Orden aleatorio activado")

    def test_aleatorio_desactivado(self):
        self.assertEqual(anuncios.aviso_aleatorio(False).texto,
                         "Orden aleatorio desactivado")

    def test_sin_carpeta_lleva_sonido_de_error(self):
        aviso = anuncios.aviso_sin_carpeta()
        self.assertEqual(
            aviso.texto,
            "No hay carpeta de música. Elige una en Preferencias, página Música")
        self.assertEqual(aviso.sonido, "error")

    def test_motor_no_disponible_lleva_sonido_de_error(self):
        aviso = anuncios.aviso_motor_no_disponible()
        self.assertEqual(
            aviso.texto,
            "La música no está disponible: no se pudo cargar VLC")
        self.assertEqual(aviso.sonido, "error")

    def test_preparando_sin_sonido(self):
        aviso = anuncios.aviso_preparando()
        self.assertEqual(aviso.texto, "Preparando la música")
        self.assertIsNone(aviso.sonido)

    def test_preparando_ocupado_sin_sonido(self):
        aviso = anuncios.aviso_preparando_ocupado()
        self.assertEqual(aviso.texto, "La música se está preparando")
        self.assertIsNone(aviso.sonido)

    def test_agregados_plural(self):
        aviso = anuncios.aviso_agregados(3)
        self.assertEqual(aviso.texto, "3 temas agregados a la cola")
        self.assertIsNone(aviso.sonido)

    def test_agregados_plural_con_lo_que_suena(self):
        aviso = anuncios.aviso_agregados(2, "Tema 1")
        self.assertEqual(aviso.texto,
                         "2 temas agregados a la cola. Sonando: Tema 1")
        self.assertIsNone(aviso.sonido)

    def test_a_continuacion_con_artista(self):
        aviso = anuncios.aviso_a_continuacion(_tema(1, artista="Ana"), True)
        self.assertEqual(aviso.texto, "A continuación: Tema 1, de Ana")
        self.assertIsNone(aviso.sonido)

    def test_a_continuacion_sin_artista(self):
        aviso = anuncios.aviso_a_continuacion(_tema(1, artista="Ana"), False)
        self.assertEqual(aviso.texto, "A continuación: Tema 1")
        self.assertIsNone(aviso.sonido)

    def test_leyendo_enlace_sin_sonido(self):
        aviso = anuncios.aviso_leyendo_enlace()
        self.assertEqual(aviso.texto, "Leyendo el enlace")
        self.assertIsNone(aviso.sonido)

    def test_enlace_no_youtube_lleva_sonido_de_error(self):
        aviso = anuncios.aviso_enlace_no_youtube()
        self.assertEqual(aviso.texto, "Esa dirección no es de YouTube")
        self.assertEqual(aviso.sonido, "error")

    def test_error_de_enlace_lleva_el_mensaje_y_sonido(self):
        aviso = anuncios.aviso_error_enlace("El enlace no tiene vídeos")
        self.assertEqual(aviso.texto, "El enlace no tiene vídeos")
        self.assertEqual(aviso.sonido, "error")


class TestEstadoParaF2(unittest.TestCase):

    def test_sin_estado_da_vacio(self):
        self.assertEqual(anuncios.texto_estado_musica(None, False), "")

    def test_sin_tema_da_vacio(self):
        self.assertEqual(
            anuncios.texto_estado_musica(_estado(), False), "")

    def test_terminada_da_vacio(self):
        self.assertEqual(
            anuncios.texto_estado_musica(
                _estado([_tema(1)], 0, terminado=True), False), "")

    def test_sonando(self):
        estado = _estado([_tema(1), _tema(2)], 0)
        self.assertEqual(anuncios.texto_estado_musica(estado, False),
                         "Música: Tema 1, tema 1 de 2")

    def test_en_pausa(self):
        estado = _estado([_tema(1), _tema(2)], 1, pausado=True)
        self.assertEqual(anuncios.texto_estado_musica(estado, False),
                         "Música en pausa: Tema 2, tema 2 de 2")

    def test_con_artista(self):
        estado = _estado([_tema(1, artista="Ana")], 0)
        self.assertEqual(anuncios.texto_estado_musica(estado, True),
                         "Música: Tema 1, de Ana, tema 1 de 1")

    def test_retomando(self):
        aviso = anuncios.aviso_retomando("Tema 3")
        self.assertEqual(aviso.texto, "Retomando: Tema 3")
        self.assertIsNone(aviso.sonido)


class TestAvisosDeCola(unittest.TestCase):

    def test_a_continuacion_con_posicion_y_artista(self):
        aviso = anuncios.aviso_a_continuacion_posicion(_tema(1, artista="Ana"),
                                                       2, True)
        self.assertEqual(aviso.texto, "A continuación: Tema 1, de Ana, posición 2")
        self.assertIsNone(aviso.sonido)

    def test_varios_a_continuacion(self):
        aviso = anuncios.aviso_a_continuacion_varios(3, 5)
        self.assertEqual(aviso.texto,
                         "3 temas a continuación, desde la posición 5")
        self.assertIsNone(aviso.sonido)

    def test_agregado_con_posicion(self):
        aviso = anuncios.aviso_agregado_posicion(4)
        self.assertEqual(aviso.texto, "Agregado a la cola, posición 4")
        self.assertIsNone(aviso.sonido)

    def test_agregado_con_posicion_y_lo_que_suena(self):
        aviso = anuncios.aviso_agregado_posicion(1, "Tema 1")
        self.assertEqual(aviso.texto,
                         "Agregado a la cola, posición 1. Sonando: Tema 1")
        self.assertIsNone(aviso.sonido)

    def test_quitado_de_la_cola(self):
        aviso = anuncios.aviso_quitado_de_cola("Tema 2")
        self.assertEqual(aviso.texto, "Quitado de la cola: Tema 2")
        self.assertIsNone(aviso.sonido)

    def test_cola_vaciada_con_y_sin_tema_actual(self):
        self.assertEqual(anuncios.aviso_cola_vaciada().texto, "Cola vaciada")
        self.assertEqual(anuncios.aviso_cola_vaciada("Tema 1").texto,
                         "Cola vaciada, sigue sonando Tema 1")
        self.assertIsNone(anuncios.aviso_cola_vaciada("Tema 1").sonido)

    def test_cola_mezclada(self):
        aviso = anuncios.aviso_cola_mezclada()
        self.assertEqual(aviso.texto, "Cola mezclada")
        self.assertIsNone(aviso.sonido)

    def test_repetir_con_los_tres_modos(self):
        self.assertEqual(anuncios.aviso_repetir("no").texto, "Repetir: no")
        self.assertEqual(anuncios.aviso_repetir("todo").texto,
                         "Repetir: toda la cola")
        self.assertEqual(anuncios.aviso_repetir("tema").texto,
                         "Repetir: este tema")
        self.assertEqual(anuncios.aviso_repetir("otro").texto, "Repetir: no")
        self.assertIsNone(anuncios.aviso_repetir("todo").sonido)


class TestAvisosDeListas(unittest.TestCase):

    def test_saltadas_singular_y_plural(self):
        self.assertEqual(anuncios.aviso_saltadas(1).texto,
                         "Se saltó 1 entrada que no se pudo leer")
        self.assertEqual(anuncios.aviso_saltadas(3).texto,
                         "Se saltaron 3 entradas que no se pudieron leer")
        self.assertIsNone(anuncios.aviso_saltadas(2).sonido)

    def test_agregado_a_lista(self):
        aviso = anuncios.aviso_agregado_a_lista("Favoritas")
        self.assertEqual(aviso.texto, "Agregado a la lista Favoritas")
        self.assertIsNone(aviso.sonido)

    def test_creada_renombrada_borrada_guardada(self):
        self.assertEqual(anuncios.aviso_lista_creada("Rock").texto,
                         "Lista creada: Rock")
        self.assertEqual(anuncios.aviso_lista_renombrada("Rock").texto,
                         "Lista renombrada: Rock")
        self.assertEqual(anuncios.aviso_lista_borrada("Rock").texto,
                         "Lista borrada: Rock")
        self.assertEqual(anuncios.aviso_lista_guardada("Rock").texto,
                         "Lista guardada: Rock")

    def test_tema_movido_y_quitado(self):
        self.assertEqual(anuncios.aviso_tema_movido(2, 5).texto,
                         "Tema movido a la posición 2 de 5")
        self.assertEqual(anuncios.aviso_tema_quitado().texto,
                         "Tema quitado de la lista")
        self.assertIsNone(anuncios.aviso_tema_movido(1, 2).sonido)

    def test_sin_cola(self):
        aviso = anuncios.aviso_sin_cola()
        self.assertEqual(aviso.texto, "No hay temas en la cola")
        self.assertIsNone(aviso.sonido)

    def test_error_listas_lleva_sonido_de_error(self):
        aviso = anuncios.aviso_error_listas("Ya hay una lista con ese nombre")
        self.assertEqual(aviso.texto, "Ya hay una lista con ese nombre")
        self.assertEqual(aviso.sonido, "error")


class TestPropiedad(unittest.TestCase):

    CODIGOS = [
        OK, COLA_VACIA, SIN_TEMA, FIN_LISTA, INICIO_LISTA, VOLUMEN_INVALIDO,
        ERROR_MOTOR, TEMA_FALLIDO, AVANZO, "codigo_inventado",
    ]

    def test_aviso_automatico_nunca_lanza_y_su_sonido_esta_registrado(self):
        registrados = set(config._EVENTOS_SONIDO)
        for codigo in self.CODIGOS:
            for sonido_tema in (True, False):
                for decir_titulo in (True, False):
                    for incluir_artista in (True, False):
                        with self.subTest(codigo=codigo, sonido_tema=sonido_tema,
                                          decir_titulo=decir_titulo,
                                          incluir_artista=incluir_artista):
                            r = _resultado(codigo, cola=[_tema(1)], posicion=0,
                                           tema=_tema(1))
                            aviso = anuncios.aviso_automatico(
                                r, sonido_tema, decir_titulo, incluir_artista)
                            if aviso is not None:
                                self.assertIn(aviso.sonido, (None,) + tuple(registrados))

    def test_los_tres_sonidos_nuevos_estan_registrados_y_tienen_generador(self):
        for evento in ("musica_tema", "musica_fin", "musica_fallo"):
            with self.subTest(evento=evento):
                self.assertIn(evento, config._EVENTOS_SONIDO)
                self.assertIn(f"{evento}.wav", sound_gen.TEMAS["default"])
                self.assertIn(f"{evento}.wav", sound_gen.TEMAS["suave"])


if __name__ == "__main__":
    unittest.main()
