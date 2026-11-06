"""Pruebas del aviso de privacidad de la IA, sin red ni ventanas.

El cuadro va simulado.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from guyrapu.ui import ia_privacidad


def _ajustes(aceptada):
    return SimpleNamespace(privacidad_aceptada=aceptada)


class TestConfirmar(unittest.TestCase):

    def test_ya_aceptada_no_muestra_nada(self):
        with mock.patch.object(ia_privacidad.confirmaciones,
                               "preguntar") as caja:
            self.assertTrue(
                ia_privacidad.confirmar(None, _ajustes(True), "OpenAI"))
        caja.assert_not_called()

    def test_si_guarda_y_da_verdadero(self):
        with mock.patch.object(ia_privacidad.confirmaciones, "preguntar",
                               return_value=True) as caja, \
                mock.patch.object(ia_privacidad.ajustes_ia,
                                  "guardar_privacidad_aceptada",
                                  return_value=True) as guardar:
            self.assertTrue(
                ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
        caja.assert_called_once_with(
            None, ia_privacidad.TEXTO_AVISO.format(proveedor="OpenAI"),
            ia_privacidad.TITULO_AVISO, "&Enviar", "&Cancelar",
            icono=ia_privacidad.confirmaciones.ICON_INFORMATION,
            predeterminado_si=False)
        guardar.assert_called_once_with(ia_privacidad.paths.config_ini(),
                                        True)

    def test_no_no_guarda_y_da_falso(self):
        with mock.patch.object(ia_privacidad.confirmaciones, "preguntar",
                               return_value=False), \
                mock.patch.object(ia_privacidad.ajustes_ia,
                                  "guardar_privacidad_aceptada") as guardar:
            self.assertFalse(
                ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
        guardar.assert_not_called()

    def test_aviso_y_titulo_salen_marcados(self):
        captado = {}

        def caja(padre, mensaje, titulo, etiqueta_si, etiqueta_no, **kwargs):
            captado["mensaje"] = mensaje
            captado["titulo"] = titulo
            captado["etiqueta_si"] = etiqueta_si
            captado["etiqueta_no"] = etiqueta_no
            return True

        with mock.patch.object(ia_privacidad.confirmaciones, "preguntar",
                               caja), \
                mock.patch.object(ia_privacidad.ajustes_ia,
                                   "guardar_privacidad_aceptada",
                                   return_value=True), \
                con_pseudo():
            self.assertTrue(
                ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
        for clave in ("mensaje", "titulo", "etiqueta_si", "etiqueta_no"):
            with self.subTest(clave=clave):
                self.assertTrue(captado[clave].startswith("[¡"),
                                captado[clave])

    def test_si_el_guardado_falla_igual_deja_pasar(self):
        def falla_con_valor():
            return mock.patch.object(ia_privacidad.ajustes_ia,
                                     "guardar_privacidad_aceptada",
                                     return_value=False)

        def falla_con_error():
            return mock.patch.object(ia_privacidad.ajustes_ia,
                                     "guardar_privacidad_aceptada",
                                     side_effect=OSError("sin disco"))

        for fabrica in (falla_con_valor, falla_con_error):
            with self.subTest(fabrica=fabrica.__name__), \
                    mock.patch.object(ia_privacidad.confirmaciones,
                                      "preguntar", return_value=True), \
                    fabrica(), \
                    mock.patch.object(ia_privacidad.logger,
                                      "warning") as aviso:
                self.assertTrue(
                    ia_privacidad.confirmar(None, _ajustes(False), "OpenAI"))
            aviso.assert_called_once()


if __name__ == "__main__":
    unittest.main()
