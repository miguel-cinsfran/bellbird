"""Texto de cada fila de la lista de fuentes de audio del Panel de OBS."""

import unittest

from guyrapu.obs import filtros_microfono
from guyrapu.ui import fila_audio


def _filtro(tipo, activo=True, **ajustes):
    return {"filterKind": tipo, "filterEnabled": activo,
            "filterSettings": ajustes}


class TestTextoDeFila(unittest.TestCase):

    def test_activa_sin_filtros(self):
        self.assertEqual(fila_audio.texto("Mic/Aux", False, ()),
                         "Mic/Aux, activa, sin filtros")

    def test_silenciada_con_ruido_y_ganancia(self):
        filtros = (_filtro(filtros_microfono.TIPO_RUIDO),
                   _filtro(filtros_microfono.TIPO_GANANCIA, db=6))
        self.assertEqual(
            fila_audio.texto("Mic/Aux", True, filtros),
            "Mic/Aux, silenciada, eliminación de ruido, ganancia +6 dB")

    def test_un_filtro_desconocido_activo_se_cuenta_aparte(self):
        filtros = (_filtro("filter_desconocido"),)
        self.assertEqual(fila_audio.texto("Mic/Aux", False, filtros),
                         "Mic/Aux, activa, y 1 filtro más")

    def test_los_filtros_desconocidos_apagados_no_se_cuentan(self):
        filtros = (_filtro("filter_desconocido", activo=False),)
        self.assertEqual(fila_audio.texto("Mic/Aux", False, filtros),
                         "Mic/Aux, activa, sin filtros")

    def test_varios_filtros_desconocidos_van_en_plural(self):
        filtros = (_filtro("uno"), _filtro("dos"))
        self.assertEqual(fila_audio.texto("Mic/Aux", False, filtros),
                         "Mic/Aux, activa, y 2 filtros más")


if __name__ == "__main__":
    unittest.main()
