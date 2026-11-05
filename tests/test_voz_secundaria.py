"""Voz secundaria por evento: voz, velocidad y volumen de cada mensaje.

Cubre la elección de voz por mensaje en `guyrapu/voice/tts_worker.py` con
motores dobles que registran la voz, la velocidad, el volumen y el tono de
cada frase en el orden en que suenan. Sin ventanas ni motores reales.
"""

import queue
import time
import unittest

from guyrapu.voice import elevenlabs
from guyrapu.voice import tts_worker
from guyrapu.voice.voz_secundaria import VozSecundaria


class Motor:
    """Doble de motor que anota los ajustes con los que sonó cada frase."""

    def __init__(self, voces, motor="sapi", registro=None, falla=None):
        self.motor = motor
        self._voces = list(voces)
        self._voz = 0
        self._t0 = 0.0
        self.velocidad = self.volumen = self.tono = None
        self.hablados = []
        self.elegidas = []
        self.cerrado = False
        self.falla = falla
        self.caracteres = 0
        self.registro = registro if registro is not None else []

    def voces(self):
        return list(self._voces)

    def elegir_voz(self, idx):
        idx = int(idx)
        self.elegidas.append(idx)
        if 0 <= idx < len(self._voces):
            self._voz = idx
            return True
        return False

    def hablar(self, texto):
        self.hablados.append(texto)
        if self.falla is not None:
            raise self.falla
        self.registro.append((texto, self._voces[self._voz],
                              self.velocidad, self.volumen, self.tono))
        self.caracteres += len(texto)
        self._t0 = time.monotonic()
        return True

    def hablando(self):
        return time.monotonic() - self._t0 < 0.005

    def parar(self):
        pass

    def pausar(self):
        pass

    def reanudar(self):
        pass

    def fijar_velocidad(self, pct):
        self.velocidad = pct

    def fijar_volumen(self, pct):
        self.volumen = pct

    def fijar_tono(self, pct):
        self.tono = pct

    def caracteres_usados(self):
        return self.caracteres

    def cerrar(self):
        self.cerrado = True


class Fabrica:
    """Motor principal fijo y respaldos de Windows nuevos en cada pedido."""

    def __init__(self, principal, voces_respaldo=()):
        self.principal = principal
        self.voces_respaldo = list(voces_respaldo)
        self.respaldos = []

    def __call__(self, nombre):
        if nombre == self.principal.motor:
            return self.principal
        respaldo = Motor(self.voces_respaldo,
                         registro=self.principal.registro)
        self.respaldos.append(respaldo)
        return respaldo


def _worker(principal, respaldos=(), **config):
    fabrica = Fabrica(principal, respaldos)
    worker = tts_worker.TTSWorker(queue.Queue(), config, fabrica_motor=fabrica)
    worker._abrir_motor()
    return worker, fabrica


def _config_sapi(**extras):
    base = {"voz": "Voz A", "velocidad_voz": 50, "volumen": 1.0, "tono": 50,
            "voz_secundaria": "Voz B", "velocidad_secundaria": 20,
            "volumen_secundaria": 0.3}
    base.update(extras)
    return base


def _config_elevenlabs(**extras):
    base = {"motor": "elevenlabs", "voz": "EL A", "velocidad_voz": 50,
            "volumen": 1.0, "tono": 50, "voz_secundaria": "EL B",
            "velocidad_secundaria": 20, "volumen_secundaria": 0.3,
            "voz_respaldo": "Respaldo principal",
            "voz_respaldo_secundaria": "Respaldo secundario"}
    base.update(extras)
    return base


class TestSecundariaNoDisponible(unittest.TestCase):
    """Sin voz secundaria, o con una que no existe, suena la principal."""

    def test_voz_secundaria_vacia_usa_principal(self):
        motor = Motor(("Voz A", "Voz B"))
        worker, _ = _worker(motor, **_config_sapi(voz_secundaria=""))
        worker._hablar("hola", secundaria=True)
        self.assertEqual(motor.registro, [("hola", "Voz A", 50, 100, 50)])

    def test_voz_secundaria_inexistente_usa_principal(self):
        motor = Motor(("Voz A", "Voz B"))
        worker, _ = _worker(motor, **_config_sapi(voz_secundaria="No existe"))
        worker._hablar("hola", secundaria=True)
        self.assertEqual(motor.registro, [("hola", "Voz A", 50, 100, 50)])


class TestAjustesPorMensaje(unittest.TestCase):
    """Cada mensaje usa sus ajustes y el siguiente vuelve a la principal."""

    def test_secundaria_y_principal_en_orden(self):
        motor = Motor(("Voz A", "Voz B"))
        worker, _ = _worker(motor, **_config_sapi())
        worker._hablar("evento", secundaria=True)
        worker._hablar("mensaje")
        self.assertEqual(motor.registro, [
            ("evento", "Voz B", 20, 30, 50),
            ("mensaje", "Voz A", 50, 100, 50),
        ])
        self.assertFalse(worker._voz_secundaria.sonando)

    def test_la_velocidad_y_el_volumen_no_cambian_la_secundaria_en_curso(self):
        motor = Motor(("Voz A", "Voz B"))
        worker, _ = _worker(motor, **_config_sapi())
        motor.velocidad = 20
        motor.volumen = 30
        worker._voz_secundaria.sonando = True
        worker._cmds.put(("rate", 60))
        worker._cmds.put(("volume", 90))
        worker._procesar_comandos()
        self.assertEqual((motor.velocidad, motor.volumen), (20, 30))
        worker._voz_secundaria.sonando = False
        worker._cmds.put(("rate", 60))
        worker._cmds.put(("volume", 90))
        worker._procesar_comandos()
        self.assertEqual((motor.velocidad, motor.volumen), (60, 90))

    def test_el_bucle_real_lee_la_marca_secundaria(self):
        motor = Motor(("Voz A", "Voz B"))
        fabrica = Fabrica(motor)
        worker = tts_worker.TTSWorker(
            queue.Queue(), _config_sapi(), fabrica_motor=fabrica)
        worker.start()
        self.addCleanup(worker.detener)
        self.assertTrue(worker.esperar_inicio(timeout=5))
        worker.cola.put({"texto_tts": "evento", "secundaria": True})
        worker.cola.put({"texto_tts": "mensaje"})
        fin = time.monotonic() + 5
        while len(motor.registro) < 2 and time.monotonic() < fin:
            time.sleep(0.02)
        self.assertEqual(motor.registro, [
            ("evento", "Voz B", 20, 30, 50),
            ("mensaje", "Voz A", 50, 100, 50),
        ])


class TestRespaldoSecundario(unittest.TestCase):
    """El mensaje secundario que cae a Windows usa su respaldo y ajustes."""

    def _worker_el(self, **extras):
        principal = Motor(("EL A", "EL B"), motor="elevenlabs")
        return _worker(principal, ("Respaldo principal", "Respaldo secundario"),
                       **_config_elevenlabs(**extras))

    def test_solo_importantes_usa_el_respaldo_secundario(self):
        worker, fabrica = self._worker_el(elevenlabs_solo_importantes=True)
        worker._hablar("evento", secundaria=True)
        worker._hablar("principal", importante=True)
        self.assertEqual(fabrica.principal.registro, [
            ("evento", "Respaldo secundario", 20, 30, 50),
            ("principal", "EL A", 50, 100, 50),
        ])
        self.assertEqual(fabrica.principal.hablados, ["principal"])

    def test_tope_usa_el_respaldo_secundario(self):
        worker, fabrica = self._worker_el(elevenlabs_tope=10)
        fabrica.principal.caracteres = 100
        worker._hablar("evento", secundaria=True)
        self.assertEqual(fabrica.principal.registro, [
            ("evento", "Respaldo secundario", 20, 30, 50),
        ])

    def test_error_de_red_usa_el_respaldo_secundario(self):
        principal = Motor(("EL A", "EL B"), motor="elevenlabs")
        principal.falla = elevenlabs.ElevenLabsError(
            "red", "No se pudo conectar con ElevenLabs.")
        worker, fabrica = _worker(
            principal, ("Respaldo principal", "Respaldo secundario"),
            **_config_elevenlabs())
        worker._hablar("evento", secundaria=True)
        self.assertEqual(principal.registro, [
            ("evento", "Respaldo secundario", 20, 30, 50),
        ])

    def test_respaldo_vacio_usa_voz_respaldo(self):
        worker, fabrica = self._worker_el(
            elevenlabs_solo_importantes=True, voz_respaldo_secundaria="")
        worker._hablar("evento", secundaria=True)
        self.assertEqual(fabrica.principal.registro, [
            ("evento", "Respaldo principal", 20, 30, 50),
        ])


class TestConfiguracionEnCaliente(unittest.TestCase):
    """Preferencias cambia la voz secundaria sin recrear el worker."""

    def test_configurar_en_caliente_aplica_sin_recrear_el_respaldo(self):
        principal = Motor(("EL A", "EL B"), motor="elevenlabs")
        worker, fabrica = _worker(
            principal, ("Respaldo principal", "Respaldo secundario"),
            **_config_elevenlabs(elevenlabs_solo_importantes=True))
        worker._hablar("evento", secundaria=True)
        respaldo = fabrica.respaldos[-1]
        self.assertIsNotNone(respaldo)

        worker.configurar_voz_secundaria(
            "EL A", 40, 0.6, "Respaldo principal")
        self.assertEqual(worker._voz_secundaria.voz, "EL B")
        worker._procesar_comandos()

        self.assertEqual(worker._voz_secundaria.voz, "EL A")
        self.assertEqual(worker._voz_secundaria.velocidad, 40)
        self.assertEqual(worker._voz_secundaria.volumen, 60)
        self.assertIs(fabrica.respaldos[-1], respaldo)
        self.assertEqual((respaldo.velocidad, respaldo.volumen), (40, 60))


class FabricaRespaldos:
    """Crea un motor de respaldo nuevo en cada pedido."""

    def __init__(self, voces=("Respaldo A", "Respaldo B")):
        self.voces = list(voces)
        self.creados = []
        self.motores = []

    def __call__(self, nombre):
        self.creados.append(nombre)
        motor = Motor(self.voces)
        self.motores.append(motor)
        return motor


def _config_voz_secundaria(**extras):
    base = {"voz_secundaria": "Voz B", "velocidad_secundaria": 20,
            "volumen_secundaria": 0.3,
            "voz_respaldo_secundaria": "Respaldo B"}
    base.update(extras)
    return base


class TestVozSecundaria(unittest.TestCase):
    """La clase decide el índice y los ajustes, y maneja su respaldo."""

    def _voz(self, **extras):
        self.fabrica = FabricaRespaldos()
        return VozSecundaria(
            self.fabrica, _config_voz_secundaria(**extras), 50)

    def test_indice_con_voz_secundaria(self):
        self.assertEqual(self._voz().indice(("Voz A", "Voz B"), True),
                         (1, 20, 30))

    def test_sonando_nace_en_falso(self):
        self.assertFalse(self._voz().sonando)

    def test_indice_sin_pedir_secundaria(self):
        self.assertIsNone(self._voz().indice(("Voz A", "Voz B"), False))

    def test_indice_voz_vacia_o_inexistente(self):
        self.assertIsNone(
            self._voz(voz_secundaria="").indice(("Voz A", "Voz B"), True))
        self.assertIsNone(
            self._voz(voz_secundaria="No existe").indice(
                ("Voz A", "Voz B"), True))

    def test_respaldo_usa_su_voz_y_ajustes(self):
        voz = self._voz()
        motor = voz.conseguir_respaldo()
        self.assertEqual(self.fabrica.creados, ["sapi"])
        self.assertEqual(motor.elegidas, [1])
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (20, 30, 50))

    def test_respaldo_sin_voz_propia_usa_la_principal(self):
        voz = self._voz(voz_respaldo_secundaria="")
        motor = voz.conseguir_respaldo("Respaldo A")
        self.assertEqual(motor.elegidas, [0])

    def test_seguir_respaldo_solo_sin_voz_propia(self):
        voz = self._voz(voz_respaldo_secundaria="")
        motor = voz.conseguir_respaldo("Respaldo A")
        motor.elegidas.clear()
        voz.seguir_respaldo("Respaldo B")
        self.assertEqual(motor.elegidas, [1])

        propia = self._voz()
        motor = propia.conseguir_respaldo()
        motor.elegidas.clear()
        propia.seguir_respaldo("Respaldo A")
        self.assertEqual(motor.elegidas, [])

    def test_configurar_en_caliente_actualiza_voz_y_respaldo(self):
        voz = self._voz()
        motor = voz.conseguir_respaldo()
        motor.elegidas.clear()
        voz.configurar("Voz A", 40, 0.6, "Respaldo A", "Respaldo B", 30)
        self.assertEqual(voz.indice(("Voz A", "Voz B"), True), (0, 40, 60))
        self.assertEqual(motor.elegidas, [0])
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (40, 60, 30))
        self.assertEqual(len(self.fabrica.creados), 1)

    def test_configurar_antes_de_crear_se_usa_al_crear(self):
        voz = self._voz()
        voz.configurar("Voz A", 40, 0.6, "Respaldo A", "Respaldo B", 30)
        motor = voz.conseguir_respaldo()
        self.assertEqual(motor.elegidas, [0])
        self.assertEqual((motor.velocidad, motor.volumen, motor.tono),
                         (40, 60, 30))

    def test_cerrar_cierra_y_permite_crear_otro(self):
        voz = self._voz()
        motor = voz.conseguir_respaldo()
        voz.cerrar()
        self.assertTrue(motor.cerrado)
        self.assertIsNot(voz.conseguir_respaldo(), motor)
        self.assertEqual(len(self.fabrica.creados), 2)


if __name__ == "__main__":
    unittest.main()
