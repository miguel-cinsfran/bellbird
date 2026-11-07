"""Pruebas del inicio de un directo de YouTube con los datos de un perfil."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from guyrapu.restream import perfiles
from guyrapu.restream.perfiles import Perfil
from guyrapu.ui import inicio_youtube
from guyrapu.youtube.emision import EmisionError


def _perfil(nombre="Uno", youtube=True, directo=None):
    return Perfil(nombre=nombre, canales=(1,), orientacion="horizontal",
                  youtube=youtube, chat="",
                  directo=directo if directo is not None else {
                      "titulo": "Viejo", "descripcion": "Antes",
                      "privacidad": "private", "latencia": "low",
                      "ninos": False, "dvr": True, "categoria": "",
                      "etiquetas": [], "miniatura": "", "lista": "",
                      "lista_titulo": ""})


NUEVO = {"titulo": "Nuevo", "descripcion": "Después",
         "privacidad": "public", "latencia": "normal", "ninos": True,
         "dvr": False, "categoria": "20", "etiquetas": ["uno"],
         "miniatura": "", "lista": "", "lista_titulo": ""}


class TestPerfil(unittest.TestCase):

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta = Path(self.temporal.name) / "perfiles_restream.json"

    def _pedir(self, perfil, pedido=NUEVO, hay=True):
        recibido = {}

        def pedir(_padre, **kwargs):
            recibido.update(kwargs)
            return pedido

        with mock.patch.object(inicio_youtube, "hay_sesion", return_value=hay), \
                mock.patch.object(inicio_youtube, "_cliente",
                                  return_value=mock.Mock()), \
                mock.patch.object(inicio_youtube, "_preparados",
                                  return_value={"marca": True}), \
                mock.patch("guyrapu.ui.gui_directo_youtube.pedir_datos_directo",
                           side_effect=pedir), \
                mock.patch("guyrapu.core.paths.perfiles_restream",
                           return_value=self.ruta):
            return (inicio_youtube.pedir_y_guardar_perfil(
                None, None, perfil, [perfil]), recibido)

    def test_p4_el_cuadro_recibe_lo_ultimo_del_perfil(self):
        _armado, recibido = self._pedir(_perfil())

        self.assertEqual("Viejo", recibido["titulo"])
        self.assertEqual("Antes", recibido["descripcion"])
        self.assertEqual("private", recibido["privacidad"])
        self.assertEqual("low", recibido["latencia"])
        self.assertFalse(recibido["solo_titulo"])
        self.assertEqual("Directo con Restream: Uno",
                         recibido["titulo_ventana"])

    def test_p5_lo_aceptado_se_guarda_en_el_perfil(self):
        armado, _recibido = self._pedir(_perfil())

        actualizado, preparados = armado
        self.assertEqual(NUEVO, actualizado.directo)
        self.assertEqual({"marca": True}, preparados)
        [guardado] = perfiles.cargar(self.ruta)
        self.assertEqual(NUEVO, guardado.directo)

    def test_p5_las_etiquetas_guardadas_como_texto_no_se_parten(self):
        _armado, recibido = self._pedir(_perfil(directo={
            "titulo": "Viejo", "etiquetas": "uno, dos"}))

        self.assertEqual("uno, dos", recibido["etiquetas"])

    def test_un_fallo_al_armar_el_cuerpo_avisa_y_no_transmite(self):
        with mock.patch.object(inicio_youtube, "hay_sesion", return_value=True),                 mock.patch.object(inicio_youtube, "_cliente",
                                  return_value=mock.Mock()),                 mock.patch.object(inicio_youtube, "_preparados",
                                  side_effect=EmisionError(
                                      "Falta el título del directo.")),                 mock.patch("guyrapu.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=NUEVO),                 mock.patch("guyrapu.core.paths.perfiles_restream",
                           return_value=self.ruta),                 mock.patch.object(inicio_youtube, "avisar") as avisar:
            resultado = inicio_youtube.pedir_y_guardar_perfil(
                None, None, _perfil(), [_perfil()])

        self.assertIsNone(resultado)
        avisar.assert_called_once_with("Falta el título del directo.",
                                       error=True)

    def test_p4_sin_youtube_el_cuadro_pide_solo_titulo(self):
        _armado, recibido = self._pedir(_perfil(youtube=False))

        self.assertTrue(recibido["solo_titulo"])
        self.assertEqual("Directo con Restream: Uno",
                         recibido["titulo_ventana"])

    def test_p6_sin_sesion_no_se_transmite_ni_se_guarda(self):
        with mock.patch.object(inicio_youtube, "hay_sesion", return_value=False), \
                mock.patch.object(inicio_youtube, "avisar") as avisar, \
                mock.patch("guyrapu.ui.gui_directo_youtube.pedir_datos_directo") as pedir:
            resultado = inicio_youtube.pedir_y_guardar_perfil(
                None, None, _perfil(), [])
        self.assertIsNone(resultado)
        avisar.assert_called_once_with(
            inicio_youtube._(inicio_youtube.MENSAJE_SIN_GOOGLE),
            "transmision_problema", error=True)
        pedir.assert_not_called()
        self.assertFalse(self.ruta.exists())

    def test_p4_cancelar_no_transmite_ni_guarda(self):
        with mock.patch.object(inicio_youtube, "hay_sesion", return_value=True), \
                mock.patch.object(inicio_youtube, "_cliente",
                                  return_value=mock.Mock()), \
                mock.patch("guyrapu.ui.gui_directo_youtube.pedir_datos_directo",
                           return_value=None), \
                mock.patch("guyrapu.ui.gui.anunciar") as anunciar, \
                mock.patch("guyrapu.core.paths.perfiles_restream",
                           return_value=self.ruta):
            resultado = inicio_youtube.pedir_y_guardar_perfil(
                None, None, _perfil(), [])

        self.assertIsNone(resultado)
        anunciar.assert_called_once_with("No se transmitió.")
        self.assertFalse(self.ruta.exists())


class TestSoloYoutube(unittest.TestCase):

    def test_el_directo_solo_a_youtube_sigue_leyendo_y_guardando_config(self):
        frame = SimpleNamespace(
            _config={"transmision_youtube_titulo": "De config",
                     "transmision_youtube_privacidad": "public"},
            _guardar_datos_directo_youtube=mock.Mock(
                return_value={"titulo": NUEVO["titulo"],
                              "descripcion": NUEVO["descripcion"],
                              "privacidad": NUEVO["privacidad"],
                              "latencia": NUEVO["latencia"]}))
        recibido = {}

        def pedir(_padre, *args, **kwargs):
            recibido["args"] = args
            return NUEVO

        with mock.patch.object(inicio_youtube, "hay_sesion", return_value=True), \
                mock.patch.object(inicio_youtube, "_cliente",
                                  return_value=mock.Mock()), \
                mock.patch.object(inicio_youtube, "_ganchos",
                                  return_value={"ganchos": True}), \
                mock.patch("guyrapu.ui.gui_directo_youtube.pedir_datos_directo",
                           side_effect=pedir):
            resultado = inicio_youtube.pedir_y_armar(frame, None)

        self.assertEqual("De config", recibido["args"][0])
        self.assertEqual("public", recibido["args"][2])
        frame._guardar_datos_directo_youtube.assert_called_once_with(
            "Nuevo", "Después", "public", "normal", True, False, "20",
            ["uno"], "", "", "")
        self.assertEqual(({"titulo": "Nuevo", "descripcion": "Después",
                           "privacidad": "public", "latencia": "normal"},
                          {"ganchos": True}), resultado)


if __name__ == "__main__":
    unittest.main()
