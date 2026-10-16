"""Tests del worker TTS con Prism: arranque del motor, habla, pausa y atajos."""

import queue
import threading
import time
import unittest
from unittest import mock

from ytchat.voice import elevenlabs
from ytchat.voice import motores
from ytchat.voice import tts_worker
from ytchat.voice.tts_worker import sanitizar, construir_tts


class MotorFalso:
    """Doble del envoltorio de Prism. Con `duracion` simula el habla real: el
    estado sube a True recién a `subida` segundos y baja solo a `duracion`."""

    def __init__(self, voces=("Voz A", "Voz B"), motor="sapi"):
        self.motor = motor
        self._voces = list(voces)
        self.hablando_ = False
        self.subida = 0.0
        self.duracion = 0.0
        self.t0 = 0.0
        self.hablar_ok = True
        self.elegidas = []
        self.hablados = []
        self.paradas = 0
        self.pausas = 0
        self.reanudadas = 0
        self.velocidad = self.volumen = self.tono = None
        self.cerrado = False

    def voces(self):
        return list(self._voces)

    def elegir_voz(self, idx):
        self.elegidas.append(idx)
        return True

    def hablar(self, texto):
        self.hablados.append((texto, time.monotonic()))
        self.t0 = time.monotonic()
        self.hablando_ = True
        return self.hablar_ok

    def hablando(self):
        if self.duracion:
            e = time.monotonic() - self.t0
            return self.subida <= e < self.duracion
        return self.hablando_

    def parar(self):
        self.hablando_ = False
        self.paradas += 1

    def pausar(self):
        self.pausas += 1

    def reanudar(self):
        self.reanudadas += 1

    def fijar_velocidad(self, pct):
        self.velocidad = pct

    def fijar_volumen(self, pct):
        self.volumen = pct

    def fijar_tono(self, pct):
        self.tono = pct

    def cerrar(self):
        self.cerrado = True


class FabricaFalsa:
    """Fábrica de motores: devuelve el doble pedido o falla como Prism."""

    def __init__(self, por_nombre, fallan=()):
        self.por_nombre = por_nombre
        self.fallan = set(fallan)
        self.creados = []

    def __call__(self, nombre):
        self.creados.append(nombre)
        if nombre in self.fallan:
            raise motores.MotorNoDisponible(f"{nombre} no disponible")
        return self.por_nombre[nombre]


def _worker_con(motor, config=None):
    w = tts_worker.TTSWorker(queue.Queue(), config or {},
                             fabrica_motor=FabricaFalsa({"sapi": motor}))
    return w


class MotorElevenlabsFalso(MotorFalso):
    """Doble de ElevenLabs: mismo motor que MotorFalso, más el error y el
    contador de caracteres que usa el worker para el respaldo y el tope."""

    def __init__(self, voces=("Voz EL A", "Voz EL B")):
        super().__init__(voces=voces, motor="elevenlabs")
        self.falla = None
        self.caracteres = 0

    def hablar(self, texto):
        self.hablados.append((texto, time.monotonic()))
        if self.falla is not None:
            raise self.falla
        self.caracteres += len(texto)
        self.t0 = time.monotonic()
        self.hablando_ = True
        return self.hablar_ok

    def caracteres_usados(self):
        return self.caracteres


class TestArranque(unittest.TestCase):
    """El arranque no debe tumbar la app por una voz desinstalada ni por un
    motor que falta: cae a la primera voz o a SAPI, y deja constancia."""

    def test_arranca_y_carga_voces_y_ajustes(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"velocidad_voz": 40, "volumen": 0.5, "tono": 30})
        worker._abrir_motor()
        self.assertEqual(worker.voces(), ["Voz A", "Voz B"])
        self.assertEqual(worker.motor_activo(), "sapi")
        self.assertEqual(motor.elegidas, [0])
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono), (40, 50, 30))

    def test_voz_desinstalada_cae_a_la_primera(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"voz": "Lucía"})
        with mock.patch.object(tts_worker.logger, "warning") as avisar:
            worker._abrir_motor()
        self.assertEqual(motor.elegidas, [0])
        self.assertIn("no encontrada", avisar.call_args.args[0])

    def test_voz_por_nombre_se_resuelve(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"voz": "Voz B"})
        worker._abrir_motor()
        self.assertEqual(motor.elegidas, [1])

    def test_motor_pedido_que_falta_usa_sapi(self):
        sapi, onecore = MotorFalso(), MotorFalso()
        fabrica = FabricaFalsa({"sapi": sapi, "onecore": onecore}, fallan=["onecore"])
        worker = tts_worker.TTSWorker(queue.Queue(), {"motor": "onecore"},
                                      fabrica_motor=fabrica)
        worker._abrir_motor()
        self.assertEqual(fabrica.creados, ["onecore", "sapi"])
        self.assertEqual(worker.motor_activo(), "sapi")

    def test_motor_sin_voces_es_error(self):
        motor = MotorFalso(voces=[])
        worker = _worker_con(motor)
        worker.start()
        self.addCleanup(worker.detener)
        self.assertFalse(worker.esperar_inicio(timeout=5))
        self.assertIn("voces", str(worker._error))

    def test_sapi_que_falla_no_se_respalda(self):
        fabrica = FabricaFalsa({}, fallan=["sapi"])
        worker = tts_worker.TTSWorker(queue.Queue(), {"motor": "sapi"},
                                      fabrica_motor=fabrica)
        worker.start()
        self.addCleanup(worker.detener)
        self.assertFalse(worker.esperar_inicio(timeout=5))
        self.assertEqual(fabrica.creados, ["sapi"])


class TestHabla(unittest.TestCase):

    def test_espera_la_subida_del_estado_antes_de_dar_por_terminado(self):
        motor = MotorFalso()
        motor.subida = 0.05
        motor.duracion = 0.30
        worker = _worker_con(motor)
        worker._abrir_motor()
        worker._procesar_comandos = mock.Mock()
        inicio = time.monotonic()
        worker._hablar("mensaje")
        transcurrido = time.monotonic() - inicio
        # Sin esperar la subida, `hablando()` arranca en False y el mensaje se
        # daría por terminado al instante (transcurrido casi cero).
        self.assertGreaterEqual(transcurrido, 0.20)

    def test_onecore_en_pausa_no_termina_la_frase(self):
        motor = MotorFalso()
        motor.hablando_ = True
        worker = _worker_con(motor)
        worker._abrir_motor()
        pasos = {"n": 0}

        def procesar():
            pasos["n"] += 1
            if pasos["n"] == 1:
                worker._active.clear()       # pausa
                motor.hablando_ = False      # OneCore calla el estado al pausar
            if pasos["n"] == 3:
                worker._active.set()         # reanudar
                motor.hablando_ = False      # ...ya terminó

        worker._procesar_comandos = mock.Mock(side_effect=procesar)
        worker._hablar("mensaje")
        self.assertEqual(motor.pausas, 1)
        self.assertEqual(motor.reanudadas, 1)

    def test_una_purga_armada_no_corta_el_mensaje_siguiente(self):
        motor = MotorFalso()
        motor.duracion = 0.1
        worker = _worker_con(motor)
        worker._abrir_motor()
        worker._procesar_comandos = mock.Mock()
        worker._purge_pending.set()   # detener_actual() con la voz callada
        worker._hablar("primer mensaje tras reconectar")
        self.assertEqual(motor.paradas, 0)
        self.assertEqual([t for t, _ in motor.hablados], ["primer mensaje tras reconectar"])

    def test_una_purga_durante_la_lectura_corta(self):
        motor = MotorFalso()
        motor.hablando_ = True
        worker = _worker_con(motor)
        worker._abrir_motor()
        worker._procesar_comandos = mock.Mock(
            side_effect=lambda: worker._purge_pending.set())
        worker._hablar("mensaje largo")
        self.assertEqual(motor.paradas, 1)


class TestVozPorMensaje(unittest.TestCase):

    def test_sin_voz_usa_la_base(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"voz": "Voz B"})
        worker._abrir_motor()
        motor.elegidas.clear()
        worker._aplicar_voz(None)
        self.assertEqual(motor.elegidas, [])   # ya es la base, no la re-elige

    def test_voz_del_evento_se_aplica(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"voz": "Voz A"})
        worker._abrir_motor()
        motor.elegidas.clear()
        worker._aplicar_voz("Voz B")
        self.assertEqual(motor.elegidas, [1])

    def test_voz_no_resuelta_cae_a_la_base(self):
        motor = MotorFalso()
        worker = _worker_con(motor, {"voz": "Voz A"})
        worker._abrir_motor()
        motor.elegidas.clear()
        worker._aplicar_voz("Inexistente")
        self.assertEqual(motor.elegidas, [])


class TestAjustes(unittest.TestCase):

    def test_rate_sube_de_a_cinco_en_porcentaje(self):
        worker = tts_worker.TTSWorker(queue.Queue(), {"velocidad_voz": 50})
        worker.cambiar_rate(1)
        self.assertEqual(worker.get_rate(), 55)

    def test_rate_baja_y_topea(self):
        worker = tts_worker.TTSWorker(queue.Queue(), {"velocidad_voz": 5})
        worker.cambiar_rate(-1)
        self.assertEqual(worker.get_rate(), 0)

    def test_volumen_topea_en_rango(self):
        worker = tts_worker.TTSWorker(queue.Queue(), {"volumen": 0.9})
        worker.cambiar_volumen(50)
        self.assertEqual(worker.get_volume(), 100)

    def test_fijar_rate_deja_multiplo_de_cinco_y_lo_aplica(self):
        motor = MotorFalso()
        worker = tts_worker.TTSWorker(
            queue.Queue(), {"velocidad_voz": 50},
            fabrica_motor=FabricaFalsa({"sapi": motor}))
        worker._abrir_motor()
        worker.fijar_rate(52)
        worker._procesar_comandos()
        self.assertEqual(worker.get_rate(), 50)
        self.assertEqual(motor.velocidad, 50)

    def test_fijar_volumen_pct_absoluto_y_acotado(self):
        motor = MotorFalso()
        worker = tts_worker.TTSWorker(
            queue.Queue(), {}, fabrica_motor=FabricaFalsa({"sapi": motor}))
        worker._abrir_motor()
        worker.fijar_volumen_pct(30)
        worker.fijar_volumen_pct(180)
        worker._procesar_comandos()
        self.assertEqual(worker.get_volume(), 100)
        self.assertEqual(motor.volumen, 100)


class TestCambioDeMotor(unittest.TestCase):
    """Cambiar de motor en caliente: el nuevo se crea en el hilo del worker,
    toma los ajustes actuales y reemplaza al viejo solo si se pudo crear."""

    def test_cambiar_motor_activa_el_nuevo_aplica_ajustes_y_cierra_el_viejo(self):
        sapi = MotorFalso(voces=("Voz A", "Voz B"), motor="sapi")
        onecore = MotorFalso(voces=("Microsoft Laura", "Microsoft David"),
                             motor="onecore")
        fabrica = FabricaFalsa({"sapi": sapi, "onecore": onecore})
        worker = tts_worker.TTSWorker(
            queue.Queue(), {"velocidad_voz": 40, "volumen": 0.5, "tono": 30},
            fabrica_motor=fabrica)
        worker._abrir_motor()

        worker.cambiar_motor("onecore", "Microsoft Laura")
        worker._procesar_comandos()

        self.assertEqual(worker.motor_activo(), "onecore")
        self.assertEqual(worker.voces(), ["Microsoft Laura", "Microsoft David"])
        self.assertEqual(onecore.elegidas, [0])
        self.assertEqual((onecore.velocidad, onecore.volumen, onecore.tono),
                         (40, 50, 30))
        self.assertTrue(sapi.cerrado)

    def test_cambiar_motor_que_falla_conserva_el_viejo_y_sigue_hablando(self):
        sapi = MotorFalso(motor="sapi")
        sapi.duracion = 0.02
        fabrica = FabricaFalsa({"sapi": sapi}, fallan=["onecore"])
        worker = tts_worker.TTSWorker(
            queue.Queue(), {}, fabrica_motor=fabrica)
        worker._abrir_motor()

        with mock.patch.object(tts_worker.logger, "warning") as avisar:
            worker.cambiar_motor("onecore", None)
            worker._procesar_comandos()

        self.assertEqual(worker.motor_activo(), "sapi")
        self.assertFalse(sapi.cerrado)
        self.assertTrue(avisar.called)
        worker._hablar("sigue hablando")
        self.assertEqual([t for t, _ in sapi.hablados], ["sigue hablando"])


class TestUltimoAutor(unittest.TestCase):
    """El worker recuerda quién mandó lo que empezó a leer (F3)."""

    def _worker_en_marcha(self, hablados):
        cola = queue.Queue()
        motor = MotorFalso()
        motor.duracion = 0.02
        worker = tts_worker.TTSWorker(
            cola, {}, fabrica_motor=FabricaFalsa({"sapi": motor}))
        worker.start()
        self.assertTrue(worker.esperar_inicio(timeout=5))
        self.addCleanup(worker.detener)
        return worker, cola

    def _esperar_autor(self, worker, esperado, timeout=5.0):
        fin = time.monotonic() + timeout
        while time.monotonic() < fin:
            if worker.ultimo_autor() == esperado:
                return
            time.sleep(0.02)
        self.assertEqual(worker.ultimo_autor(), esperado)

    def test_empieza_sin_autor(self):
        worker, _cola = self._worker_en_marcha([])
        self.assertEqual(worker.ultimo_autor(), "")

    def test_registra_el_autor_que_empieza_a_leer(self):
        worker, cola = self._worker_en_marcha([])
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")

    def test_un_item_sin_autor_no_borra_el_anterior(self):
        worker, cola = self._worker_en_marcha([])
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")
        cola.put({"texto_tts": "aviso interno"})
        time.sleep(0.2)
        self.assertEqual(worker.ultimo_autor(), "Ana")

    def test_un_item_con_texto_vacio_no_cambia_el_autor(self):
        worker, cola = self._worker_en_marcha([])
        cola.put({"texto_tts": "hola", "autor": "Ana"})
        self._esperar_autor(worker, "Ana")
        cola.put({"texto_tts": "   ", "autor": "Beto"})
        time.sleep(0.5)
        self.assertEqual(worker.ultimo_autor(), "Ana")


class TestRespaldoElevenLabs(unittest.TestCase):
    """Con el motor en elevenlabs, el worker decide entre la nube y la voz de
    Windows, y avisa una sola vez por racha."""

    def _worker(self, **config):
        el = MotorElevenlabsFalso()
        el.duracion = 0.02
        sapi = MotorFalso()
        sapi.duracion = 0.02
        base = {"motor": "elevenlabs"}
        base.update(config)
        fabrica = FabricaFalsa({"elevenlabs": el, "sapi": sapi})
        worker = tts_worker.TTSWorker(queue.Queue(), base, fabrica_motor=fabrica)
        worker._abrir_motor()
        worker._avisos = []
        worker.al_avisar = worker._avisos.append
        return worker, el, sapi

    def test_solo_importantes_manda_lo_comun_al_respaldo(self):
        worker, el, sapi = self._worker(elevenlabs_solo_importantes=True)
        worker._hablar("mensaje comun", None, False)
        self.assertEqual([t for t, _ in el.hablados], [])
        self.assertEqual([t for t, _ in sapi.hablados], ["mensaje comun"])
        self.assertEqual(worker._avisos, [])

    def test_el_item_importante_va_a_elevenlabs(self):
        worker, el, sapi = self._worker(elevenlabs_solo_importantes=True)
        worker._hablar("super chat", None, True)
        self.assertEqual([t for t, _ in el.hablados], ["super chat"])
        self.assertEqual([t for t, _ in sapi.hablados], [])

    def test_tope_una_sola_vez_por_sesion(self):
        worker, el, sapi = self._worker(elevenlabs_tope=10)
        el.caracteres = 100
        worker._hablar("hola", None, False)
        worker._hablar("otra", None, False)
        self.assertEqual([t for t, _ in sapi.hablados], ["hola", "otra"])
        self.assertEqual([t for t, _ in el.hablados], [])
        self.assertEqual(len(worker._avisos), 1)
        self.assertIn("tope de caracteres", worker._avisos[0])

    def test_error_reciente_va_al_respaldo_sin_reintentar(self):
        worker, el, sapi = self._worker()
        el.falla = elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")
        worker._hablar("uno", None, False)
        worker._hablar("dos", None, False)
        # El segundo mensaje no vuelve a pedirle nada a ElevenLabs.
        self.assertEqual([t for t, _ in el.hablados], ["uno"])
        self.assertEqual([t for t, _ in sapi.hablados], ["uno", "dos"])
        self.assertEqual(len(worker._avisos), 1)
        self.assertIn("Se usa la voz de Windows", worker._avisos[0])

    @mock.patch.object(tts_worker, "_VENTANA_ERROR_ELEVENLABS", 0.0)
    def test_aviso_una_vez_por_racha_y_otra_tras_racha_nueva(self):
        worker, el, sapi = self._worker()
        el.falla = elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")
        worker._hablar("uno", None, False)
        worker._hablar("dos", None, False)
        self.assertEqual(len(worker._avisos), 1)   # una sola vez por racha
        el.falla = None
        worker._hablar("tres", None, False)        # ElevenLabs lee bien
        el.falla = elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")
        worker._hablar("cuatro", None, False)      # racha nueva
        self.assertEqual(len(worker._avisos), 2)

    def test_sin_al_avisar_no_lanza(self):
        worker, el, sapi = self._worker()
        worker.al_avisar = None
        el.falla = elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")
        worker._hablar("uno", None, False)   # solo queda en el log
        self.assertEqual([t for t, _ in sapi.hablados], ["uno"])

    def test_configurar_elevenlabs_aplica_en_el_hilo_del_worker(self):
        worker, el, sapi = self._worker()
        worker._conseguir_respaldo()
        sapi.elegidas.clear()

        # Encolado: todavía no se aplicó nada (lo hace el hilo del worker).
        worker.configurar_elevenlabs(5000, True, "Voz B")
        self.assertEqual(worker._tope_elevenlabs, 0)
        worker._procesar_comandos()

        self.assertEqual(worker._tope_elevenlabs, 5000)
        self.assertTrue(worker._solo_importantes)
        self.assertEqual(worker._voz_respaldo, "Voz B")
        # La voz del respaldo ya creado cambia sin recrearlo.
        self.assertIs(worker._respaldo, sapi)
        self.assertEqual(sapi.elegidas, [1])


class TestPrismReal(unittest.TestCase):
    """Ejecuta el envoltorio real de Prism: si Prism o las voces cambian de
    forma incompatible, esto lo caza (volumen 0 para no sonar)."""

    def test_habla_sin_sonido_con_el_motor_real(self):
        if not motores.listar_voces("sapi"):
            self.skipTest("no hay voces SAPI en este equipo")
        cola = queue.Queue()
        worker = tts_worker.TTSWorker(cola, {"motor": "sapi", "volumen": 0.0})
        worker.start()
        self.addCleanup(worker.detener)
        self.assertTrue(worker.esperar_inicio(timeout=10))
        self.assertTrue(worker.voces())
        cola.put({"texto_tts": "prueba de voz", "autor": "QA"})
        time.sleep(0.6)
        worker.detener()
        self.assertEqual(worker._error, None)

    def test_cambia_de_sapi_a_onecore_con_el_motor_real(self):
        if not motores.listar_voces("sapi"):
            self.skipTest("no hay voces SAPI en este equipo")
        if not motores.listar_voces("onecore"):
            self.skipTest("OneCore no está disponible en este equipo")
        worker = tts_worker.TTSWorker(
            queue.Queue(), {"motor": "sapi", "volumen": 0.0})
        worker.start()
        self.addCleanup(worker.detener)
        self.assertTrue(worker.esperar_inicio(timeout=10))
        worker.cambiar_motor("onecore", None)
        fin = time.monotonic() + 5.0
        while worker.motor_activo() != "onecore" and time.monotonic() < fin:
            time.sleep(0.02)
        self.assertEqual(worker.motor_activo(), "onecore")
        self.assertTrue(worker.voces())


class TestSanitizar(unittest.TestCase):

    def test_vacio(self):
        self.assertEqual(sanitizar("", True, True, 200), "")

    def test_colapsa_espacios(self):
        self.assertEqual(sanitizar("hola    mundo", True, True, 200), "hola mundo")

    def test_elimina_urls(self):
        self.assertEqual(
            sanitizar("mira esto http://example.com/x ya", True, True, 200),
            "mira esto ya")

    def test_conserva_urls_si_se_pide(self):
        out = sanitizar("ve a http://example.com", True, False, 200)
        self.assertIn("http://example.com", out)

    def test_elimina_emojis(self):
        self.assertEqual(sanitizar("hola 😀🎉 mundo", True, True, 200), "hola mundo")

    def test_conserva_emojis_si_se_pide(self):
        out = sanitizar("hola 😀 mundo", False, True, 200)
        self.assertIn("😀", out)

    def test_elimina_caracteres_de_control(self):
        self.assertEqual(sanitizar("a\x00b\x07c", True, True, 200), "abc")

    def test_truncado_por_palabra(self):
        texto = "palabra " * 50  # 400 chars aprox
        out = sanitizar(texto.strip(), True, True, 40)
        self.assertTrue(out.endswith("..."))
        self.assertLessEqual(len(out), 43)

    def test_sin_truncado_si_maxlen_cero(self):
        texto = "x" * 500
        self.assertEqual(sanitizar(texto, True, True, 0), texto)


class TestConstruirTTS(unittest.TestCase):

    def _cfg(self, fmt="nombre_mensaje"):
        return {"limpiar_emojis": True, "formato_prefijo": fmt}

    def test_nombre_mensaje(self):
        self.assertEqual(construir_tts("Juan", "hola", self._cfg()), "Juan: hola")

    def test_solo_mensaje(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("solo_mensaje")), "hola")

    def test_solo_nombre(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("solo_nombre")), "Juan")

    def test_mensaje_nombre(self):
        self.assertEqual(
            construir_tts("Juan", "hola", self._cfg("mensaje_nombre")),
            "hola, de Juan")

    def test_mensaje_nombre_autor_vacio_usa_placeholder(self):
        self.assertEqual(
            construir_tts("", "hola", self._cfg("mensaje_nombre")),
            "hola, de Usuario")

    def test_autor_vacio_usa_placeholder(self):
        self.assertEqual(construir_tts("", "hola", self._cfg()), "Usuario: hola")


if __name__ == "__main__":
    unittest.main()
