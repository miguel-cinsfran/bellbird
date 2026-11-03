"""Pruebas de la lógica pura de la auditoría de las ventanas de OBS.

Solo cubren lo que no necesita la sonda: la comparación de pestañas, los
esperados que faltan en el orden de Tab y la espera de la carga inicial. La
auditoría real de las ventanas la corre el banco.
"""

import importlib.util
import unittest
from pathlib import Path

_QA = Path(__file__).resolve().parent.parent / "qa"
_RUTA = _QA / "ventanas_obs.py"
_paquete = importlib.util.spec_from_file_location("ventanas_obs_qa", _RUTA)
ventanas_obs = importlib.util.module_from_spec(_paquete)
_paquete.loader.exec_module(ventanas_obs)


class _Resultado:
    def __init__(self):
        self.fallos = []
        self.notas = []

    def fallo(self, texto):
        self.fallos.append(texto)

    def nota(self, texto):
        self.notas.append(texto)


class _Aplicacion:
    def arbol(self, ventana=None):
        return []


class TestDescuadreDePestanas(unittest.TestCase):

    def test_las_seis_en_orden_no_descuidran(self):
        self.assertIsNone(ventanas_obs.descuadre_de_pestanas(
            ["Escena", "Audio", "Grabación", "Fuentes", "Agregar",
             "General"]))

    def test_una_pestana_de_mas_es_fallo_y_la_nombra(self):
        texto = ventanas_obs.descuadre_de_pestanas(
            ["Escena", "Audio", "Grabación", "Fuentes", "Agregar",
             "General", "Filtros"])
        self.assertIsNotNone(texto)
        self.assertIn("Filtros", texto)

    def test_una_pestana_de_menos_es_fallo(self):
        texto = ventanas_obs.descuadre_de_pestanas(
            ["Escena", "Audio", "Grabación", "Fuentes", "Agregar"])
        self.assertIsNotNone(texto)

    def test_el_orden_cambiado_es_fallo_y_lo_muestra(self):
        texto = ventanas_obs.descuadre_de_pestanas(
            ["Audio", "Escena", "Grabación", "Fuentes", "Agregar",
             "General"])
        self.assertIsNotNone(texto)
        self.assertIn("Audio", texto)

    def test_ignora_mayusculas_y_espacios(self):
        self.assertIsNone(ventanas_obs.descuadre_de_pestanas(
            [" escena ", "Audio", "grabación", "Fuentes", "AGREGAR",
             "General"]))


class TestFaltanEnTab(unittest.TestCase):

    def test_lo_que_esta_no_falta(self):
        orden = ["Choice: &Escena", "Button: Cambiar escena"]
        self.assertEqual(
            ventanas_obs.faltan_en_tab(("Escena", "Cambiar escena"), orden),
            [])

    def test_la_marca_de_mnemonico_no_esconde_el_esperado(self):
        orden = ["Choice: &Escena", "Button: &Fuente"]
        self.assertEqual(
            ventanas_obs.faltan_en_tab(("Escena", "Fuente"), orden), [])

    def test_la_marca_de_mnemonico_en_medio_tampoco_lo_esconde(self):
        orden = ["Button: Cambiar e&scena"]
        self.assertEqual(
            ventanas_obs.faltan_en_tab(("Cambiar escena",), orden), [])

    def test_lo_que_no_esta_se_informa_por_su_nombre(self):
        self.assertEqual(
            ventanas_obs.faltan_en_tab(
                ("Escena", "Audio"), ["Choice: &Escena"]),
            ["Audio"])


class TestEsperadosDePestana(unittest.TestCase):

    def test_cada_pestana_suma_ayuda_y_cerrar(self):
        for nombre in ventanas_obs.PESTANAS_OBS:
            esperados = ventanas_obs.esperados_de_pestana(nombre)
            self.assertIn("Ayuda", esperados)
            self.assertIn("Cerrar", esperados)

    def test_audio_pide_su_microfono(self):
        esperados = ventanas_obs.esperados_de_pestana("Audio")
        self.assertIn("Silenciar micrófono", esperados)
        self.assertIn("Elegir micrófono", esperados)

    def test_grabacion_pide_su_estado_y_su_lista(self):
        esperados = ventanas_obs.esperados_de_pestana("Grabación")
        self.assertIn("Estado", esperados)
        self.assertIn("Iniciar grabación", esperados)
        self.assertIn("Grabaciones", esperados)
        self.assertNotIn("Escena…", esperados)
        self.assertNotIn("Grabaciones…", esperados)

    def test_general_pide_estado_actualizar_y_mostrar(self):
        esperados = ventanas_obs.esperados_de_pestana("General")
        self.assertIn("Estado de OBS", esperados)
        self.assertIn("Actualizar estado", esperados)
        self.assertIn("Mostrar OBS", esperados)


class TestEsperarHabilitado(unittest.TestCase):

    def test_si_no_se_habilita_nombra_el_control(self):
        res = _Resultado()
        sin_habilitar = lambda controles, nombres: list(nombres)
        self.assertFalse(ventanas_obs.esperar_habilitado(
            _Aplicacion(), sin_habilitar, "Cambiar escena", 0.0, res))
        self.assertTrue(res.fallos)
        self.assertIn("Cambiar escena", res.fallos[0])
        self.assertIn("no se habilitó", res.fallos[0])

    def test_si_se_habilita_no_hay_fallo(self):
        res = _Resultado()
        habilitado = lambda controles, nombres: []
        self.assertTrue(ventanas_obs.esperar_habilitado(
            _Aplicacion(), habilitado, "Cambiar escena", 0.0, res))
        self.assertEqual(res.fallos, [])


if __name__ == "__main__":
    unittest.main()
