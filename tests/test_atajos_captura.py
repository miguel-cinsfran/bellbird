"""Pruebas de las decisiones de captura de atajos."""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from bellbird.core.idioma import _
from bellbird.ui import atajos_captura
from bellbird.ui import teclado_altgr
from bellbird.core import config

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

    def test_consulta_rapida_acepta_ctrl_shift_f2(self):
        self.assertEqual(
            atajos_captura.ETIQUETAS.get("consulta_rapida_ia"),
            "Consulta rápida a la IA sobre la escena")
        resultado = atajos_captura.resolver(
            "consulta_rapida_ia", "ctrl+shift+f2", {})
        self.assertEqual(resultado, (
            "capturado", "ctrl+shift+f2",
            "Capturado: Ctrl+Mayús+F2. Se aplica al pulsar Guardar."))

    def test_choque_con_otra_accion(self):
        resultado = atajos_captura.resolver("rep_play", "ctrl+k", self.valores)
        self.assertEqual(resultado, (
            "rechazado", None, "Ya lo usa: Retroceder 1 minuto. Elige otra."))

    def test_todas_las_acciones_tienen_etiqueta(self):
        for accion in config.todos_los_atajos_default():
            with self.subTest(accion=accion):
                self.assertIn(accion, atajos_captura.ETIQUETAS)

    def test_etiquetas_sin_sufijo_de_fija(self):
        for accion, etiqueta in atajos_captura.ETIQUETAS.items():
            with self.subTest(accion=accion):
                self.assertNotIn("(fija)", etiqueta)
                self.assertNotIn("(fijo)", etiqueta)

    def test_choque_con_obs_micro_usa_nombre_legible(self):
        valores = {"abrir_preferencias": "ctrl+shift+m",
                   "obs_micro": "ctrl+shift+m"}
        resultado = atajos_captura.resolver(
            "abrir_preferencias", "ctrl+shift+m", valores)
        self.assertEqual(resultado, (
            "rechazado", None,
            "Ya lo usa: Silenciar el micrófono de OBS. Elige otra."))

    def test_desactivado(self):
        resultado = atajos_captura.resolver("rep_play", None, self.valores)
        self.assertEqual(resultado, (
            "desactivado", "", "Reproducir o pausa sin atajo. Desactivado."))

    def test_accion_de_area_ctrl_alt_captura_una_flecha(self):
        with mock.patch.dict(config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
            resultado = atajos_captura.resolver(
                "musica_siguiente", "ctrl+alt+right", {})
        self.assertEqual(resultado, (
            "capturado", "ctrl+alt+right",
            "Capturado: Ctrl+Alt+Flecha derecha. Se aplica al pulsar Guardar."))

    def test_accion_de_area_ctrl_alt_rechaza_letra_que_escribe_altgr(self):
        altgr = mock.Mock(return_value="@")
        with mock.patch.dict(config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
            resultado = atajos_captura.resolver(
                "musica_siguiente", "ctrl+alt+q", {}, altgr)
        self.assertEqual(resultado, (
            "rechazado", None,
            "Con este teclado, AltGr+Q escribe @. Elige otra."))

    def test_ctrl_alt_letra_se_captura_si_altgr_no_escribe(self):
        altgr = mock.Mock(return_value="")
        with mock.patch.dict(config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
            resultado = atajos_captura.resolver(
                "musica_siguiente", "ctrl+alt+t", {}, altgr)
        altgr.assert_called_once_with("t")
        self.assertEqual(resultado, (
            "capturado", "ctrl+alt+t",
            "Capturado: Ctrl+Alt+T. Se aplica al pulsar Guardar."))

    def test_ctrl_alt_flecha_no_consulta_altgr(self):
        altgr = mock.Mock(side_effect=AssertionError("no debe llamarse"))
        with mock.patch.dict(config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
            resultado = atajos_captura.resolver(
                "musica_siguiente", "ctrl+alt+right", {}, altgr)
        altgr.assert_not_called()
        self.assertEqual(resultado[0], "capturado")

    def test_area_ctrl_no_consulta_altgr(self):
        altgr = mock.Mock(side_effect=AssertionError("no debe llamarse"))
        resultado = atajos_captura.resolver(
            "rep_play", "ctrl+q", self.valores, altgr)
        altgr.assert_not_called()
        self.assertEqual(resultado[0], "capturado")

    def test_por_defecto_rechaza_letra_que_escribe_altgr(self):
        with mock.patch.object(
                teclado_altgr, "caracter_altgr", return_value="@"):
            with mock.patch.dict(
                    config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
                resultado = atajos_captura.resolver(
                    "musica_siguiente", "ctrl+alt+q", {})
        self.assertEqual(resultado, (
            "rechazado", None,
            "Con este teclado, AltGr+Q escribe @. Elige otra."))

    def test_por_defecto_captura_si_altgr_no_escribe(self):
        with mock.patch.object(
                teclado_altgr, "caracter_altgr", return_value=""):
            with mock.patch.dict(
                    config.ATAJOS_AREA, {"musica_siguiente": "ctrl+alt"}):
                resultado = atajos_captura.resolver(
                    "musica_siguiente", "ctrl+alt+t", {})
        self.assertEqual(resultado, (
            "capturado", "ctrl+alt+t",
            "Capturado: Ctrl+Alt+T. Se aplica al pulsar Guardar."))

    def test_accion_de_area_ctrl_rechaza_ctrl_alt(self):
        resultado = atajos_captura.resolver(
            "rep_play", "ctrl+alt+left", self.valores)
        self.assertEqual(resultado[0], "rechazado")
        self.assertIsNone(resultado[1])
        self.assertIn(
            "Debe ser Ctrl y una tecla (por ejemplo Ctrl+P).", resultado[2])

    def test_mostrar_atajo_habla_en_espanol(self):
        # mostrar_atajo es atajo_legible; para leer en voz alta no hay inglés.
        casos = {
            "ctrl+left": "Ctrl+Flecha izquierda",
            "ctrl+shift+p": "Ctrl+Mayús+P",
            "alt+enter": "Alt+Intro",
            "ctrl+alt+space": "Ctrl+Alt+Espacio",
            "ctrl+end": "Ctrl+Fin",
            "shift+f6": "Mayús+F6",
        }
        for guardado, esperado in casos.items():
            with self.subTest(guardado=guardado):
                self.assertEqual(atajos_captura.mostrar_atajo(guardado), esperado)
                self.assertEqual(
                    atajos_captura.mostrar_atajo(guardado),
                    atajos_captura.atajo_legible(guardado))

    def test_mostrar_atajo_vacio_dice_sin_asignar(self):
        self.assertEqual(atajos_captura.mostrar_atajo(""), "(sin asignar)")

    def test_mostrar_atajo_de_fabrica_sin_ingles(self):
        ingles = ("Shift", "Enter", "Left", "Right",
                  "Up", "Down", "Space", "End")
        for accion, valor in config.todos_los_atajos_default().items():
            with self.subTest(accion=accion):
                mostrado = atajos_captura.mostrar_atajo(valor)
                for palabra in ingles:
                    self.assertNotIn(palabra, mostrado)
                self.assertEqual(
                    mostrado, atajos_captura.atajo_legible(valor))

    def test_combinacion_fuera_de_gramatica_se_rechaza_sin_culpar(self):
        resultado = atajos_captura.resolver("rep_play", "win+q", self.valores)
        self.assertEqual(resultado, (
            "rechazado", None, "Esa combinación no se puede usar. Elige otra."))

    def test_ayuda_ctrl_alt_nombra_a_mayus(self):
        self.assertEqual(
            atajos_captura._AREA_AYUDA["ctrl+alt"],
            "Debe ser Ctrl+Alt y una flecha, Espacio, una letra o un número, "
            "o Ctrl+Alt+Mayús y Flecha izquierda o derecha "
            "(por ejemplo Ctrl+Alt+T).")

    def test_titulos_de_grupo_dicen_mayus(self):
        grupos = dict(config.ATAJOS_GRUPOS)
        self.assertIn("Ventanas (Ctrl+Mayús)", grupos)
        self.assertIn("Directo y OBS (Alt+Mayús)", grupos)

    def test_ayuda_para_cada_area(self):
        for area in config._AREA_POR_GRUPO:
            if area is None:
                continue
            with self.subTest(area=area):
                self.assertTrue(atajos_captura._AREA_AYUDA.get(area))
        self.assertIn("Mayús", atajos_captura._AREA_AYUDA["ctrl+shift"])
        self.assertIn("Mayús", atajos_captura._AREA_AYUDA["alt+shift"])

    def test_textos_de_etiqueta_y_espera(self):
        self.assertEqual(
            atajos_captura.mostrar_atajo("alt+enter"), "Alt+Intro")
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
            "Intro la deja sin atajo. Escape cancela.")

    def test_etiqueta_boton_nombra_la_tecla_en_espanol(self):
        self.assertEqual(
            atajos_captura.etiqueta_boton("Retroceder 1 minuto", "ctrl+left"),
            "Retroceder 1 minuto: Ctrl+Flecha izquierda")
        self.assertEqual(
            atajos_captura.etiqueta_boton(
                "Abrir Preferencias", "ctrl+shift+p"),
            "Abrir Preferencias: Ctrl+Mayús+P")

    def test_nota_pagina_nombra_las_familias_en_espanol(self):
        nota = atajos_captura.NOTA_PAGINA
        self.assertNotIn("Shift", nota)
        self.assertNotIn("Enter", nota)
        for familia in ("Ctrl+Mayús", "Alt+Mayús", "Ctrl+Alt", "teclas F",
                        "Ctrl es para el reproductor", "Alt para el chat"):
            with self.subTest(familia=familia):
                self.assertIn(familia, nota)

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_la_pagina_entrega_la_combinacion_al_resolvedor(self):
        import wx
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
        from bellbird.ui import preferencias_atajos as gp
        from bellbird.core import config as cfg
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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
            "Atajos restablecidos a los valores de fábrica. Se aplican al pulsar Guardar.")

    @unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
    def test_cancelar_restaurar_la_etiqueta_y_anunciar_sin_cambios(self):
        from bellbird.ui import preferencias_atajos as gp
        dialogo = gp.PaginaAtajos.__new__(gp.PaginaAtajos)
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


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_resolver_marca_todos_los_caminos(self):
        valores = {"rep_play": "ctrl+p", "rep_retro": "ctrl+k"}
        with con_pseudo():
            marcados = [
                atajos_captura.resolver("rep_play", "ctrl+q", valores)[2],
                atajos_captura.resolver("rep_play", "ctrl+k", valores)[2],
                atajos_captura.resolver("rep_play", "win+q", valores)[2],
                atajos_captura.resolver("rep_play", None, valores)[2],
                atajos_captura.texto_de_espera("Etiqueta", "Ayuda."),
                atajos_captura.mostrar_atajo(""),
                atajos_captura.atajo_legible("ctrl+end"),
                atajos_captura.etiqueta_de_accion("rep_play"),
                _(atajos_captura.NOTA_PAGINA),
            ]
            for etiqueta in atajos_captura.ETIQUETAS.values():
                marcados.append(_(etiqueta))
            for ayuda in atajos_captura._AREA_AYUDA.values():
                marcados.append(_(ayuda))
        for texto in marcados:
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)

    def test_rechazo_fuera_de_area_marca_ayuda(self):
        with con_pseudo():
            _, _, texto = atajos_captura.resolver(
                "rep_play", "alt+k", {"rep_play": "ctrl+p"})
        self.assertTrue(texto.startswith("[¡"), texto)


if __name__ == "__main__":
    unittest.main()
