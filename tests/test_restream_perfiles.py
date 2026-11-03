"""Pruebas de los perfiles de transmisión por Restream."""

import json
import tempfile
import unittest
from pathlib import Path

from bellbird.restream.perfiles import Perfil, cargar, guardar, validar


def _perfil(**cambios):
    datos = dict(
        nombre="Canal principal",
        canales=(1, 2),
        orientacion="horizontal",
        titulo="Directo",
        descripcion="Prueba",
        privacidad="public",
        latencia="normal",
    )
    datos.update(cambios)
    return Perfil(**datos)


class TestArchivo(unittest.TestCase):

    def test_p7_archivo_ausente_da_lista_vacia(self):
        with tempfile.TemporaryDirectory() as temporal:
            self.assertEqual(
                cargar(Path(temporal) / "perfiles_restream.json"), [])

    def test_p7_json_roto_da_lista_vacia(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "perfiles_restream.json"
            ruta.write_text("{", encoding="utf-8")
            self.assertEqual(cargar(ruta), [])

    def test_p7_salta_las_entradas_invalidas(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "perfiles_restream.json"
            ruta.write_text(json.dumps([
                _perfil(nombre="Válido").a_dict(),
                _perfil(nombre="").a_dict(),
                _perfil(nombre="Otro", orientacion="inventada").a_dict(),
            ], ensure_ascii=False), encoding="utf-8")
            self.assertEqual(cargar(ruta), [_perfil(nombre="Válido")])

    def test_p7_guardar_y_cargar_conservan_los_datos(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "perfiles_restream.json"
            perfiles = [_perfil(nombre="Niño Ágil")]
            guardar(ruta, perfiles)
            self.assertEqual(cargar(ruta), perfiles)


class TestValidacion(unittest.TestCase):

    def test_p8_valida_antes_de_guardar(self):
        self.assertEqual(validar(_perfil(), []), [])
        self.assertEqual(validar(_perfil(), [_perfil(nombre="Otro")]), [])

        casos = [
            ("nombre vacío", _perfil(nombre="   "), []),
            ("nombre repetido sin distinguir mayúsculas",
             _perfil(nombre="CANAL"), [_perfil(nombre="canal")]),
            ("YouTube reservado", _perfil(nombre="YouTube"), []),
            ("YouTube reservado en minúsculas", _perfil(nombre="youtube"), []),
            ("sin canales", _perfil(canales=()), []),
            ("orientación fuera de sus valores",
             _perfil(orientacion="diagonal"), []),
            ("privacidad fuera de sus valores",
             _perfil(privacidad="secreta"), []),
            ("latencia fuera de sus valores", _perfil(latencia="lenta"), []),
        ]
        for motivo, perfil, existentes in casos:
            with self.subTest(caso=motivo):
                self.assertTrue(validar(perfil, existentes))

    def test_p2_los_mensajes_dicen_perfil_de_restream_y_destino(self):
        casos = [
            (_perfil(nombre="   "), [],
             "Escribe un nombre para el perfil de Restream."),
            (_perfil(nombre="CANAL"), [_perfil(nombre="canal")],
             "Ya existe un perfil de Restream con ese nombre."),
            (_perfil(canales=()), [],
             "Agrega al menos un destino al perfil de Restream."),
            (_perfil(orientacion="diagonal"), [],
             "La orientación del perfil de Restream debe ser horizontal o "
             "vertical."),
            (_perfil(privacidad="secreta"), [],
             "La privacidad del perfil de Restream no está entre las "
             "opciones."),
            (_perfil(latencia="lenta"), [],
             "La latencia del perfil de Restream no está entre las opciones."),
        ]
        for perfil, existentes, esperado in casos:
            with self.subTest(mensaje=esperado):
                self.assertIn(esperado, validar(perfil, existentes))


if __name__ == "__main__":
    unittest.main()
