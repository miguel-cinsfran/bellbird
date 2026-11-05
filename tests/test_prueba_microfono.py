"""Prueba por tramos del micrófono de OBS. Sin wx ni conexiones reales."""

import threading
import time
import unittest

from guyrapu.obs import dispositivo_windows
from guyrapu.obs import obs_cliente
from guyrapu.obs import obs_entradas_audio
from guyrapu.obs import prueba_microfono


def _evento(pico, fuente="Mic/Aux"):
    return {"inputs": [{"inputName": fuente,
                        "inputLevelsMul": [[pico, pico, pico]]}]}


class ClientePorTramos:
    """Cliente doble que entrega un tramo de eventos por escucha."""

    def __init__(self, tramos=(), fallo=None):
        self.tramos = list(tramos)
        self.fallo = fallo
        self.conexiones = 0
        self.escuchas = 0
        self.cerrado = False

    def conectar(self, parada=None):
        self.conexiones += 1

    def escuchar(self, tipo_evento, segundos, parada=None):
        self.escuchas += 1
        if self.fallo is not None:
            raise self.fallo
        if self.tramos:
            return self.tramos.pop(0)
        if parada is not None:
            parada.wait(segundos)
        else:
            time.sleep(segundos)
        return []

    def cerrar(self):
        self.cerrado = True


class GestorFalso:
    def __init__(self, entradas=(("Mic/Aux", obs_entradas_audio.TIPO_MICROFONO),),
                 especial="", silenciada=False, nombre="Micrófono USB",
                 predeterminado=False, fallo_dispositivo=None):
        self.entradas = tuple(entradas)
        self.especial = especial
        self.silencio = silenciada
        self.nombre = nombre
        self.predeterminado = predeterminado
        self.fallo_dispositivo = fallo_dispositivo
        self.consultas_dispositivo = []

    def entradas_audio(self, parada=None):
        return self.entradas

    def microfono_especial(self, parada=None):
        return self.especial

    def silenciada(self, fuente, parada=None):
        self.fuente_silencio = fuente
        return self.silencio

    def dispositivo(self, fuente, predeterminado, parada=None):
        self.consultas_dispositivo.append((fuente, predeterminado))
        if self.fallo_dispositivo is not None:
            raise self.fallo_dispositivo
        return self.nombre, self.predeterminado


def _esperar(condicion, segundos=2.0):
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.002)
    return condicion()


class PrepararTest(unittest.TestCase):
    def test_sin_microfono_devuelve_fuente_vacia(self):
        gestor = GestorFalso(entradas=())
        self.assertEqual(prueba_microfono.preparar(gestor, ""),
                         ("", False, ""))

    def test_microfono_silenciado_lo_informa(self):
        gestor = GestorFalso(silenciada=True)
        self.assertEqual(prueba_microfono.preparar(gestor, ""),
                         ("Mic/Aux", True, "Micrófono USB"))

    def test_fallo_al_leer_el_dispositivo_deja_el_nombre_vacio(self):
        gestor = GestorFalso(fallo_dispositivo=RuntimeError("sin datos"))
        self.assertEqual(prueba_microfono.preparar(gestor, ""),
                         ("Mic/Aux", False, ""))

    def test_elige_el_preferido_y_pregunta_por_el_predeterminado(self):
        gestor = GestorFalso(
            entradas=(("Mic/Aux", obs_entradas_audio.TIPO_MICROFONO),
                      ("Audio USB", obs_entradas_audio.TIPO_MICROFONO)))
        prueba_microfono.preparar(gestor, "Audio USB")
        self.assertEqual(gestor.fuente_silencio, "Audio USB")
        self.assertEqual(
            gestor.consultas_dispositivo,
            [("Audio USB", dispositivo_windows.microfono_predeterminado)])


class FraseDeInicioTest(unittest.TestCase):
    def test_sin_manos_libres_solo_anuncia_el_inicio(self):
        self.assertEqual(
            prueba_microfono.frase_de_inicio("Micrófono USB"),
            "Prueba del micrófono iniciada. Habla como en un directo.")

    def test_con_manos_libres_avisa_de_la_poca_calidad(self):
        nombre = "Auriculares Bluetooth Hands-Free"
        self.assertEqual(
            prueba_microfono.frase_de_inicio(nombre),
            "Prueba del micrófono iniciada. Habla como en un directo. "
            f"{nombre} es un auricular en modo manos libres y suena con poca "
            "calidad. Para el directo, usa otro micrófono.")


class PruebaMicrofonoTest(unittest.TestCase):
    def _lanzar(self, cliente, **opciones):
        niveles = []
        motivos = []
        terminado = threading.Event()

        def al_terminar(motivo):
            motivos.append(motivo)
            terminado.set()

        fabricados = []

        def fabrica():
            fabricados.append(cliente)
            return cliente

        prueba = prueba_microfono.PruebaMicrofono(
            "Mic/Aux", niveles.append, al_terminar,
            crear_cliente=fabrica, **opciones)
        prueba.iniciar()
        return prueba, niveles, motivos, terminado, fabricados

    def test_tres_tramos_dan_tres_avisos_con_un_solo_cliente(self):
        cliente = ClientePorTramos([
            [_evento(0.11)],
            [_evento(0.0011)],
            [_evento(0.5)],
        ])
        prueba, niveles, motivos, terminado, fabricados = self._lanzar(
            cliente, segundos_tramo=5.0, tope=30.0)
        self.assertTrue(_esperar(lambda: len(niveles) == 3))
        prueba.detener()
        self.assertTrue(terminado.wait(2.0))
        self.assertEqual(
            [nivel.estado for nivel in niveles], ["bien", "bajo", "alto"])
        self.assertEqual(len(fabricados), 1)
        self.assertEqual(cliente.conexiones, 1)
        self.assertTrue(cliente.cerrado)
        self.assertEqual(motivos, ["detenida"])

    def test_detener_termina_con_detenida_y_cierra_el_cliente(self):
        cliente = ClientePorTramos([])
        prueba, _niveles, motivos, terminado, _fabricados = self._lanzar(
            cliente, segundos_tramo=5.0, tope=30.0)
        self.assertTrue(_esperar(lambda: cliente.conexiones == 1))
        prueba.detener()
        self.assertTrue(terminado.wait(2.0))
        self.assertEqual(motivos, ["detenida"])
        self.assertTrue(cliente.cerrado)

    def test_el_tope_termina_la_prueba(self):
        cliente = ClientePorTramos([])
        _prueba, _niveles, motivos, terminado, _fabricados = self._lanzar(
            cliente, segundos_tramo=0.01, tope=0.03)
        self.assertTrue(terminado.wait(2.0))
        self.assertEqual(motivos, ["tope"])
        self.assertTrue(cliente.cerrado)

    def test_un_fallo_al_escuchar_termina_con_fallo(self):
        cliente = ClientePorTramos(
            fallo=obs_cliente.ObsError("Se perdió la conexión con OBS."))
        _prueba, _niveles, motivos, terminado, _fabricados = self._lanzar(
            cliente, segundos_tramo=0.01, tope=1.0)
        self.assertTrue(terminado.wait(2.0))
        self.assertEqual(motivos, ["fallo"])
        self.assertTrue(cliente.cerrado)

    def test_al_terminar_se_llama_una_sola_vez(self):
        cliente = ClientePorTramos([[_evento(0.11)]])
        _prueba, _niveles, motivos, terminado, _fabricados = self._lanzar(
            cliente, segundos_tramo=0.01, tope=0.03)
        self.assertTrue(terminado.wait(2.0))
        time.sleep(0.05)
        self.assertEqual(motivos, ["tope"])


if __name__ == "__main__":
    unittest.main()
