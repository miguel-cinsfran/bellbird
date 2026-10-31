"""Pruebas de la página Cámara de Preferencias.

Abren ventanas.
"""

import unittest
from unittest import mock

from bellbird.ui import gui_preferencias
from bellbird.ui import preferencias_camara
from bellbird.voice import motores
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import destruir
from pathlib import Path


class TestPaginaCamara(unittest.TestCase):
    # Con ventana: los controles necesitan un padre real.

    def setUp(self):
        import wx
        self.app = wx.App.Get() or wx.App(False)
        self.ruta = Path.cwd()
        self.parche_ruta = redirigir_rutas(self.ruta)
        self.parche_ruta.__enter__()
        self.addCleanup(self.parche_ruta.__exit__, None, None, None)

    def _dialogo(self, configuracion=None):
        with mock.patch.object(motores, "listar_voces", return_value=["Voz de prueba"]):
            dialogo = gui_preferencias.PreferenciasDialog(
                None, configuracion or {})
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_camara_guardada_se_conserva_sin_consultar_obs(self):
        dialogo = self._dialogo({"camara_fuente": "Cam"})
        self.assertEqual(dialogo.pagina_camara.cho_camara_obs.GetStringSelection(), "Cam")
        self.assertEqual(dialogo.pagina_camara.cho_camara_obs.GetStrings(),
                         ["Elegir automáticamente", "Cam"])

    def test_guardar_con_automatico_deja_fuente_vacia(self):
        dialogo = self._dialogo({"camara_fuente": "Cam"})
        dialogo.pagina_camara.cho_camara_obs.SetSelection(0)
        dialogo.pagina_camara.chk_avisar_encuadre.SetValue(True)
        dialogo.pagina_camara.chk_invertir_camara.SetValue(False)
        cambios = {}
        dialogo.pagina_camara.guardar(
            lambda s, k, v: cambios.setdefault((s, k), v), dialogo._config)
        self.assertEqual(cambios[("transmision", "camara_fuente")], "")
        self.assertEqual(dialogo._config["camara_fuente"], "")

    def test_guardar_con_camara_deja_su_nombre(self):
        dialogo = self._dialogo({})
        dialogo.pagina_camara.cho_camara_obs.Set(
            ["Elegir automáticamente", "Cam"])
        dialogo.pagina_camara.cho_camara_obs.SetSelection(1)
        dialogo.pagina_camara.chk_avisar_encuadre.SetValue(False)
        dialogo.pagina_camara.chk_invertir_camara.SetValue(True)
        cambios = {}
        dialogo.pagina_camara.guardar(
            lambda s, k, v: cambios.setdefault((s, k), v), dialogo._config)
        self.assertEqual(cambios[("transmision", "camara_fuente")], "Cam")
        self.assertEqual(dialogo._config["camara_fuente"], "Cam")
        self.assertEqual(cambios[("transmision", "avisar_encuadre")], "false")
        self.assertEqual(cambios[("transmision", "camara_invertir")], "true")

    def test_sin_camaras_anuncia_que_no_hay_ninguna(self):
        dialogo = self._dialogo({"camara_fuente": "Vieja"})
        with mock.patch.object(preferencias_camara, "anunciar") as anunciar:
            dialogo.pagina_camara._camaras_encontradas(())
        anunciar.assert_called_once_with("No hay ninguna cámara en OBS.")
        self.assertEqual(dialogo.pagina_camara.cho_camara_obs.GetStrings(),
                         ["Elegir automáticamente", "Vieja"])

    def test_una_camara_se_anuncia_en_singular(self):
        dialogo = self._dialogo({})
        with mock.patch.object(preferencias_camara, "anunciar") as anunciar:
            dialogo.pagina_camara._camaras_encontradas(("Cam",))
        anunciar.assert_called_once_with("Se encontró una cámara en OBS.")

    def test_tres_camaras_anuncian_cantidad_y_conservan_la_elegida(self):
        dialogo = self._dialogo({"camara_fuente": "Vieja"})
        with mock.patch.object(preferencias_camara, "anunciar") as anunciar:
            dialogo.pagina_camara._camaras_encontradas(
                ("Nueva", "Vieja", "Otra"))
        anunciar.assert_called_once_with(
            "Se encontraron 3 cámaras en OBS.")
        self.assertEqual(dialogo.pagina_camara.cho_camara_obs.GetStrings(),
                         ["Elegir automáticamente", "Vieja", "Nueva", "Otra"])
        self.assertEqual(
            dialogo.pagina_camara.cho_camara_obs.GetStringSelection(), "Vieja")

    def test_respuesta_ignora_el_dialogo_destruido(self):
        dialogo = self._dialogo({})
        with mock.patch.object(gui_preferencias.PreferenciasDialog, "__bool__",
                               lambda self: False, create=True), \
                mock.patch.object(preferencias_camara, "anunciar") as anunciar:
            dialogo.pagina_camara._camaras_encontradas(("Cam",))
        anunciar.assert_not_called()

    def test_buscar_camaras_lanza_hilo_sin_conectar_al_construir(self):
        dialogo = self._dialogo({})
        hilo = mock.Mock()
        consulta = {}

        def crear_hilo(target, nombre):
            consulta["target"] = target
            consulta["nombre"] = nombre
            return hilo

        cliente = mock.Mock()
        cliente.fuentes_video = mock.Mock(return_value=("Cam",))
        with mock.patch.object(preferencias_camara.diagnostico, "crear_hilo",
                               side_effect=crear_hilo), \
                mock.patch.object(preferencias_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente) as cliente_clase, \
                mock.patch.object(preferencias_camara.obs_cliente, "leer_ajustes"), \
                mock.patch.object(preferencias_camara.obs_camara, "fuentes_video",
                                  return_value=("Cam",)) as fuentes, \
                mock.patch.object(preferencias_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args: funcion(*args)):
            dialogo.pagina_camara._buscar_camaras(None)
            cliente_clase.assert_not_called()
            consulta["target"]()

        self.assertEqual(consulta["nombre"], "CamarasPrefs")
        hilo.start.assert_called_once_with()
        cliente.conectar.assert_called_once_with()
        fuentes.assert_called_once_with(cliente)
        cliente.cerrar.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
