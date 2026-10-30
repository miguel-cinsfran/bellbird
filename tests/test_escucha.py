"""Pruebas de la escucha de resultados de búsqueda, sin ventanas ni red.

Ni libVLC de verdad (salvo la prueba marcada) ni red: el resolutor y el
motor van doblados, y los hilos corren en el acto o a pedido.
"""

import threading
import time
import unittest
from unittest import mock

from bellbird.music import escucha as escucha_modulo
from bellbird.music.escucha import Escucha
from bellbird.music import enlaces


class _MedioFalso:
    """El medio de libVLC: solo anota las opciones de red."""

    def __init__(self):
        self.opciones = []

    def add_option(self, opcion):
        self.opciones.append(opcion)


class _GestorFalso:
    """El gestor de eventos: guarda los callbacks para lanzarlos a mano."""

    def __init__(self):
        self.callbacks = {}

    def event_attach(self, tipo, callback):
        self.callbacks[tipo] = callback

    def lanzar(self, tipo):
        self.callbacks[tipo](None)


class _ReproductorFalso:
    """Un reproductor de libVLC: anota llamadas y finge que suena."""

    def __init__(self, instancia):
        self._instancia = instancia
        self.llamadas = []
        self.medios = []
        self.gestor = _GestorFalso()
        self.arranque = 0

    def audio_output_device_set(self, _nada, dispositivo):
        self.llamadas.append(("dispositivo", dispositivo))

    def set_media(self, medio):
        self.medios.append(medio)

    def audio_set_volume(self, valor):
        self.llamadas.append(("volumen", valor))

    def event_manager(self):
        return self.gestor

    def play(self):
        self.llamadas.append(("play",))
        return self.arranque

    def set_pause(self, valor):
        self.llamadas.append(("pausa", valor))

    def stop(self):
        self.llamadas.append(("stop",))

    def release(self):
        self.llamadas.append(("release",))


class _InstanciaFalsa:
    """La instancia de libVLC: crea reproductores y medios falsos."""

    def __init__(self):
        self.reproductores = []
        self.medios = []
        self.sin_reproductor = False

    def media_player_new(self):
        if self.sin_reproductor:
            return None
        reproductor = _ReproductorFalso(self)
        self.reproductores.append(reproductor)
        return reproductor

    def media_new(self, destino):
        medio = _MedioFalso()
        medio.destino = destino
        self.medios.append(medio)
        return medio


class _TiposFalsos:
    """El módulo de libVLC: solo los tipos de evento que se enganchan."""

    class EventType:
        MediaPlayerEndReached = "fin"
        MediaPlayerEncounteredError = "error"
        MediaPlayerPlaying = "sonando"


class _MotorFalso:
    """Doble de `motor_vlc`: instancia, módulo y salida fijada."""

    SALIDA_AUDIO = "directsound"

    def __init__(self, instancia=None):
        self._instancia = instancia if instancia is not None else _InstanciaFalsa()
        self.salidas = []

    def instancia(self):
        return self._instancia

    def modulo(self):
        return _TiposFalsos()

    def fijar_salida_audio(self, _reproductor, salida):
        self.salidas.append(salida)
        return True


class _CorreYa:
    """Hilo que corre en el acto, para pruebas sin esperas."""

    def __init__(self, destino, argumentos):
        self._destino = destino
        self._argumentos = argumentos

    def start(self):
        self._destino(*self._argumentos)


def _avisos():
    """Un aviso que anota (evento, detalle) con candado, desde cualquier hilo."""
    anotados = []
    bloqueo = threading.Lock()

    def avisar(evento, detalle=""):
        with bloqueo:
            anotados.append((evento, detalle))

    return anotados, avisar


class _Entorno:
    """El motor y los hilos doblados para cada prueba."""

    def __init__(self, prueba, resolver=None, instancia=None):
        self.motor = _MotorFalso(instancia)
        self.resolver = resolver if resolver is not None else (lambda url: "audio://" + url)
        parches = [
            mock.patch.object(escucha_modulo, "motor_vlc", self.motor),
            mock.patch.object(escucha_modulo.diagnostico, "crear_hilo",
                              side_effect=lambda destino, nombre, args=(), **kw: _CorreYa(destino, args)),
        ]
        for parche in parches:
            parche.start()
            prueba.addCleanup(parche.stop)

    def escucha(self, **cambios):
        avisados, avisar = _avisos()
        parametros = {"aviso": avisar, "resolver": self.resolver}
        parametros.update(cambios)
        return Escucha(**parametros), avisados


class TestTablaAlternar(unittest.TestCase):
    """La tabla de `alternar` por estado, con libVLC falso."""

    def test_sonando_la_misma_pausa(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        reproductor = entorno.motor._instancia.reproductores[-1]
        reproductor.gestor.lanzar("sonando")
        avisados.clear()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "en_pausa")
        self.assertIn(("pausa", 1), reproductor.llamadas)
        self.assertEqual(avisados, [("pausa", "")])

    def test_en_pausa_la_misma_reanuda(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        reproductor = entorno.motor._instancia.reproductores[-1]
        reproductor.gestor.lanzar("sonando")
        escucha.alternar("https://www.youtube.com/watch?v=a")
        avisados.clear()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "sonando")
        self.assertIn(("pausa", 0), reproductor.llamadas)
        self.assertEqual(avisados, [("reanudada", "")])

    def test_cargando_no_hace_nada(self):
        llamadas = []

        def resolver(url):
            llamadas.append(url)
            return "audio://" + url

        pendientes = []

        def crear_hilo(destino, nombre, args=(), **kw):
            pendientes.append((destino, args))
            return mock.Mock()

        entorno = _Entorno(self, resolver=resolver)
        with mock.patch.object(escucha_modulo.diagnostico, "crear_hilo", side_effect=crear_hilo):
            escucha, avisados = entorno.escucha()
            escucha.alternar("https://www.youtube.com/watch?v=a")
            escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "cargando")
        self.assertEqual(llamadas, [])
        self.assertEqual(avisados, [("cargando", "")])

    def test_otra_url_detiene_lo_anterior_y_empieza(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        primera = entorno.motor._instancia.reproductores[-1]
        primera.gestor.lanzar("sonando")
        escucha.alternar("https://www.youtube.com/watch?v=b")
        self.assertEqual(escucha.estado, "cargando")
        self.assertEqual(escucha.url, "https://www.youtube.com/watch?v=b")
        self.assertIn(("stop",), primera.llamadas)
        self.assertIn(("release",), primera.llamadas)
        self.assertEqual(avisados[-1], ("cargando", ""))

    def test_inactivo_empieza(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        self.assertEqual(escucha.estado, "inactivo")
        self.assertIsNone(escucha.url)
        escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "cargando")
        self.assertEqual(avisados, [("cargando", "")])


class TestResolucionTardia(unittest.TestCase):
    """Una resolución tardía tras `detener` no arranca nada."""

    def test_resolver_tarde_no_crea_reproductor(self):
        pendientes = []

        def crear_hilo(destino, nombre, args=(), **kw):
            pendientes.append((destino, args))
            return mock.Mock()

        entorno = _Entorno(self)
        with mock.patch.object(escucha_modulo.diagnostico, "crear_hilo", side_effect=crear_hilo):
            escucha, avisados = entorno.escucha()
            escucha.alternar("https://www.youtube.com/watch?v=a")
            escucha.detener()
            self.assertEqual(escucha.estado, "inactivo")
            destino, argumentos = pendientes[0]
            destino(*argumentos)
        self.assertEqual(entorno.motor._instancia.reproductores, [])
        self.assertEqual(escucha.estado, "inactivo")
        self.assertIsNone(escucha.url)
        self.assertEqual(avisados, [("cargando", "")])


class TestEventoViejo(unittest.TestCase):
    """Un evento viejo de libVLC se descarta."""

    def test_fin_viejo_no_avisa_ni_cierra_lo_nuevo(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        vieja = entorno.motor._instancia.reproductores[-1]
        vieja.gestor.lanzar("sonando")
        escucha.alternar("https://www.youtube.com/watch?v=b")
        avisados.clear()
        vieja.gestor.lanzar("fin")
        self.assertEqual(escucha.url, "https://www.youtube.com/watch?v=b")
        self.assertEqual(avisados, [])


class TestFalloResolver(unittest.TestCase):
    """Un fallo del resolutor avisa `fallo` con su motivo."""

    def test_error_de_enlace_da_su_mensaje(self):
        def resolver(_url):
            raise enlaces.ErrorEnlace("Sin audio por acá")

        entorno = _Entorno(self, resolver=resolver)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "inactivo")
        self.assertEqual(avisados, [("cargando", ""), ("fallo", "Sin audio por acá")])

    def test_otro_error_da_el_generico(self):
        def resolver(_url):
            raise RuntimeError("se cortó la red")

        entorno = _Entorno(self, resolver=resolver)
        with mock.patch.object(escucha_modulo.logger, "exception") as excepcion:
            escucha, avisados = entorno.escucha()
            escucha.alternar("https://www.youtube.com/watch?v=a")
        excepcion.assert_called_once()
        self.assertEqual(avisados[0], ("cargando", ""))
        self.assertEqual(avisados[1][0], "fallo")
        self.assertIn("No se pudo cargar el audio", avisados[1][1])

    def test_sin_instancia_da_fallo(self):
        motor = _MotorFalso(None)
        motor._instancia = None
        entorno = _Entorno(self, instancia=None)
        entorno.motor._instancia = None
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        self.assertEqual(escucha.estado, "inactivo")
        self.assertEqual(avisados, [("cargando", ""),
                                    ("fallo", "No se pudo iniciar el reproductor de audio.")])


class TestCierreFueraDelCallback(unittest.TestCase):
    """`stop` nunca corre en el hilo del callback de libVLC."""

    def test_el_fin_cierra_en_un_hilo_aparte(self):
        orden = []

        def crear_hilo(destino, nombre, args=(), **kw):
            orden.append(("hilo", nombre))
            hilo = _CorreYa(destino, args)
            hilo.start()
            return mock.Mock()

        entorno = _Entorno(self)
        with mock.patch.object(escucha_modulo.diagnostico, "crear_hilo", side_effect=crear_hilo):
            escucha, avisados = entorno.escucha()
            escucha.alternar("https://www.youtube.com/watch?v=a")
            reproductor = entorno.motor._instancia.reproductores[-1]
            original_stop = reproductor.stop

            def stop_anotado():
                orden.append(("stop",))
                original_stop()

            reproductor.stop = stop_anotado
            reproductor.gestor.lanzar("fin")
        self.assertEqual(avisados[-1], ("fin", ""))
        self.assertIn(("hilo", "escucha-cierre"), orden)
        self.assertLess(orden.index(("hilo", "escucha-cierre")), orden.index(("stop",)))


class TestDetener(unittest.TestCase):
    """`detener` es idempotente y no avisa."""

    def test_detener_dos_veces_no_falla_ni_avisa(self):
        entorno = _Entorno(self)
        escucha, avisados = entorno.escucha()
        escucha.alternar("https://www.youtube.com/watch?v=a")
        reproductor = entorno.motor._instancia.reproductores[-1]
        reproductor.gestor.lanzar("sonando")
        avisados.clear()
        escucha.detener()
        escucha.detener()
        self.assertEqual(escucha.estado, "inactivo")
        self.assertIsNone(escucha.url)
        self.assertEqual(avisados, [])
        self.assertEqual(reproductor.llamadas.count(("stop",)), 1)


class TestConLibVlcDeVerdad(unittest.TestCase):
    """Con libVLC de verdad: suena un WAV local y termina."""

    def test_suena_un_wav_y_termina(self):
        from pathlib import Path

        from bellbird.player import motor_vlc

        if not motor_vlc.disponible():
            self.skipTest("sin libVLC en esta PC")
        if motor_vlc.instancia() is None:
            self.skipTest("sin instancia de libVLC en esta PC")
        wav = (Path(__file__).resolve().parent.parent / "sounds" / "themes"
               / "default" / "copiar.wav")
        llegadas = []
        terminado = threading.Event()
        sonando = threading.Event()

        def avisar(evento, detalle=""):
            llegadas.append(evento)
            if evento == "sonando":
                sonando.set()
            if evento == "fin":
                terminado.set()

        escucha = Escucha(avisar, resolver=lambda _url: str(wav),
                          salida_audio="adummy")
        escucha.alternar("cualquiera")
        self.assertTrue(sonando.wait(timeout=30), f"no sonó: {llegadas}")
        self.assertTrue(terminado.wait(timeout=30), f"no terminó: {llegadas}")
        inicio = time.monotonic()
        escucha.detener()
        self.assertLess(time.monotonic() - inicio, 5)


if __name__ == "__main__":
    unittest.main()
