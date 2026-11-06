"""Pruebas de los atajos de cámara y del comando de mostrar u ocultar.

Todo sin ventanas: el marco es un doble que anota los atajos registrados y
`wx.CallAfter` corre en el acto.
"""

import unittest
from unittest import mock

import wx

from guyrapu.core.atajos import Atajo
from guyrapu.obs.obs_camara import CamaraNoEncontrada
from guyrapu.ui import camara_atajos


class _HiloInmediato:
    def __init__(self, target):
        self._target = target

    def start(self):
        self._target()


def _crear_hilo_inmediato(target, nombre, **kwargs):
    return _HiloInmediato(target)


class MarcoFalso:
    """Marco y ventana de wx a la vez: anota los atajos del sistema."""

    def __init__(self, config=None, atajos=None):
        self._config = dict(config or {})
        self._atajos = dict(atajos or {})
        self.registrados = {}
        self.fallan_vk = set()
        self.manejadores = {}

    def RegisterHotKey(self, ident, mods, vk):
        if vk in self.fallan_vk:
            return False
        self.registrados[ident] = (mods, vk)
        return True

    def UnregisterHotKey(self, ident):
        self.registrados.pop(ident, None)
        return True

    def Bind(self, evento, manejador, id=-1):
        self.manejadores[id] = manejador

    def Unbind(self, evento, id=-1):
        self.manejadores.pop(id, None)


def _atajos(usuario=False):
    return {
        "anunciar_encuadre": Atajo("anunciar_encuadre",
                                   "ctrl+f5" if usuario else "ctrl+f3",
                                   "f5" if usuario else "f3"),
        "avisos_encuadre": Atajo("avisos_encuadre",
                                 "ctrl+shift+f5" if usuario else "ctrl+shift+f3",
                                 "f5" if usuario else "f3"),
        "camara_visible": Atajo("camara_visible",
                                "alt+f5" if usuario else "alt+f3",
                                "f5" if usuario else "f3"),
    }


class TestRegistroDeAtajos(unittest.TestCase):

    def _crear(self, marco):
        with mock.patch.object(camara_atajos.wx, "CallAfter",
                               side_effect=lambda fn, *a: fn(*a)), \
                mock.patch.object(camara_atajos, "anunciar"), \
                mock.patch.object(camara_atajos._snd, "reproducir"):
            return camara_atajos.CamaraAtajos(marco)

    def test_registra_las_tres_acciones_con_los_atajos_del_usuario(self):
        marco = MarcoFalso({"camara_atajos_globales": False},
                           _atajos(usuario=True))
        atajos = camara_atajos.CamaraAtajos(marco)
        marco._config["camara_atajos_globales"] = True
        with mock.patch.object(camara_atajos, "anunciar"), \
                mock.patch.object(camara_atajos._snd, "reproducir"):
            atajos.aplicar_preferencias()
        self.assertEqual(
            set(marco.registrados.values()),
            {(wx.MOD_CONTROL, 0x74),
             (wx.MOD_CONTROL | wx.MOD_SHIFT, 0x74),
             (wx.MOD_ALT, 0x74)})
        self.assertTrue(atajos._globales.activos)

    def test_arranque_callado_sin_fallos(self):
        marco = MarcoFalso({"camara_atajos_globales": True}, _atajos())
        with mock.patch.object(camara_atajos.wx, "CallAfter",
                               side_effect=lambda fn, *a: fn(*a)), \
                mock.patch.object(camara_atajos, "anunciar") as anunciar, \
                mock.patch.object(camara_atajos._snd,
                                  "reproducir") as reproducir:
            camara_atajos.CamaraAtajos(marco)
        anunciar.assert_not_called()
        reproducir.assert_not_called()
        self.assertEqual(len(marco.registrados), 3)

    def test_arranque_con_fallo_avisa_con_el_tono_de_ocupado(self):
        marco = MarcoFalso({"camara_atajos_globales": True}, _atajos())
        marco.fallan_vk = {0x72}
        with mock.patch.object(camara_atajos.wx, "CallAfter",
                               side_effect=lambda fn, *a: fn(*a)), \
                mock.patch.object(camara_atajos, "anunciar") as anunciar, \
                mock.patch.object(camara_atajos._snd,
                                  "reproducir") as reproducir:
            camara_atajos.CamaraAtajos(marco)
        reproducir.assert_called_once_with("atajos_ocupados")
        self.assertIn("No se pudieron usar en cualquier aplicación",
                      anunciar.call_args.args[0])

    def test_activar_desde_preferencias_anuncia(self):
        marco = MarcoFalso({"camara_atajos_globales": False}, _atajos())
        atajos = camara_atajos.CamaraAtajos(marco)
        marco._config["camara_atajos_globales"] = True
        with mock.patch.object(camara_atajos, "anunciar") as anunciar, \
                mock.patch.object(camara_atajos._snd,
                                  "reproducir") as reproducir:
            atajos.aplicar_preferencias()
        anunciar.assert_called_once_with(
            "Atajos de cámara en cualquier aplicación")
        reproducir.assert_not_called()
        self.assertTrue(atajos._globales.activos)

    def test_desactivar_desde_preferencias_anuncia(self):
        marco = MarcoFalso({"camara_atajos_globales": True}, _atajos())
        atajos = self._crear(marco)
        marco._config["camara_atajos_globales"] = False
        with mock.patch.object(camara_atajos, "anunciar") as anunciar, \
                mock.patch.object(camara_atajos._snd,
                                  "reproducir") as reproducir:
            atajos.aplicar_preferencias()
        anunciar.assert_called_once_with(
            "Atajos de cámara solo en Guyrapu")
        reproducir.assert_not_called()
        self.assertFalse(atajos._globales.activos)

    def test_cada_accion_llama_a_su_funcion(self):
        marco = MarcoFalso({"camara_atajos_globales": False}, _atajos())
        atajos = camara_atajos.CamaraAtajos(marco)
        with mock.patch.object(camara_atajos.encuadre_camara,
                               "anunciar_encuadre") as anunciar, \
                mock.patch.object(camara_atajos.encuadre_camara,
                                  "alternar_avisos") as avisos, \
                mock.patch.object(camara_atajos,
                                  "alternar_camara") as alternar:
            acciones = atajos._globales._acciones
            acciones["anunciar_encuadre"]()
            acciones["avisos_encuadre"]()
            acciones["camara_visible"]()
        anunciar.assert_called_once_with(marco)
        avisos.assert_called_once_with(marco)
        alternar.assert_called_once_with(marco)

    def test_un_fallo_al_aplicar_avisa_con_el_tono_de_ocupado(self):
        marco = MarcoFalso({"camara_atajos_globales": False}, _atajos())
        marco.fallan_vk = {0x72}
        atajos = camara_atajos.CamaraAtajos(marco)
        marco._config["camara_atajos_globales"] = True
        with mock.patch.object(camara_atajos, "anunciar") as anunciar, \
                mock.patch.object(camara_atajos._snd,
                                  "reproducir") as reproducir:
            atajos.aplicar_preferencias()
        reproducir.assert_called_once_with("atajos_ocupados")
        self.assertIn("No se pudieron usar en cualquier aplicación",
                      anunciar.call_args.args[0])


class TestAlternarCamara(unittest.TestCase):

    def _marco(self):
        return MarcoFalso({"camara_fuente": "Cam"})

    def _con_obs(self, funcion, **extra):
        parches = {
            "crear_hilo": mock.patch.object(
                camara_atajos.diagnostico, "crear_hilo",
                side_effect=_crear_hilo_inmediato),
            "activacion": mock.patch.object(
                camara_atajos.obs_activacion, "obs_esta_en_ejecucion",
                return_value=True),
            "cliente": mock.patch.object(
                camara_atajos.obs_cliente, "ClienteObs"),
            "ajustes": mock.patch.object(
                camara_atajos.obs_cliente, "leer_ajustes"),
            "olvidar": mock.patch.object(
                camara_atajos.encuadre_camara, "olvidar_camara"),
            "anunciar": mock.patch.object(camara_atajos, "anunciar"),
        }
        parches.update(extra)
        iniciados = []
        for parche in parches.values():
            iniciados.append(parche.start())
            self.addCleanup(parche.stop)
        return iniciados

    def test_con_obs_cerrado_lo_dice_y_no_cambia_nada(self):
        marco = self._marco()
        _hilo, _activacion, _cliente, _ajustes, olvidar, anunciar = \
            self._con_obs(None)
        with mock.patch.object(camara_atajos.obs_activacion,
                               "obs_esta_en_ejecucion",
                               return_value=False):
            camara_atajos.alternar_camara(marco)
        anunciar.assert_called_once_with("OBS no está abierto.")
        olvidar.assert_not_called()

    def _alternar(self, resultado):
        marco = self._marco()
        valores = self._con_obs(None)
        cliente = valores[2].return_value
        with mock.patch.object(camara_atajos.obs_camara, "alternar_camara",
                               return_value=resultado) as alternar:
            camara_atajos.alternar_camara(marco)
        return marco, cliente, alternar, valores

    def test_si_estaba_visible_anuncia_oculta_y_olvida(self):
        marco, cliente, alternar, valores = self._alternar(False)
        _hilo, _activacion, _cli, _ajustes, olvidar, anunciar = valores
        alternar.assert_called_once_with(cliente, "Cam")
        cliente.cerrar.assert_called_once_with()
        anunciar.assert_called_once_with("Cámara oculta")
        olvidar.assert_called_once_with(marco)

    def test_si_estaba_oculta_anuncia_visible_y_olvida(self):
        marco, cliente, alternar, valores = self._alternar(True)
        _hilo, _activacion, _cli, _ajustes, olvidar, anunciar = valores
        alternar.assert_called_once_with(cliente, "Cam")
        cliente.cerrar.assert_called_once_with()
        anunciar.assert_called_once_with("Cámara visible")
        olvidar.assert_called_once_with(marco)

    def test_sin_la_camara_en_la_escena_anuncia_y_no_olvida(self):
        marco = self._marco()
        valores = self._con_obs(None)
        _hilo, _activacion, cliente, _ajustes, olvidar, anunciar = valores
        with mock.patch.object(
                camara_atajos.obs_camara, "alternar_camara",
                side_effect=CamaraNoEncontrada(
                    "La cámara de OBS no está en la escena actual.")):
            camara_atajos.alternar_camara(marco)
        anunciar.assert_called_once_with(
            "La cámara de OBS no está en la escena actual.")
        olvidar.assert_not_called()
        cliente.return_value.cerrar.assert_called_once_with()

    def test_un_fallo_de_obs_anuncia_su_mensaje_y_no_olvida(self):
        marco = self._marco()
        valores = self._con_obs(None)
        _hilo, _activacion, cliente, _ajustes, olvidar, anunciar = valores
        with mock.patch.object(
                camara_atajos.obs_camara, "alternar_camara",
                side_effect=RuntimeError("boom")), \
                mock.patch.object(camara_atajos.obs_cliente,
                                  "mensaje_de_fallo_obs",
                                  return_value="Fallo de OBS."):
            camara_atajos.alternar_camara(marco)
        anunciar.assert_called_once_with("Fallo de OBS.")
        olvidar.assert_not_called()
        cliente.return_value.cerrar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
