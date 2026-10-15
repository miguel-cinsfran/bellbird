"""Pruebas del aviso de directo huérfano al arrancar.

Sin ventana: la consulta y la decisión se prueban sin wx, reemplazando
`wx.CallAfter` con un doble. El diálogo con NVDA lo verifica el dueño.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from ytchat.ui import gui_directo_huerfano as huerfano


class TestDirectosSinImagen(unittest.TestCase):

    def test_sin_activas_devuelve_vacio(self):
        self.assertEqual(huerfano.directos_sin_imagen([], "flujo-1", False),
                         [])

    def test_activa_de_otra_clave_devuelve_vacio(self):
        activas = [("vid1", "flujo-otra", "Charla")]
        self.assertEqual(
            huerfano.directos_sin_imagen(activas, "flujo-1", False), [])

    def test_obs_transmitiendo_devuelve_vacio(self):
        activas = [("vid1", "flujo-1", "Charla")]
        self.assertEqual(
            huerfano.directos_sin_imagen(activas, "flujo-1", True), [])

    def test_id_flujo_vacio_devuelve_vacio(self):
        activas = [("vid1", "flujo-1", "Charla")]
        self.assertEqual(huerfano.directos_sin_imagen(activas, "", False),
                         [])

    def test_varias_activas_devuelve_las_de_la_clave(self):
        activas = [("vid1", "flujo-1", "Charla"),
                   ("vid2", "flujo-otra", "Ajena"),
                   ("vid3", "flujo-1", "Música")]
        self.assertEqual(
            huerfano.directos_sin_imagen(activas, "flujo-1", False),
            [("vid1", "Charla"), ("vid3", "Música")])


class ClienteFalso:
    """Doble de ClienteYouTube con flujo y activas fijos."""

    construido_con = None

    def __init__(self, credenciales):
        ClienteFalso.construido_con = credenciales
        self.flujo = ("flujo-1", "rtmp://a", "clave")
        self.activas = [("vid1", "flujo-1", "Charla")]
        self.token = None

    def flujo_reutilizable(self):
        return self.flujo

    def emisiones_activas(self):
        return self.activas

    def token_actualizado(self):
        return self.token


class TestCableadoConsulta(unittest.TestCase):
    # Prueba de cableado: dobles de credenciales, cliente y OBS.

    def _contexto(self, hay_sesion=True, obs_corre=False,
                  salida_obs=None, activas=None):
        credenciales = SimpleNamespace(
            cargar=lambda: {"token": "t" if hay_sesion else None},
            hay_sesion=lambda datos: bool(datos.get("token")),
            efectivas=lambda datos: {"efectivas": True},
            guardar_campo=mock.Mock(return_value=True))
        creados = []

        def _construir(cred):
            creados.append(cred)
            cliente = ClienteFalso(cred)
            if activas is not None:
                cliente.activas = activas
            return cliente

        obs_activacion = SimpleNamespace(
            obs_esta_en_ejecucion=lambda: obs_corre)
        gestores = []

        def _gestor():
            gestor = mock.Mock()
            gestores.append(gestor)
            if isinstance(salida_obs, Exception):
                gestor.conectar.side_effect = salida_obs
            else:
                gestor.estado_transmision.return_value = {
                    "outputActive": salida_obs}
            return gestor

        parches = [
            mock.patch.object(huerfano, "credenciales", credenciales),
            mock.patch.object(huerfano.youtube_api, "ClienteYouTube",
                              _construir),
            mock.patch.object(huerfano, "obs_activacion", obs_activacion),
            mock.patch.object(huerfano, "GestorPanelObs",
                              side_effect=lambda *a, **k: _gestor()),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        llamadas = []
        llamada = mock.patch.object(
            huerfano.wx, "CallAfter",
            side_effect=lambda f, *a: llamadas.append((f, a)))
        llamada.start()
        self.addCleanup(llamada.stop)
        frame = SimpleNamespace(_alive=True)
        return frame, llamadas, creados

    def test_activa_de_la_clave_y_obs_sin_correr_agenda_la_pregunta(self):
        frame, llamadas, _creados = self._contexto(obs_corre=False)
        huerfano._consultar(frame)
        self.assertEqual(len(llamadas), 1)
        funcion, args = llamadas[0]
        self.assertIs(funcion, huerfano._preguntar)
        self.assertIs(args[0], frame)
        self.assertEqual(args[1], [("vid1", "Charla")])

    def test_obs_transmitiendo_no_agenda_nada(self):
        frame, llamadas, _creados = self._contexto(
            obs_corre=True, salida_obs=True)
        huerfano._consultar(frame)
        self.assertEqual(llamadas, [])

    def test_obs_que_no_responde_no_agenda_nada(self):
        frame, llamadas, _creados = self._contexto(
            obs_corre=True, salida_obs=RuntimeError("sin websocket"))
        huerfano._consultar(frame)
        self.assertEqual(llamadas, [])

    def test_sin_sesion_no_crea_el_cliente(self):
        frame, llamadas, creados = self._contexto(hay_sesion=False)
        huerfano._consultar(frame)
        self.assertEqual(creados, [])
        self.assertEqual(llamadas, [])


if __name__ == "__main__":
    unittest.main()
