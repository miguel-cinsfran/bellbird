"""Pruebas de las decisiones de captura de atajos."""

import unittest
from unittest import mock

from ytchat.ui import atajos_captura

try:
    import wx  # noqa: F401
    _HAY_WX = True
except Exception:
    _HAY_WX = False


class TestAtajosCaptura(unittest.TestCase):

    def setUp(self):
        self.valores = {
            "rep_play": "ctrl+p",
            "rep_retro": "ctrl+k",
        }

    def test_captura_valida(self):
        resultado = atajos_captura.resolver("rep_play", "ctrl+q", self.valores)
        self.assertEqual(resultado, (
            "capturado", "ctrl+q", "Capturado: Ctrl+Q. Se aplica al pulsar Guardar."))

    def test_captura_no_promete_guardado(self):
        _, _, texto = atajos_captura.resolver("rep_play", "ctrl+q", self.valores)
        self.assertIn("Se aplica al pulsar Guardar", texto)
        self.assertNotIn("Guardado.", texto)

    def test_combinacion_invalida_para_el_area(self):
        resultado = atajos_captura.resolver("rep_play", "alt+k", self.valores)
        self.assertEqual(resultado, (
            "rechazado", None,
            "No vale aquí. Debe ser Ctrl y una tecla (por ejemplo Ctrl+P)."))

    def test_describir_escena_acepta_ctrl_f2(self):
        resultado = atajos_captura.resolver("describir_escena", "ctrl+f2", {})
        self.assertEqual(resultado, (
            "capturado", "ctrl+f2",
            "Capturado: Ctrl+F2. Se aplica al pulsar Guardar."))

    def test_describir_escena_rechaza_otro_modificador(self):
        resultado = atajos_captura.resolver("describir_escena", "alt+e", {})
        self.assertEqual(resultado[0], "rechazado")
        self.assertIn("F1 a F12", resultado[2])

    def test_choque_con_otra_accion(self):
        resultado = atajos_captura.resolver("rep_play", "ctrl+k", self.valores)
        self.assertEqual(resultado, (
            "rechazado", None, "Ya lo usa: Retroceder 1 minuto. Elige otra."))

    def test_desactivado(self):
        resultado = atajos_captura.resolver("rep_play", None, self.valores)
        self.assertEqual(resultado, (
            "desactivado", "", "Reproducir o pausa sin atajo. Desactivado."))

    def test_mostrar_atajo_sigue_en_ingles_de_menu(self):
        # El formato de menú no se usa para leer; para eso está atajo_legible.
        self.assertEqual(atajos_captura.mostrar_atajo("ctrl+end"), "Ctrl+End")

    def test_textos_de_etiqueta_y_espera(self):
        self.assertEqual(
            atajos_captura.mostrar_atajo("alt+enter"), "Alt+Enter")
        self.assertEqual(
            atajos_captura.etiqueta_boton("Conectar", "alt+c"),
            "Conectar: Alt+C")
        self.assertEqual(
            atajos_captura.etiqueta_boton("Conectar", ""),
            "Conectar: (sin asignar)")
        self.assertEqual(
            atajos_captura.texto_de_espera(
                "Conectar", "Debe ser Alt y una tecla (por ejemplo Alt+C)."),
            "Pulsa la combinación para Conectar. "
            "Debe ser Alt y una tecla (por ejemplo Alt+C). "
            "Enter la deja sin atajo. Escape cancela.")

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_la_pagina_entrega_la_combinacion_al_resolvedor(self):
        import wx
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        boton = mock.Mock()
        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        dialogo._valores_atajo = {"rep_play": "ctrl+p"}
        dialogo._botones_atajo = {"rep_play": boton}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = ord("Q")
        evento.GetModifiers.return_value = wx.MOD_CONTROL
        with mock.patch.object(gp.atajos_captura, "resolver",
                               return_value=("capturado", "ctrl+q", "Guardado")) as resolver:
            with mock.patch.object(gp, "anunciar"):
                dialogo._on_tecla_captura(evento)
        resolver.assert_called_once_with(
            "rep_play", "ctrl+q", {"rep_play": "ctrl+q"})
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+q")
        boton.SetLabel.assert_called_once_with(
            "Reproducir o pausa: Ctrl+Q")

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_escape_cancela_la_captura(self):
        import wx
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        dialogo._valores_atajo = {"rep_play": "ctrl+q"}
        dialogo._botones_atajo = {"rep_play": mock.Mock()}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_ESCAPE
        evento.GetModifiers.return_value = wx.MOD_NONE
        with mock.patch.object(gp, "anunciar") as anunciar:
            dialogo._on_tecla_captura(evento)
        self.assertIsNone(dialogo._capturando_atajo)
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+q")
        anunciar.assert_called_once_with("Sin cambios")

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_tab_sale_de_la_captura_y_deja_navegar(self):
        import wx
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        dialogo._valores_atajo = {"rep_play": "ctrl+q"}
        dialogo._botones_atajo = {"rep_play": mock.Mock()}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_TAB
        evento.GetModifiers.return_value = wx.MOD_NONE
        dialogo._on_tecla_captura(evento)
        self.assertIsNone(dialogo._capturando_atajo)
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+q")
        evento.Skip.assert_called_once_with()

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_tecla_de_solo_modificador_no_resuelve_el_atajo(self):
        import wx
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        captura = ("rep_play", "Reproducir o pausa")
        dialogo._capturando_atajo = captura
        dialogo._valores_atajo = {"rep_play": "ctrl+q"}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_SHIFT
        evento.GetModifiers.return_value = wx.MOD_NONE
        with mock.patch.object(gp.atajos_captura, "resolver") as resolver:
            dialogo._on_tecla_captura(evento)
        self.assertEqual(dialogo._capturando_atajo, captura)
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+q")
        resolver.assert_not_called()

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_enter_solo_desactiva_y_alt_enter_se_captura(self):
        import wx
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        dialogo._valores_atajo = {"rep_play": "ctrl+p"}
        dialogo._botones_atajo = {"rep_play": mock.Mock()}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_RETURN
        evento.GetModifiers.return_value = wx.MOD_ALT
        with mock.patch.object(
                gp.atajos_captura, "resolver",
                return_value=("capturado", "alt+enter", "Guardado")) as resolver:
            dialogo._on_tecla_captura(evento)
        resolver.assert_called_once_with(
            "rep_play", "alt+enter", {"rep_play": "alt+enter"})

        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        evento.GetModifiers.return_value = wx.MOD_NONE
        with mock.patch.object(
                gp.atajos_captura, "resolver",
                return_value=("desactivado", "", "Desactivado")) as resolver:
            dialogo._on_tecla_captura(evento)
        resolver.assert_called_once_with(
            "rep_play", None, {"rep_play": ""})

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_restablecer_cambia_solo_los_atajos_editables(self):
        from ytchat.ui import gui_preferencias as gp
        from ytchat.core import config as cfg
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        dialogo._valores_atajo = cfg.todos_los_atajos_default()
        dialogo._valores_atajo["rep_play"] = "ctrl+q"
        dialogo._valores_atajo["salir"] = "alt+x"
        dialogo._botones_atajo = {
            accion: mock.Mock() for accion in dialogo._valores_atajo}
        with mock.patch.object(gp, "anunciar") as anunciar:
            dialogo._restablecer_atajos(None)
        self.assertEqual(dialogo._valores_atajo["rep_play"], "ctrl+p")
        self.assertEqual(dialogo._valores_atajo["salir"], "alt+x")
        dialogo._botones_atajo["rep_play"].SetLabel.assert_called_once_with(
            "Reproducir o pausa: Ctrl+P")
        anunciar.assert_called_once_with(
            "Atajos restablecidos a los valores de fábrica. Se aplican al pulsar Guardar")

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_cancelar_restaurar_la_etiqueta_y_anunciar_sin_cambios(self):
        from ytchat.ui import gui_preferencias as gp
        dialogo = gp.PreferenciasDialog.__new__(gp.PreferenciasDialog)
        boton = mock.Mock()
        dialogo._capturando_atajo = ("rep_play", "Reproducir o pausa")
        dialogo._valores_atajo = {"rep_play": "ctrl+q"}
        dialogo._botones_atajo = {"rep_play": boton}
        with mock.patch.object(gp, "anunciar") as anunciar:
            dialogo._salir_captura_atajo(True)
        boton.SetLabel.assert_called_once_with(
            "Reproducir o pausa: Ctrl+Q")
        anunciar.assert_called_once_with("Sin cambios")


class TestAtajoLegible(unittest.TestCase):

    def test_fabrica_da_ctrl_fin(self):
        self.assertEqual(atajos_captura.atajo_legible("ctrl+end"), "Ctrl+Fin")

    def test_letra_cambiada_en_mayuscula(self):
        self.assertEqual(atajos_captura.atajo_legible("alt+d"), "Alt+D")

    def test_funcion_sola(self):
        self.assertEqual(atajos_captura.atajo_legible("f2"), "F2")

    def test_teclas_con_nombre_en_espanol(self):
        casos = {
            "ctrl+home": "Ctrl+Inicio",
            "ctrl+left": "Ctrl+Flecha izquierda",
            "ctrl+right": "Ctrl+Flecha derecha",
            "ctrl+up": "Ctrl+Flecha arriba",
            "ctrl+down": "Ctrl+Flecha abajo",
            "ctrl+pageup": "Ctrl+Re Pág",
            "ctrl+pagedown": "Ctrl+Av Pág",
            "ctrl+delete": "Ctrl+Supr",
            "alt+enter": "Alt+Intro",
            "alt+space": "Alt+Espacio",
            "ctrl+backspace": "Ctrl+Retroceso",
            "ctrl+escape": "Ctrl+Escape",
            "ctrl+shift+f5": "Ctrl+Mayús+F5",
        }
        for guardado, esperado in casos.items():
            with self.subTest(guardado=guardado):
                self.assertEqual(atajos_captura.atajo_legible(guardado), esperado)

    def test_tab_solo(self):
        self.assertEqual(atajos_captura.atajo_legible("ctrl+tab"), "Ctrl+Tab")

    def test_sin_atajo_da_vacio(self):
        self.assertEqual(atajos_captura.atajo_legible(""), "")
        self.assertEqual(atajos_captura.atajo_legible(None), "")


if __name__ == "__main__":
    unittest.main()
