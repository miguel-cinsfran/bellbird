"""Pruebas del nombre y la migración de la fuente del chat en OBS."""

import unittest
from unittest import mock

from bellbird.obs import fuente_chat, obs_captura, obs_cliente, obs_panel


VIEJA = {"inputName": "Chat YTChat", "inputKind": "browser_source"}
NUEVA = {"inputName": "Chat en el vídeo", "inputKind": "browser_source"}


class PedirFalso:
    def __init__(self, entradas, error=None):
        self.entradas = list(entradas)
        self.error = error
        self.llamadas = []

    def __call__(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, datos or {}, parada))
        if self.error is not None:
            raise self.error
        if tipo == "GetInputList":
            return {"inputs": list(self.entradas)}
        return {}


class RenombrarAnteriorTest(unittest.TestCase):
    def test_renombra_la_fuente_vieja_sola(self):
        pedir = PedirFalso([VIEJA])
        fuente_chat.renombrar_anterior(pedir)
        self.assertIn(("SetInputName",
                       {"inputName": "Chat YTChat",
                        "newInputName": "Chat en el vídeo"}, None),
                      pedir.llamadas)

    def test_no_toca_si_ya_existen_las_dos(self):
        pedir = PedirFalso([VIEJA, NUEVA])
        fuente_chat.renombrar_anterior(pedir)
        self.assertEqual([tipo for tipo, _datos, _parada in pedir.llamadas],
                         ["GetInputList"])

    def test_no_toca_si_la_vieja_no_es_navegador(self):
        pedir = PedirFalso([{"inputName": "Chat YTChat",
                             "inputKind": "text_gdiplus_v2"}])
        fuente_chat.renombrar_anterior(pedir)
        self.assertEqual([tipo for tipo, _datos, _parada in pedir.llamadas],
                         ["GetInputList"])

    def test_no_toca_sin_ninguna(self):
        pedir = PedirFalso([])
        fuente_chat.renombrar_anterior(pedir)
        self.assertEqual([tipo for tipo, _datos, _parada in pedir.llamadas],
                         ["GetInputList"])

    def test_un_obs_error_no_sale_de_la_funcion(self):
        pedir = PedirFalso([VIEJA], error=obs_cliente.ObsError("600 sin OBS"))
        fuente_chat.renombrar_anterior(pedir)


class ConectarTest(unittest.TestCase):
    def _cliente(self, entradas):
        cliente = mock.Mock()
        cliente.conectado = True

        def pedir(tipo, datos=None, parada=None):
            if tipo == "GetInputList":
                return {"responseData": {"inputs": list(entradas)}}
            return {"responseData": {}}

        cliente.pedir.side_effect = pedir
        return cliente

    def test_conectar_renombra_la_fuente_vieja(self):
        cliente = self._cliente([VIEJA])
        obs_panel.GestorPanelObs(cliente).conectar()
        cliente.conectar.assert_called_once_with(None)
        tipos = [llamada.args[0] for llamada in cliente.pedir.call_args_list]
        self.assertIn("SetInputName", tipos)

    def test_preparar_destino_renombra_la_fuente_vieja(self):
        cliente = self._cliente([VIEJA])
        gestor = obs_panel.GestorPanelObs(cliente)
        with mock.patch.object(obs_panel.obs_destinos,
                               "preparar_para_transmitir",
                               return_value={"destino": "TikTok"}):
            gestor.preparar_destino("TikTok")
        tipos = [llamada.args[0] for llamada in cliente.pedir.call_args_list]
        self.assertIn("SetInputName", tipos)


class ClienteRecarga:
    def __init__(self, entradas):
        self.entradas = list(entradas)
        self.pedidos = []

    def conectar(self, parada=None):
        pass

    def cerrar(self):
        pass

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.pedidos.append((tipo, datos))
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "SetInputName":
            for entrada in self.entradas:
                if entrada.get("inputName") == datos["inputName"]:
                    entrada["inputName"] = datos["newInputName"]
        return {"responseData": {}}


class RecargaRenombraTest(unittest.TestCase):
    def test_la_recarga_renombra_la_vieja_y_pulsa_la_nueva(self):
        from bellbird.obs import obs_panel_recarga

        cliente = ClienteRecarga([dict(VIEJA)])
        resultado = obs_panel_recarga.recargar_fuente_panel(
            crear_cliente=lambda: cliente, obs_abierto=lambda: True)
        self.assertTrue(resultado)
        tipos = [tipo for tipo, _datos in cliente.pedidos]
        self.assertIn("SetInputName", tipos)
        recarga = next(datos for tipo, datos in cliente.pedidos
                       if tipo == "PressInputPropertiesButton")
        self.assertEqual(recarga["inputName"], "Chat en el vídeo")


class NombreNuevoTest(unittest.TestCase):
    def test_la_fuente_nueva_se_llama_chat_en_el_video(self):
        self.assertEqual(fuente_chat.NOMBRE_FUENTE, "Chat en el vídeo")
        self.assertIs(obs_panel.NOMBRE_FUENTE, fuente_chat.NOMBRE_FUENTE)
        self.assertIs(obs_panel.TIPO_FUENTE, fuente_chat.TIPO_FUENTE)

    def test_la_sonda_de_ventanas_se_llama_bellbird(self):
        self.assertEqual(obs_captura.NOMBRE_SONDA,
                         "Bellbird, lista de ventanas")


if __name__ == "__main__":
    unittest.main()
