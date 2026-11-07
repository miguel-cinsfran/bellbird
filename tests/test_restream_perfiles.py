"""Pruebas de los perfiles de transmisión por Restream."""

import json
import tempfile
import unittest
from pathlib import Path

from guyrapu.restream.api import Canal
from guyrapu.restream.perfiles import (
    Perfil,
    cargar,
    destinos_para_perfil,
    guardar,
    normalizar_youtube,
    validar,
)


def _perfil(**cambios):
    datos = dict(
        nombre="Canal principal",
        canales=(1, 2),
        orientacion="horizontal",
        youtube=False,
        chat="",
        directo={"titulo": "Directo", "descripcion": "Prueba",
                 "privacidad": "public", "latencia": "normal"},
    )
    datos.update(cambios)
    return Perfil(**datos)


def _canal(identificador, plataforma_id=67, nombre="", texto=""):
    return Canal(id=identificador, plataforma_id=plataforma_id,
                 plataforma="TikTok", nombre=nombre, url="", activo=True)


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

    def test_p11_un_perfil_viejo_pasa_sus_datos_a_lo_ultimo_usado(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "perfiles_restream.json"
            ruta.write_text(json.dumps([{
                "nombre": "Viejo", "canales": [1], "orientacion": "vertical",
                "titulo": "Título viejo", "descripcion": "Descripción vieja",
                "privacidad": "public", "latencia": "low",
            }], ensure_ascii=False), encoding="utf-8")

            [perfil] = cargar(ruta)

        self.assertEqual(perfil.directo, {
            "titulo": "Título viejo", "descripcion": "Descripción vieja",
            "privacidad": "public", "latencia": "low"})
        self.assertFalse(perfil.youtube)

    def test_p11_un_perfil_viejo_sin_privacidad_no_se_descarta(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "perfiles_restream.json"
            ruta.write_text(json.dumps([{
                "nombre": "Viejo", "canales": [1], "orientacion": "horizontal",
                "titulo": "Sin opciones",
            }], ensure_ascii=False), encoding="utf-8")

            [perfil] = cargar(ruta)

        self.assertEqual(perfil.directo,
                         {"titulo": "Sin opciones", "descripcion": ""})


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
            ("sin canales ni YouTube", _perfil(canales=(), youtube=False), []),
            ("orientación fuera de sus valores",
             _perfil(orientacion="diagonal"), []),
        ]
        for motivo, perfil, existentes in casos:
            with self.subTest(caso=motivo):
                self.assertTrue(validar(perfil, existentes))

    def test_p3_vale_con_solo_la_casilla_de_youtube(self):
        self.assertEqual(validar(_perfil(canales=(), youtube=True), []), [])

    def test_p3_vale_con_solo_un_destino(self):
        self.assertEqual(validar(_perfil(canales=(1,), youtube=False), []), [])

    def test_p2_los_mensajes_dicen_perfil_de_restream_y_destino(self):
        casos = [
            (_perfil(nombre="   "), [],
             "Escribe un nombre para el perfil de Restream."),
            (_perfil(nombre="CANAL"), [_perfil(nombre="canal")],
             "Ya existe un perfil de Restream con ese nombre."),
            (_perfil(canales=(), youtube=False), [],
             "Agrega al menos un destino al perfil de Restream."),
            (_perfil(orientacion="diagonal"), [],
             "La orientación del perfil de Restream debe ser horizontal o "
             "vertical."),
        ]
        for perfil, existentes, esperado in casos:
            with self.subTest(mensaje=esperado):
                self.assertIn(esperado, validar(perfil, existentes))


class TestYoutubeDeRestream(unittest.TestCase):

    def test_p11_el_canal_de_plataforma_cinco_pasa_a_la_casilla(self):
        perfil = _perfil(canales=(1, 2), youtube=False)
        canales = [_canal(1), _canal(2, plataforma_id=5)]

        normalizado = normalizar_youtube(perfil, canales)

        self.assertTrue(normalizado.youtube)
        self.assertEqual(normalizado.canales, (1,))

    def test_sin_canal_de_plataforma_cinco_no_cambia(self):
        perfil = _perfil(canales=(1,), youtube=False)
        self.assertIs(normalizar_youtube(perfil, [_canal(1)]), perfil)

    def test_un_youtube_de_la_cuenta_que_el_perfil_no_usa_no_lo_cambia(self):
        perfil = _perfil(canales=(1,), youtube=False)
        canales = [_canal(1), _canal(9, plataforma_id=5)]
        self.assertIs(normalizar_youtube(perfil, canales), perfil)

    def test_p2_los_destinos_del_cuadro_saltan_plataforma_cinco_y_el_manual(
            self):
        canales = [_canal(1, nombre="tiktok"),
                   _canal(2, plataforma_id=5, nombre="canal"),
                   _canal(3, plataforma_id=29, nombre="YouTube de Guyrapu")]

        self.assertEqual(destinos_para_perfil(canales),
                         [(1, "TikTok: tiktok")])


if __name__ == "__main__":
    unittest.main()
