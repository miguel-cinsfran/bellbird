"""Pruebas de la recarga de la fuente del panel en OBS."""

import socket
import unittest
from unittest import mock

from bellbird.obs import obs_activacion, obs_cliente, obs_panel, obs_panel_recarga


class DobleCliente:
    def __init__(self, entradas=(), error_conectar=None, error_pedir=None):
        self.entradas = list(entradas)
        self.error_conectar = error_conectar
        self.error_pedir = error_pedir
        self.conectado = False
        self.cerrado = False
        self.pedidos = []

    def conectar(self, parada=None):
        if self.error_conectar is not None:
            raise self.error_conectar
        self.conectado = True

    def cerrar(self):
        self.cerrado = True

    def pedir(self, tipo, datos=None, parada=None):
        self.pedidos.append((tipo, datos or {}))
        if self.error_pedir is not None:
            raise self.error_pedir
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        return {"responseData": {}}


def _entrada(nombre=obs_panel.NOMBRE_FUENTE, tipo=obs_panel.TIPO_FUENTE):
    return {"inputName": nombre, "inputKind": tipo}


class RecargarFuentePanelTest(unittest.TestCase):

    def _recargar(self, cliente, obs_abierto=lambda: True):
        return obs_panel_recarga.recargar_fuente_panel(
            crear_cliente=lambda: cliente, obs_abierto=obs_abierto)

    def test_recarga_la_fuente_del_panel(self):
        cliente = DobleCliente(entradas=[_entrada()])
        self.assertTrue(self._recargar(cliente))
        self.assertTrue(cliente.conectado)
        self.assertTrue(cliente.cerrado)
        self.assertIn((
            "PressInputPropertiesButton",
            {"inputName": obs_panel.NOMBRE_FUENTE,
             "propertyName": "refreshnocache"},
        ), cliente.pedidos)

    def test_por_defecto_pregunta_si_obs_esta_abierto(self):
        creados = []
        with mock.patch.object(obs_activacion, "obs_esta_en_ejecucion",
                               return_value=False) as abierto:
            resultado = obs_panel_recarga.recargar_fuente_panel(
                crear_cliente=lambda: creados.append(True))
        self.assertFalse(resultado)
        abierto.assert_called_once_with()
        self.assertEqual(creados, [])

    def test_sin_obs_abierto_no_crea_cliente(self):
        creados = []

        def crear():
            creados.append(True)
            return DobleCliente(entradas=[_entrada()])

        self.assertFalse(obs_panel_recarga.recargar_fuente_panel(
            crear_cliente=crear, obs_abierto=lambda: False))
        self.assertEqual(creados, [])

    def test_sin_la_fuente_no_recarga(self):
        cliente = DobleCliente(entradas=[_entrada(nombre="Otra fuente")])
        self.assertFalse(self._recargar(cliente))
        self.assertTrue(cliente.cerrado)
        self.assertNotIn("PressInputPropertiesButton",
                         [tipo for tipo, _datos in cliente.pedidos])

    def test_una_fuente_del_mismo_nombre_pero_de_otro_tipo_no_se_toca(self):
        cliente = DobleCliente(entradas=[_entrada(tipo="image_source")])
        self.assertFalse(self._recargar(cliente))
        self.assertTrue(cliente.cerrado)
        self.assertNotIn("PressInputPropertiesButton",
                         [tipo for tipo, _datos in cliente.pedidos])

    def test_una_excepcion_al_conectar_devuelve_false_y_cierra(self):
        cliente = DobleCliente(error_conectar=RuntimeError("sin OBS"))
        self.assertFalse(self._recargar(cliente))
        self.assertTrue(cliente.cerrado)

    def test_una_excepcion_al_pedir_devuelve_false_y_cierra(self):
        cliente = DobleCliente(error_pedir=RuntimeError("OBS colgó"))
        self.assertFalse(self._recargar(cliente))
        self.assertTrue(cliente.cerrado)


class ClienteRealTest(unittest.TestCase):

    def test_un_puerto_sin_escucha_devuelve_false_sin_lanzar(self):
        # Se mantiene el socket abierto y sin listen: el puerto queda
        # reservado y la conexión se rechaza en el acto.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservado:
            reservado.bind(("127.0.0.1", 0))
            puerto = reservado.getsockname()[1]
            ajustes = obs_cliente.AjustesObs(puerto=puerto)
            resultado = obs_panel_recarga.recargar_fuente_panel(
                crear_cliente=lambda: obs_cliente.ClienteObs(ajustes),
                obs_abierto=lambda: True)
        self.assertFalse(resultado)


if __name__ == "__main__":
    unittest.main()
