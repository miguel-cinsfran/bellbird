"""Pruebas de la ventanita para elegir el destino al transmitir.

TestDestinoInicial y TestValidarEleccion son lógica pura y se corren
aquí. TestDialogoElegirDestinoVentana crea un wx.Dialog de verdad: NO
correr en esta máquina (abre ventanas); las corre el dueño.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.ui import gui_elegir_destino as elegir
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


class TestDestinoInicial(unittest.TestCase):

    def test_guardado_valido_se_respeta(self):
        self.assertEqual(elegir.destino_inicial("YouTube"), "YouTube")
        self.assertEqual(elegir.destino_inicial("TikTok"), "TikTok")

    def test_sin_guardado_arranca_en_el_primero(self):
        self.assertEqual(elegir.destino_inicial(""), "TikTok")
        self.assertEqual(elegir.destino_inicial("Twitch"), "TikTok")
        self.assertEqual(elegir.destino_inicial(None), "TikTok")


class TestValidarEleccion(unittest.TestCase):

    def test_tiktok_sin_usuario_rechazado(self):
        with self.assertRaises(ValueError) as contexto:
            elegir.validar_eleccion("TikTok", "")
        self.assertEqual(str(contexto.exception),
                         "Falta el usuario de TikTok.")
        with self.assertRaises(ValueError):
            elegir.validar_eleccion("TikTok", "   ")
        with self.assertRaises(ValueError):
            elegir.validar_eleccion("TikTok", "@")

    def test_tiktok_con_usuario_normaliza(self):
        self.assertEqual(elegir.validar_eleccion("TikTok", "@amigo"),
                         ("TikTok", "amigo"))

    def test_youtube_sin_usuario_aceptado(self):
        self.assertEqual(elegir.validar_eleccion("YouTube", ""),
                         ("YouTube", ""))
        self.assertEqual(elegir.validar_eleccion("YouTube", "algo"),
                         ("YouTube", ""))

    def test_destino_invalido_cae_al_primero(self):
        destino, _ = elegir.validar_eleccion("Twitch", "amigo")
        self.assertEqual(destino, "TikTok")


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoElegirDestinoVentana(unittest.TestCase):
    # Con ventana: las corre el dueño. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, **kwargs):
        dialogo = elegir.DialogoElegirDestino(None, **kwargs)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_nombres_accesibles_y_destinos(self):
        dialogo = self._dialogo(destino="YouTube", usuario="amigo")
        self.assertEqual(dialogo.cho_destino.GetStrings(),
                         ["TikTok", "YouTube"])
        self.assertEqual(dialogo.cho_destino.GetName(), "Transmitir a")
        self.assertEqual(dialogo.txt_usuario.GetName(), "Usuario de TikTok")

    def test_destino_guardado_ya_elegido_y_foco_en_lista(self):
        dialogo = self._dialogo(destino="YouTube", usuario="")
        self.assertEqual(dialogo.cho_destino.GetStringSelection(),
                         "YouTube")
        self.assertIs(dialogo.FindFocus(), dialogo.cho_destino)

    def test_sin_guardado_arranca_en_el_primero(self):
        dialogo = self._dialogo(destino="", usuario="")
        self.assertEqual(dialogo.cho_destino.GetStringSelection(),
                         "TikTok")

    def test_usuario_solo_visible_con_tiktok(self):
        dialogo = self._dialogo(destino="TikTok", usuario="amigo")
        self.assertTrue(dialogo.txt_usuario.IsShown())
        dialogo.cho_destino.SetStringSelection("YouTube")
        evento = wx.CommandEvent(wx.EVT_CHOICE.typeId,
                                 dialogo.cho_destino.GetId())
        dialogo.cho_destino.GetEventHandler().ProcessEvent(evento)
        self.assertFalse(dialogo.txt_usuario.IsShown())
        dialogo.cho_destino.SetStringSelection("TikTok")
        dialogo.cho_destino.GetEventHandler().ProcessEvent(
            wx.CommandEvent(wx.EVT_CHOICE.typeId,
                            dialogo.cho_destino.GetId()))
        self.assertTrue(dialogo.txt_usuario.IsShown())

    def test_orden_de_tab_y_botones(self):
        dialogo = self._dialogo(destino="TikTok", usuario="amigo")
        self.assertEqual(dialogo.btn_continuar.GetLabel(), "&Continuar")
        self.assertEqual(dialogo.btn_continuar.GetId(), wx.ID_OK)
        self.assertEqual(dialogo.btn_cancelar.GetLabel(), "C&ancelar")
        self.assertEqual(dialogo.btn_cancelar.GetId(), wx.ID_CANCEL)
        self.assertIs(dialogo.GetDefaultItem(), dialogo.btn_continuar)

    def test_teclas_rapidas_distintas(self):
        dialogo = self._dialogo(destino="TikTok", usuario="amigo")
        teclas = set()
        for boton in (dialogo.btn_continuar, dialogo.btn_cancelar):
            etiqueta = boton.GetLabel()
            posicion = etiqueta.find("&")
            self.assertNotEqual(posicion, -1,
                                f"Sin tecla rápida en {etiqueta!r}.")
            self.assertLess(posicion + 1, len(etiqueta))
            teclas.add(etiqueta[posicion + 1].lower())
        self.assertEqual(len(teclas), 2)

    def test_tiktok_sin_usuario_anuncia_y_enfoca(self):
        dialogo = self._dialogo(destino="TikTok", usuario="")
        dialogo.txt_usuario.SetValue("")
        with mock.patch.object(elegir, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_continuar(mock.Mock())
        anunciar.assert_called_once_with("Falta el usuario de TikTok.")
        fin.assert_not_called()
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_usuario)

    def test_pedir_destino_devuelve_tupla_y_none(self):
        dialogo = self._dialogo(destino="YouTube", usuario="")
        with mock.patch.object(elegir, "DialogoElegirDestino",
                               return_value=dialogo), \
                mock.patch.object(dialogo, "Destroy"):
            dialogo._datos = ("YouTube", "")
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_OK):
                self.assertEqual(
                    elegir.pedir_destino(None, "TikTok", "amigo"),
                    ("YouTube", ""))
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_CANCEL):
                self.assertIsNone(
                    elegir.pedir_destino(None, "TikTok", "amigo"))


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoElegirDestino(unittest.TestCase):
    # Pseudotraducción de la ventana: la corre el advisor, abre ventanas.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, **kwargs):
        dialogo = elegir.DialogoElegirDestino(None, **kwargs)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = self._dialogo(destino="TikTok", usuario="amigo")
            sin_marcar = textos_sin_marcar(
                dialogo, propios=("TikTok", "YouTube"))
        self.assertEqual([], sin_marcar)

    def test_anuncio_propio_sale_marcado(self):
        dialogo = self._dialogo(destino="TikTok", usuario="")
        dialogo.txt_usuario.SetValue("")
        with con_pseudo(), \
                mock.patch.object(elegir, "anunciar") as anunciar:
            dialogo._al_continuar(mock.Mock())
        anunciar.assert_called_once()
        self.assertTrue(anunciar.call_args.args[0].startswith("[¡"))


if __name__ == "__main__":
    unittest.main()
