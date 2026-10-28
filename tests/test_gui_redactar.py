import unittest
from unittest import mock

import wx

from ytchat.core.idioma import _
from ytchat.ui import gui_redactar
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir


class EventoTeclado:
    def __init__(self, codigo, mayus=False):
        self.codigo = codigo
        self.mayus = mayus
        self.omitido = False

    def GetKeyCode(self):
        return self.codigo

    def ShiftDown(self):
        return self.mayus

    def Skip(self):
        self.omitido = True


class TestPanelRedactar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()
        cls.frame = wx.Frame(None)

    @classmethod
    def tearDownClass(cls):
        # Un objeto de wx en un atributo de clase se libera al cerrar
        # Python, con wx ya bajado, y el proceso se cae.
        destruir(cls.frame)
        del cls.frame
        del cls.app

    def panel(self, texto="mensaje", motivo=""):
        enviado = []
        panel = gui_redactar.PanelRedactar(
            self.frame, "&Mensaje:", 200, enviado.append)
        panel.texto.SetValue(texto)
        panel.establecer_motivo(motivo)
        panel._enviado = enviado
        return panel

    def test_enter_envia_y_no_deja_pasarlo(self):
        panel = self.panel()
        evento = EventoTeclado(wx.WXK_RETURN)
        with mock.patch.object(panel, "_on_enviar", wraps=panel._on_enviar) as enviar:
            panel._on_char_hook(evento)
        self.assertEqual(panel._enviado, ["mensaje"])
        enviar.assert_called_once_with(evento)
        self.assertFalse(evento.omitido)
        panel.Destroy()

    def test_texto_enlaza_char_hook(self):
        with mock.patch.object(wx.TextCtrl, "Bind") as enlazar:
            panel = gui_redactar.PanelRedactar(
                self.frame, "&Mensaje:", 200, lambda texto: None)
        eventos = [llamada.args[0] for llamada in enlazar.call_args_list]
        self.assertIn(wx.EVT_CHAR_HOOK, eventos)
        panel.Destroy()

    def test_mayusculas_enter_inserta_salto_y_no_envia(self):
        panel = self.panel()
        evento = EventoTeclado(wx.WXK_RETURN, mayus=True)
        panel._on_char_hook(evento)
        self.assertEqual(panel._enviado, [])
        self.assertTrue(evento.omitido)
        panel.Destroy()

    def test_otra_tecla_se_deja_pasar(self):
        panel = self.panel()
        evento = EventoTeclado(ord("a"))
        panel._on_char_hook(evento)
        self.assertEqual(panel._enviado, [])
        self.assertTrue(evento.omitido)
        panel.Destroy()

    def test_motivo_no_envia_y_anuncia(self):
        panel = self.panel(motivo="Inicia sesión")
        with mock.patch.object(gui_redactar, "_anunciar") as anunciar:
            panel._on_enviar(None)
        self.assertEqual(panel._enviado, [])
        anunciar.assert_called_once_with("Inicia sesión")
        panel.Destroy()

    def test_texto_vacio_no_envia_y_anuncia_validacion(self):
        panel = self.panel(texto="   ")
        with mock.patch.object(gui_redactar, "_anunciar") as anunciar:
            panel._on_enviar(None)
        self.assertEqual(panel._enviado, [])
        anunciar.assert_called_once_with("Escribe un mensaje antes de enviar")
        panel.Destroy()

    def test_envio_correcto_vacia_el_cuadro(self):
        panel = self.panel("  mensaje  ")
        panel._on_enviar(None)
        self.assertEqual(panel._enviado, ["mensaje"])
        self.assertEqual(panel.texto.GetValue(), "")
        panel.Destroy()


class TestDialogoRedactar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()
        cls.frame = wx.Frame(None)

    @classmethod
    def tearDownClass(cls):
        destruir(cls.frame)
        del cls.frame
        del cls.app

    def dialogo(self, texto="mensaje", motivo=""):
        llamadas = []
        dialogo = gui_redactar.DialogoRedactar(
            self.frame, "&Comentario:", 200, llamadas.append, motivo=motivo)
        dialogo.panel.texto.SetValue(texto)
        dialogo._llamadas = llamadas
        return dialogo

    def test_publicar_llama_al_enviar_una_vez_con_el_texto(self):
        dialogo = self.dialogo()
        with mock.patch.object(dialogo, "EndModal"):
            dialogo.panel._on_enviar(None)
        self.assertEqual(dialogo._llamadas, ["mensaje"])
        destruir(dialogo)

    def test_publicar_guarda_el_texto_enviado(self):
        dialogo = self.dialogo("  mensaje  ")
        with mock.patch.object(dialogo, "EndModal"):
            dialogo.panel._on_enviar(None)
        self.assertEqual(dialogo.texto_enviado, "mensaje")
        destruir(dialogo)

    def test_motivo_no_llama_al_enviar(self):
        dialogo = self.dialogo(motivo="Inicia sesión")
        with mock.patch.object(gui_redactar, "_anunciar"):
            dialogo.panel._on_enviar(None)
        self.assertEqual(dialogo._llamadas, [])
        destruir(dialogo)


# La etiqueta del panel suelto la armaba `ytchat/ui/gui.py` («&Mensaje:»):
# ya pasa por gettext, así que no queda pendiente. La comparación es exacta
# en los dos sentidos: falla si aparece un texto nuevo sin envolver.
PENDIENTES_REDACTAR = ()


class TestPseudoRedactar(unittest.TestCase):
    # Pseudotraducción: abre ventanas, la corre el advisor.

    @classmethod
    def setUpClass(cls):
        cls.app = wx.App() if not wx.App.Get() else wx.App.Get()
        cls.frame = wx.Frame(None)

    @classmethod
    def tearDownClass(cls):
        destruir(cls.frame)
        del cls.frame
        del cls.app

    def test_panel_con_etiqueta_marcada_no_deja_nada(self):
        with con_pseudo():
            panel = gui_redactar.PanelRedactar(
                self.frame, _("&Mensaje:"), 200, lambda texto: None)
            sin_marcar = textos_sin_marcar(panel)
        panel.Destroy()
        self.assertEqual(sin_marcar, list(PENDIENTES_REDACTAR))

    def test_dialogo_sin_texto_ajeno_no_deja_nada(self):
        with con_pseudo():
            dialogo = gui_redactar.DialogoRedactar(
                self.frame, _("&Comentario:"), 200, lambda texto: None,
                titulo=_("Comentar"), nombre_texto=_("Texto del comentario"),
                nombre_boton=_("Publicar"))
            sin_marcar = textos_sin_marcar(dialogo)
        destruir(dialogo)
        self.assertEqual([], sin_marcar)

    def test_valores_por_defecto_salen_marcados(self):
        with con_pseudo():
            dialogo = gui_redactar.DialogoRedactar(
                self.frame, _("&Comentario:"), 200, lambda texto: None)
            titulo = dialogo.GetTitle()
            nombre_texto = dialogo.panel.texto.GetName()
            boton = dialogo.panel.boton.GetLabel()
        destruir(dialogo)
        for texto in (titulo, nombre_texto, boton):
            self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()
