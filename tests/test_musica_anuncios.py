"""Pruebas de los avisos de música (anuncios.py), sin wx ni VLC."""

import unittest

from scripts import sound_gen
from tests.pseudo_prueba import con_pseudo
from ytchat.core import config
from ytchat.core.idioma import _
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
        aviso = anuncios.aviso_automatico(r, True, "titulo")
        self.assertEqual(aviso.texto, "Tema 2")
        self.assertEqual(aviso.sonido, "musica_tema")

    def test_avanzo_con_nada_solo_sonido(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_automatico(r, True, "nada")
        self.assertEqual(aviso.texto, "")
        self.assertEqual(aviso.sonido, "musica_tema")

    def test_avanzo_solo_titulo(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, "titulo")
        self.assertEqual(aviso.texto, "Tema 1")
        self.assertIsNone(aviso.sonido)

    def test_avanzo_con_nada_y_sin_sonido_no_avisa(self):
        r = _resultado(AVANZO, cola=[_tema(1)], posicion=0)
        self.assertIsNone(anuncios.aviso_automatico(r, False, "nada"))

    def test_avanzo_con_los_dos_dice_titulo_de_artista(self):
        r = _resultado(AVANZO, cola=[_tema(1, artista="Ana")], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, "titulo_artista")
        self.assertEqual(aviso.texto, "Tema 1, de Ana")

    def test_avanzo_con_artista_dice_solo_el_artista(self):
        r = _resultado(AVANZO, cola=[_tema(1, artista="Ana")], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, "artista")
        self.assertEqual(aviso.texto, "Ana")

    def test_avanzo_sin_tema_usa_el_archivo(self):
        r = _resultado(AVANZO, cola=[Tema(r"C:\musica\cancion.mp3", "")], posicion=0)
        aviso = anuncios.aviso_automatico(r, False, "titulo")
        self.assertEqual(aviso.texto, "cancion")

    def test_fin_lista_siempre_avisa(self):
        r = _resultado(FIN_LISTA)
        aviso = anuncios.aviso_automatico(r, False, "nada")
        self.assertEqual(aviso.texto, "Fin de la lista de música")
        self.assertEqual(aviso.sonido, "musica_fin")

    def test_tema_fallido_siempre_avisa_sin_artista(self):
        r = _resultado(TEMA_FALLIDO, tema=_tema(3, artista="Ana"))
        aviso = anuncios.aviso_automatico(r, False, "artista")
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
                    anuncios.aviso_automatico(r, True, "titulo_artista"))


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
        self.assertEqual(aviso.texto, "Última canción de la lista")

    def test_anterior_inicio_de_lista(self):
        aviso = anuncios.aviso_accion("anterior", _resultado(INICIO_LISTA), False)
        self.assertEqual(aviso.texto, "Primera canción de la lista")

    def test_anterior_reiniciado_dice_desde_el_comienzo(self):
        r = _resultado(REINICIADO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False)
        self.assertEqual(aviso.texto, "Desde el comienzo")
        self.assertIsNone(aviso.sonido)

    def test_reinicio_con_decir_pausa_en_falso_calla(self):
        r = _resultado(REINICIADO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False, False)
        self.assertEqual(aviso.texto, "")
        self.assertIsNone(aviso.sonido)

    def test_reinicio_con_decir_pausa_en_verdadero_avisa(self):
        r = _resultado(REINICIADO, cola=[_tema(1)], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False, True)
        self.assertEqual(aviso.texto, anuncios.TEXTO_REINICIADO)
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
        self.assertEqual(aviso.texto, "No hay canciones para reproducir")

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

    def test_manual_con_nada_dice_el_titulo(self):
        r = _resultado(OK, cola=[_tema(1, artista="Ana")], posicion=0)
        for accion in ("siguiente", "anterior", "reproducir"):
            with self.subTest(accion=accion):
                aviso = anuncios.aviso_accion(accion, r, False, True, "nada")
                self.assertEqual(aviso.texto, "Tema 1")
                self.assertIsNone(aviso.sonido)

    def test_manual_con_artista_dice_solo_el_artista(self):
        r = _resultado(OK, cola=[_tema(1, artista="Ana")], posicion=0)
        aviso = anuncios.aviso_accion("siguiente", r, True, True, "artista")
        self.assertEqual(aviso.texto, "Ana")

    def test_manual_con_los_dos_dice_titulo_de_artista(self):
        r = _resultado(OK, cola=[_tema(1, artista="Ana")], posicion=0)
        aviso = anuncios.aviso_accion("anterior", r, False, True, "titulo_artista")
        self.assertEqual(aviso.texto, "Tema 1, de Ana")

    def test_manual_sin_modo_respeta_la_casilla_vieja(self):
        r = _resultado(OK, cola=[_tema(1, artista="Ana")], posicion=0)
        self.assertEqual(anuncios.aviso_accion("siguiente", r, False).texto,
                         "Tema 1")
        self.assertEqual(anuncios.aviso_accion("siguiente", r, True).texto,
                         "Tema 1, de Ana")

    def test_pausa_con_decir_pausa_en_falso_calla(self):
        for pausado in (True, False):
            with self.subTest(pausado=pausado):
                r = _resultado(OK, cola=[_tema(1)], posicion=0, pausado=pausado)
                aviso = anuncios.aviso_accion("pausa", r, False, False)
                self.assertEqual(aviso.texto, "")
                self.assertIsNone(aviso.sonido)

    def test_pausa_con_decir_pausa_igual_que_hoy(self):
        en_pausa = _resultado(OK, cola=[_tema(1)], posicion=0, pausado=True)
        reanudada = _resultado(OK, cola=[_tema(1)], posicion=0, pausado=False)
        self.assertEqual(anuncios.aviso_accion("pausa", en_pausa, False, True).texto,
                         "Música en pausa")
        self.assertEqual(anuncios.aviso_accion("pausa", reanudada, False, True).texto,
                         "Música reanudada")

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
        self.assertEqual(aviso.texto, "Sonando: Tema 1. Canción 1 de 2")

    def test_que_suena_en_pausa(self):
        estado = _estado([_tema(1), _tema(2)], 1, pausado=True)
        aviso = anuncios.aviso_que_suena(estado, False)
        self.assertEqual(aviso.texto, "En pausa: Tema 2. Canción 2 de 2")

    def test_que_suena_con_artista(self):
        estado = _estado([_tema(1, artista="Ana")], 0)
        aviso = anuncios.aviso_que_suena(estado, True)
        self.assertEqual(aviso.texto, "Sonando: Tema 1, de Ana. Canción 1 de 1")

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
        self.assertEqual(aviso.texto, "3 canciones agregadas a la cola")
        self.assertIsNone(aviso.sonido)

    def test_agregados_plural_con_lo_que_suena(self):
        aviso = anuncios.aviso_agregados(2, "Tema 1")
        self.assertEqual(aviso.texto,
                          "2 canciones agregadas a la cola. Sonando: Tema 1")
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
                          "Música: Tema 1, canción 1 de 2")

    def test_en_pausa(self):
        estado = _estado([_tema(1), _tema(2)], 1, pausado=True)
        self.assertEqual(anuncios.texto_estado_musica(estado, False),
                          "Música en pausa: Tema 2, canción 2 de 2")

    def test_con_artista(self):
        estado = _estado([_tema(1, artista="Ana")], 0)
        self.assertEqual(anuncios.texto_estado_musica(estado, True),
                          "Música: Tema 1, de Ana, canción 1 de 1")

    def test_retomando_una_cancion(self):
        aviso = anuncios.aviso_retomando("Tema 3", 1)
        self.assertEqual(aviso.texto, "Retomando 1 canción: Tema 3")
        self.assertIsNone(aviso.sonido)

    def test_retomando_varias_canciones(self):
        aviso = anuncios.aviso_retomando("Tema 3", 6)
        self.assertEqual(aviso.texto, "Retomando 6 canciones: Tema 3")
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
                          "3 canciones a continuación, desde la posición 5")
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
        self.assertEqual(aviso.texto, "Eliminado de la cola: Tema 2")
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
                          "Repetir: esta canción")
        self.assertEqual(anuncios.aviso_repetir("otro").texto, "Repetir: no")
        self.assertIsNone(anuncios.aviso_repetir("todo").sonido)


class TestAvisosDeListas(unittest.TestCase):

    def test_faltantes_nombra_una_o_varias_canciones(self):
        self.assertEqual(
            anuncios.aviso_faltantes(("Don Quijote",)).texto,
            "No se encontró una canción de la lista: Don Quijote")
        self.assertEqual(
            anuncios.aviso_faltantes(("A", "B")).texto,
            "No se encontraron 2 canciones de la lista: A y B")
        self.assertEqual(
            anuncios.aviso_faltantes(("A", "B", "C")).texto,
            "No se encontraron 3 canciones de la lista: A, B y C")

    def test_faltantes_con_mas_de_tres_resume_el_resto(self):
        self.assertEqual(
            anuncios.aviso_faltantes(("A", "B", "C", "D")).texto,
            "No se encontraron 4 canciones de la lista: A, B, C y 1 más")
        self.assertEqual(
            anuncios.aviso_faltantes(("A", "B", "C", "D", "E")).texto,
            "No se encontraron 5 canciones de la lista: A, B, C y 2 más")
        self.assertIsNone(anuncios.aviso_faltantes(("A", "B")).sonido)

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
                          "Canción movida a la posición 2 de 5")
        self.assertEqual(anuncios.aviso_tema_quitado().texto,
                         "Canción eliminada de la lista")
        self.assertIsNone(anuncios.aviso_tema_movido(1, 2).sonido)

    def test_sin_cola(self):
        aviso = anuncios.aviso_sin_cola()
        self.assertEqual(aviso.texto, "No hay canciones en la cola")
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
                for modo in ("nada", "titulo", "titulo_artista", "artista"):
                    with self.subTest(codigo=codigo, sonido_tema=sonido_tema,
                                      modo=modo):
                        r = _resultado(codigo, cola=[_tema(1)], posicion=0,
                                       tema=_tema(1))
                        aviso = anuncios.aviso_automatico(r, sonido_tema, modo)
                        if aviso is not None:
                            self.assertIn(aviso.sonido, (None,) + tuple(registrados))

    def test_aviso_accion_nunca_lanza_con_los_modos(self):
        for modo in ("nada", "titulo", "titulo_artista", "artista", None):
            for decir_pausa in (True, False):
                with self.subTest(modo=modo, decir_pausa=decir_pausa):
                    r = _resultado(OK, cola=[_tema(1, artista="Ana")],
                                   posicion=0, tema=_tema(1, artista="Ana"))
                    for accion in ("siguiente", "anterior", "reproducir",
                                   "pausa", "detener"):
                        aviso = anuncios.aviso_accion(
                            accion, r, False, decir_pausa, modo)
                        self.assertIsInstance(aviso.texto, str)

    def test_los_tres_sonidos_nuevos_estan_registrados_y_tienen_generador(self):
        for evento in ("musica_tema", "musica_fin", "musica_fallo"):
            with self.subTest(evento=evento):
                self.assertIn(evento, config._EVENTOS_SONIDO)
                self.assertIn(f"{evento}.wav", sound_gen.TEMAS["default"])
                self.assertIn(f"{evento}.wav", sound_gen.TEMAS["suave"])


class TestTextosVentanaMusica(unittest.TestCase):

    def test_busqueda(self):
        self.assertEqual(anuncios.TEXTO_BUSQUEDA_BORRADA, "Búsqueda borrada")

    def test_coincidencias(self):
        self.assertEqual(anuncios.TEXTO_UN_TEMA_COINCIDE, "1 canción coincide")
        self.assertEqual(anuncios.TEXTO_TEMAS_COINCIDEN,
                         "{cantidad} canciones coinciden")
        self.assertEqual(anuncios.TEXTO_NINGUN_TEMA_COINCIDE,
                         "Ninguna canción coincide")

    def test_ayudas(self):
        self.assertEqual(
            anuncios.TEXTO_AYUDA_BIBLIOTECA,
            "Intro reproduce ahora, Mayús más Intro a continuación, "
            "Control más Intro al final, tecla de aplicaciones para más "
            "opciones")
        self.assertEqual(
            anuncios.TEXTO_AYUDA_BIBLIOTECA_LISTA,
            "Intro reproduce ahora, Mayús más Intro a continuación, Ctrl más Intro "
            "al final, tecla de aplicaciones para más opciones, Suprimir elimina de la lista")
        self.assertEqual(
            anuncios.TEXTO_AYUDA_COLA,
            "Intro reproduce, Suprimir elimina, Alt más flechas mueve, "
            "tecla de aplicaciones para más opciones")
        self.assertEqual(
            anuncios.TEXTO_AYUDA_BUSCAR,
            "Escribe para filtrar, flecha abajo va a las canciones, "
            "Escape borra la búsqueda")

    def test_confirmar_borrar(self):
        self.assertEqual(anuncios.TEXTO_CONFIRMAR_BORRAR_LISTA,
                         "¿Borrar la lista {nombre}?")
        self.assertEqual(
            anuncios.TEXTO_CONFIRMAR_BORRAR_LISTA.format(nombre="Rock"),
            "¿Borrar la lista Rock?")


class TestPseudoAnuncios(unittest.TestCase):
    """Pseudotraducción de los avisos de música.

    Sin ventanas: llama a las funciones bajo `con_pseudo()` y exige cada
    texto propio marcado. Los datos (nombres, cantidades, combinaciones)
    viajan con ejemplos y se exigen presentes.
    """

    _CONSTANTES = (
        "TEXTO_FIN_LISTA",
        "TEXTO_SIN_TEMA",
        "TEXTO_COLA_VACIA",
        "TEXTO_ULTIMO",
        "TEXTO_PRIMERO",
        "TEXTO_REINICIADO",
        "TEXTO_PAUSA",
        "TEXTO_REANUDADA",
        "TEXTO_DETENIDA",
        "TEXTO_ERROR_MOTOR",
        "TEXTO_QUE_SUENA",
        "TEXTO_EN_PAUSA",
        "TEXTO_ESTADO_MUSICA",
        "TEXTO_ESTADO_MUSICA_PAUSA",
        "TEXTO_RETOMANDO",
        "TEXTO_ALEATORIO_ON",
        "TEXTO_ALEATORIO_OFF",
        "TEXTO_SIN_CARPETA",
        "TEXTO_MOTOR",
        "TEXTO_PREPARANDO",
        "TEXTO_PREPARANDO_OCUPADO",
        "TEXTO_AGREGADOS",
        "TEXTO_AGREGADO_POSICION",
        "TEXTO_AGREGADO_SUENA",
        "TEXTO_A_CONTINUACION",
        "TEXTO_A_CONTINUACION_POSICION",
        "TEXTO_A_CONTINUACION_VARIOS",
        "TEXTO_QUITADO_COLA",
        "TEXTO_COLA_VACIADA",
        "TEXTO_COLA_VACIADA_SIGUE",
        "TEXTO_COLA_MEZCLADA",
        "TEXTO_REPETIR_NO",
        "TEXTO_REPETIR_TODO",
        "TEXTO_REPETIR_TEMA",
        "TEXTO_FALTANTE",
        "TEXTO_FALTANTES",
        "TEXTO_AGREGADO_A_LISTA",
        "TEXTO_LISTA_CREADA",
        "TEXTO_LISTA_RENOMBRADA",
        "TEXTO_LISTA_BORRADA",
        "TEXTO_LISTA_GUARDADA",
        "TEXTO_TEMA_MOVIDO",
        "TEXTO_TEMA_QUITADO",
        "TEXTO_COLA_SIN_TEMAS",
        "TEXTO_LEYENDO_ENLACE",
        "TEXTO_ENLACE_NO_YOUTUBE",
        "TEXTO_ATAJOS_GLOBALES_FALLO",
        "TEXTO_ATAJOS_GLOBALES_ACTIVOS",
        "TEXTO_VENTANA_ABIERTA",
        "TEXTO_BUSQUEDA_BORRADA",
        "TEXTO_FILTROS_VISIBLES",
        "TEXTO_FILTROS_OCULTOS",
        "TEXTO_UN_TEMA_COINCIDE",
        "TEXTO_TEMAS_COINCIDEN",
        "TEXTO_NINGUN_TEMA_COINCIDE",
        "TEXTO_AYUDA_BIBLIOTECA",
        "TEXTO_AYUDA_BIBLIOTECA_LISTA",
        "TEXTO_AYUDA_COLA",
        "TEXTO_AYUDA_BUSCAR",
        "TEXTO_CONFIRMAR_BORRAR_LISTA",
    )

    def test_constantes_salen_marcadas_donde_se_usan(self):
        with con_pseudo():
            for nombre in self._CONSTANTES:
                with self.subTest(nombre=nombre):
                    self.assertTrue(
                        _(getattr(anuncios, nombre)).startswith("[¡"), nombre)
            self.assertTrue(
                _(anuncios._TEXTO_ATAJOS_GLOBALES_SOLO).startswith("[¡"))

    def test_nombre_tema_marca_el_conector_con_los_datos(self):
        with con_pseudo():
            texto = anuncios.nombre_tema(_tema(1, artista="Ana"), True)
        self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("Tema 1", texto)
        self.assertIn("Ana", texto)

    def test_automatico_marca_fin_y_fallo_con_el_nombre(self):
        with con_pseudo():
            fin = anuncios.aviso_automatico(_resultado(FIN_LISTA), False,
                                            "nada")
            fallo = anuncios.aviso_automatico(
                _resultado(TEMA_FALLIDO, tema=_tema(3)), False, "nada")
        self.assertTrue(fin.texto.startswith("[¡"), fin.texto)
        self.assertTrue(fallo.texto.startswith("[¡"), fallo.texto)
        self.assertIn("Tema 3", fallo.texto)

    def test_accion_marca_cada_camino_con_sus_datos(self):
        with con_pseudo():
            sin_tema = anuncios.aviso_accion(
                "reproducir", _resultado(SIN_TEMA), False)
            cola_vacia = anuncios.aviso_accion(
                "reproducir", _resultado(COLA_VACIA), False)
            error = anuncios.aviso_accion(
                "reproducir", _resultado(ERROR_MOTOR, tema=_tema(4)), False)
            ultimo = anuncios.aviso_accion(
                "siguiente", _resultado(FIN_LISTA), False)
            primero = anuncios.aviso_accion(
                "anterior", _resultado(INICIO_LISTA), False)
            reiniciado = anuncios.aviso_accion(
                "anterior", _resultado(REINICIADO), False)
            pausa = anuncios.aviso_accion(
                "pausa", _resultado(OK, cola=[_tema(1)], posicion=0,
                                    pausado=True), False)
            detenida = anuncios.aviso_accion(
                "detener", _resultado(OK, cola=[_tema(1)], posicion=0), False)
            suena = anuncios.aviso_accion(
                "reproducir", _resultado(OK, cola=[_tema(5)], posicion=0),
                False)
        for aviso in (sin_tema, cola_vacia, error, ultimo, primero,
                      reiniciado, pausa, detenida):
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
        self.assertIn("Tema 4", error.texto)
        self.assertEqual(suena.texto, "Tema 5")

    def test_que_suena_y_estado_marcan_con_posicion_y_total(self):
        estado = _estado([_tema(1), _tema(2)], posicion=0)
        with con_pseudo():
            suena = anuncios.aviso_que_suena(estado, False)
            en_pausa = anuncios.aviso_que_suena(
                _estado([_tema(1), _tema(2)], posicion=1, pausado=True),
                False)
            estado_f2 = anuncios.texto_estado_musica(estado, False)
        for texto in (suena.texto, en_pausa.texto, estado_f2):
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)
        self.assertIn("Tema 1", suena.texto)
        self.assertIn("Tema 2", en_pausa.texto)
        self.assertIn("Tema 1", estado_f2)
        self.assertIn("1", suena.texto)
        self.assertIn("2", suena.texto)

    def test_retomando_marca_en_singular_y_en_plural(self):
        with con_pseudo():
            uno = anuncios.aviso_retomando("Tema 3", 1)
            varios = anuncios.aviso_retomando("Tema 3", 6)
        for aviso in (uno, varios):
            self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
            self.assertIn("Tema 3", aviso.texto)
        self.assertIn("1", uno.texto)
        self.assertIn("6", varios.texto)

    def test_agregados_marcan_cantidad_y_lo_que_suena(self):
        with con_pseudo():
            sin_sonar = anuncios.aviso_agregados(2)
            sonando = anuncios.aviso_agregados(2, "Tema 1")
            posicion = anuncios.aviso_agregado_posicion(4, "Tema 2")
            a_continuacion = anuncios.aviso_a_continuacion(_tema(6), False)
        for aviso in (sin_sonar, sonando, posicion, a_continuacion):
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
        self.assertIn("2", sonando.texto)
        self.assertIn("Tema 1", sonando.texto)
        self.assertIn("4", posicion.texto)
        self.assertIn("Tema 6", a_continuacion.texto)

    def test_cola_marca_quitado_vaciada_y_mezclada(self):
        with con_pseudo():
            quitado = anuncios.aviso_quitado_de_cola("Tema 7")
            vaciada = anuncios.aviso_cola_vaciada()
            vaciada_sigue = anuncios.aviso_cola_vaciada("Tema 8")
            mezclada = anuncios.aviso_cola_mezclada()
            movido = anuncios.aviso_tema_movido(3, 9)
        for aviso in (quitado, vaciada, vaciada_sigue, mezclada, movido):
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
        self.assertIn("Tema 7", quitado.texto)
        self.assertIn("Tema 8", vaciada_sigue.texto)
        self.assertIn("3", movido.texto)
        self.assertIn("9", movido.texto)

    def test_faltantes_marcan_desde_cero_hasta_varios(self):
        with con_pseudo():
            vacio = anuncios.aviso_faltantes(())
            uno = anuncios.aviso_faltantes(("Don Quijote",))
            dos = anuncios.aviso_faltantes(("A", "B"))
            tres = anuncios.aviso_faltantes(("A", "B", "C"))
            cinco = anuncios.aviso_faltantes(("A", "B", "C", "D", "E"))
        self.assertEqual(vacio.texto, "")
        for aviso in (uno, dos, tres, cinco):
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
        self.assertIn("Don Quijote", uno.texto)
        self.assertIn("5", cinco.texto)

    def test_listas_marcan_con_el_nombre(self):
        with con_pseudo():
            agregados = (
                ("Rock", anuncios.aviso_agregado_a_lista("Rock")),
                ("Rock", anuncios.aviso_lista_creada("Rock")),
                ("Pop", anuncios.aviso_lista_renombrada("Pop")),
                ("Pop", anuncios.aviso_lista_borrada("Pop")),
                ("Mezcla", anuncios.aviso_lista_guardada("Mezcla")),
            )
            fijos = (
                anuncios.aviso_tema_quitado(),
                anuncios.aviso_sin_cola(),
                anuncios.aviso_leyendo_enlace(),
            )
        for nombre, aviso in agregados:
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
                self.assertIn(nombre, aviso.texto)
        for aviso in fijos:
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)

    def test_atajos_marcan_con_las_combinaciones_y_la_app(self):
        with con_pseudo():
            fallo = anuncios.aviso_atajos_globales_fallo(
                ["Ctrl+Alt+T", "Ctrl+Alt+M"])
            activos = anuncios.aviso_atajos_globales_activos()
            solo = anuncios.aviso_atajos_globales_solo()
        for aviso in (fallo, activos, solo):
            with self.subTest(aviso=aviso.texto):
                self.assertTrue(aviso.texto.startswith("[¡"), aviso.texto)
        self.assertIn("Ctrl+Alt+T", fallo.texto)
        self.assertIn(config.APP_NAME, solo.texto)


if __name__ == "__main__":
    unittest.main()
