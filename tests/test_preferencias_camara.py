"""Pruebas de la página Cámara de Preferencias.

Abren ventanas.
"""

import unittest
from unittest import mock

from bellbird.obs import obs_disposicion
from bellbird.ui import agregar_camara
from bellbird.ui import gui_preferencias
from bellbird.ui import preferencias_camara
from bellbird.voice import motores
from tests.rutas_temporales import redirigir_rutas
from tests.ventanas_prueba import app_de_prueba, destruir
from pathlib import Path


class HiloInmediato:
    """Corre el trabajo en el acto, para no esperar hilos en la prueba."""

    def __init__(self, target, *args):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _crear_hilo_inmediato(target, nombre, *, args=(), daemon=True):
    return HiloInmediato(target, *args)


class TestPaginaCamara(unittest.TestCase):
    # Con ventana: los controles necesitan un padre real.

    def setUp(self):
        self.app = app_de_prueba()
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

    def _pulsar_agregar_camara(self, dialogo):
        boton = dialogo.pagina_camara.btn_agregar_camara
        boton.GetEventHandler().ProcessEvent(
            preferencias_camara.wx.CommandEvent(
                preferencias_camara.wx.EVT_BUTTON.typeId, boton.GetId()))

    def test_la_lista_de_sonido_tiene_su_nombre_y_sus_opciones(self):
        dialogo = self._dialogo({})
        lista = dialogo.pagina_camara.cho_sonido_guia
        self.assertEqual(lista.GetName(), "Sonido de la guía")
        self.assertEqual(lista.GetStrings(), ["Normal", "Cálido", "8 bits"])
        self.assertEqual(lista.GetSelection(), 0)

    def test_la_lista_conserva_el_timbre_guardado(self):
        dialogo = self._dialogo({"guia_timbre": "calido"})
        self.assertEqual(
            dialogo.pagina_camara.cho_sonido_guia.GetStringSelection(),
            "Cálido")

    def test_un_timbre_desconocido_muestra_normal(self):
        dialogo = self._dialogo({"guia_timbre": "raro"})
        self.assertEqual(
            dialogo.pagina_camara.cho_sonido_guia.GetSelection(), 0)

    def test_guardar_el_timbre_lo_deja_en_transmision(self):
        dialogo = self._dialogo({})
        dialogo.pagina_camara.cho_sonido_guia.SetSelection(2)
        cambios = {}
        dialogo.pagina_camara.guardar(
            lambda s, k, v: cambios.setdefault((s, k), v), dialogo._config)
        self.assertEqual(cambios[("transmision", "guia_timbre")], "8bits")
        self.assertEqual(dialogo._config["guia_timbre"], "8bits")

    def test_al_cambiar_la_eleccion_suena_la_muestra_elegida(self):
        dialogo = self._dialogo({})
        lista = dialogo.pagina_camara.cho_sonido_guia
        lista.SetSelection(1)
        with mock.patch.object(preferencias_camara.tono_guia, "muestra",
                               return_value=b"muestra") as muestra,                 mock.patch.object(preferencias_camara.sonido_memoria,
                                  "reproducir") as reproducir:
            lista.GetEventHandler().ProcessEvent(
                preferencias_camara.wx.CommandEvent(
                    preferencias_camara.wx.EVT_CHOICE.typeId, lista.GetId()))
        muestra.assert_called_once_with("calido")
        reproducir.assert_called_once_with(b"muestra")

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

    def test_el_boton_de_agregar_camara_tiene_su_nombre_y_su_lugar(self):
        dialogo = self._dialogo({})
        boton = dialogo.pagina_camara.btn_agregar_camara
        self.assertEqual(boton.GetLabel(), "&Agregar cámara a OBS…")
        self.assertEqual(boton.GetName(), "Agregar cámara a OBS…")
        hijos = list(boton.GetParent().GetChildren())
        self.assertLess(hijos.index(dialogo.pagina_camara.btn_buscar_camaras),
                        hijos.index(boton))

    def test_con_una_camara_la_agrega_y_anuncia_donde_quedo(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        with mock.patch.object(agregar_camara.diagnostico, "crear_hilo",
                               side_effect=_crear_hilo_inmediato), \
                mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara, "_escena_al_aire",
                                  return_value="Escena"), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "camaras_disponibles",
                                  return_value=(("EasyCamera", "abc"),)), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "agregar", return_value=("Cámara", True)), \
                mock.patch.object(agregar_camara.obs_panel,
                                  "GestorPanelObs"), \
                mock.patch.object(agregar_camara.obs_disposicion,
                                  "describir_fuente",
                                  return_value="Cámara. Se ve completa."), \
                mock.patch.object(agregar_camara.obs_camara,
                                  "fuentes_video", return_value=("Cámara",)), \
                mock.patch.object(agregar_camara.wx,
                                  "SingleChoiceDialog") as cuadro, \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            self._pulsar_agregar_camara(dialogo)
        cuadro.assert_not_called()
        anunciar.assert_called_once_with(
            "Se agregó Cámara a la escena Escena. Quedó abajo a la derecha, "
            "delante de las demás fuentes. Cámara. Se ve completa. "
            "Para moverla, usa la pestaña Fuentes de la ventana Escena.")
        self.assertIn("Cámara",
                      dialogo.pagina_camara.cho_camara_obs.GetStrings())

    def test_sin_tamano_anuncia_la_frase_fija_y_no_se_ve_completa(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        gestor = mock.Mock()
        gestor.instantanea.return_value = obs_disposicion.SnapshotPanel(
            conectado=True)
        with mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                               return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara, "_escena_al_aire",
                                  return_value="Escena"), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "agregar", return_value=("Cámara", True)), \
                mock.patch.object(agregar_camara.obs_panel,
                                  "GestorPanelObs", return_value=gestor), \
                mock.patch.object(agregar_camara.obs_camara,
                                  "fuentes_video", return_value=("Cámara",)), \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            agregar_camara._agregar_camara_en_obs(
                dialogo, dialogo.pagina_camara._llenar_camaras, "abc")
        anunciar.assert_called_once_with(
            "Se agregó Cámara a la escena Escena. Quedó abajo a la derecha, "
            "delante de las demás fuentes. Para moverla, usa la pestaña "
            "Fuentes de la ventana Escena.")
        self.assertNotIn("Se ve completa", anunciar.call_args.args[0])

    def test_con_tamano_anuncia_la_frase_fija_y_la_descripcion(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        gestor = mock.Mock()
        gestor.instantanea.return_value = obs_disposicion.SnapshotPanel(
            conectado=True, ancho=540, alto=303, lienzo_ancho=1080,
            lienzo_alto=1920)
        with mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                               return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara, "_escena_al_aire",
                                  return_value="Escena"), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "agregar", return_value=("Cámara", True)), \
                mock.patch.object(agregar_camara.obs_panel,
                                  "GestorPanelObs", return_value=gestor), \
                mock.patch.object(agregar_camara.obs_disposicion,
                                  "describir_fuente",
                                  return_value="Cámara. Abajo a la derecha."), \
                mock.patch.object(agregar_camara.obs_camara,
                                  "fuentes_video", return_value=("Cámara",)), \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            agregar_camara._agregar_camara_en_obs(
                dialogo, dialogo.pagina_camara._llenar_camaras, "abc")
        anunciar.assert_called_once_with(
            "Se agregó Cámara a la escena Escena. Quedó abajo a la derecha, "
            "delante de las demás fuentes. Cámara. Abajo a la derecha. "
            "Para moverla, usa la pestaña Fuentes de la ventana Escena.")

    def test_sin_camaras_de_windows_anuncia_que_no_hay(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        with mock.patch.object(agregar_camara.diagnostico, "crear_hilo",
                               side_effect=_crear_hilo_inmediato), \
                mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara, "_escena_al_aire",
                                  return_value="Escena"), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "camaras_disponibles", return_value=()), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "agregar") as agregar, \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            self._pulsar_agregar_camara(dialogo)
        anunciar.assert_called_once_with(
            "Windows no tiene ninguna cámara disponible para OBS.")
        agregar.assert_not_called()

    def test_un_fallo_de_obs_anuncia_su_mensaje(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        cliente.conectar.side_effect = RuntimeError("sin OBS")
        with mock.patch.object(agregar_camara.diagnostico, "crear_hilo",
                               side_effect=_crear_hilo_inmediato), \
                mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "mensaje_de_fallo_obs",
                                  return_value="Fallo de OBS."), \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            self._pulsar_agregar_camara(dialogo)
        anunciar.assert_called_once_with("Fallo de OBS.")

    def test_la_lista_suma_la_camara_sin_cambiar_lo_elegido(self):
        dialogo = self._dialogo({"camara_fuente": "Vieja"})
        with mock.patch.object(agregar_camara, "anunciar") as anunciar:
            agregar_camara._camara_agregada(
                dialogo, dialogo.pagina_camara._llenar_camaras,
                "Cámara", "Escena", "Cámara. Se ve completa.",
                ("Vieja", "Cámara"))
        lista = dialogo.pagina_camara.cho_camara_obs
        self.assertEqual(lista.GetStrings(),
                         ["Elegir automáticamente", "Vieja", "Cámara"])
        self.assertEqual(lista.GetStringSelection(), "Vieja")
        self.assertEqual(anunciar.call_count, 1)

    def test_una_camara_que_ya_esta_solo_anuncia_su_nombre(self):
        dialogo = self._dialogo({})
        cliente = mock.Mock()
        with mock.patch.object(agregar_camara.obs_cliente, "ClienteObs",
                               return_value=cliente), \
                mock.patch.object(agregar_camara.obs_cliente,
                                  "leer_ajustes"), \
                mock.patch.object(agregar_camara, "_escena_al_aire",
                                  return_value="Escena"), \
                mock.patch.object(agregar_camara.obs_camara_nueva,
                                  "agregar", return_value=("Mi cámara", False)), \
                mock.patch.object(agregar_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            agregar_camara._agregar_camara_en_obs(
                dialogo, dialogo.pagina_camara._llenar_camaras, "abc")
        anunciar.assert_called_once_with(
            "Esa cámara ya está en OBS como Mi cámara.")

    def test_con_varias_camaras_pregunta_con_titulo_y_nombres(self):
        dialogo = self._dialogo({})
        cuadro = mock.Mock()
        cuadro.ShowModal.return_value = agregar_camara.wx.ID_OK
        cuadro.GetSelection.return_value = 1
        al_agregar = dialogo.pagina_camara._llenar_camaras
        with mock.patch.object(agregar_camara.wx,
                               "SingleChoiceDialog",
                               return_value=cuadro) as clase, \
                mock.patch.object(agregar_camara,
                                  "_agregar_en_hilo") as agregar:
            agregar_camara._preguntar_camara(
                dialogo, al_agregar,
                (("Primera", "a"), ("Segunda", "b")))
        clase.assert_called_once_with(
            dialogo, "Cámaras de Windows:", "Elegir cámara",
            ["Primera", "Segunda"])
        agregar.assert_called_once_with(dialogo, al_agregar, "b")
        cuadro.Destroy.assert_called_once_with()

    def test_agregado_ignora_el_dialogo_destruido(self):
        dialogo = self._dialogo({})
        with mock.patch.object(gui_preferencias.PreferenciasDialog, "__bool__",
                               lambda self: False, create=True), \
                mock.patch.object(agregar_camara, "anunciar") as anunciar:
            agregar_camara._camara_agregada(
                dialogo, dialogo.pagina_camara._llenar_camaras,
                "Cámara", "Escena", "Cámara. Se ve completa.", ("Cámara",))
        anunciar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
