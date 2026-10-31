"""Pruebas del diálogo de datos del directo de YouTube.

TestResultadoDirecto no crea ventanas y se corre aquí. TestDialogoDirectoVentana
crea un wx.Dialog de verdad: NO correr en esta máquina (abre ventanas); las
corre el dueño.
"""

import unittest
from unittest import mock

try:
    import wx
    _HAY_WX = True
except Exception:
    _HAY_WX = False

from bellbird.ui import gui_directo_youtube as directo
from tests.pseudo_prueba import con_pseudo, textos_sin_marcar
from tests.ventanas_prueba import destruir
from bellbird.youtube.emision import (
    ETIQUETAS_PRIVACIDAD,
    PRIVACIDADES,
    EmisionError,
    titulo_por_defecto,
)


def _controles_en_orden(dialogo):
    """Hijos en orden de Tab, bajando dentro de la zona con desplazamiento."""
    orden = []
    for hijo in dialogo.GetChildren():
        if isinstance(hijo, wx.ScrolledWindow):
            orden.extend(hijo.GetChildren())
        else:
            orden.append(hijo)
    return orden


class TestResultadoDirecto(unittest.TestCase):
    # Lógica pura del diálogo, sin ventanas.

    def test_titulo_vacio_falla_como_cuerpo_emision(self):
        with self.assertRaises(EmisionError) as contexto:
            directo.resultado_directo("   ", "algo", "unlisted")
        self.assertEqual(str(contexto.exception),
                         "Falta el título del directo.")

    def test_recorta_titulo_a_cien(self):
        datos = directo.resultado_directo("x" * 150, "", "public")
        self.assertEqual(len(datos["titulo"]), 100)

    def test_privacidad_invalida_cae_a_no_listado(self):
        datos = directo.resultado_directo("Hola", "", "solo-yo")
        self.assertEqual(datos["privacidad"], "unlisted")

    def test_devuelve_los_valores_con_opciones(self):
        datos = directo.resultado_directo("Hola", "línea1\nlínea2", "private")
        self.assertEqual(datos, {
            "titulo": "Hola", "descripcion": "línea1\nlínea2",
            "privacidad": "private", "latencia": "normal", "ninos": False,
            "dvr": True, "categoria": "", "etiquetas": [], "miniatura": "",
            "lista": "", "lista_titulo": ""})

    def test_lista_y_titulo_se_recortan(self):
        datos = directo.resultado_directo(
            "Hola", "", "public", lista=" PL9 ", lista_titulo=" Mi lista ")
        self.assertEqual(datos["lista"], "PL9")
        self.assertEqual(datos["lista_titulo"], "Mi lista")

    def test_lista_vacia_deja_titulo_vacio(self):
        datos = directo.resultado_directo(
            "Hola", "", "public", lista="", lista_titulo="Algo")
        self.assertEqual(datos["lista"], "")
        self.assertEqual(datos["lista_titulo"], "")

    def test_opciones_se_conservan(self):
        datos = directo.resultado_directo(
            "Hola", "", "public", latencia="ultraLow", ninos=True, dvr=False,
            categoria="20", etiquetas="uno, dos", miniatura=" C:\\x\\f.jpg ")
        self.assertEqual(datos["latencia"], "ultraLow")
        self.assertTrue(datos["ninos"])
        self.assertFalse(datos["dvr"])
        self.assertEqual(datos["categoria"], "20")
        self.assertEqual(datos["miniatura"], "C:\\x\\f.jpg")

    def test_latencia_invalida_cae_a_normal(self):
        datos = directo.resultado_directo("Hola", "", "public",
                                          latencia="turbo")
        self.assertEqual(datos["latencia"], "normal")

    def test_categoria_invalida_queda_vacia(self):
        datos = directo.resultado_directo("Hola", "", "public",
                                          categoria="999")
        self.assertEqual(datos["categoria"], "")

    def test_etiquetas_se_arman_con_etiquetas_de_texto(self):
        datos = directo.resultado_directo("Hola", "", "public",
                                          etiquetas="uno, dos , uno")
        self.assertEqual(datos["etiquetas"], ["uno", "dos"])


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestDialogoDirectoVentana(unittest.TestCase):
    # Con ventana: las corre el dueño. No correr aquí.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def _dialogo(self, **kwargs):
        dialogo = directo.DialogoDirectoYoutube(None, **kwargs)
        self.addCleanup(destruir, dialogo)
        return dialogo

    def test_titulo_vacio_usa_el_por_defecto_seleccionado(self):
        from datetime import datetime
        dialogo = self._dialogo(titulo="")
        self.assertEqual(dialogo.txt_titulo.GetValue(),
                         titulo_por_defecto(datetime.now()))
        inicio, fin = dialogo.txt_titulo.GetSelection()
        self.assertEqual((inicio, fin),
                         (0, len(dialogo.txt_titulo.GetValue())))

    def test_titulo_limitado_a_100_caracteres(self):
        with mock.patch.object(wx.TextCtrl, "SetMaxLength") as maximo:
            dialogo = self._dialogo(titulo="Hola")
        maximo.assert_called_once_with(100)

    def test_nombres_accesibles_y_rotulos(self):
        dialogo = self._dialogo(titulo="Hola", descripcion="d",
                                privacidad="public")
        self.assertEqual(dialogo.txt_titulo.GetName(), "Título del directo")
        self.assertEqual(dialogo.txt_descripcion.GetName(),
                         "Descripción del directo")
        self.assertEqual(dialogo.cho_privacidad.GetName(), "Privacidad")
        textos = [h.GetLabel() for h in _controles_en_orden(dialogo)
                  if isinstance(h, wx.StaticText)]
        self.assertIn("Título:", textos)
        self.assertIn("Descripción, opcional:", textos)
        self.assertIn("Privacidad:", textos)

    def test_orden_de_tab_y_privacidad(self):
        dialogo = self._dialogo(titulo="Hola", privacidad="private")
        orden = [h.GetName() for h in _controles_en_orden(dialogo)
                 if h.GetName() in ("Título del directo",
                                    "Descripción del directo", "Privacidad")]
        self.assertEqual(orden, ["Título del directo",
                                 "Descripción del directo", "Privacidad"])
        self.assertEqual(
            [dialogo.cho_privacidad.GetString(i)
             for i in range(dialogo.cho_privacidad.GetCount())],
            [ETIQUETAS_PRIVACIDAD[p] for p in PRIVACIDADES])
        self.assertEqual(dialogo.cho_privacidad.GetSelection(),
                         PRIVACIDADES.index("private"))
        estilo = dialogo.txt_descripcion.GetWindowStyle()
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertFalse(estilo & wx.TE_PROCESS_TAB)

    def test_titulo_con_ancho_minimo_para_que_no_se_corte(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertGreaterEqual(
            dialogo.txt_titulo.GetMinSize().GetWidth(), 420)

    def test_botones_y_foco(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertEqual(dialogo.btn_crear.GetLabel(), "&Transmitir")
        self.assertEqual(dialogo.btn_crear.GetId(), wx.ID_OK)
        self.assertEqual(dialogo.btn_cancelar.GetLabel(), "C&ancelar")
        self.assertEqual(dialogo.btn_cancelar.GetId(), wx.ID_CANCEL)
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_revision_a_la_vista_lectura_y_orden(self):
        from bellbird.obs import obs_prevuelo
        revision = obs_prevuelo.Revision(
            "YouTube", "YouTube", "Sin Título", 1280, 720, "Principal",
            (), (), None, ())
        dialogo = self._dialogo(titulo="Hola", revision=revision)
        self.assertEqual(dialogo.txt_revision.GetName(), "Revisión de OBS")
        self.assertEqual(dialogo.txt_revision.GetValue(),
                         obs_prevuelo.frase_revision(revision))
        estilo = dialogo.txt_revision.GetWindowStyle()
        self.assertTrue(estilo & wx.TE_MULTILINE)
        self.assertTrue(estilo & wx.TE_READONLY)
        orden = [h.GetName() for h in _controles_en_orden(dialogo)
                 if h.GetName() in ("Título del directo",
                                    "Descripción del directo", "Privacidad",
                                    "Revisión de OBS")]
        self.assertEqual(orden, ["Título del directo",
                                 "Descripción del directo", "Privacidad",
                                 "Revisión de OBS"])
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_revision_con_problemas_enfoca_cancelar(self):
        from bellbird.obs import obs_prevuelo
        revision = obs_prevuelo.Revision(
            "YouTube", "YouTube", "Sin Título", 1280, 720, "Principal",
            (), (), None, ("La imagen está vacía.",))
        dialogo = self._dialogo(titulo="Hola", revision=revision)
        self.assertIn("La imagen está vacía.",
                      dialogo.txt_revision.GetValue())
        self.assertEqual(dialogo.FindFocus(), dialogo.btn_cancelar)

    def test_crear_con_titulo_vacio_anuncia_y_sigue_abierto(self):
        dialogo = self._dialogo(titulo="Hola")
        dialogo.txt_titulo.SetValue("   ")
        with mock.patch.object(directo, "anunciar") as anunciar, \
                mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_crear(mock.Mock())
        anunciar.assert_called_once_with("Falta el título del directo.")
        fin.assert_not_called()
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_crear_devuelve_las_opciones(self):
        dialogo = self._dialogo(titulo="Hola", latencia="low", ninos=True,
                                dvr=False, categoria="22", etiquetas="uno, dos",
                                miniatura="C:\\x\\foto.jpg")
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_crear(mock.Mock())
        self.assertEqual(dialogo._datos["latencia"], "low")
        self.assertTrue(dialogo._datos["ninos"])
        self.assertFalse(dialogo._datos["dvr"])
        self.assertEqual(dialogo._datos["categoria"], "22")
        self.assertEqual(dialogo._datos["etiquetas"], ["uno", "dos"])
        self.assertEqual(dialogo._datos["miniatura"], "C:\\x\\foto.jpg")
        fin.assert_called_once_with(wx.ID_OK)

    def test_nombres_accesibles_de_las_opciones(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertEqual(dialogo.cho_latencia.GetName(), "Latencia")
        self.assertEqual(dialogo.chk_ninos.GetName(), "Hecho para niños")
        self.assertEqual(dialogo.chk_dvr.GetName(), "Permitir rebobinar")
        self.assertEqual(dialogo.cho_categoria.GetName(), "Categoría")
        self.assertEqual(dialogo.txt_etiquetas.GetName(), "Etiquetas")
        self.assertEqual(dialogo.txt_miniatura.GetName(), "Miniatura")
        self.assertEqual(dialogo.btn_elegir_miniatura.GetName(),
                         "Elegir miniatura")
        self.assertEqual(dialogo.btn_quitar_miniatura.GetName(),
                         "Eliminar miniatura")
        self.assertEqual(dialogo.cho_lista.GetName(),
                         "Lista de reproducción")
        self.assertEqual(dialogo.btn_cargar_listas.GetName(),
                         "Cargar listas")

    def test_rotulos_con_mnemonicas(self):
        dialogo = self._dialogo(titulo="Hola")
        textos = [h.GetLabel() for h in _controles_en_orden(dialogo)
                  if isinstance(h, wx.StaticText)]
        self.assertIn("&Latencia:", textos)
        self.assertIn("Cate&goría:", textos)
        self.assertIn("&Etiquetas, separadas por comas:", textos)
        self.assertEqual(dialogo.chk_ninos.GetLabel(),
                         "Hecho para &niños (YouTube apaga el chat)")
        self.assertEqual(dialogo.chk_dvr.GetLabel(),
                         "Permitir re&bobinar el directo")
        self.assertEqual(dialogo.btn_elegir_miniatura.GetLabel(),
                         "Elegir &miniatura…")
        self.assertEqual(dialogo.btn_quitar_miniatura.GetLabel(),
                         "El&iminar miniatura")
        self.assertIn("Lista de re&producción:", textos)
        self.assertEqual(dialogo.btn_cargar_listas.GetLabel(),
                         "Ca&rgar listas")

    def test_casillas_con_borde_de_arriba_como_los_demas_controles(self):
        dialogo = self._dialogo(titulo="Hola")
        for casilla in (dialogo.chk_ninos, dialogo.chk_dvr):
            with self.subTest(casilla=casilla.GetName()):
                partida = casilla.GetContainingSizer().GetItem(casilla)
                self.assertTrue(partida.GetFlag() & wx.TOP)
                self.assertEqual(partida.GetBorder(), 6)

    def test_orden_de_tab_con_las_opciones(self):
        dialogo = self._dialogo(titulo="Hola")
        nombres = ("Título del directo", "Descripción del directo",
                   "Privacidad", "Latencia", "Hecho para niños",
                   "Permitir rebobinar", "Categoría", "Etiquetas",
                    "Miniatura", "Elegir miniatura", "Eliminar miniatura",
                   "Lista de reproducción", "Cargar listas",
                   "Revisión de OBS")
        orden = [h.GetName() for h in _controles_en_orden(dialogo)
                 if h.GetName() in nombres]
        self.assertEqual(orden, list(nombres))

    def test_latencia_choices_y_seleccion(self):
        from bellbird.youtube.emision import ETIQUETAS_LATENCIA, LATENCIAS
        dialogo = self._dialogo(titulo="Hola", latencia="ultraLow")
        self.assertEqual(
            [dialogo.cho_latencia.GetString(i)
             for i in range(dialogo.cho_latencia.GetCount())],
            [ETIQUETAS_LATENCIA[l] for l in LATENCIAS])
        self.assertEqual(dialogo.cho_latencia.GetSelection(),
                         LATENCIAS.index("ultraLow"))

    def test_categoria_choices_y_seleccion(self):
        from bellbird.youtube.emision import CATEGORIAS
        dialogo = self._dialogo(titulo="Hola", categoria="20")
        self.assertEqual(
            [dialogo.cho_categoria.GetString(i)
             for i in range(dialogo.cho_categoria.GetCount())],
            [texto for _id, texto in CATEGORIAS])
        self.assertEqual(dialogo.cho_categoria.GetSelection(),
                         [i for i, (id_, _t) in enumerate(CATEGORIAS)
                          if id_ == "20"][0])

    def test_miniatura_muestra_nombre_o_ninguna(self):
        dialogo = self._dialogo(titulo="Hola", miniatura="C:\\x\\foto.jpg")
        self.assertEqual(dialogo.txt_miniatura.GetValue(), "foto.jpg")
        self.assertTrue(
            dialogo.txt_miniatura.GetWindowStyle() & wx.TE_READONLY)
        otro = self._dialogo(titulo="Hola")
        self.assertEqual(otro.txt_miniatura.GetValue(), "Ninguna")

    def test_miniatura_entra_en_el_tab(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertTrue(
            dialogo.txt_miniatura.AcceptsFocusFromKeyboard())
        dialogo.txt_etiquetas.SetFocus()
        dialogo.txt_etiquetas.Navigate()
        self.assertIs(wx.Window.FindFocus(), dialogo.txt_miniatura)

    def test_elegir_miniatura_valida(self):
        dialogo = self._dialogo(titulo="Hola")
        with mock.patch.object(directo.wx, "FileDialog") as fd, \
                mock.patch.object(directo, "error_de_miniatura",
                                  return_value=None), \
                mock.patch.object(directo, "anunciar") as anunciar:
            cuadro = fd.return_value.__enter__.return_value
            cuadro.ShowModal.return_value = wx.ID_OK
            cuadro.GetPath.return_value = "C:\\x\\foto.png"
            dialogo._al_elegir_miniatura(mock.Mock())
        self.assertEqual(dialogo.txt_miniatura.GetValue(), "foto.png")
        anunciar.assert_called_once_with("Miniatura: foto.png")

    def test_elegir_miniatura_invalida_no_cambia(self):
        dialogo = self._dialogo(titulo="Hola")
        with mock.patch.object(directo.wx, "FileDialog") as fd, \
                mock.patch.object(directo, "error_de_miniatura",
                                  return_value="La miniatura pasa de 2 MB."), \
                mock.patch.object(directo, "anunciar") as anunciar:
            cuadro = fd.return_value.__enter__.return_value
            cuadro.ShowModal.return_value = wx.ID_OK
            cuadro.GetPath.return_value = "C:\\x\\grande.jpg"
            dialogo._al_elegir_miniatura(mock.Mock())
        self.assertEqual(dialogo.txt_miniatura.GetValue(), "Ninguna")
        anunciar.assert_called_once_with("La miniatura pasa de 2 MB.")

    def test_quitar_miniatura(self):
        dialogo = self._dialogo(titulo="Hola", miniatura="C:\\x\\foto.jpg")
        with mock.patch.object(directo, "anunciar") as anunciar:
            dialogo._al_quitar_miniatura(mock.Mock())
        self.assertEqual(dialogo.txt_miniatura.GetValue(), "Ninguna")
        anunciar.assert_called_once_with("Sin miniatura.")

    def test_selector_lista_sin_recordada(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertEqual(dialogo.cho_lista.GetCount(), 1)
        self.assertEqual(dialogo.cho_lista.GetString(0), "Ninguna")
        self.assertEqual(dialogo.cho_lista.GetSelection(), 0)

    def test_selector_lista_con_recordada(self):
        dialogo = self._dialogo(titulo="Hola", lista="PL9",
                                lista_titulo="Mi lista")
        self.assertEqual(
            [dialogo.cho_lista.GetString(i)
             for i in range(dialogo.cho_lista.GetCount())],
            ["Ninguna", "Mi lista"])
        self.assertEqual(dialogo.cho_lista.GetSelection(), 1)

    def test_boton_cargar_listas_sin_cargador_deshabilitado(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertFalse(dialogo.btn_cargar_listas.IsEnabled())

    def test_boton_cargar_listas_con_cargador_habilitado(self):
        dialogo = self._dialogo(titulo="Hola", cargar_listas=lambda: [])
        self.assertTrue(dialogo.btn_cargar_listas.IsEnabled())

    def test_listas_ok_rellena_y_anuncia(self):
        dialogo = self._dialogo(titulo="Hola", cargar_listas=lambda: [])
        with mock.patch.object(directo, "anunciar") as anunciar:
            dialogo._listas_ok([("PL1", "Uno"), ("PL2", "Dos")])
        self.assertEqual(
            [dialogo.cho_lista.GetString(i)
             for i in range(dialogo.cho_lista.GetCount())],
            ["Ninguna", "Uno", "Dos"])
        anunciar.assert_called_once_with("2 listas.")

    def test_listas_ok_una_anuncia_en_singular(self):
        dialogo = self._dialogo(titulo="Hola", cargar_listas=lambda: [])
        with mock.patch.object(directo, "anunciar") as anunciar:
            dialogo._listas_ok([("PL1", "Uno")])
        anunciar.assert_called_once_with("1 lista.")

    def test_listas_ok_vacia_anuncia_sin_listas(self):
        dialogo = self._dialogo(titulo="Hola", cargar_listas=lambda: [])
        with mock.patch.object(directo, "anunciar") as anunciar:
            dialogo._listas_ok([])
        anunciar.assert_called_once_with("El canal no tiene listas.")

    def test_listas_ok_conserva_la_elegida(self):
        dialogo = self._dialogo(titulo="Hola", lista="PL2",
                                lista_titulo="Dos",
                                cargar_listas=lambda: [])
        with mock.patch.object(directo, "anunciar"):
            dialogo._listas_ok([("PL1", "Uno"), ("PL2", "Dos")])
        self.assertEqual(dialogo.cho_lista.GetSelection(), 2)
        self.assertEqual(dialogo._opcion_lista_elegida(), ("PL2", "Dos"))

    def test_listas_fallo_anuncia_y_conserva(self):
        dialogo = self._dialogo(titulo="Hola", lista="PL9",
                                lista_titulo="Guardada",
                                cargar_listas=lambda: [])
        with mock.patch.object(directo, "anunciar") as anunciar:
            dialogo._listas_fallo(RuntimeError("sin red"))
        anunciar.assert_called_once_with(
            "No se pudieron cargar las listas: "
            "Error de la API de YouTube: sin red")
        self.assertEqual(dialogo._opcion_lista_elegida(),
                         ("PL9", "Guardada"))

    def test_crear_devuelve_la_lista_elegida(self):
        dialogo = self._dialogo(titulo="Hola", lista="PL9",
                                lista_titulo="Mi lista",
                                cargar_listas=lambda: [])
        with mock.patch.object(dialogo, "EndModal") as fin:
            dialogo._al_crear(mock.Mock())
        self.assertEqual(dialogo._datos["lista"], "PL9")
        self.assertEqual(dialogo._datos["lista_titulo"], "Mi lista")
        fin.assert_called_once_with(wx.ID_OK)

    def test_zona_con_desplazamiento_con_los_botones_fuera(self):
        dialogo = self._dialogo(titulo="Hola")
        zona = dialogo.zona_desplazamiento
        self.assertIsInstance(zona, wx.ScrolledWindow)
        self.assertTrue(zona.GetWindowStyle() & wx.VSCROLL)
        self.assertTrue(zona.GetWindowStyle() & wx.TAB_TRAVERSAL)
        self.assertIs(dialogo.txt_titulo.GetParent(), zona)
        self.assertIs(dialogo.txt_descripcion.GetParent(), zona)
        self.assertIs(dialogo.txt_revision.GetParent(), zona)
        self.assertIs(dialogo.btn_crear.GetParent(), dialogo)
        self.assertIs(dialogo.btn_cancelar.GetParent(), dialogo)
        self.assertNotIn(dialogo.btn_crear, zona.GetChildren())
        hijos = list(dialogo.GetChildren())
        self.assertLess(hijos.index(zona),
                        hijos.index(dialogo.btn_crear))

    def test_alto_entre_300_y_700_con_pantalla_real(self):
        dialogo = self._dialogo(titulo="Hola")
        alto = dialogo.GetSize().height
        self.assertGreater(alto, 300)
        self.assertLessEqual(alto, 700)

    def test_alto_no_pasa_del_area_de_trabajo(self):
        area = wx.Rect(0, 0, 800, 500)
        with mock.patch.object(wx.Display, "GetClientArea",
                               return_value=area):
            dialogo = self._dialogo(titulo="Hola")
        self.assertLessEqual(dialogo.GetSize().height, 500)

    def test_zona_virtual_alcanza_para_todo_el_contenido(self):
        dialogo = self._dialogo(titulo="Hola")
        zona = dialogo.zona_desplazamiento
        ultimo = dialogo.txt_revision
        abajo = ultimo.GetPosition().y + ultimo.GetSize().height
        self.assertGreaterEqual(zona.GetVirtualSize().height, abajo)

    def test_orden_de_tab_completo_con_el_pie_al_final(self):
        dialogo = self._dialogo(titulo="Hola")
        nombres = ("Título del directo", "Descripción del directo",
                   "Privacidad", "Latencia", "Hecho para niños",
                   "Permitir rebobinar", "Categoría", "Etiquetas",
                    "Miniatura", "Elegir miniatura", "Eliminar miniatura",
                   "Lista de reproducción", "Cargar listas",
                   "Revisión de OBS")
        orden = [h.GetName() for h in _controles_en_orden(dialogo)
                 if h.GetName() in nombres]
        self.assertEqual(orden, list(nombres))
        hijos = list(dialogo.GetChildren())
        self.assertLess(hijos.index(dialogo.zona_desplazamiento),
                        hijos.index(dialogo.btn_cancelar))

    def test_descripcion_conserva_tres_lineas_de_alto(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertEqual(
            dialogo.txt_descripcion.GetMinSize().height,
            3 * dialogo.txt_descripcion.GetCharHeight() + 12)

    def test_miniatura_sin_flechas_de_desplazamiento(self):
        dialogo = self._dialogo(titulo="Hola")
        self.assertTrue(dialogo.txt_miniatura.GetWindowStyle()
                        & wx.TE_NO_VSCROLL)

    def test_pedir_datos_devuelve_dict_y_none(self):
        dialogo = self._dialogo(titulo="Hola")
        with mock.patch.object(directo, "DialogoDirectoYoutube",
                               return_value=dialogo), \
                mock.patch.object(dialogo, "Destroy"):
            dialogo._datos = {"titulo": "Hola", "descripcion": "",
                              "privacidad": "unlisted"}
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_OK):
                self.assertEqual(
                    directo.pedir_datos_directo(None, "Hola", "", "unlisted"),
                    {"titulo": "Hola", "descripcion": "",
                     "privacidad": "unlisted"})
            with mock.patch.object(dialogo, "ShowModal",
                                   return_value=wx.ID_CANCEL):
                self.assertIsNone(
                    directo.pedir_datos_directo(None, "Hola", "", "unlisted"))


# Textos que armaban otros módulos y ya pasan por gettext: las opciones de
# privacidad, latencia y categoría de `bellbird/youtube/emision.py`
# (ETIQUETAS_PRIVACIDAD, ETIQUETAS_LATENCIA y CATEGORIAS, traducidas donde
# se muestran) y el Ninguna de `opciones_lista`, del mismo módulo. El
# título de la lista recordada es un dato del usuario y va como propio.
# La comparación es exacta en los dos sentidos: falla si aparece un texto
# nuevo sin envolver y si un pendiente vuelve al recorrido.
PENDIENTES_DIRECTO_YOUTUBE = ()


@unittest.skipUnless(_HAY_WX, "wxPython no está instalado")
class TestPseudoDirectoYoutubeVentana(unittest.TestCase):
    # Abre ventanas.

    def setUp(self):
        self.app = wx.App.Get() or wx.App(False)

    def test_no_queda_ningun_texto_visible_sin_envolver(self):
        with con_pseudo():
            dialogo = directo.DialogoDirectoYoutube(
                None, titulo="Hola", lista="PL9", lista_titulo="Mi lista",
                cargar_listas=lambda: [])
            sin_marcar = textos_sin_marcar(dialogo, propios=("Mi lista",))
        self.addCleanup(destruir, dialogo)
        self.assertEqual(sorted(sin_marcar),
                         sorted(PENDIENTES_DIRECTO_YOUTUBE))


class TestPseudoAnunciosDirectoYoutube(unittest.TestCase):
    # Sin ventana: los controles van con dobles, así se corre acá. Los
    # anuncios que arman otros módulos (`error_de_miniatura`, el mensaje
    # de la API y `str(exc)` de `emision`) no entran.

    def setUp(self):
        self.captados = []
        parche = mock.patch.object(directo, "anunciar",
                                   self.captados.append)
        parche.start()
        self.addCleanup(parche.stop)
        pseudo = con_pseudo()
        pseudo.__enter__()
        self.addCleanup(pseudo.__exit__, None, None, None)
        # El doble se crea sin __init__ y para wx es falso: finge una
        # ventana viva para que los métodos pasen la guarda `if not self`.
        parche_vivo = mock.patch.object(
            directo.DialogoDirectoYoutube, "__bool__", lambda _s: True)
        parche_vivo.start()
        self.addCleanup(parche_vivo.stop)

    def _exigir_marcados(self, cantidad):
        self.assertEqual(len(self.captados), cantidad)
        for frase in self.captados:
            self.assertTrue(frase.startswith("[¡"), frase)
        del self.captados[:]

    def _dialogo(self):
        dialogo = directo.DialogoDirectoYoutube.__new__(
            directo.DialogoDirectoYoutube)
        dialogo._miniatura = ""
        dialogo._cargar_listas = lambda: []
        dialogo._opciones_lista = [("", "Ninguna")]
        dialogo.txt_miniatura = mock.Mock()
        dialogo.cho_lista = mock.Mock()
        dialogo.cho_lista.GetSelection.return_value = 0
        dialogo.btn_cargar_listas = mock.Mock()
        return dialogo

    def test_quitar_miniatura_anuncia_marcado(self):
        dialogo = self._dialogo()
        dialogo._miniatura = "C:\\x\\foto.jpg"
        dialogo._al_quitar_miniatura(mock.Mock())
        self._exigir_marcados(1)

    def test_cargar_listas_anuncia_marcado_sin_hilo(self):
        dialogo = self._dialogo()
        with mock.patch.object(directo.diagnostico, "crear_hilo") as hilos:
            dialogo._al_cargar_listas(mock.Mock())
        dialogo.btn_cargar_listas.Disable.assert_called_once_with()
        hilos.assert_called_once()
        self._exigir_marcados(1)

    def test_listas_ok_marca_los_tres_caminos(self):
        dialogo = self._dialogo()
        dialogo._listas_ok([])
        self._exigir_marcados(1)
        dialogo._listas_ok([("PL1", "Uno")])
        self._exigir_marcados(1)
        dialogo._listas_ok([("PL1", "Uno"), ("PL2", "Dos")])
        self._exigir_marcados(1)

    def test_listas_fallo_marca_el_prefijo_propio(self):
        dialogo = self._dialogo()
        dialogo._listas_fallo(RuntimeError("sin red"))
        self._exigir_marcados(1)

    def test_elegir_miniatura_marca_titulo_filtro_y_anuncio(self):
        dialogo = self._dialogo()
        captado = {}

        def fabrica(padre, titulo="", **kwargs):
            captado["titulo"] = titulo
            captado["filtro"] = kwargs.get("wildcard")
            cuadro = mock.MagicMock()
            cuadro.__enter__.return_value = cuadro
            cuadro.ShowModal.return_value = wx.ID_OK
            cuadro.GetPath.return_value = "C:\\x\\foto.png"
            return cuadro

        with mock.patch.object(directo.wx, "FileDialog", fabrica), \
                mock.patch.object(directo, "error_de_miniatura",
                                  return_value=None):
            dialogo._al_elegir_miniatura(mock.Mock())
        self.assertTrue(captado["titulo"].startswith("[¡"))
        self.assertTrue(captado["filtro"].startswith("[¡"))
        self._exigir_marcados(1)


if __name__ == "__main__":
    unittest.main()
