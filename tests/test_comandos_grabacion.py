"""Pruebas sin ventana de `bellbird/ui/comandos_grabacion.py`."""

import unittest
from types import SimpleNamespace
from unittest import mock

from bellbird.obs import obs_cliente
from bellbird.ui import comandos_grabacion


def _llamada_inmediata(funcion, *args, **kwargs):
    return funcion(*args, **kwargs)


class HiloInmediato:
    """Doble de `diagnostico.crear_hilo` que ejecuta el objetivo al arrancar."""

    def __init__(self, target, nombre, **kwargs):
        self.target = target
        self.nombre = nombre
        self.daemon = kwargs.get("daemon", True)
        self.iniciado = False

    def start(self):
        self.iniciado = True
        self.target()


class GestorGrabacionFalso:
    """Doble de GestorPanelObs para los comandos de grabación del menú."""

    def __init__(self, grabando=False, en_pausa=False, fallo=None):
        self.grabando = grabando
        self.en_pausa = en_pausa
        self.fallo = fallo
        self.llamadas = []
        self.cerrado = False

    def conectar(self):
        self.llamadas.append("conectar")
        if self.fallo is not None:
            raise self.fallo

    def cerrar(self):
        self.cerrado = True

    def estado_grabacion(self):
        self.llamadas.append("estado_grabacion")
        return {"outputActive": self.grabando, "outputPaused": self.en_pausa,
                "outputTimecode": "00:00:00.000"}

    def alternar_grabacion(self):
        self.llamadas.append("alternar_grabacion")
        self.grabando = not self.grabando
        return self.grabando

    def alternar_pausa_grabacion(self):
        anterior = self.en_pausa
        self.en_pausa = not self.en_pausa
        self.llamadas.append("alternar_pausa_grabacion")
        return self.en_pausa, anterior


class TestComandosGrabacion(unittest.TestCase):

    def _correr(self, funcion, gestor=None):
        gestor = gestor or GestorGrabacionFalso()
        with mock.patch.object(comandos_grabacion, "GestorPanelObs",
                               return_value=gestor), \
                mock.patch.object(comandos_grabacion.diagnostico,
                                  "crear_hilo", HiloInmediato), \
                mock.patch.object(comandos_grabacion.wx, "CallAfter",
                                  side_effect=_llamada_inmediata), \
                mock.patch.object(comandos_grabacion, "anunciar") as anunciar, \
                mock.patch.object(comandos_grabacion.sound_player,
                                  "reproducir") as sonar:
            funcion(SimpleNamespace())
        return gestor, anunciar, sonar

    def test_alternar_grabacion_inicia_y_avisa_como_el_panel(self):
        gestor, anunciar, sonar = self._correr(
            comandos_grabacion.alternar_grabacion,
            GestorGrabacionFalso(grabando=False))
        self.assertTrue(gestor.grabando)
        anunciar.assert_called_once_with("Grabación iniciada")
        sonar.assert_called_once_with("grabacion_iniciada")
        self.assertTrue(gestor.cerrado)

    def test_alternar_grabacion_detiene_y_avisa_como_el_panel(self):
        gestor, anunciar, sonar = self._correr(
            comandos_grabacion.alternar_grabacion,
            GestorGrabacionFalso(grabando=True))
        self.assertFalse(gestor.grabando)
        anunciar.assert_called_once_with("Grabación detenida")
        sonar.assert_called_once_with("grabacion_detenida")
        self.assertTrue(gestor.cerrado)

    def test_pausar_avisa_y_suena_como_el_panel(self):
        gestor, anunciar, sonar = self._correr(
            comandos_grabacion.alternar_pausa_grabacion,
            GestorGrabacionFalso(grabando=True, en_pausa=False))
        self.assertTrue(gestor.en_pausa)
        anunciar.assert_called_once_with("Grabación en pausa")
        sonar.assert_called_once_with("grabacion_en_pausa")

    def test_reanudar_avisa_y_suena_como_el_panel(self):
        gestor, anunciar, sonar = self._correr(
            comandos_grabacion.alternar_pausa_grabacion,
            GestorGrabacionFalso(grabando=True, en_pausa=True))
        self.assertFalse(gestor.en_pausa)
        anunciar.assert_called_once_with("Grabación reanudada")
        sonar.assert_called_once_with("grabacion_reanudada")

    def test_pausar_sin_grabacion_avisa_y_no_toca_obs(self):
        gestor, anunciar, sonar = self._correr(
            comandos_grabacion.alternar_pausa_grabacion,
            GestorGrabacionFalso(grabando=False))
        self.assertEqual(gestor.llamadas, ["conectar", "estado_grabacion"])
        anunciar.assert_called_once_with("No hay ninguna grabación en curso.")
        sonar.assert_called_once_with("error")

    def test_pausa_sin_cambio_avisa_el_fallo_segun_el_estado(self):
        casos = (
            (False, "OBS no pausó la grabación: este perfil puede no permitirlo."),
            (True, "OBS no reanudó la grabación."),
        )
        for en_pausa, frase in casos:
            with self.subTest(en_pausa=en_pausa):
                gestor = GestorGrabacionFalso(grabando=True,
                                              en_pausa=en_pausa)
                gestor.alternar_pausa_grabacion = mock.Mock(
                    return_value=(None, en_pausa))
                gestor, anunciar, sonar = self._correr(
                    comandos_grabacion.alternar_pausa_grabacion, gestor)
                anunciar.assert_called_once_with(frase)
                sonar.assert_called_once_with("error")

    def test_si_cerrar_falla_igual_avisa_el_resultado(self):
        gestor = GestorGrabacionFalso(grabando=False)

        def cerrar():
            gestor.cerrado = True
            raise obs_cliente.ObsError("no se pudo cerrar")

        gestor.cerrar = cerrar
        with self.assertLogs(comandos_grabacion.logger, level="DEBUG"):
            gestor, anunciar, sonar = self._correr(
                comandos_grabacion.alternar_grabacion, gestor)
        anunciar.assert_called_once_with("Grabación iniciada")
        sonar.assert_called_once_with("grabacion_iniciada")
        self.assertTrue(gestor.cerrado)

    def test_sin_obs_avisa_su_mensaje_y_no_lo_abre(self):
        for funcion in (comandos_grabacion.alternar_grabacion,
                        comandos_grabacion.alternar_pausa_grabacion):
            with self.subTest(funcion=funcion.__name__):
                error = obs_cliente.ObsError("No se pudo conectar con OBS.")
                with mock.patch(
                        "bellbird.obs.obs_lanzador.asegurar_obs") as asegurar:
                    gestor, anunciar, sonar = self._correr(
                        funcion, GestorGrabacionFalso(fallo=error))
                asegurar.assert_not_called()
                anunciar.assert_called_once_with(
                    obs_cliente.mensaje_de_fallo_obs(error))
                sonar.assert_called_once_with("error")
                self.assertTrue(gestor.cerrado)

    def test_la_interfaz_no_espera_a_obs(self):
        gestor = GestorGrabacionFalso()
        hilos = []

        class HiloSinArrancar:
            def __init__(self, target, nombre, **kwargs):
                self.target = target
                self.nombre = nombre
                hilos.append(self)

            def start(self):
                pass

        with mock.patch.object(comandos_grabacion, "GestorPanelObs",
                               return_value=gestor), \
                mock.patch.object(comandos_grabacion.diagnostico,
                                  "crear_hilo", HiloSinArrancar):
            comandos_grabacion.alternar_grabacion(SimpleNamespace())
        self.assertEqual([hilo.nombre for hilo in hilos], ["GrabacionObs"])
        self.assertEqual(gestor.llamadas, [])


if __name__ == "__main__":
    unittest.main()
