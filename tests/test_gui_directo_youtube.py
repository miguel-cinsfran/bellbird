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

from ytchat.ui import gui_directo_youtube as directo
from ytchat.youtube.emision import (
    ETIQUETAS_PRIVACIDAD,
    PRIVACIDADES,
    EmisionError,
    titulo_por_defecto,
)


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
            "dvr": True, "categoria": "", "etiquetas": [], "miniatura": ""})

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
        self.addCleanup(dialogo.Destroy)
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
        textos = [h.GetLabel() for h in dialogo.GetChildren()
                  if isinstance(h, wx.StaticText)]
        self.assertIn("Título:", textos)
        self.assertIn("Descripción, opcional:", textos)
        self.assertIn("Privacidad:", textos)

    def test_orden_de_tab_y_privacidad(self):
        dialogo = self._dialogo(titulo="Hola", privacidad="private")
        orden = [h.GetName() for h in dialogo.GetChildren()
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
        from ytchat.obs import obs_prevuelo
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
        orden = [h.GetName() for h in dialogo.GetChildren()
                 if h.GetName() in ("Título del directo",
                                    "Descripción del directo", "Privacidad",
                                    "Revisión de OBS")]
        self.assertEqual(orden, ["Título del directo",
                                 "Descripción del directo", "Privacidad",
                                 "Revisión de OBS"])
        self.assertEqual(dialogo.FindFocus(), dialogo.txt_titulo)

    def test_revision_con_problemas_enfoca_cancelar(self):
        from ytchat.obs import obs_prevuelo
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
                         "Quitar miniatura")

    def test_rotulos_con_mnemonicas(self):
        dialogo = self._dialogo(titulo="Hola")
        textos = [h.GetLabel() for h in dialogo.GetChildren()
                  if isinstance(h, wx.StaticText)]
        self.assertIn("&Latencia:", textos)
        self.assertIn("Cate&goría:", textos)
        self.assertIn("&Etiquetas, separadas por comas:", textos)
        self.assertEqual(dialogo.chk_ninos.GetLabel(),
                         "Hecho para &niños (YouTube apaga el chat)")
        self.assertEqual(dialogo.chk_dvr.GetLabel(),
                         "Permitir re&bobinar el directo")
        self.assertEqual(dialogo.btn_elegir_miniatura.GetLabel(),
                         "Elegir &miniatura...")
        self.assertEqual(dialogo.btn_quitar_miniatura.GetLabel(),
                         "&Quitar miniatura")

    def test_orden_de_tab_con_las_opciones(self):
        dialogo = self._dialogo(titulo="Hola")
        nombres = ("Título del directo", "Descripción del directo",
                   "Privacidad", "Latencia", "Hecho para niños",
                   "Permitir rebobinar", "Categoría", "Etiquetas",
                   "Miniatura", "Elegir miniatura", "Quitar miniatura",
                   "Revisión de OBS")
        orden = [h.GetName() for h in dialogo.GetChildren()
                 if h.GetName() in nombres]
        self.assertEqual(orden, list(nombres))

    def test_latencia_choices_y_seleccion(self):
        from ytchat.youtube.emision import ETIQUETAS_LATENCIA, LATENCIAS
        dialogo = self._dialogo(titulo="Hola", latencia="ultraLow")
        self.assertEqual(
            [dialogo.cho_latencia.GetString(i)
             for i in range(dialogo.cho_latencia.GetCount())],
            [ETIQUETAS_LATENCIA[l] for l in LATENCIAS])
        self.assertEqual(dialogo.cho_latencia.GetSelection(),
                         LATENCIAS.index("ultraLow"))

    def test_categoria_choices_y_seleccion(self):
        from ytchat.youtube.emision import CATEGORIAS
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


if __name__ == "__main__":
    unittest.main()
