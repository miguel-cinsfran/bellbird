"""Pruebas del aviso de directo huérfano al arrancar.

Sin ventana: la consulta y la decisión se prueban sin wx, reemplazando
`wx.CallAfter` con un doble. El diálogo con NVDA lo verifica el dueño.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bellbird.ui import gui_directo_huerfano as huerfano
from tests.pseudo_prueba import con_pseudo


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

    def test_excluir_deja_fuera_los_que_ya_se_terminan(self):
        activas = [("vid1", "flujo-1", "Charla"),
                   ("vid3", "flujo-1", "Música")]
        self.assertEqual(
            huerfano.directos_sin_imagen(activas, "flujo-1", False,
                                         excluir={"vid1"}),
            [("vid3", "Música")])


class ClienteFalso:
    """Doble de ClienteYouTube con flujo y activas fijos."""

    construido_con = None
    instancias = []

    def __init__(self, credenciales):
        ClienteFalso.construido_con = credenciales
        ClienteFalso.instancias.append(self)
        self.flujo = ("flujo-1", "rtmp://a", "clave")
        self.activas = [("vid1", "flujo-1", "Charla")]
        self.token = None
        self.finalizados = []
        self.esta_vivo = True

    def flujo_reutilizable(self):
        return self.flujo

    def emisiones_activas(self):
        return self.activas

    def token_actualizado(self):
        return self.token

    def estado_emision(self, id_video):
        return "live" if self.esta_vivo else "complete"

    def finalizar_emision(self, id_video):
        self.finalizados.append(id_video)


class TestCableadoConsulta(unittest.TestCase):
    # Prueba de cableado: dobles de credenciales, cliente y OBS.

    def _contexto(self, hay_sesion=True, obs_corre=False,
                  salida_obs=None, activas=None, pendientes=None):
        credenciales = SimpleNamespace(
            cargar=lambda: {"token": "t" if hay_sesion else None},
            hay_sesion=lambda datos: bool(datos.get("token")),
            efectivas=lambda datos: {"efectivas": True},
            guardar_campo=mock.Mock(return_value=True))
        creados = []
        ClienteFalso.instancias = []

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

        tmp = Path(tempfile.mkdtemp()) / "fin_pendiente.json"
        for id_video in (pendientes or []):
            huerfano.fin_pendiente.anotar(tmp, id_video)

        parches = [
            mock.patch.object(huerfano, "credenciales", credenciales),
            mock.patch.object(huerfano.youtube_api, "ClienteYouTube",
                              _construir),
            mock.patch.object(huerfano, "obs_activacion", obs_activacion),
            mock.patch.object(huerfano, "GestorPanelObs",
                              side_effect=lambda *a, **k: _gestor()),
            mock.patch.object(huerfano.paths, "fin_pendiente",
                              return_value=tmp),
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
        return frame, llamadas, creados, tmp

    def test_activa_de_la_clave_y_obs_sin_correr_agenda_la_pregunta(self):
        frame, llamadas, _creados, _ruta = self._contexto(obs_corre=False)
        huerfano._consultar(frame)
        self.assertEqual(len(llamadas), 1)
        funcion, args = llamadas[0]
        self.assertIs(funcion, huerfano._preguntar)
        self.assertIs(args[0], frame)
        self.assertEqual(args[1], [("vid1", "Charla")])

    def test_obs_transmitiendo_no_agenda_nada(self):
        frame, llamadas, _creados, _ruta = self._contexto(
            obs_corre=True, salida_obs=True)
        huerfano._consultar(frame)
        self.assertEqual(llamadas, [])

    def test_obs_que_no_responde_no_agenda_nada(self):
        frame, llamadas, _creados, _ruta = self._contexto(
            obs_corre=True, salida_obs=RuntimeError("sin websocket"))
        huerfano._consultar(frame)
        self.assertEqual(llamadas, [])

    def test_sin_sesion_no_crea_el_cliente(self):
        frame, llamadas, creados, _ruta = self._contexto(hay_sesion=False)
        huerfano._consultar(frame)
        self.assertEqual(creados, [])
        self.assertEqual(llamadas, [])

    def test_pendiente_se_finaliza_y_no_se_pregunta_como_huerfano(self):
        frame, llamadas, _creados, ruta = self._contexto(
            obs_corre=False, activas=[("vid9", "flujo-1", "Pendiente")],
            pendientes=["vid9"])
        huerfano._consultar(frame)
        # Se finalizó y se anunció, y no se preguntó por él como huérfano.
        self.assertEqual(ClienteFalso.instancias[-1].finalizados, ["vid9"])
        self.assertEqual(huerfano.fin_pendiente.leer(ruta), [])
        self.assertTrue(any(f is huerfano._anunciar_fin_pendiente
                            for f, _a in llamadas))
        self.assertFalse(any(f is huerfano._preguntar
                             for f, _a in llamadas))

    def test_dos_pendientes_que_fallan_avisan_una_vez(self):
        frame, llamadas, _creados, _ruta = self._contexto(
            obs_corre=False, pendientes=["vid1", "vid2"])
        with mock.patch.object(huerfano.emision, "finalizar_en_youtube",
                               side_effect=RuntimeError("sin red")), \
                mock.patch.object(huerfano, "_reintentar_en_hilo") as reintentar:
            huerfano._terminar_pendientes(frame, mock.Mock())
        avisos = [f for f, _a in llamadas
                  if f is huerfano._anunciar_reintento_pendiente]
        self.assertEqual(len(avisos), 1)
        self.assertEqual(reintentar.call_count, 2)


class TestPseudoPreguntarHuerfano(unittest.TestCase):
    # Sin ventana: el MessageDialog va simulado. Los títulos de los
    # directos son datos del usuario y van como ejemplo.

    def _preguntar(self, huerfanos):
        captado = {}
        creados = []

        def fabrica(padre, mensaje, titulo, estilo):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            dialogo = mock.Mock()
            dialogo.ShowModal.return_value = huerfano.wx.ID_YES
            creados.append(dialogo)
            return dialogo

        frame = SimpleNamespace(
            _alive=True,
            _supervisar_transmision=mock.Mock(return_value=False))
        with con_pseudo(), \
                mock.patch.object(huerfano.wx, "MessageDialog", fabrica), \
                mock.patch.object(huerfano.diagnostico, "crear_hilo"):
            huerfano._preguntar(frame, huerfanos)
        return captado, creados

    def test_singular_marca_mensaje_titulo_y_botones(self):
        captado, creados = self._preguntar([("vid1", "Charla")])
        self.assertIn("Charla", captado["mensaje"])
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        for etiqueta in creados[0].SetYesNoLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"), etiqueta)

    def test_plural_marca_mensaje_titulo_y_botones(self):
        captado, creados = self._preguntar(
            [("vid1", "Charla"), ("vid2", "Música")])
        self.assertNotIn("Charla", captado["mensaje"])
        self.assertTrue(captado["mensaje"].startswith("[¡"))
        self.assertTrue(captado["titulo"].startswith("[¡"))
        for etiqueta in creados[0].SetYesNoLabels.call_args.args:
            self.assertTrue(etiqueta.startswith("[¡"), etiqueta)


class TestPseudoAnunciosHuerfano(unittest.TestCase):
    # Sin ventana: marco y sonidos con dobles.

    def setUp(self):
        self.captados = []
        parches = [
            mock.patch.object(huerfano, "anunciar", self.captados.append),
            mock.patch.object(huerfano._snd, "reproducir"),
        ]
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        pseudo = con_pseudo()
        pseudo.__enter__()
        self.addCleanup(pseudo.__exit__, None, None, None)

    def _exigir_marcados(self, cantidad):
        self.assertEqual(len(self.captados), cantidad)
        for frase in self.captados:
            self.assertTrue(frase.startswith("[¡"), frase)
        del self.captados[:]

    def _frame(self):
        return SimpleNamespace(
            _alive=True,
            _supervisar_transmision=mock.Mock(return_value=False))

    def test_dejar_al_aire_avisa_marcado(self):
        dialogo = mock.Mock()
        dialogo.ShowModal.return_value = huerfano.wx.ID_NO
        with mock.patch.object(huerfano.wx, "MessageDialog",
                               return_value=dialogo):
            huerfano._preguntar(self._frame(), [("vid1", "Charla")])
        dialogo.SetYesNoLabels.assert_called_once()
        self._exigir_marcados(1)

    def test_fin_singular_y_plural_marcan(self):
        frame = self._frame()
        huerfano._anunciar_fin(frame, 1)
        self._exigir_marcados(1)
        huerfano._anunciar_fin(frame, 3)
        self._exigir_marcados(1)

    def test_fallo_y_pendientes_marcan(self):
        frame = self._frame()
        huerfano._anunciar_fallo(frame)
        self._exigir_marcados(1)
        huerfano._anunciar_fin_pendiente(frame)
        self._exigir_marcados(1)
        huerfano._anunciar_fallo_pendiente(frame)
        self._exigir_marcados(1)
        huerfano._anunciar_reintento_pendiente(frame)
        self._exigir_marcados(1)


if __name__ == "__main__":
    unittest.main()
