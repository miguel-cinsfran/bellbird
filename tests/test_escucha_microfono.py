"""Monitorización de audio del micrófono de OBS: activar, restaurar y frases."""

import unittest

from guyrapu.obs import escucha_microfono
from guyrapu.obs.obs_cliente import ObsError

TIPO_LECTURA = "GetInputAudioMonitorType"
TIPO_ESCRITURA = "SetInputAudioMonitorType"


class ClienteFalso:
    """Cliente de OBS que recuerda el tipo y los pedidos recibidos."""

    def __init__(self, tipo, fallo=None):
        self.tipo = tipo
        self.fallo = fallo
        self.pedidos = []
        self.cerrado = False
        self.conectado = False

    def conectar(self):
        self.conectado = True

    def cerrar(self):
        self.cerrado = True

    def pedir(self, tipo, datos=None):
        self.pedidos.append((tipo, datos))
        if tipo == self.fallo:
            raise ObsError("fallo de prueba")
        if tipo == TIPO_LECTURA:
            return {"responseData": {"monitorType": self.tipo}}
        if tipo == TIPO_ESCRITURA:
            self.tipo = datos["monitorType"]
            return {}
        return {}


def _fabrica(cliente):
    return lambda: cliente


def _escrituras(cliente):
    return [datos for tipo, datos in cliente.pedidos if tipo == TIPO_ESCRITURA]


class TestActivar(unittest.TestCase):
    def _activar_desde(self, tipo):
        cliente = ClienteFalso(tipo)
        anterior = escucha_microfono.activar(
            "Mic/Aux", crear_cliente=_fabrica(cliente))
        return cliente, anterior

    def test_desde_ninguna_pide_monitorizar_y_emitir(self):
        cliente, anterior = self._activar_desde(escucha_microfono.NINGUNA)
        self.assertEqual(anterior, escucha_microfono.NINGUNA)
        self.assertEqual(_escrituras(cliente), [
            {"inputName": "Mic/Aux",
             "monitorType": escucha_microfono.MONITOR_Y_SALIDA}])
        self.assertTrue(cliente.cerrado)

    def test_desde_solo_monitor_pide_monitorizar_y_emitir(self):
        cliente, anterior = self._activar_desde(escucha_microfono.SOLO_MONITOR)
        self.assertEqual(anterior, escucha_microfono.SOLO_MONITOR)
        self.assertEqual(_escrituras(cliente), [
            {"inputName": "Mic/Aux",
             "monitorType": escucha_microfono.MONITOR_Y_SALIDA}])

    def test_desde_monitor_y_salida_no_pide_nada(self):
        cliente, anterior = self._activar_desde(
            escucha_microfono.MONITOR_Y_SALIDA)
        self.assertEqual(anterior, escucha_microfono.MONITOR_Y_SALIDA)
        self.assertEqual(_escrituras(cliente), [])
        self.assertTrue(cliente.cerrado)

    def test_cierra_el_cliente_si_el_pedido_falla(self):
        cliente = ClienteFalso(escucha_microfono.NINGUNA,
                               fallo=TIPO_ESCRITURA)
        with self.assertRaises(ObsError):
            escucha_microfono.activar(
                "Mic/Aux", crear_cliente=_fabrica(cliente))
        self.assertTrue(cliente.cerrado)


class TestRestaurar(unittest.TestCase):
    def test_devuelve_el_tipo_anterior(self):
        cliente = ClienteFalso(escucha_microfono.MONITOR_Y_SALIDA)
        escucha_microfono.restaurar(
            "Mic/Aux", escucha_microfono.NINGUNA,
            crear_cliente=_fabrica(cliente))
        self.assertEqual(_escrituras(cliente), [
            {"inputName": "Mic/Aux", "monitorType": escucha_microfono.NINGUNA}])
        self.assertTrue(cliente.cerrado)

    def test_con_monitor_y_salida_no_pide_nada(self):
        cliente = ClienteFalso(escucha_microfono.MONITOR_Y_SALIDA)
        escucha_microfono.restaurar(
            "Mic/Aux", escucha_microfono.MONITOR_Y_SALIDA,
            crear_cliente=_fabrica(cliente))
        self.assertEqual(_escrituras(cliente), [])
        self.assertTrue(cliente.cerrado)

    def test_cierra_el_cliente_si_el_pedido_falla(self):
        cliente = ClienteFalso(escucha_microfono.MONITOR_Y_SALIDA,
                               fallo=TIPO_ESCRITURA)
        with self.assertRaises(ObsError):
            escucha_microfono.restaurar(
                "Mic/Aux", escucha_microfono.NINGUNA,
                crear_cliente=_fabrica(cliente))
        self.assertTrue(cliente.cerrado)


class TestFrases(unittest.TestCase):
    def test_activada_cuando_ya_estaba(self):
        self.assertEqual(
            escucha_microfono.frase_activada(
                escucha_microfono.MONITOR_Y_SALIDA),
            "La monitorización ya estaba activada en OBS.")

    def test_activada_con_el_aviso_del_acople(self):
        self.assertEqual(
            escucha_microfono.frase_activada(escucha_microfono.NINGUNA),
            "Monitorización activada. Te oyes por el dispositivo de "
            "monitorización de OBS. Usa auriculares para evitar acople.")

    def test_desactivada_desde_ninguna(self):
        self.assertEqual(
            escucha_microfono.frase_desactivada(escucha_microfono.NINGUNA),
            "Monitorización desactivada.")

    def test_desactivada_restablecida(self):
        self.assertEqual(
            escucha_microfono.frase_desactivada(escucha_microfono.SOLO_MONITOR),
            "Monitorización restablecida como estaba en OBS.")


if __name__ == "__main__":
    unittest.main()
