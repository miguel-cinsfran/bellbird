"""Pruebas del módulo puro de fines de directo pendientes.

La E/S se prueba contra un archivo de verdad en una carpeta temporal, y el
reintento con un reloj y un dormir falsos, sin hilos y sin dormir de verdad.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from ytchat.youtube import fin_pendiente


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.siestas = []

    def reloj(self):
        return self.ahora

    def dormir(self, segundos):
        self.siestas.append(segundos)
        self.ahora += segundos


class PruebasFinPendiente(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "fin_pendiente.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_anotar_escribe_y_leer_devuelve(self):
        fin_pendiente.anotar(self.ruta, "vid1",
                             ahora=datetime(2026, 10, 16, 19, 5, 0))
        pendientes = fin_pendiente.leer(self.ruta)
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0]["id"], "vid1")
        self.assertEqual(pendientes[0]["fecha"], "2026-10-16T19:05:00")

    def test_anotar_no_duplica_el_mismo_id(self):
        fin_pendiente.anotar(self.ruta, "vid1")
        fin_pendiente.anotar(self.ruta, "vid1")
        ids = [e["id"] for e in fin_pendiente.leer(self.ruta)]
        self.assertEqual(ids, ["vid1"])

    def test_quitar_deja_los_demas(self):
        fin_pendiente.anotar(self.ruta, "vid1")
        fin_pendiente.anotar(self.ruta, "vid2")
        restantes = fin_pendiente.quitar(self.ruta, "vid1")
        self.assertEqual([e["id"] for e in restantes], ["vid2"])
        self.assertEqual([e["id"] for e in fin_pendiente.leer(self.ruta)],
                         ["vid2"])

    def test_quitar_un_id_que_no_esta_no_crea_el_archivo(self):
        self.assertFalse(self.ruta.exists())
        self.assertEqual(fin_pendiente.quitar(self.ruta, "vid1"), [])
        self.assertFalse(self.ruta.exists())

    def test_archivo_roto_se_lee_como_vacio(self):
        self.ruta.write_text("esto no es json {", encoding="utf-8")
        self.assertEqual(fin_pendiente.leer(self.ruta), [])

    def test_archivo_con_otra_forma_se_lee_como_vacio(self):
        self.ruta.write_text('{"id": "vid1"}', encoding="utf-8")
        self.assertEqual(fin_pendiente.leer(self.ruta), [])

    def test_entradas_sin_id_se_descartan(self):
        self.ruta.write_text('[{"fecha": "x"}, "basura", {"id": "vid1"}]',
                             encoding="utf-8")
        self.assertEqual([e["id"] for e in fin_pendiente.leer(self.ruta)],
                         ["vid1"])


class PruebasReintento(unittest.TestCase):

    def test_logra_al_tercer_intento(self):
        reloj = RelojFalso()
        intentos = []

        def intento():
            intentos.append(reloj.ahora)
            if len(intentos) < 3:
                raise RuntimeError("red caída")

        self.assertTrue(fin_pendiente.reintentar(
            intento, reloj.dormir, reloj.reloj))
        self.assertEqual(intentos, [15.0, 30.0, 45.0])

    def test_se_rinde_a_los_diez_minutos(self):
        reloj = RelojFalso()

        def intento():
            raise RuntimeError("sigue caída")

        self.assertFalse(fin_pendiente.reintentar(
            intento, reloj.dormir, reloj.reloj))
        self.assertGreaterEqual(reloj.ahora, fin_pendiente.LIMITE_REINTENTO)
        self.assertLessEqual(reloj.ahora,
                             fin_pendiente.LIMITE_REINTENTO
                             + fin_pendiente.INTERVALO_REINTENTO)

    def test_nunca_intenta_mas_seguido_que_el_intervalo(self):
        reloj = RelojFalso()
        intentos = []

        def intento():
            intentos.append(reloj.ahora)
            raise RuntimeError("sigue caída")

        fin_pendiente.reintentar(intento, reloj.dormir, reloj.reloj)
        self.assertGreater(len(intentos), 1)
        anteriores = [0.0] + intentos[:-1]
        for antes, ahora in zip(anteriores, intentos):
            self.assertGreaterEqual(ahora - antes,
                                    fin_pendiente.INTERVALO_REINTENTO)


if __name__ == "__main__":
    unittest.main()
