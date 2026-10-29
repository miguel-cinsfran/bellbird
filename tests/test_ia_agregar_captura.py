"""Pruebas de la subventana para agregar una captura de OBS.

Con ventana: las corre el dueño. No correr aquí, abren diálogos.
"""

import base64
import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.ui import ia_agregar_captura as agregar
from bellbird.obs import obs_captura_ia
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


_IMAGEN_FALSA = base64.b64encode(b"falso-jpeg-para-la-doble").decode("ascii")


class ClienteDoble:
    """Contesta lo justo para que `opciones` arme escena y una fuente."""

    def pedir(self, tipo, datos=None, parada=None):
        if tipo == "GetCurrentProgramScene":
            return {"responseData": {"currentProgramSceneName": "Escena"}}
        if tipo == "GetVideoSettings":
            return {"responseData": {"baseWidth": 1280, "baseHeight": 720}}
        if tipo == "GetSceneItemList":
            return {"responseData": {"sceneItems": [{
                "sourceName": "Cámara",
                "sceneItemEnabled": True,
                "sceneItemTransform": {"sourceWidth": 640,
                                      "sourceHeight": 360},
                "sceneItemIndex": 1}]}}
        if tipo == "GetInputList":
            return {"responseData": {"inputs": [{
                "inputName": "Cámara", "inputKind": "v4l2_input"}]}}
        if tipo == "GetSourceScreenshot":
            return {"responseData": {"imageData": _IMAGEN_FALSA}}
        raise AssertionError(tipo)


def _hilo_directo(target, nombre, **kwargs):
    target()
    hilo = mock.Mock()
    hilo.start.return_value = None
    return hilo


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoAgregarCapturaVentana(unittest.TestCase):
    # Con ventana: las corre el dueño. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)
        parche_hilo = mock.patch.object(
            agregar.diagnostico, "crear_hilo", side_effect=_hilo_directo)
        parche_hilo.start()
        self.addCleanup(parche_hilo.stop)
        parche_llamada = mock.patch.object(
            agregar.wx, "CallAfter",
            side_effect=lambda funcion, *args, **kwargs: funcion(*args,
                                                                **kwargs))
        parche_llamada.start()
        self.addCleanup(parche_llamada.stop)

    def _dialogo(self, cliente=None):
        dialogo = agregar.DialogoAgregarCaptura(None, cliente or ClienteDoble())
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_nombres_accesibles(self):
        dialogo = self._dialogo()
        self.assertEqual(dialogo.GetName(), "DialogoAgregarCaptura")
        self.assertEqual(dialogo.cho_fuente.GetName(), "Capturar de")
        self.assertEqual(dialogo.btn_capturar.GetName(), "Capturar")
        self.assertEqual(dialogo.btn_cancelar.GetName(), "Cancelar")
        self.assertEqual(dialogo.bmp_vista.GetName(), "Vista previa")

    def test_orden_de_tab(self):
        dialogo = self._dialogo()
        navegables = [hijo.GetName() for hijo in dialogo.GetChildren()
                      if isinstance(hijo, (wx.Choice, wx.Button))]
        self.assertEqual(navegables, ["Capturar de", "Capturar", "Cancelar"])
        hijos = list(dialogo.GetChildren())
        self.assertLess(hijos.index(dialogo.cho_fuente),
                        hijos.index(dialogo.bmp_vista))
        self.assertLess(hijos.index(dialogo.bmp_vista),
                        hijos.index(dialogo.btn_capturar))

    def test_mnemonicos_sin_repetir(self):
        dialogo = self._dialogo()
        letras = set()
        for rotulo in (dialogo.rotulo_fuente.GetLabel(),
                       dialogo.btn_capturar.GetLabel(),
                       dialogo.btn_cancelar.GetLabel()):
            posicion = rotulo.find("&")
            self.assertNotEqual(posicion, -1, f"Sin tecla en {rotulo!r}.")
            self.assertLess(posicion + 1, len(rotulo))
            letras.add(rotulo[posicion + 1].lower())
        self.assertEqual(letras, {"c", "r", "n"})

    def test_foco_inicial_y_primera_opcion_elegida(self):
        dialogo = self._dialogo()
        self.assertIs(dialogo.FindFocus(), dialogo.cho_fuente)
        self.assertEqual(dialogo.cho_fuente.GetSelection(), 0)
        self.assertEqual(dialogo.cho_fuente.GetStringSelection(),
                         "Escena al aire: Escena")
        self.assertEqual(dialogo._opciones[0].fuente, "Escena")
        self.assertTrue(dialogo.btn_capturar.IsEnabled())

    def test_negra_no_cierra_anuncia_y_vuelve(self):
        dialogo = self._dialogo()
        opcion = dialogo._opcion_elegida()
        captura = obs_captura_ia.Captura(b"x", 320, 180, True, "sin_elegir",
                                         "Cámara")
        with mock.patch.object(dialogo, "EndModal") as fin, \
                mock.patch.object(agregar, "anunciar") as anunciar, \
                mock.patch.object(agregar, "reproducir") as sonar, \
                mock.patch.object(agregar.obs_captura_ia, "capturar",
                                  return_value=captura):
            dialogo._al_capturar(mock.Mock())
        fin.assert_not_called()
        anunciar.assert_called_once_with(
            agregar.texto_negra(opcion.etiqueta, "sin_elegir", "Cámara"))
        sonar.assert_called_once_with("ia_imagen_negra")
        self.assertIsNone(dialogo.resultado)
        self.assertTrue(dialogo.btn_capturar.IsEnabled())
        self.assertIs(dialogo.FindFocus(), dialogo.cho_fuente)

    def test_buena_cierra_con_ok_y_guarda_la_fuente(self):
        dialogo = self._dialogo()
        opcion = dialogo._opcion_elegida()
        captura = obs_captura_ia.Captura(b"x", 320, 180, False)
        with mock.patch.object(dialogo, "EndModal") as fin, \
                mock.patch.object(agregar.obs_captura_ia, "capturar",
                                  return_value=captura):
            dialogo._al_capturar(mock.Mock())
        fin.assert_called_once_with(wx.ID_OK)
        self.assertEqual(dialogo.resultado, (opcion.fuente, captura))

    def test_fallo_de_captura_anuncia_y_no_cierra(self):
        dialogo = self._dialogo()
        mensaje = "No se pudo capturar Cámara. Comprueba que esté visible."
        with mock.patch.object(dialogo, "EndModal") as fin, \
                mock.patch.object(agregar, "anunciar") as anunciar, \
                mock.patch.object(agregar, "reproducir") as sonar, \
                mock.patch.object(
                    agregar.obs_captura_ia, "capturar",
                    side_effect=obs_captura_ia.CapturaFallida(mensaje)):
            dialogo._al_capturar(mock.Mock())
        fin.assert_not_called()
        anunciar.assert_called_once_with(mensaje)
        sonar.assert_called_once_with("ia_error")
        self.assertIsNone(dialogo.resultado)
        self.assertTrue(dialogo.btn_capturar.IsEnabled())
        self.assertIs(dialogo.FindFocus(), dialogo.cho_fuente)

    def test_vista_que_falla_deja_vacio_y_no_anuncia(self):
        dialogo = self._dialogo()
        with mock.patch.object(agregar, "anunciar") as anunciar, \
                mock.patch.object(
                    agregar.obs_captura_ia, "vista_previa",
                    side_effect=obs_captura_ia.CapturaFallida("sin luz")):
            dialogo._al_temporizador(mock.Mock())
        anunciar.assert_not_called()
        self.assertFalse(dialogo.bmp_vista.GetBitmap().IsOk())

    # Lo arma bellbird/obs/obs_captura_ia.py: el nombre de la fuente tal
    # cual lo da OBS es dato del usuario y pasa sin marcar. La etiqueta de
    # la escena al aire ya sale marcada porque ese módulo la traduce.
    PENDIENTES_OTRO_MODULO = (
        "Cámara",
    )

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo()
            sin_marcar = textos_sin_marcar(dialogo)

        self.assertEqual(sorted(sin_marcar),
                         sorted(self.PENDIENTES_OTRO_MODULO))

    def test_pseudo_sin_obs_avisa_marcado(self):
        with con_pseudo(), \
                mock.patch.object(agregar.obs_activacion,
                                   "obs_esta_en_ejecucion",
                                   return_value=False), \
                mock.patch.object(agregar, "anunciar") as anunciar, \
                mock.patch.object(agregar, "reproducir"):
            terminado = mock.Mock()
            agregar.pedir_captura(mock.Mock(), terminado)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])
        terminado.assert_called_once_with(None)

    def test_pseudo_negra_anuncia_marcado(self):
        dialogo = self._dialogo()
        opcion = dialogo._opcion_elegida()
        captura = obs_captura_ia.Captura(b"x", 320, 180, True, "sin_elegir",
                                         "Cámara")
        with con_pseudo(), \
                mock.patch.object(agregar, "anunciar") as anunciar, \
                mock.patch.object(agregar, "reproducir"):
            dialogo._captura_lista(opcion, captura)
        args, _kwargs = anunciar.call_args
        self.assertTrue(args[0].startswith("[¡"), args[0])

    def test_escape_cierra_con_cancel(self):
        dialogo = self._dialogo()
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_tecla(evento)
        fin.assert_called_once_with(wx.ID_CANCEL)

    def test_cancelar_cierra_y_no_toca_despues(self):
        dialogo = self._dialogo()
        antes = dialogo.cho_fuente.GetStringSelection()
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo.btn_cancelar.GetEventHandler().ProcessEvent(
                wx.CommandEvent(wx.EVT_BUTTON.typeId,
                                dialogo.btn_cancelar.GetId()))
        fin.assert_called_once_with(wx.ID_CANCEL)
        self.assertTrue(dialogo._cerrado)
        dialogo._opciones_listas([obs_captura_ia.OpcionCaptura(
            "Otra", "Otra", 640, 360)])
        self.assertEqual(dialogo.cho_fuente.GetStringSelection(), antes)


if __name__ == "__main__":
    unittest.main()
