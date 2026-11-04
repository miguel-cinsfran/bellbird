"""Pruebas sin ventana de `bellbird/ui/comandos_clips.py`."""

import unittest
from types import SimpleNamespace
from unittest import mock

from bellbird.core.idioma import _
from bellbird.obs import obs_cliente, obs_clips
from bellbird.ui import comandos_clips


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


class GestorClipsFalso:
    def __init__(self, fallo=None):
        self.fallo = fallo
        self._cliente = self
        self.llamadas = []
        self.cerrado = False

    def conectar(self):
        self.llamadas.append("conectar")
        if self.fallo is not None:
            raise self.fallo

    def cerrar(self):
        self.cerrado = True


def estado(salida=False, buffer=False, preparado=False, soportado=True,
           conocido=True):
    return obs_clips.EstadoClips(salida, buffer, preparado, soportado,
                                 conocido)


class TestComandosClips(unittest.TestCase):

    def _correr(self, gestor=None, segundos=30, estado_leido=None,
                ruta="", decision=None):
        gestor = gestor or GestorClipsFalso()
        funciones = {
            "leer_segundos": mock.Mock(return_value=segundos),
            "leer_estado": mock.Mock(return_value=estado_leido or estado()),
            "preparar": mock.Mock(),
            "iniciar": mock.Mock(),
            "guardar": mock.Mock(return_value=ruta),
        }
        if decision is not None:
            funciones["decidir"] = mock.Mock(return_value=decision)
        anunciar = mock.Mock()
        sonar = mock.Mock()
        parches = [mock.patch.object(comandos_clips.obs_clips, nombre, valor)
                   for nombre, valor in funciones.items()]
        parches.extend([
            mock.patch.object(comandos_clips, "GestorPanelObs",
                              return_value=gestor),
            mock.patch.object(comandos_clips.diagnostico, "crear_hilo",
                              HiloInmediato),
            mock.patch.object(comandos_clips.wx, "CallAfter",
                              side_effect=_llamada_inmediata),
            mock.patch.object(comandos_clips, "anunciar", anunciar),
            mock.patch.object(comandos_clips.sound_player,
                              "reproducir", sonar),
        ])
        for aplicado in parches:
            aplicado.start()
            self.addCleanup(aplicado.stop)
        comandos_clips.guardar_clip(SimpleNamespace())
        return gestor, funciones, anunciar, sonar

    def test_desactivados_avisa_y_no_consulta_obs(self):
        gestor, parche, anunciar, sonar = self._correr(segundos=0)
        anunciar.assert_called_once_with(
            _("Los clips están desactivados en Preferencias."))
        sonar.assert_called_once_with("error")
        parche["leer_estado"].assert_not_called()
        self.assertTrue(gestor.cerrado)

    def test_perfil_sin_bufer_avisa_y_no_lo_intenta(self):
        gestor, parche, anunciar, sonar = self._correr(
            estado_leido=estado(soportado=False))
        anunciar.assert_called_once_with(
            _("OBS no ofrece clips con la calidad de grabación de este perfil."))
        sonar.assert_called_once_with("error")
        parche["preparar"].assert_not_called()
        parche["guardar"].assert_not_called()
        self.assertTrue(gestor.cerrado)

    def test_con_el_bufer_en_marcha_guarda_el_clip(self):
        gestor, parche, anunciar, sonar = self._correr(
            estado_leido=estado(buffer=True, preparado=True),
            ruta="C:/Videos/clips/clip 1.mkv")
        parche["guardar"].assert_called_once()
        anunciar.assert_called_once_with("Clip guardado: clip 1.mkv.")
        sonar.assert_called_once_with("clip")
        self.assertTrue(gestor.cerrado)

    def test_sin_salida_activa_prepara_y_avisa(self):
        gestor, parche, anunciar, sonar = self._correr(
            estado_leido=estado(salida=False, preparado=False))
        parche["preparar"].assert_called_once_with(
            gestor._cliente, 30)
        anunciar.assert_called_once_with(
            "Clips listos: desde ahora se guardan los últimos 30 segundos.")
        sonar.assert_called_once_with("clip")
        self.assertTrue(gestor.cerrado)

    def test_con_el_perfil_preparado_solo_lo_pone_en_marcha(self):
        gestor, parche, anunciar, sonar = self._correr(
            estado_leido=estado(salida=True, preparado=True))
        parche["iniciar"].assert_called_once_with(gestor._cliente)
        parche["preparar"].assert_not_called()
        anunciar.assert_called_once_with(
            "Clips listos: desde ahora se guardan los últimos 30 segundos.")
        sonar.assert_called_once_with("clip")

    def test_con_salida_activa_y_sin_preparar_rechaza(self):
        gestor, parche, anunciar, sonar = self._correr(
            estado_leido=estado(salida=True, preparado=False))
        anunciar.assert_called_once_with(
            "Los clips se preparan antes de transmitir o grabar. Detén el "
            "directo y la grabación y vuelve a intentarlo.")
        sonar.assert_called_once_with("error")
        parche["preparar"].assert_not_called()
        parche["iniciar"].assert_not_called()
        parche["guardar"].assert_not_called()

    def test_sin_obs_avisa_su_mensaje_y_cierra(self):
        error = obs_cliente.ObsError("No se pudo conectar con OBS.")
        gestor = GestorClipsFalso(fallo=error)
        gestor, parche, anunciar, sonar = self._correr(gestor=gestor)
        anunciar.assert_called_once_with(
            obs_cliente.mensaje_de_fallo_obs(error))
        sonar.assert_called_once_with("error")
        self.assertTrue(gestor.cerrado)

    def test_la_interfaz_no_espera_a_obs(self):
        gestor = GestorClipsFalso()
        hilos = []

        class HiloSinArrancar:
            def __init__(self, target, nombre, **kwargs):
                self.target = target
                self.nombre = nombre
                hilos.append(self)

            def start(self):
                pass

        with mock.patch.object(comandos_clips, "GestorPanelObs",
                               return_value=gestor), \
                mock.patch.object(comandos_clips.diagnostico, "crear_hilo",
                                  HiloSinArrancar):
            comandos_clips.guardar_clip(SimpleNamespace())
        self.assertEqual([hilo.nombre for hilo in hilos], ["ClipsObs"])
        self.assertEqual(gestor.llamadas, [])


if __name__ == "__main__":
    unittest.main()
