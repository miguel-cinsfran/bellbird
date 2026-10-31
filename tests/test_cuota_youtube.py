"""Pruebas de la cuota de YouTube: costos, día del Pacífico y persistencia."""

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bellbird.core import paths
from bellbird.youtube import cuota
from tests.rutas_temporales import redirigir_rutas


UTC = dt.timezone.utc


def _pacifico(anio, mes, dia, hora, minuto=0):
    return dt.datetime(anio, mes, dia, hora, minuto, tzinfo=UTC)


class TestCostos(unittest.TestCase):

    def test_metodo_conocido(self):
        self.assertEqual(cuota.costo("videos.list"), 1)
        self.assertEqual(cuota.costo("videos.update"), 50)
        self.assertEqual(cuota.costo("liveChatMessages.list"), 5)
        self.assertEqual(cuota.costo("liveChatBans.insert"), 200)

    def test_desconocido_cuesta_uno(self):
        self.assertEqual(cuota.costo("inventado.metodo"), 1)

    def test_quita_el_prefijo_youtube(self):
        self.assertEqual(cuota.costo("youtube.videos.list"), 1)
        self.assertEqual(cuota.costo("youtube.comments.insert"), 50)

    def test_la_fecha_es_la_de_la_tabla(self):
        self.assertEqual(cuota.FECHA_COSTOS, "15/10/2026")


class TestDiaPacifico(unittest.TestCase):

    def test_medianoche_del_pacifico_en_horario_de_verano(self):
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 10, 20, 6, 59)),
                         dt.date(2026, 10, 19))
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 10, 20, 7, 0)),
                         dt.date(2026, 10, 20))

    def test_medianoche_del_pacifico_en_horario_de_invierno(self):
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 12, 20, 7, 59)),
                         dt.date(2026, 12, 19))
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 12, 20, 8, 0)),
                         dt.date(2026, 12, 20))

    def test_cambio_de_marzo(self):
        # El 8 de marzo de 2026 a las 2:00 PST (10:00 UTC) pasa a PDT.
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 3, 8, 9, 0)),
                         dt.date(2026, 3, 8))
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 3, 9, 6, 30)),
                         dt.date(2026, 3, 8))
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 3, 9, 7, 30)),
                         dt.date(2026, 3, 9))

    def test_cambio_de_noviembre(self):
        # El 1 de noviembre de 2026 a las 2:00 PDT (9:00 UTC) pasa a PST.
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 11, 2, 7, 30)),
                         dt.date(2026, 11, 1))
        self.assertEqual(cuota.dia_pacifico(_pacifico(2026, 11, 2, 8, 30)),
                         dt.date(2026, 11, 2))


class TestPersistencia(unittest.TestCase):

    def test_suma_y_persiste_entre_lecturas(self):
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            ahora = _pacifico(2026, 10, 20, 18, 0)
            cuota._registrar("videos.list", ahora_utc=ahora)
            cuota._registrar("comments.insert", ahora_utc=ahora)
            self.assertEqual(cuota.usadas_hoy(ahora), 51)
            self.assertEqual(cuota.usadas_hoy(ahora), 51)
            datos = json.loads(paths.cuota_youtube().read_text(encoding="utf-8"))
            self.assertEqual(datos["dia"], "2026-10-20")
            self.assertEqual(datos["unidades"], 51)
            self.assertEqual(datos["por_metodo"],
                             {"videos.list": 1, "comments.insert": 50})

    def test_cambio_de_dia_vuelve_a_cero(self):
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            cuota._registrar("videos.list",
                             ahora_utc=_pacifico(2026, 10, 20, 18, 0))
            self.assertEqual(cuota.usadas_hoy(_pacifico(2026, 10, 21, 18, 0)), 0)
            cuota._registrar("comments.insert",
                             ahora_utc=_pacifico(2026, 10, 21, 18, 0))
            self.assertEqual(cuota.usadas_hoy(_pacifico(2026, 10, 21, 18, 0)),
                             50)

    def test_archivo_ilegible_cuenta_como_cero(self):
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            ruta = Path(tmp) / "cuota_youtube.json"
            ruta.write_text("esto no es JSON", encoding="utf-8")
            ahora = _pacifico(2026, 10, 20, 18, 0)
            self.assertEqual(cuota.usadas_hoy(ahora), 0)
            cuota._registrar("videos.list", ahora_utc=ahora)
            self.assertEqual(cuota.usadas_hoy(ahora), 1)

    def test_fallo_al_escribir_no_rompe_la_llamada(self):
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            with mock.patch.object(cuota.archivos,
                                            "escribir_texto_atomico",
                                            side_effect=OSError("disco lleno")):
                cuota._registrar("videos.list",
                                 ahora_utc=_pacifico(2026, 10, 20, 18, 0))


class TestContadora(unittest.TestCase):

    def test_suma_antes_de_que_el_execute_original_lance(self):
        from googleapiclient.http import HttpRequest
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            clase = cuota.clase_contadora()
            self.assertTrue(issubclass(clase, HttpRequest))

            class HttpQueFalla:
                def request(self, *args, **kwargs):
                    raise RuntimeError("sin red")

            peticion = clase(HttpQueFalla(), None, "https://example.invalid/",
                             methodId="youtube.comments.insert")
            with self.assertRaises(RuntimeError):
                peticion.execute()
            self.assertEqual(cuota.usadas_hoy(), 50)

    def test_build_real_suma_sin_red(self):
        from googleapiclient.http import HttpMockSequence
        with tempfile.TemporaryDirectory() as tmp, redirigir_rutas(tmp):
            servicio = cuota.construir(developerKey="x", cache_discovery=False)
            http = HttpMockSequence([({"status": "200"}, "{}")])
            respuesta = servicio.videos().list(part="id", id="abc").execute(
                http=http)
            self.assertEqual(respuesta, {})
            self.assertEqual(cuota.usadas_hoy(), 1)


if __name__ == "__main__":
    unittest.main()
