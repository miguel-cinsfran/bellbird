"""Tests del parseo de atajos de teclado (config.parsear_atajos)."""

import unittest
import inspect
from unittest import mock

from ytchat.core.config import (
    _normalizar_atajo, parsear_atajos, detectar_conflictos_atajos,
    ATAJOS_DEFAULTS, ATAJOS_AREA, atajo_valido_para_area,
    ATAJOS_FIJOS, ATAJOS_FIJOS_DEFAULTS, ATAJOS_GRUPOS, todos_los_atajos_default,
    _AREA_POR_GRUPO,
)
from ytchat.ui import gui_preferencias
from ytchat.ui import preferencias_atajos
from ytchat.ui import gui
from ytchat.ui import gui_menu
from ytchat.ui import atajos_captura
from ytchat.core import config
from ytchat.core import atajos
from ytchat.ui.gui_preferencias import _ETIQUETAS_ATAJO, etiqueta_de_accion


class TestNormalizarAtajo(unittest.TestCase):

    def test_none(self):
        self.assertIsNone(_normalizar_atajo(None))

    def test_vacio(self):
        self.assertIsNone(_normalizar_atajo("  "))

    def test_alt_letra(self):
        self.assertEqual(_normalizar_atajo("alt+u"), "alt+u")

    def test_alt_letra_mayuscula_y_espacios(self):
        self.assertEqual(_normalizar_atajo(" ALT + U "), "alt+u")

    def test_fkey(self):
        self.assertEqual(_normalizar_atajo("f5"), "f5")
        self.assertEqual(_normalizar_atajo("F12"), "f12")

    def test_ctrl_mas_fkey(self):
        self.assertEqual(_normalizar_atajo("ctrl+f2"), "ctrl+f2")
        self.assertEqual(_normalizar_atajo("Ctrl+Shift+F5"), "ctrl+shift+f5")
        self.assertIsNone(_normalizar_atajo("ctrl+f13"))
        self.assertIsNone(_normalizar_atajo("shift+f2"))

    def test_fkey_fuera_de_rango(self):
        self.assertIsNone(_normalizar_atajo("f13"))

    def test_simbolo_permitido(self):
        self.assertEqual(_normalizar_atajo("alt+."), "alt+.")

    def test_ctrl_letra(self):
        self.assertEqual(_normalizar_atajo("ctrl+d"), "ctrl+d")

    def test_teclas_con_nombre(self):
        self.assertEqual(_normalizar_atajo("ctrl+left"), "ctrl+left")
        self.assertEqual(_normalizar_atajo("alt+enter"), "alt+enter")
        self.assertEqual(_normalizar_atajo("ctrl+up"), "ctrl+up")

    def test_modificador_no_soportado(self):
        # Shift solo no se admite; Alt+Shift sí, con el orden normalizado.
        self.assertIsNone(_normalizar_atajo("shift+u"))
        self.assertEqual(_normalizar_atajo("alt+shift+x"), "alt+shift+x")
        self.assertEqual(_normalizar_atajo("shift+alt+x"), "alt+shift+x")
        self.assertEqual(_normalizar_atajo("ctrl+alt+x"), "ctrl+alt+x")
        self.assertEqual(_normalizar_atajo("ctrl+shift+x"), "ctrl+shift+x")

    def test_tecla_nombre_desconocida(self):
        self.assertIsNone(_normalizar_atajo("ctrl+home"))

    def test_ctrl_shift_tecla_con_nombre(self):
        self.assertEqual(_normalizar_atajo("ctrl+shift+left"), "ctrl+shift+left")

    def test_ctrl_alt_teclas_permitidas(self):
        for tecla in ("left", "right", "up", "down", "space"):
            with self.subTest(tecla=tecla):
                self.assertEqual(
                    _normalizar_atajo(f"ctrl+alt+{tecla}"),
                    f"ctrl+alt+{tecla}")

    def test_ctrl_alt_orden_invertido_mayusculas_y_espacios(self):
        self.assertEqual(_normalizar_atajo("alt+ctrl+left"), "ctrl+alt+left")
        self.assertEqual(
            _normalizar_atajo(" Ctrl + Alt + Right "), "ctrl+alt+right")

    def test_ctrl_alt_acepta_letras_y_digitos(self):
        for tecla in "abcdefghijklmnopqrstuvwxyz0123456789":
            with self.subTest(tecla=tecla):
                self.assertEqual(
                    _normalizar_atajo(f"ctrl+alt+{tecla}"),
                    f"ctrl+alt+{tecla}")

    def test_ctrl_alt_normaliza_mayusculas_y_orden(self):
        self.assertEqual(_normalizar_atajo("Ctrl+Alt+T"), "ctrl+alt+t")
        self.assertEqual(_normalizar_atajo("ALT+CTRL+2"), "ctrl+alt+2")

    def test_ctrl_alt_rechaza_teclas_f_enter_end_simbolos_y_shift_con_letra(self):
        for valor in ("ctrl+alt+f5", "ctrl+alt+enter", "ctrl+alt+end",
                      "ctrl+alt+.", "ctrl+alt+shift+a"):
            with self.subTest(valor=valor):
                self.assertIsNone(_normalizar_atajo(valor))

    def test_ctrl_alt_shift_solo_acepta_las_flechas_horizontales(self):
        self.assertEqual(_normalizar_atajo("ctrl+alt+shift+left"),
                         "ctrl+alt+shift+left")
        self.assertEqual(_normalizar_atajo("ctrl+alt+shift+right"),
                         "ctrl+alt+shift+right")
        self.assertIsNone(_normalizar_atajo("ctrl+alt+shift+up"))
        self.assertIsNone(_normalizar_atajo("ctrl+alt+shift+down"))

    def test_ctrl_alt_shift_normaliza_los_otros_ordenes(self):
        for valor in ("shift+ctrl+alt+left", "ctrl+shift+alt+left",
                      "alt+ctrl+shift+left", "alt+shift+ctrl+left",
                      "shift+alt+ctrl+left"):
            with self.subTest(valor=valor):
                self.assertEqual(_normalizar_atajo(valor),
                                 "ctrl+alt+shift+left")


class TestAreasAtajo(unittest.TestCase):

    def test_ctrl_shift_no_pertenece_al_area_ctrl(self):
        with mock.patch.dict(config.ATAJOS_AREA, {"accion": "ctrl"}):
            self.assertFalse(atajo_valido_para_area("accion", "ctrl+shift+p"))

    def test_ctrl_shift_pertenece_a_su_area(self):
        with mock.patch.dict(config.ATAJOS_AREA, {"accion": "ctrl+shift"}):
            self.assertTrue(atajo_valido_para_area("accion", "ctrl+shift+p"))

    def test_rechaza_el_modificador_de_la_otra_area(self):
        modificador_equivocado = {"ctrl": "alt+p", "alt": "ctrl+c"}
        for accion, area in ATAJOS_AREA.items():
            if area in modificador_equivocado:
                with self.subTest(accion=accion):
                    self.assertFalse(atajo_valido_para_area(
                        accion, modificador_equivocado[area]))

    def test_ctrl_alt_pertenece_a_su_area(self):
        with mock.patch.dict(config.ATAJOS_AREA, {"accion": "ctrl+alt"}):
            self.assertTrue(atajo_valido_para_area("accion", "ctrl+alt+left"))

    def test_ctrl_alt_no_pertenece_al_area_ctrl(self):
        with mock.patch.dict(config.ATAJOS_AREA, {"accion": "ctrl"}):
            self.assertFalse(atajo_valido_para_area("accion", "ctrl+alt+left"))

    def test_ctrl_alt_solo_vale_en_su_area(self):
        for tecla in ("left", "right", "up", "down", "space"):
            normalizado = f"ctrl+alt+{tecla}"
            with self.subTest(tecla=tecla, area="ctrl+alt"):
                with mock.patch.dict(config.ATAJOS_AREA,
                                     {"accion": "ctrl+alt"}):
                    self.assertTrue(
                        atajo_valido_para_area("accion", normalizado))
            for area in _AREA_POR_GRUPO:
                if area is None or area == "ctrl+alt":
                    continue
                with self.subTest(tecla=tecla, area=area):
                    with mock.patch.dict(config.ATAJOS_AREA, {"accion": area}):
                        self.assertFalse(
                            atajo_valido_para_area("accion", normalizado))

    def test_consulta_rapida_acepta_ctrl_shift_f2(self):
        self.assertEqual(ATAJOS_AREA.get("consulta_rapida_ia"), "f")
        self.assertEqual(ATAJOS_DEFAULTS.get("consulta_rapida_ia"),
                         "ctrl+shift+f2")
        self.assertTrue(atajo_valido_para_area(
            "consulta_rapida_ia", "ctrl+shift+f2"))

    def test_consulta_rapida_rechaza_ctrl_shift_letra(self):
        self.assertFalse(atajo_valido_para_area(
            "consulta_rapida_ia", "ctrl+shift+a"))

    def test_describir_escena_queda_igual(self):
        self.assertTrue(atajo_valido_para_area(
            "describir_escena", "ctrl+f2"))
        self.assertFalse(atajo_valido_para_area(
            "describir_escena", "alt+e"))


class TestParsearAtajos(unittest.TestCase):

    def test_pagina_de_atajos_usa_etiqueta_de_accion(self):
        pagina = preferencias_atajos.PaginaAtajos.__new__(
            preferencias_atajos.PaginaAtajos)
        pagina._config = {"atajos_raw": {}}
        panel = mock.Mock()
        boton = mock.Mock()
        sizer = mock.Mock()
        crear_boton = mock.Mock(return_value=boton)
        with mock.patch.object(preferencias_atajos, "crear_panel",
                               return_value=panel), \
                mock.patch.object(gui_preferencias.wx, "BoxSizer", return_value=sizer), \
                mock.patch.object(preferencias_atajos, "caja_de_grupo",
                                  return_value=(sizer, panel)), \
                mock.patch.object(gui_preferencias.wx, "StaticText", return_value=mock.Mock()), \
                mock.patch.object(gui_preferencias.wx, "Button", crear_boton), \
                mock.patch.object(preferencias_atajos, "etiqueta_de_accion",
                                  return_value="Acción desconocida") as etiqueta:
            with mock.patch.object(atajos, "ATAJOS_DEFAULTS",
                                   {"accion_nueva": "ctrl+a"}), \
                    mock.patch.object(gui_preferencias.cfg, "ATAJOS_GRUPOS",
                                      [("Grupo", ["accion_nueva"])]), \
                    mock.patch.object(gui_preferencias.cfg, "ATAJOS_FIJOS", set()):
                pagina.construir(object())
        etiqueta.assert_called_once_with("accion_nueva")
        llamada = next(llamada for llamada in crear_boton.call_args_list
                       if llamada.kwargs["name"] == "Atajo_accion_nueva")
        self.assertEqual(llamada.kwargs["label"],
                         "Acción desconocida: Ctrl+A")

    def test_clave_desconocida_se_ignora(self):
        atajos = parsear_atajos({"musica_listas": "ctrl+alt+l"})
        self.assertNotIn("musica_listas", atajos)
        self.assertEqual(set(atajos), set(todos_los_atajos_default()))

    def test_pagina_ignora_clave_desconocida(self):
        pagina = preferencias_atajos.PaginaAtajos.__new__(
            preferencias_atajos.PaginaAtajos)
        pagina._config = {"atajos_raw": {"musica_listas": "ctrl+alt+l"}}
        panel = mock.Mock()
        sizer = mock.Mock()
        crear_boton = mock.Mock(return_value=mock.Mock())
        with mock.patch.object(preferencias_atajos, "crear_panel",
                               return_value=panel), \
                mock.patch.object(gui_preferencias.wx, "BoxSizer", return_value=sizer), \
                mock.patch.object(preferencias_atajos, "caja_de_grupo",
                                  return_value=(sizer, panel)), \
                mock.patch.object(gui_preferencias.wx, "StaticText", return_value=mock.Mock()), \
                mock.patch.object(gui_preferencias.wx, "Button", crear_boton):
            pagina.construir(object())
        nombres = [c.kwargs["name"] for c in crear_boton.call_args_list]
        self.assertNotIn("Atajo_musica_listas", nombres)

    def test_todas_las_acciones_tienen_etiqueta(self):
        self.assertTrue(set(todos_los_atajos_default()) <= set(_ETIQUETAS_ATAJO))

    def test_etiquetas_de_preferencias_son_las_de_captura(self):
        self.assertIs(gui_preferencias._ETIQUETAS_ATAJO,
                      atajos_captura.ETIQUETAS)

    def test_etiquetas_de_defaults_no_exponen_guiones_bajos(self):
        for accion in todos_los_atajos_default():
            self.assertNotIn("_", etiqueta_de_accion(accion))

    def test_todos_los_atajos_tienen_metadatos_y_no_colisionan(self):
        todos = todos_los_atajos_default()
        grupos = {accion for _, acciones in ATAJOS_GRUPOS for accion in acciones}
        self.assertEqual(set(todos), set(ATAJOS_AREA))
        self.assertEqual(set(todos), grupos)
        self.assertEqual(set(todos), set(_ETIQUETAS_ATAJO))
        self.assertEqual(len(todos), len(set(todos.values())))
        for accion, valor in todos.items():
            self.assertTrue(etiqueta_de_accion(accion))
            if accion in ATAJOS_FIJOS_DEFAULTS:
                normalizado = valor
            else:
                normalizado = _normalizar_atajo(valor)
            area = ATAJOS_AREA.get(accion)
            if area is None:
                self.assertIn(accion, ATAJOS_FIJOS_DEFAULTS)
                continue
            if area == "f":
                self.assertRegex(normalizado, r"^(ctrl\+(shift\+)?)?f(1[0-2]|[1-9])$")
            else:
                self.assertTrue(normalizado.startswith(area + "+"))
        self.assertEqual(set(ATAJOS_FIJOS_DEFAULTS) | {
            "velocidad_menos", "velocidad_mas", "volumen_menos", "volumen_mas"
        }, ATAJOS_FIJOS)

    def test_atajos_fijos_tienen_grupo_sin_area(self):
        grupos_fijos = [acciones for titulo, acciones in ATAJOS_GRUPOS
                        if "Ventana y navegación" in titulo]
        self.assertEqual(grupos_fijos, [["salir", "region_siguiente", "region_anterior"]])
        for accion in ATAJOS_FIJOS_DEFAULTS:
            self.assertIsNone(ATAJOS_AREA[accion])

    def test_etiqueta_desconocida_es_frase(self):
        self.assertEqual(
            etiqueta_de_accion("algo_que_no_existe"), "Algo que no existe")

    def test_defaults_completos(self):
        atajos = parsear_atajos({})
        # Todas las acciones por defecto quedan resueltas.
        self.assertEqual(set(atajos.keys()), set(todos_los_atajos_default().keys()))

    def test_fija_reserva_su_combinacion(self):
        atajos = parsear_atajos({"pausa": "f6"})
        self.assertEqual(atajos["region_siguiente"].texto, "f6")
        self.assertNotIn("pausa", atajos)

    def test_fija_reciente_desactiva_la_ventana_que_la_ocupa(self):
        atajos = parsear_atajos({"musica_ventana": "ctrl+shift+1"})
        self.assertEqual(atajos["chat_reciente_1"].texto, "ctrl+shift+1")
        self.assertNotIn("musica_ventana", atajos)

    def test_desactivar_con_valor_vacio(self):
        atajos = parsear_atajos({"pausa": ""})
        self.assertNotIn("pausa", atajos)

    def test_las_fijas_sobreviven_a_un_valor_vacio(self):
        atajos = parsear_atajos({accion: "" for accion in ATAJOS_FIJOS})
        for accion, esperado in ATAJOS_FIJOS_DEFAULTS.items():
            self.assertEqual(atajos[accion].texto, esperado)
        for accion in ("velocidad_menos", "velocidad_mas",
                       "volumen_menos", "volumen_mas"):
            self.assertEqual(atajos[accion].texto, ATAJOS_DEFAULTS[accion])

    def test_valor_invalido_cae_al_default(self):
        atajos = parsear_atajos({"pausa": "ctrl+home"})
        # Inválido -> usa el default de pausa (f5).
        self.assertIn("pausa", atajos)
        self.assertEqual(atajos["pausa"].texto, ATAJOS_DEFAULTS["pausa"])

    def test_conflicto_descarta_el_segundo(self):
        # Dos acciones reclamando la misma tecla: la segunda se descarta.
        atajos = parsear_atajos({"pausa": "f3", "detener_tts": "f3"})
        teclas = [a.tecla for a in atajos.values()]
        # 'f3' aparece una sola vez.
        self.assertEqual(teclas.count("f3"), 1)

    def test_override_valido(self):
        atajos = parsear_atajos({"pausa": "alt+j"})
        self.assertEqual(atajos["pausa"].texto, "alt+j")

    def test_ctrl_y_alt_misma_letra_no_chocan(self):
        # 'ctrl+d' (rep_detener) y 'alt+shift+d' (desconectar) conviven.
        atajos = parsear_atajos({})
        self.assertEqual(atajos["rep_detener"].texto, "ctrl+d")
        self.assertEqual(atajos["desconectar"].texto, "alt+shift+d")

    def test_nuevos_atajos_editables_tienen_area_y_grupo(self):
        for accion, valor, area in (
                ("pantalla_completa", "ctrl+f", "ctrl"),
                ("ir_lista", "alt+shift+l", "alt+shift"),
                ("abrir_preferencias", "ctrl+shift+p", "ctrl+shift"),
                ("abrir_historial", "ctrl+shift+h", "ctrl+shift"),
                ("marcar_incidencia", "alt+shift+i", "alt+shift"),
                ("abrir_transmision", "ctrl+shift+t", "ctrl+shift"),
                ("mostrar_obs", "ctrl+shift+o", "ctrl+shift"),
                ("copiar_enlace", "alt+shift+e", "alt+shift"),
                ("anunciar_autor", "f3", "f"),
                ("describir_escena", "ctrl+f2", "f"),
                ("consulta_rapida_ia", "ctrl+shift+f2", "f"),
                ("obs_micro", "alt+shift+m", "alt+shift"),
                ("avisos_sobrecarga", "alt+shift+a", "alt+shift"),
                ("musica_ventana", "ctrl+shift+m", "ctrl+shift"),
                ("preguntar_ia", "ctrl+shift+i", "ctrl+shift"),
                ("musica_silenciar", "ctrl+alt+m", "ctrl+alt"),
                ("musica_aleatorio", "ctrl+alt+a", "ctrl+alt"),
                ("musica_repetir", "ctrl+alt+r", "ctrl+alt"),
                ("musica_detener", "ctrl+alt+d", "ctrl+alt"),
                ("musica_adelantar", "ctrl+alt+shift+right", "ctrl+alt"),
                ("musica_retroceder", "ctrl+alt+shift+left", "ctrl+alt")):
            self.assertEqual(ATAJOS_DEFAULTS[accion], valor)
            self.assertTrue(atajo_valido_para_area(accion, valor),
                            f"{accion} no tiene un atajo válido para su área")
            self.assertEqual(ATAJOS_AREA[accion], area)
            self.assertNotIn(accion, ATAJOS_FIJOS)
            self.assertIn(accion, {
                accion_grupo for _, acciones in ATAJOS_GRUPOS for accion_grupo in acciones
            })

    def test_grupo_de_musica_justo_antes_del_de_fijos(self):
        titulos = [titulo for titulo, _acciones in ATAJOS_GRUPOS]
        self.assertEqual(titulos[-3], "Música (Ctrl+Alt)")
        self.assertEqual(titulos[-2], "Ventana y navegación (fijos)")
        self.assertEqual(titulos[-1], "Mensajes recientes del chat (fijos)")
        self.assertEqual(_AREA_POR_GRUPO[5], "ctrl+alt")
        self.assertIsNone(_AREA_POR_GRUPO[6])
        self.assertIsNone(_AREA_POR_GRUPO[7])
        self.assertEqual(len(titulos), len(_AREA_POR_GRUPO))

    def test_las_acciones_de_musica_solo_aceptan_ctrl_alt(self):
        acciones = dict(ATAJOS_GRUPOS)["Música (Ctrl+Alt)"]
        self.assertEqual(len(acciones), 12)
        for accion in acciones:
            with self.subTest(accion=accion):
                self.assertEqual(ATAJOS_AREA[accion], "ctrl+alt")
                self.assertTrue(atajo_valido_para_area(
                    accion, ATAJOS_DEFAULTS[accion]))
                for otra in ("ctrl+p", "alt+p", "f5", "ctrl+shift+p"):
                    self.assertFalse(atajo_valido_para_area(accion, otra))
        self.assertEqual(detectar_conflictos_atajos({}), [])
        self.assertTrue(all(accion in parsear_atajos({}) for accion in acciones))

    def test_menus_usan_el_sistema_para_los_nuevos_atajos(self):
        fuente = inspect.getsource(gui_menu.construir_menu)
        fuente += inspect.getsource(gui_menu._construir_menu_transmision)
        fuente += inspect.getsource(gui_menu._construir_menu_ver)
        fuente += inspect.getsource(gui_menu._construir_menu_musica)
        fuente += inspect.getsource(gui_menu._construir_menu_ayuda)
        self.assertIn('._accel("ir_lista")', fuente)
        self.assertIn('._accel("pantalla_completa")', fuente)
        self.assertIn('._accel("abrir_historial")', fuente)
        self.assertIn('._accel("abrir_preferencias")', fuente)
        self.assertIn('._accel("marcar_incidencia")', fuente)
        self.assertIn('._accel("abrir_transmision")', fuente)
        self.assertIn('._accel("mostrar_obs")', fuente)
        self.assertIn('._accel("copiar_enlace")', fuente)
        self.assertIn('._accel("anunciar_autor")', fuente)
        # Los diez recientes se arman en un bucle con su etiqueta y su _accel.
        self.assertIn("ETIQUETAS[accion] + frame._accel(accion)", fuente)
        self.assertIn('._accel("describir_escena")', fuente)
        self.assertIn('._accel("consulta_rapida_ia")', fuente)
        self.assertIn('._accel("obs_micro")', fuente)
        self.assertIn('._accel("avisos_sobrecarga")', fuente)
        self.assertIn('._accel("musica_play")', fuente)
        self.assertIn('._accel("musica_siguiente")', fuente)
        self.assertIn('._accel("musica_anterior")', fuente)
        self.assertIn('._accel("musica_vol_mas")', fuente)
        self.assertIn('._accel("musica_vol_menos")', fuente)
        self.assertIn('._accel("musica_que_suena")', fuente)
        self.assertIn('._accel("musica_ventana")', fuente)
        self.assertIn('._accel("preguntar_ia")', fuente)
        self.assertIn('._accel("musica_silenciar")', fuente)
        self.assertIn('._accel("musica_aleatorio")', fuente)
        self.assertIn('._accel("musica_repetir")', fuente)
        self.assertIn('._accel("musica_detener")', fuente)
        self.assertIn('._accel("musica_adelantar")', fuente)
        self.assertIn('._accel("musica_retroceder")', fuente)
        self.assertNotIn("musica_listas", fuente)
        self.assertNotIn("\\tAlt+L", fuente)
        self.assertNotIn("\\tCtrl+F", fuente)

    def test_conflicto_incluye_las_fijas(self):
        self.assertEqual(
            detectar_conflictos_atajos({"pausa": "f6"}),
            [("pausa", "region_siguiente", "f6")])

    def test_captura_rechaza_fija_incluso_si_la_gramatica_no_la_admite(self):
        resultado = atajos_captura.resolver(
            "ir_lista", "alt+f4", {"ir_lista": "alt+l", "salir": "alt+f4"})
        self.assertEqual(resultado, (
            "rechazado", None,
            "Ya lo usa: Salir de la aplicación. Elige otra."))

    def test_rechazo_muestra_aviso_y_vuelve_a_capturar(self):
        import wx
        pagina = preferencias_atajos.PaginaAtajos.__new__(
            preferencias_atajos.PaginaAtajos)
        pagina._ventana = mock.Mock()
        boton = mock.Mock()
        pagina._capturando_atajo = ("ir_lista", "Ir a la lista del panel actual")
        pagina._valores_atajo = {"ir_lista": "alt+l", "salir": "alt+f4"}
        pagina._botones_atajo = {"ir_lista": boton}
        evento = mock.Mock()
        evento.GetKeyCode.return_value = wx.WXK_F4
        evento.GetModifiers.return_value = wx.MOD_ALT
        texto = "Ya lo usa: Salir de la aplicación. Elige otra."
        anuncios = []
        with mock.patch.object(preferencias_atajos, "anunciar",
                               side_effect=anuncios.append), \
                mock.patch.object(gui_preferencias.wx, "MessageBox") as aviso:
            pagina._on_tecla_captura(evento)
        aviso.assert_called_once_with(
            texto, preferencias_atajos.APP_NAME, wx.OK | wx.ICON_ERROR,
            pagina._ventana)
        boton.SetFocus.assert_called_once_with()
        self.assertEqual(pagina._capturando_atajo,
                         ("ir_lista", "Ir a la lista del panel actual"))
        self.assertEqual(anuncios, [texto,
                                    atajos_captura.texto_de_espera(
                                        "Ir a la lista del panel actual",
                                        "Debe ser Alt+Mayús y una tecla (por ejemplo Alt+Mayús+C).")])

    def test_arranque_anuncia_la_accion_que_pierde(self):
        anuncios = []
        with mock.patch.object(gui, "anunciar", side_effect=anuncios.append):
            gui.anunciar_conflictos_atajos({"pausa": "f6"})
        self.assertEqual(anuncios, [
            "Conflicto de atajos: pausa se quedó sin atajo porque "
            "region_siguiente usa f6."
        ])


    def test_construccion_del_frame_anuncia_los_conflictos(self):
        frame = gui.YTChatFrame.__new__(gui.YTChatFrame)
        configuracion = {"atajos_raw": {"pausa": "f6"}}
        with mock.patch.object(gui.wx.Frame, "__init__", return_value=None), \
                mock.patch.object(gui.YTChatFrame, "SetBackgroundColour"), \
                mock.patch.object(gui.YTChatFrame, "_build_menubar"), \
                mock.patch.object(gui.YTChatFrame, "_build_ui"), \
                mock.patch.object(gui.YTChatFrame, "_bind_events"), \
                mock.patch.object(gui.YTChatFrame, "_init_timer"), \
                mock.patch.object(gui.YTChatFrame, "Centre"), \
                mock.patch.object(gui, "anunciar_conflictos_atajos") as anunciar:
            gui.YTChatFrame.__init__(frame, None, configuracion, None, None, None, None)

        anunciar.assert_called_once_with(configuracion["atajos_raw"])


if __name__ == "__main__":
    unittest.main()
