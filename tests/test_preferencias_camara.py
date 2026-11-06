"""Pruebas de la página Cámara de Preferencias.

Abren ventanas.
"""

import unittest
from unittest import mock

from guyrapu.obs import obs_disposicion
from guyrapu.ui import agregar_camara
from guyrapu.ui import gui_preferencias
from guyrapu.ui import preferencias_camara
from guyrapu.voice import motores
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
        agregar_camara.agregar(dialogo, dialogo.pagina_camara._llenar_camaras)

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

    def test_los_atajos_globales_estan_apagados_de_fabrica(self):
        dialogo = self._dialogo({})
        casilla = dialogo.pagina_camara.chk_camara_atajos_globales
        self.assertEqual(casilla.GetName(), "CamaraAtajosGlobales")
        self.assertFalse(casilla.GetValue())

    def test_los_atajos_globales_quedan_al_final_de_la_pagina(self):
        dialogo = self._dialogo({})
        pagina = dialogo.nb.GetPage(
            self._indice_categoria(dialogo, "Cámara"))
        hijos = [h for h in pagina.GetChildren() if h.IsShown()]
        self.assertIs(hijos[-1],
                      dialogo.pagina_camara.chk_camara_atajos_globales)

    def test_la_casilla_muestra_el_valor_guardado(self):
        dialogo = self._dialogo({"camara_atajos_globales": True})
        self.assertTrue(
            dialogo.pagina_camara.chk_camara_atajos_globales.GetValue())

    def test_guardar_deja_la_preferencia_en_transmision(self):
        dialogo = self._dialogo({})
        dialogo.pagina_camara.chk_camara_atajos_globales.SetValue(True)
        cambios = {}
        dialogo.pagina_camara.guardar(
            lambda s, k, v: cambios.setdefault((s, k), v), dialogo._config)
        self.assertEqual(
            cambios[("transmision", "camara_atajos_globales")], "true")
        self.assertIs(
            dialogo._config["camara_atajos_globales"], True)

    def _indice_categoria(self, dialogo, nombre):
        for i in range(dialogo.nb.GetPageCount()):
            if dialogo.nb.GetPageText(i) == nombre:
                return i
        raise AssertionError(f"no está la categoría {nombre}")

    def test_construir_el_dialogo_no_consulta_obs(self):
        with mock.patch.object(preferencias_camara.diagnostico,
                               "crear_hilo") as hilo:
            self._dialogo({})
        hilo.assert_not_called()

    def test_elegir_camara_consulta_obs_una_sola_vez(self):
        dialogo = self._dialogo({"camara_fuente": "Vieja"})
        llamadas = []

        def crear_hilo(target, nombre):
            llamadas.append(nombre)
            return HiloInmediato(target)

        cliente = mock.Mock()
        with (
                mock.patch.object(preferencias_camara.diagnostico, "crear_hilo",
                                  side_effect=crear_hilo),
                mock.patch.object(preferencias_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente),
                mock.patch.object(preferencias_camara.obs_cliente,
                                  "leer_ajustes"),
                mock.patch.object(preferencias_camara.obs_camara,
                                  "fuentes_video", return_value=("Cam",)),
                mock.patch("guyrapu.ui.accesibilidad.anunciar") as anunciar,
                mock.patch.object(preferencias_camara.wx, "CallAfter",
                                  side_effect=lambda funcion, *args:
                                  funcion(*args)),
        ):
            camara = self._indice_categoria(dialogo, "Cámara")
            general = self._indice_categoria(dialogo, "General")
            dialogo.nb.SetSelection(camara)
            dialogo.nb.SetSelection(general)
            dialogo.nb.SetSelection(camara)

        self.assertEqual(llamadas, ["CamarasPrefs"])
        anunciar.assert_not_called()
        lista = dialogo.pagina_camara.cho_camara_obs
        self.assertIn("Cam", lista.GetStrings())
        self.assertEqual(lista.GetStringSelection(), "Vieja")

    def test_un_fallo_de_obs_no_anuncia_y_conserva_la_camara(self):
        dialogo = self._dialogo({"camara_fuente": "Vieja"})
        cliente = mock.Mock()
        cliente.conectar.side_effect = RuntimeError("sin OBS")
        with (
                mock.patch.object(preferencias_camara.diagnostico, "crear_hilo",
                                  side_effect=_crear_hilo_inmediato),
                mock.patch.object(preferencias_camara.obs_cliente, "ClienteObs",
                                  return_value=cliente),
                mock.patch.object(preferencias_camara.obs_cliente,
                                  "leer_ajustes"),
                mock.patch("guyrapu.ui.accesibilidad.anunciar") as anunciar,
                mock.patch.object(preferencias_camara.wx, "CallAfter") as diferido,
        ):
            dialogo.nb.SetSelection(self._indice_categoria(dialogo, "Cámara"))

        anunciar.assert_not_called()
        diferido.assert_not_called()
        lista = dialogo.pagina_camara.cho_camara_obs
        self.assertEqual(lista.GetStrings(),
                         ["Elegir automáticamente", "Vieja"])
        self.assertEqual(lista.GetStringSelection(), "Vieja")

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
            "Para moverla, usa Posición y tamaño, en la pestaña Escena "
            "del Panel de OBS.")
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
            "delante de las demás fuentes. Para moverla, usa Posición y "
            "tamaño, en la pestaña Escena del Panel de OBS.")
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
            "Para moverla, usa Posición y tamaño, en la pestaña Escena "
            "del Panel de OBS.")

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
