"""Pruebas del adaptador de música sobre libVLC (`adaptador_vlc.py`)."""

import os
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

from ytchat.music.adaptador_vlc import (
    AdaptadorVlc,
    MotorNoDisponible,
    leer_etiquetas_vlc,
    salidas_audio,
)
from ytchat.music import adaptador_vlc, enlaces
from ytchat.music.enlaces import ErrorEnlace
from ytchat.music.coordinador import Coordinador
from ytchat.music.modelo import AVANZO, FIN_LISTA, TEMA_FALLIDO, Tema
from ytchat.player import motor_vlc


def esperar(condicion, plazo=5.0):
    """Espera activa y acotada, para no colgar la suite si algo no llega."""
    fin = time.monotonic() + plazo
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.01)
    return condicion()


class FakeEvento:
    pass


class FakeGestor:
    """Gestor de eventos falso que avisa si lo llaman durante el despacho."""

    def __init__(self):
        self.manejadores = {}
        self.despachando = False

    def event_attach(self, tipo, callback):
        self.manejadores[tipo] = callback

    def disparar(self, tipo):
        callback = self.manejadores.get(tipo)
        if callback is None:
            return
        self.despachando = True
        try:
            callback(FakeEvento())
        finally:
            self.despachando = False


class FakeMedia:
    def __init__(self, origen):
        self.origen = origen
        self.opciones = []

    def add_option(self, opcion):
        self.opciones.append(opcion)


class FakeMediaEtiquetas:
    """Media falsa para leer etiquetas: puede disparar el aviso de parseo o no."""

    def __init__(self, metas=None, dispara=True):
        self.gestor = FakeGestor()
        self.metas = metas or {}
        self.dispara = dispara
        self.liberada = False

    def event_manager(self):
        return self.gestor

    def parse_with_options(self, bandera, plazo):
        if self.dispara:
            self.gestor.disparar(FakeVlc.EventType.MediaParsedChanged)
        return 0

    def get_meta(self, clave):
        return self.metas.get(clave)

    def release(self):
        self.liberada = True


class FakeReproductor:
    """Reproductor falso que revienta si libVLC se usa dentro de un callback."""

    def __init__(self, instancia, numero):
        self.instancia = instancia
        self.gestor = FakeGestor()
        self.numero = numero
        self.volumen = None
        self.salida = None
        self.dispositivo = None
        self.liberado = False
        self.pausa = None
        self.media = None
        self.tiempo = 0
        self._play = instancia.play_resultado

    def _revisar(self):
        if self.gestor.despachando:
            raise AssertionError("libVLC llamado dentro de un callback")

    def event_manager(self):
        return self.gestor

    def audio_output_set(self, nombre):
        self._revisar()
        self.salida = nombre
        return 0

    def audio_output_device_set(self, module, device):
        self._revisar()
        self.dispositivo = (module, device)
        self.instancia.eventos.append(("dispositivo", self.numero))

    def audio_output_device_enum(self):
        self._revisar()
        if self.instancia.enum_error:
            raise RuntimeError("fallo al enumerar")
        return self.instancia.enum_salida

    def set_media(self, media):
        self._revisar()
        self.media = media

    def audio_set_volume(self, valor):
        self._revisar()
        self.volumen = valor

    def play(self):
        self._revisar()
        self.instancia.eventos.append(("play", self.numero))
        return self._play

    def set_pause(self, valor):
        self._revisar()
        self.pausa = valor

    def get_time(self):
        self._revisar()
        self.instancia.eventos.append(("tiempo", self.numero))
        return self.tiempo

    def set_time(self, ms):
        self._revisar()
        self.tiempo = ms
        self.instancia.eventos.append(("ir_a", self.numero, ms))

    def stop(self):
        self._revisar()
        self.instancia.eventos.append(("stop", self.numero))

    def release(self):
        self._revisar()
        self.liberado = True
        self.instancia.eventos.append(("release", self.numero))


class FakeInstancia:
    def __init__(self):
        self.eventos = []
        self.reproductores = []
        self.play_resultado = 0
        self.media_etiquetas = None
        self.enum_error = False
        self.enum_salida = None

    def media_player_new(self):
        reproductor = FakeReproductor(self, len(self.reproductores))
        self.reproductores.append(reproductor)
        return reproductor

    def media_new(self, origen):
        if self.media_etiquetas is not None:
            return self.media_etiquetas
        return FakeMedia(origen)


class FakeVlc:
    class EventType:
        MediaPlayerEndReached = "fin"
        MediaPlayerEncounteredError = "error"
        MediaPlayerPlaying = "playing"
        MediaParsedChanged = "parsed"

    class MediaParseFlag:
        local = 0

    class Meta:
        Title = 0
        Artist = 1
        Album = 2


class _BaseDobles(unittest.TestCase):

    def setUp(self):
        self.instancia = FakeInstancia()
        self.vlc = FakeVlc()
        self.existentes = set()
        self._p_inst = mock.patch.object(
            motor_vlc, "instancia", return_value=self.instancia)
        self._p_mod = mock.patch.object(motor_vlc, "modulo", return_value=self.vlc)
        self._p_isfile = mock.patch.object(
            os.path, "isfile", side_effect=lambda ruta: ruta in self.existentes)
        self._p_inst.start()
        self._p_mod.start()
        self._p_isfile.start()

    def tearDown(self):
        self._p_isfile.stop()
        self._p_mod.stop()
        self._p_inst.stop()

    def crear(self, **kwargs):
        adaptador = AdaptadorVlc(**kwargs)
        self.addCleanup(adaptador.cerrar)
        return adaptador


class TestAdaptadorDobles(_BaseDobles):

    def test_motor_no_disponible(self):
        with mock.patch.object(motor_vlc, "instancia", return_value=None):
            with self.assertRaises(MotorNoDisponible):
                AdaptadorVlc()

    def test_archivo_ausente_corta_de_una(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        with self.assertRaises(FileNotFoundError):
            adaptador.cargar(Tema("C:/musica/no-existe.mp3", "n"), 3)
        self.assertEqual(len(self.instancia.reproductores), 1)
        self.assertIs(adaptador._actual, self.instancia.reproductores[0])

    def test_un_reproductor_por_tema(self):
        adaptador = self.crear()
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        self.assertEqual(len(self.instancia.reproductores), 2)

    def test_el_anterior_se_cierra_despues_del_play(self):
        adaptador = self.crear()
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        self.assertTrue(esperar(lambda: self.instancia.reproductores[0].liberado))
        eventos = self.instancia.eventos
        self.assertLess(eventos.index(("play", 1)), eventos.index(("stop", 0)))

    def test_play_menos_uno_deja_el_anterior(self):
        adaptador = self.crear()
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        anterior = adaptador._actual
        self.instancia.play_resultado = -1
        with self.assertRaises(RuntimeError):
            adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        self.assertIs(adaptador._actual, anterior)
        self.assertTrue(esperar(lambda: self.instancia.reproductores[1].liberado))

    def test_el_callback_no_toca_el_reproductor(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        reproductor = self.instancia.reproductores[0]
        reproductor.gestor.disparar(FakeVlc.EventType.MediaPlayerEndReached)

    def test_el_aviso_corre_en_su_hilo_y_fuera_del_callback(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        vistos = []
        recibido = threading.Event()

        def aviso(ficha, fallo):
            vistos.append((ficha, fallo, threading.current_thread().name,
                           reproductor.gestor.despachando))
            recibido.set()

        adaptador.asignar_aviso(aviso)
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 7)
        reproductor = self.instancia.reproductores[0]
        reproductor.gestor.disparar(FakeVlc.EventType.MediaPlayerEndReached)
        self.assertTrue(recibido.wait(5), "el aviso no llegó")
        ficha, fallo, nombre, dentro = vistos[0]
        self.assertEqual(ficha, 7)
        self.assertFalse(fallo)
        self.assertEqual(nombre, "musica-vlc")
        self.assertFalse(dentro)

    def test_fin_de_ficha_vieja_se_entrega(self):
        adaptador = self.crear()
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        fichas = []
        recibido = threading.Event()

        def aviso(ficha, fallo):
            fichas.append(ficha)
            recibido.set()

        adaptador.asignar_aviso(aviso)
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        self.instancia.reproductores[0].gestor.disparar(
            FakeVlc.EventType.MediaPlayerEndReached)
        self.assertTrue(recibido.wait(5), "el aviso no llegó")
        self.assertEqual(fichas, [1])

    def test_volumen_reaplicado_solo_al_actual(self):
        adaptador = self.crear()
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        viejo, actual = self.instancia.reproductores
        adaptador.volumen(70)
        self.assertEqual(actual.volumen, 70)
        viejo.volumen = None
        actual.volumen = None
        viejo.gestor.disparar(FakeVlc.EventType.MediaPlayerPlaying)
        actual.gestor.disparar(FakeVlc.EventType.MediaPlayerPlaying)
        self.assertTrue(esperar(lambda: actual.volumen == 70))
        self.assertIsNone(viejo.volumen)

    def test_aviso_que_lanza_no_mata_el_hilo(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        llamadas = []
        dos = threading.Event()

        def aviso(ficha, fallo):
            llamadas.append(ficha)
            if len(llamadas) >= 2:
                dos.set()
            raise RuntimeError("boom")

        adaptador.asignar_aviso(aviso)
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        reproductor = self.instancia.reproductores[0]
        with self.assertLogs("ytchat.adaptador_vlc", level="ERROR"):
            reproductor.gestor.disparar(FakeVlc.EventType.MediaPlayerEndReached)
            reproductor.gestor.disparar(FakeVlc.EventType.MediaPlayerEndReached)
            self.assertTrue(dos.wait(5), "el hilo no siguió tras la excepción")
        self.assertEqual(len(llamadas), 2)

    def test_cerrar_dos_veces(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cerrar()
        adaptador.cerrar()

    def test_operaciones_sin_reproductor(self):
        adaptador = self.crear()
        adaptador.pausar()
        adaptador.reanudar()
        adaptador.detener()
        adaptador.volumen(30)
        self.assertEqual(self.instancia.reproductores, [])

    def test_pausar_reanudar_y_detener(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        reproductor = self.instancia.reproductores[0]
        adaptador.pausar()
        self.assertEqual(reproductor.pausa, 1)
        adaptador.reanudar()
        self.assertEqual(reproductor.pausa, 0)
        adaptador.detener()
        self.assertIsNone(adaptador._actual)
        self.assertTrue(esperar(lambda: reproductor.liberado))

    def test_tiempo_ms_sin_tema_devuelve_none(self):
        adaptador = self.crear()
        self.assertIsNone(adaptador.tiempo_ms())

    def test_tiempo_ms_lee_el_reproductor_actual(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        self.instancia.reproductores[0].tiempo = 2500
        self.assertEqual(adaptador.tiempo_ms(), 2500)

    def test_tiempo_ms_descarta_lo_que_vlc_no_sabe(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        self.instancia.reproductores[0].tiempo = -1
        self.assertIsNone(adaptador.tiempo_ms())

    def test_ir_a_sin_tema_no_hace_nada(self):
        adaptador = self.crear()
        adaptador.ir_a(1000)
        self.assertEqual(self.instancia.eventos, [])

    def test_ir_a_salta_en_el_reproductor_actual(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.ir_a(1200)
        self.assertEqual(self.instancia.reproductores[0].tiempo, 1200)
        self.assertIn(("ir_a", 0, 1200), self.instancia.eventos)

    def test_dispositivo_se_aplica_antes_de_play_en_cada_reproductor(self):
        adaptador = self.crear(dispositivo="salida-x")
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        for numero, reproductor in enumerate(self.instancia.reproductores):
            self.assertEqual(reproductor.dispositivo, (None, "salida-x"))
            eventos = self.instancia.eventos
            self.assertLess(eventos.index(("dispositivo", numero)),
                            eventos.index(("play", numero)))

    def test_sin_dispositivo_no_se_llama(self):
        adaptador = self.crear()
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        reproductor = self.instancia.reproductores[0]
        self.assertIsNone(reproductor.dispositivo)
        self.assertNotIn(("dispositivo", 0), self.instancia.eventos)

    def test_dispositivo_vacio_usa_el_predeterminado(self):
        adaptador = self.crear(dispositivo="")
        self.existentes.add("C:/musica/a.mp3")
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        self.assertIsNone(self.instancia.reproductores[0].dispositivo)

    def test_fijar_dispositivo_no_toca_el_reproductor_actual(self):
        adaptador = self.crear(dispositivo="salida-x")
        self.existentes.update({"C:/musica/a.mp3", "C:/musica/b.mp3"})
        adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
        actual = self.instancia.reproductores[0]
        adaptador.fijar_dispositivo("salida-y")
        self.assertEqual(actual.dispositivo, (None, "salida-x"))
        adaptador.cargar(Tema("C:/musica/b.mp3", "b"), 2)
        self.assertEqual(self.instancia.reproductores[1].dispositivo,
                         (None, "salida-y"))

    def test_salidas_audio_con_doble_que_lanza_devuelve_vacio(self):
        self.instancia.enum_error = True
        self.assertEqual(salidas_audio(), [])

    def test_leer_etiquetas_sin_motor(self):
        with mock.patch.object(motor_vlc, "instancia", return_value=None):
            self.assertEqual(leer_etiquetas_vlc("C:/musica/a.mp3"), {})

    def test_leer_etiquetas_usa_las_etiquetas(self):
        self.instancia.media_etiquetas = FakeMediaEtiquetas(
            metas={0: "Canción", 1: "Artista", 2: "Álbum"})
        datos = leer_etiquetas_vlc("C:/musica/a.mp3")
        self.assertEqual(
            datos, {"titulo": "Canción", "artista": "Artista", "album": "Álbum"})

    def test_leer_etiquetas_descarta_el_nombre_del_archivo(self):
        self.instancia.media_etiquetas = FakeMediaEtiquetas(metas={0: "a"})
        self.assertEqual(leer_etiquetas_vlc("C:/musica/a.mp3")["titulo"], "")

    def test_leer_etiquetas_se_vence_el_plazo(self):
        self.instancia.media_etiquetas = FakeMediaEtiquetas(dispara=False)
        inicio = time.monotonic()
        self.assertEqual(leer_etiquetas_vlc("C:/musica/a.mp3", plazo_ms=50), {})
        self.assertLess(time.monotonic() - inicio, 5.0)
        self.assertTrue(self.instancia.media_etiquetas.liberada)


class TestAdaptadorEnlaces(_BaseDobles):
    """Enlaces de YouTube: no bloquean y resuelven el audio en un hilo."""

    def _adaptador_con_opciones(self, **kwargs):
        self._p_opciones = mock.patch.object(
            adaptador_vlc, "_opciones_enlace", return_value=(":opcion-red",))
        self._p_opciones.start()
        self.addCleanup(self._p_opciones.stop)
        return self.crear(**kwargs)

    def test_el_enlace_no_bloquea_y_suena_la_direccion_resuelta(self):
        adaptador = self._adaptador_con_opciones()
        soltar = threading.Event()

        def url_audio(_origen):
            soltar.wait(5)
            return "http://audio/stream"

        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            self.assertIsNone(adaptador._actual)
            self.assertEqual(self.instancia.reproductores, [])
            soltar.set()
            self.assertTrue(
                esperar(lambda: len(self.instancia.reproductores) == 1))
        reproductor = self.instancia.reproductores[0]
        self.assertEqual(reproductor.media.origen, "http://audio/stream")
        self.assertEqual(reproductor.media.opciones, [":opcion-red"])
        self.assertIs(adaptador._actual, reproductor)
        self.assertIn(("play", 0), self.instancia.eventos)

    def test_la_ficha_vieja_se_descarta(self):
        adaptador = self._adaptador_con_opciones()
        self.existentes.add("C:/musica/a.mp3")
        soltar = threading.Event()
        resuelto = threading.Event()

        def url_audio(_origen):
            soltar.wait(5)
            resuelto.set()
            return "http://audio/vieja"

        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "vieja"), 1)
            adaptador.cargar(Tema("C:/musica/a.mp3", "nueva"), 2)
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            time.sleep(0.1)
        self.assertEqual(len(self.instancia.reproductores), 1)
        self.assertEqual(adaptador._actual.media.origen, "C:/musica/a.mp3")

    def test_fallo_de_url_audio_avisa_fallo_desde_el_consumidor(self):
        adaptador = self._adaptador_con_opciones()
        vistos = []
        recibido = threading.Event()

        def aviso(ficha, fallo):
            vistos.append((ficha, fallo, threading.current_thread().name))
            recibido.set()

        adaptador.asignar_aviso(aviso)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=ErrorEnlace("No se pudo leer el enlace")):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 9)
            self.assertTrue(recibido.wait(5), "el aviso no llegó")
        self.assertEqual(vistos, [(9, True, "musica-vlc")])
        self.assertIsNone(adaptador._actual)

    def test_play_menos_uno_avisa_fallo(self):
        adaptador = self._adaptador_con_opciones()
        self.instancia.play_resultado = -1
        vistos = []
        recibido = threading.Event()

        def aviso(ficha, fallo):
            vistos.append((ficha, fallo))
            recibido.set()

        adaptador.asignar_aviso(aviso)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               return_value="http://audio/stream"):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 5)
            self.assertTrue(recibido.wait(5), "el aviso no llegó")
        self.assertEqual(vistos, [(5, True)])
        self.assertIsNone(adaptador._actual)
        self.assertTrue(esperar(lambda: self.instancia.reproductores[0].liberado))

    def _url_que_espera(self, soltar, destino="http://audio/stream"):
        resuelto = threading.Event()

        def url_audio(_origen):
            soltar.wait(5)
            resuelto.set()
            return destino

        return url_audio, resuelto

    def test_pedir_un_enlace_cierra_el_tema_local_antes_de_resolver(self):
        adaptador = self._adaptador_con_opciones()
        self.existentes.add("C:/musica/a.mp3")
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("C:/musica/a.mp3", "a"), 1)
            local = self.instancia.reproductores[0]
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 2)
            self.assertIsNone(adaptador._actual)
            self.assertTrue(esperar(lambda: local.liberado))
            self.assertEqual(len(self.instancia.reproductores), 1)
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            self.assertTrue(
                esperar(lambda: len(self.instancia.reproductores) == 2))
        self.assertEqual(adaptador._actual.media.origen, "http://audio/stream")

    def test_detener_durante_la_resolucion_no_crea_reproductor(self):
        adaptador = self._adaptador_con_opciones()
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            adaptador.detener()
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            time.sleep(0.1)
        self.assertEqual(self.instancia.reproductores, [])
        self.assertIsNone(adaptador._actual)
        self.assertNotIn(("play", 0), self.instancia.eventos)

    def test_pausar_durante_la_resolucion_no_suena_y_reanudar_lo_inicia(self):
        adaptador = self._adaptador_con_opciones()
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            adaptador.pausar()
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            self.assertTrue(esperar(lambda: adaptador._actual is not None))
        reproductor = self.instancia.reproductores[0]
        self.assertIs(adaptador._actual, reproductor)
        self.assertNotIn(("play", 0), self.instancia.eventos)
        self.assertIsNone(reproductor.pausa)
        adaptador.reanudar()
        self.assertIn(("play", 0), self.instancia.eventos)

    def test_pausar_y_reanudar_durante_la_resolucion_suena(self):
        adaptador = self._adaptador_con_opciones()
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            adaptador.pausar()
            adaptador.reanudar()
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            self.assertTrue(esperar(lambda: adaptador._actual is not None))
        self.assertIn(("play", 0), self.instancia.eventos)

    def test_volumen_durante_la_resolucion_se_aplica_al_abrir(self):
        adaptador = self._adaptador_con_opciones()
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            adaptador.volumen(35)
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            self.assertTrue(esperar(lambda: adaptador._actual is not None))
        self.assertEqual(self.instancia.reproductores[0].volumen, 35)

    def test_reanudar_que_falla_no_avisa_bajo_un_candado_ajeno(self):
        self._p_opciones = mock.patch.object(
            adaptador_vlc, "_opciones_enlace", return_value=(":opcion-red",))
        self._p_opciones.start()
        self.addCleanup(self._p_opciones.stop)
        adaptador = AdaptadorVlc()
        self.instancia.play_resultado = -1
        soltar = threading.Event()
        url_audio, resuelto = self._url_que_espera(soltar)
        with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                               side_effect=url_audio):
            adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 1)
            adaptador.pausar()
            soltar.set()
            self.assertTrue(resuelto.wait(5), "no se resolvió el enlace")
            self.assertTrue(esperar(lambda: adaptador._actual is not None))

        candado = threading.Lock()
        vistos = []
        avisado = threading.Event()

        def aviso(ficha, fallo):
            with candado:
                vistos.append((ficha, fallo))
            avisado.set()

        adaptador.asignar_aviso(aviso)

        def escenario():
            with candado:
                adaptador.reanudar()
            avisado.wait(2.5)

        hilo = threading.Thread(target=escenario, daemon=True)
        hilo.start()
        hilo.join(timeout=3)
        self.assertFalse(hilo.is_alive(), "reanudar se colgó con el candado tomado")
        self.assertEqual(vistos, [(1, True)])
        adaptador.cerrar()

    def test_el_aviso_de_fallo_puede_pausar_sin_colgar_la_resolucion(self):
        adaptador = self._adaptador_con_opciones()
        vistos = []
        avisado = threading.Event()

        def aviso(ficha, fallo):
            vistos.append((ficha, fallo))
            adaptador.pausar()
            avisado.set()

        adaptador.asignar_aviso(aviso)

        def escenario():
            with mock.patch.object(adaptador_vlc.enlaces, "url_audio",
                                   side_effect=ErrorEnlace("sin enlace")):
                adaptador.cargar(Tema("https://youtu.be/abc123", "x"), 3)
                avisado.wait(2.5)

        hilo = threading.Thread(target=escenario, daemon=True)
        hilo.start()
        hilo.join(timeout=3)
        self.assertFalse(hilo.is_alive(), "la resolución se colgó")
        self.assertEqual(vistos, [(3, True)])


def _wav_silencio(ruta, duracion=0.4, tasa=8000):
    fotogramas = int(duracion * tasa)
    with wave.open(str(ruta), "wb") as archivo:
        archivo.setnchannels(1)
        archivo.setsampwidth(2)
        archivo.setframerate(tasa)
        archivo.writeframes(b"\x00\x00" * fotogramas)


@unittest.skipUnless(motor_vlc.disponible(), "libVLC no está disponible")
class TestAdaptadorVlcReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temporal = tempfile.TemporaryDirectory()
        cls.wav1 = Path(cls.temporal.name) / "uno.wav"
        cls.wav2 = Path(cls.temporal.name) / "dos.wav"
        _wav_silencio(cls.wav1)
        _wav_silencio(cls.wav2)
        if motor_vlc.instancia() is None:
            cls.temporal.cleanup()
            raise unittest.SkipTest("no se pudo crear la instancia de VLC")

    @classmethod
    def tearDownClass(cls):
        # La guarda de `tests/test_referencias_de_clase.py` exige soltar
        # todo lo que guarda `setUpClass`: se suelta a mano cada nombre.
        cls.temporal.cleanup()
        del cls.wav1
        del cls.wav2
        del cls.temporal

    def _adaptador(self):
        adaptador = AdaptadorVlc(salida_audio="adummy")
        self.addCleanup(adaptador.cerrar)
        return adaptador

    def test_avanza_solo_hasta_fin_lista(self):
        adaptador = self._adaptador()
        terminado = threading.Event()
        avisos = []

        def al_cambiar(resultado):
            avisos.append(resultado.codigo)
            if resultado.codigo == FIN_LISTA:
                terminado.set()

        coordinador = Coordinador(adaptador, al_cambiar=al_cambiar)
        adaptador.asignar_aviso(coordinador.tema_terminado)
        inicio = time.monotonic()
        coordinador.reproducir_lista(
            [Tema(str(self.wav1), "uno"), Tema(str(self.wav2), "dos")])
        self.assertTrue(terminado.wait(20), "no llegó a fin_lista")
        print(f"\n[test real (a)] fin_lista en {time.monotonic() - inicio:.1f} s")
        self.assertEqual(avisos, [AVANZO, FIN_LISTA])

    def test_archivo_basura_termina_sin_colgarse(self):
        basura = Path(self.temporal.name) / "roto.mp3"
        basura.write_bytes(b"\x00\x01\x02not-a-mp3")
        adaptador = self._adaptador()
        terminado = threading.Event()
        avisos = []

        def al_cambiar(resultado):
            avisos.append(resultado.codigo)
            if resultado.codigo == FIN_LISTA:
                terminado.set()

        coordinador = Coordinador(adaptador, al_cambiar=al_cambiar)
        adaptador.asignar_aviso(coordinador.tema_terminado)
        coordinador.reproducir_lista([Tema(str(basura), "roto")])
        self.assertTrue(terminado.wait(20), "no llegó a terminar")
        self.assertEqual(avisos, [TEMA_FALLIDO, FIN_LISTA])

    def test_leer_etiquetas_de_wav_sin_tags(self):
        inicio = time.monotonic()
        datos = leer_etiquetas_vlc(str(self.wav1))
        self.assertLess(time.monotonic() - inicio, 5.0)
        self.assertIsInstance(datos, dict)
        self.assertFalse(datos.get("titulo"))

    def test_tiempo_ms_e_ir_a_con_libvlc(self):
        adaptador = self._adaptador()
        adaptador.cargar(Tema(str(self.wav1), "uno"), 1)
        self.assertTrue(
            esperar(lambda: adaptador.tiempo_ms() is not None, plazo=10.0),
            "libVLC no informó la posición")
        tiempo = adaptador.tiempo_ms()
        self.assertIsInstance(tiempo, int)
        self.assertGreaterEqual(tiempo, 0)
        adaptador.ir_a(100)
        self.assertIsInstance(adaptador.tiempo_ms(), int)

    def test_salidas_audio_real_no_lanza_y_es_rapida(self):
        inicio = time.monotonic()
        salidas = salidas_audio()
        self.assertLess(time.monotonic() - inicio, 10.0)
        self.assertIsInstance(salidas, list)
        for par in salidas:
            self.assertIsInstance(par, tuple)
            self.assertEqual(len(par), 2)
            self.assertIsInstance(par[0], str)
            self.assertIsInstance(par[1], str)


if __name__ == "__main__":
    unittest.main()
