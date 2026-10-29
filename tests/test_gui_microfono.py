"""Pruebas del cuadro «Micrófono de OBS».

Las de `abrir_microfono_obs` no tocan OBS de verdad: el cliente y los
hilos van con dobles. Las de `MicrofonoObsDialog` crean el cuadro de
verdad: NO correr en esta máquina (abren ventanas); las corre el dueño.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from ytchat.ui import gui_microfono
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir

FUENTES = ("Mic/Aux", "Audio USB")
PARES = (("Predeterminado", "default"), ("Micrófono (USB)", "{usb}"))

SIN_OBS = "OBS no pudo completar la operación. Inténtalo de nuevo."
AVISO_SIN_MICROFONO = ("OBS no tiene ningún micrófono. Elige uno en "
                       "Preferencias, página Transmisión, Micrófono de OBS.")


def _hilo_sincrono():
    """Los hilos de trabajo corren al llamar a `start`, sin hebras."""
    def crear(target, nombre, *args, **kwargs):
        hilo = mock.Mock()
        hilo.start.side_effect = lambda: target(*args)
        return hilo
    return mock.patch.object(gui_microfono.diagnostico, "crear_hilo",
                             side_effect=crear)


def _llamada_directa():
    """`wx.CallAfter` corre en el momento, sin bucle de eventos."""
    return mock.patch.object(gui_microfono.wx, "CallAfter",
                             side_effect=lambda fn, *a, **k: fn(*a, **k))


def _frame():
    frame = mock.Mock()
    frame._config = {"obs_microfono": "Audio USB"}
    return frame


def _aplicar_en(dialogo, senal=None, fallo=None, silenciada=False):
    """Pulsa Aplicar con OBS falseado y devuelve los dobles para afirmar."""
    cliente = mock.Mock()
    with mock.patch.object(gui_microfono, "_conectar",
                           return_value=cliente), \
            mock.patch.object(gui_microfono.obs_entradas_audio,
                              "cambiar_dispositivo") as cambiar, \
            mock.patch.object(gui_microfono.obs_entradas_audio,
                              "silenciada",
                              return_value=silenciada), \
            mock.patch.object(gui_microfono.obs_entradas_audio,
                              "senal_microfono",
                              return_value=senal), \
            mock.patch.object(gui_microfono, "guardar_opcion") \
            as guardar, \
            mock.patch("ytchat.ui.gui.RUTA_CONFIG", "RUTA"), \
            mock.patch.object(gui_microfono, "anunciar") as anunciar, \
            mock.patch.object(gui_microfono._snd, "reproducir") \
            as reproducir, \
            _hilo_sincrono(), _llamada_directa():
        if fallo is not None:
            cambiar.side_effect = fallo
        evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                 dialogo.btn_aplicar.GetId())
        dialogo.btn_aplicar.GetEventHandler().ProcessEvent(evento)
    return cliente, cambiar, guardar, anunciar, reproducir


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestAbrirMicrofonoObs(unittest.TestCase):

    def _abrir(self, frame, conectar=None, microfonos=None,
               especial="", dispositivos=None):
        cliente = mock.Mock()
        with mock.patch.object(gui_microfono, "_conectar",
                               return_value=cliente) as conectar_mock, \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "microfonos",
                                  return_value=tuple(microfonos or ())), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "microfono_especial",
                                  return_value=especial), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "dispositivos",
                                  return_value=dispositivos or ((), "")), \
                mock.patch.object(gui_microfono, "MicrofonoObsDialog") \
                as dialogo_clase, \
                mock.patch.object(gui_microfono, "anunciar") as anunciar, \
                _hilo_sincrono(), _llamada_directa():
            if conectar is not None:
                conectar_mock.side_effect = conectar
            gui_microfono.abrir_microfono_obs(frame)
        return cliente, dialogo_clase, anunciar

    def test_con_datos_abre_el_cuadro_con_la_fuente_elegida(self):
        frame = _frame()
        cliente, dialogo_clase, anunciar = self._abrir(
            frame, microfonos=FUENTES, especial="Mic/Aux",
            dispositivos=(PARES, "{usb}"))
        dialogo_clase.assert_called_once_with(
            frame, FUENTES, "Audio USB", PARES, "{usb}")
        dialogo = dialogo_clase.return_value
        dialogo.ShowModal.assert_called_once_with()
        dialogo.Destroy.assert_called_once_with()
        frame.SetFocus.assert_called_once_with()
        anunciar.assert_not_called()
        cliente.cerrar.assert_called_once_with()

    def test_sin_obs_no_abre_y_anuncia_el_fallo(self):
        frame = _frame()
        _cliente, dialogo_clase, anunciar = self._abrir(
            frame, conectar=RuntimeError("caído"))
        dialogo_clase.assert_not_called()
        anunciar.assert_called_once_with(SIN_OBS)
        frame.SetFocus.assert_not_called()

    def test_sin_microfonos_no_abre_y_anuncia_el_aviso(self):
        frame = _frame()
        cliente, dialogo_clase, anunciar = self._abrir(
            frame, microfonos=())
        dialogo_clase.assert_not_called()
        anunciar.assert_called_once_with(AVISO_SIN_MICROFONO)
        cliente.cerrar.assert_called_once_with()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestMicrofonoObsDialogVentana(unittest.TestCase):
    # Con ventana: las corre el dueño. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _padre(self):
        padre = wx.Frame(None)
        self.addCleanup(destruir, padre)
        padre._config = {"obs_microfono": "Mic/Aux"}
        return padre

    def _dialogo(self, padre=None, fuentes=FUENTES, fuente="Mic/Aux",
                 pares=PARES, actual="{usb}"):
        dialogo = gui_microfono.MicrofonoObsDialog(
            padre or self._padre(), fuentes, fuente, pares, actual)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_etiquetas_y_nombres_accesibles(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.rotulo_fuente.GetLabel(), "&Fuente de OBS:")
        self.assertEqual(dialogo.cho_fuente.GetName(), "Fuente de OBS")
        self.assertEqual(dialogo.rotulo_dispositivo.GetLabel(),
                         "&Dispositivo:")
        self.assertEqual(dialogo.cho_dispositivo.GetName(), "Dispositivo")

    def test_fuentes_y_dispositivos_con_el_actual_elegido(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.cho_fuente.GetStrings(), list(FUENTES))
        self.assertEqual(dialogo.cho_fuente.GetStringSelection(), "Mic/Aux")
        self.assertEqual(dialogo.cho_dispositivo.GetStrings(),
                         ["Predeterminado", "Micrófono (USB)"])
        self.assertEqual(dialogo.cho_dispositivo.GetStringSelection(),
                         "Micrófono (USB)")

    def test_actual_vacio_selecciona_el_predeterminado(self):
        dialogo = self._dialogo(actual="")
        self.assertEqual(dialogo.cho_dispositivo.GetStringSelection(),
                         "Predeterminado")

    def test_combinados_con_ancho_minimo(self):
        dialogo = self._dialogo()
        for combinado in (dialogo.cho_fuente, dialogo.cho_dispositivo):
            with self.subTest(combinado=combinado.GetName()):
                self.assertGreaterEqual(
                    combinado.GetMinSize().GetWidth(), 320)

    def test_orden_de_tab_foco_y_botones(self):
        dialogo = self._dialogo()
        focos = [hijo for hijo in dialogo.GetChildren()
                 if hijo.AcceptsFocus() and hijo.IsShown()]
        self.assertEqual(
            focos, [dialogo.cho_fuente, dialogo.cho_dispositivo,
                    dialogo.btn_aplicar, dialogo.btn_cerrar])
        self.assertIs(dialogo.FindFocus(), dialogo.cho_dispositivo)
        self.assertEqual(dialogo.btn_aplicar.GetLabel(), "&Aplicar")
        self.assertIs(dialogo.GetDefaultItem(), dialogo.btn_aplicar)
        self.assertEqual(dialogo.btn_cerrar.GetId(), wx.ID_CANCEL)

    def test_letras_de_atajo_distintas(self):
        dialogo = self._dialogo()
        teclas = set()
        for etiqueta in (dialogo.rotulo_fuente.GetLabel(),
                         dialogo.rotulo_dispositivo.GetLabel(),
                         dialogo.btn_aplicar.GetLabel()):
            posicion = etiqueta.find("&")
            self.assertNotEqual(posicion, -1,
                                f"Sin tecla rápida en {etiqueta!r}.")
            self.assertLess(posicion + 1, len(etiqueta))
            teclas.add(etiqueta[posicion + 1].lower())
        self.assertEqual(teclas, {"f", "d", "a"})

    def test_escape_cierra_y_otras_teclas_siguen(self):
        dialogo = self._dialogo()
        with mock.patch.object(dialogo, "EndModal") as fin:
            evento = wx.KeyEvent(wx.EVT_CHAR_HOOK.typeId)
            evento.KeyCode = wx.WXK_ESCAPE
            dialogo.GetEventHandler().ProcessEvent(evento)
        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_boton_cerrar_cierra(self):
        dialogo = self._dialogo()
        with mock.patch.object(dialogo, "EndModal") as fin:
            evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                     dialogo.btn_cerrar.GetId())
            dialogo.btn_cerrar.GetEventHandler().ProcessEvent(evento)
        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_cambiar_fuente_recarga_con_cliente_nuevo(self):
        dialogo = self._dialogo()
        cliente = mock.Mock()
        with mock.patch.object(gui_microfono, "_conectar",
                               return_value=cliente), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "dispositivos",
                                  return_value=(PARES, "default")) \
                as dispositivos, \
                _hilo_sincrono(), _llamada_directa():
            dialogo.cho_fuente.SetStringSelection("Audio USB")
            evento = wx.CommandEvent(wx.EVT_CHOICE.typeId,
                                     dialogo.cho_fuente.GetId())
            dialogo.cho_fuente.GetEventHandler().ProcessEvent(evento)
        dispositivos.assert_called_once_with(cliente, "Audio USB")
        cliente.cerrar.assert_called_once_with()
        self.assertEqual(dialogo.cho_dispositivo.GetStringSelection(),
                         "Predeterminado")
        self.assertTrue(dialogo.cho_dispositivo.IsEnabled())

    def test_cambiar_fuente_deshabilita_mientras_consulta(self):
        dialogo = self._dialogo()
        funciones = []
        with mock.patch.object(gui_microfono, "_conectar"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "dispositivos",
                                  return_value=(PARES, "default")), \
                mock.patch.object(gui_microfono.diagnostico, "crear_hilo",
                                  side_effect=lambda f, n: funciones.append(f)
                                  or mock.Mock()), \
                _llamada_directa():
            dialogo.cho_fuente.SetStringSelection("Audio USB")
            evento = wx.CommandEvent(wx.EVT_CHOICE.typeId,
                                     dialogo.cho_fuente.GetId())
            dialogo.cho_fuente.GetEventHandler().ProcessEvent(evento)
            self.assertFalse(dialogo.cho_dispositivo.IsEnabled())
            funciones[0]()
        self.assertTrue(dialogo.cho_dispositivo.IsEnabled())

    def _aplicar(self, dialogo, senal=None, fallo=None):
        return _aplicar_en(dialogo, senal=senal, fallo=fallo)

    def test_aplicar_cambia_guarda_y_anuncia(self):
        padre = self._padre()
        dialogo = self._dialogo(padre=padre)
        cliente, cambiar, guardar, anunciar, _reproducir = self._aplicar(
            dialogo)
        cambiar.assert_called_once_with(cliente, "Mic/Aux", "{usb}")
        cliente.cerrar.assert_called_once_with()
        guardar.assert_called_once_with("RUTA", "obs", "microfono", "Mic/Aux")
        self.assertEqual(padre._config["obs_microfono"], "Mic/Aux")
        anunciar.assert_called_once_with(
            "Micrófono cambiado: Micrófono (USB).")
        self.assertTrue(dialogo.btn_aplicar.IsEnabled())
        self.assertTrue(bool(dialogo))

    def test_aplicar_deshabilita_el_boton_mientras_trabaja(self):
        dialogo = self._dialogo()
        funciones = []
        with mock.patch.object(gui_microfono, "_conectar"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "cambiar_dispositivo"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "senal_microfono", return_value=None), \
                mock.patch.object(gui_microfono, "guardar_opcion"), \
                mock.patch.object(gui_microfono, "anunciar"), \
                mock.patch.object(gui_microfono._snd, "reproducir"), \
                mock.patch.object(gui_microfono.diagnostico, "crear_hilo",
                                  side_effect=lambda f, n: funciones.append(f)
                                  or mock.Mock()), \
                _llamada_directa():
            evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                     dialogo.btn_aplicar.GetId())
            dialogo.btn_aplicar.GetEventHandler().ProcessEvent(evento)
            self.assertFalse(dialogo.btn_aplicar.IsEnabled())
            funciones[0]()
        self.assertTrue(dialogo.btn_aplicar.IsEnabled())

    def test_sin_senal_suena_antes_de_la_frase(self):
        dialogo = self._dialogo()
        orden = []
        with mock.patch.object(gui_microfono, "_conectar"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "cambiar_dispositivo"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "silenciada", return_value=False), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "senal_microfono", return_value=False), \
                mock.patch.object(gui_microfono, "guardar_opcion"), \
                mock.patch.object(gui_microfono, "anunciar",
                                  side_effect=lambda t: orden.append(
                                      ("anuncio", t))), \
                mock.patch.object(gui_microfono._snd, "reproducir",
                                  side_effect=lambda s: orden.append(
                                      ("sonido", s))), \
                _hilo_sincrono(), _llamada_directa():
            evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                     dialogo.btn_aplicar.GetId())
            dialogo.btn_aplicar.GetEventHandler().ProcessEvent(evento)
        self.assertEqual(
            orden,
            [("anuncio", "Micrófono cambiado: Micrófono (USB)."),
             ("sonido", "microfono_sin_senal"),
             ("anuncio", "El micrófono no recibe sonido. Revisa cuál está "
              "elegido en Windows o en OBS.")])

    def test_con_senal_avisa_que_recibe_sonido(self):
        dialogo = self._dialogo()
        _cliente, _cambiar, _guardar, anunciar, reproducir = self._aplicar(
            dialogo, senal=True)
        self.assertEqual(
            [llamada.args[0] for llamada in anunciar.call_args_list],
            ["Micrófono cambiado: Micrófono (USB).",
             "El micrófono recibe sonido."])
        reproducir.assert_not_called()

    def test_sin_medicion_solo_anuncia_el_cambio(self):
        dialogo = self._dialogo()
        _cliente, _cambiar, _guardar, anunciar, reproducir = self._aplicar(
            dialogo, senal=None)
        anunciar.assert_called_once_with(
            "Micrófono cambiado: Micrófono (USB).")
        reproducir.assert_not_called()

    def test_fallo_al_aplicar_anuncia_y_no_guarda(self):
        dialogo = self._dialogo()
        _cliente, _cambiar, guardar, anunciar, _reproducir = self._aplicar(
            dialogo, fallo=RuntimeError("caído"))
        anunciar.assert_called_once_with(SIN_OBS)
        guardar.assert_not_called()
        self.assertTrue(dialogo.btn_aplicar.IsEnabled())

    def test_sin_dispositivo_avisa_y_no_llama_a_obs(self):
        dialogo = self._dialogo(pares=PARES, actual="{inexistente}")
        self.assertEqual(dialogo.cho_dispositivo.GetSelection(), wx.NOT_FOUND)
        with mock.patch.object(gui_microfono.diagnostico, "crear_hilo") \
                as hilos, \
                mock.patch.object(gui_microfono, "_conectar") as conectar, \
                mock.patch.object(gui_microfono, "anunciar") as anunciar:
            evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                     dialogo.btn_aplicar.GetId())
            dialogo.btn_aplicar.GetEventHandler().ProcessEvent(evento)
        hilos.assert_not_called()
        conectar.assert_not_called()
        anunciar.assert_called_once_with("Elige un dispositivo.")
        self.assertTrue(dialogo.btn_aplicar.IsEnabled())

    def test_silenciado_no_mide_y_avisa_que_esta_silenciado(self):
        dialogo = self._dialogo()
        cliente = mock.Mock()
        with mock.patch.object(gui_microfono, "_conectar",
                               return_value=cliente), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "cambiar_dispositivo") as cambiar, \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "silenciada",
                                  return_value=True), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "senal_microfono") as medicion, \
                mock.patch.object(gui_microfono, "guardar_opcion"), \
                mock.patch("ytchat.ui.gui.RUTA_CONFIG", "RUTA"), \
                mock.patch.object(gui_microfono, "anunciar") as anunciar, \
                mock.patch.object(gui_microfono._snd, "reproducir") \
                as reproducir, \
                _hilo_sincrono(), _llamada_directa():
            evento = wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                     dialogo.btn_aplicar.GetId())
            dialogo.btn_aplicar.GetEventHandler().ProcessEvent(evento)
        cambiar.assert_called_once_with(cliente, "Mic/Aux", "{usb}")
        medicion.assert_not_called()
        self.assertEqual(
            [llamada.args[0] for llamada in anunciar.call_args_list],
            ["Micrófono cambiado: Micrófono (USB).",
             "El micrófono está silenciado en OBS."])
        reproducir.assert_not_called()
        self.assertTrue(dialogo.btn_aplicar.IsEnabled())


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoMicrofonoObs(unittest.TestCase):
    # Pseudotraducción de la ventana: la corre el advisor, abre ventanas.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, **kwargs):
        padre = wx.Frame(None)
        self.addCleanup(destruir, padre)
        padre._config = {"obs_microfono": "Mic/Aux"}
        dialogo = gui_microfono.MicrofonoObsDialog(
            padre, kwargs.get("fuentes", FUENTES),
            kwargs.get("fuente", "Mic/Aux"),
            kwargs.get("pares", PARES), kwargs.get("actual", "{usb}"))
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(
                dialogo, propios=[n for n, _v in PARES] + list(FUENTES))
        self.assertEqual([], sin_marcar)

    def test_anuncios_propios_salen_marcados(self):
        # El clic por evento ya lo prueban las pruebas con ventana: acá
        # solo importa que los anuncios pasen por `_`, así se llama al
        # manejador directamente, como en `test_gui_elegir_destino`.
        dialogo = self._dialogo()
        with con_pseudo(), \
                mock.patch.object(gui_microfono, "_conectar"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "cambiar_dispositivo"), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "silenciada", return_value=False), \
                mock.patch.object(gui_microfono.obs_entradas_audio,
                                  "senal_microfono", return_value=True), \
                mock.patch.object(gui_microfono, "guardar_opcion"), \
                mock.patch.object(gui_microfono, "anunciar") as anunciar, \
                mock.patch.object(gui_microfono._snd, "reproducir"), \
                _hilo_sincrono(), _llamada_directa():
            dialogo._al_aplicar(mock.Mock())
        self.assertEqual(anunciar.call_count, 2)
        for llamada in anunciar.call_args_list:
            self.assertTrue(llamada.args[0].startswith("[¡"),
                            llamada.args[0])

    def test_sin_dispositivo_avisa_marcado(self):
        dialogo = self._dialogo(pares=PARES, actual="{inexistente}")
        with con_pseudo(), \
                mock.patch.object(gui_microfono, "anunciar") as anunciar:
            dialogo._al_aplicar(mock.Mock())
        anunciar.assert_called_once()
        self.assertTrue(anunciar.call_args.args[0].startswith("[¡"),
                        anunciar.call_args.args[0])

    def test_silenciado_avisa_marcado(self):
        with con_pseudo():
            dialogo = self._dialogo()
            _cliente, _cambiar, _guardar, anunciar, _reproducir = \
                _aplicar_en(dialogo, silenciada=True)
        self.assertEqual(anunciar.call_count, 2)
        for llamada in anunciar.call_args_list:
            self.assertTrue(llamada.args[0].startswith("[¡"),
                            llamada.args[0])


if __name__ == "__main__":
    unittest.main()
