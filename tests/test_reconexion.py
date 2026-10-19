"""Pruebas puras de la espera de reconexión y del filtro de mensajes."""

import types
import unittest
from datetime import datetime, timedelta, timezone

from ytchat.capture.reconexion import FiltroNuevos, espera_reconexion


def _ms(momento):
    return int(momento.timestamp() * 1_000)


def _item(ident=None, ts=None, mensaje="hola"):
    datos = {"mensaje": mensaje}
    if ident is not None:
        datos["id"] = ident
    if ts is not None:
        datos["timestamp"] = ts
    return types.SimpleNamespace(**datos)


class TestEsperaReconexion(unittest.TestCase):

    def test_la_secuencia_crece_hasta_el_tope(self):
        self.assertEqual(
            [espera_reconexion(intento, 15) for intento in range(1, 7)],
            [1, 2, 5, 10, 15, 15])

    def test_ningun_escalon_pasa_del_tope(self):
        self.assertEqual(
            [espera_reconexion(intento, 3) for intento in range(1, 6)],
            [1, 2, 3, 3, 3])

    def test_tope_cero_o_negativo_devuelve_uno(self):
        for tope in (0, -5):
            with self.subTest(tope=tope):
                self.assertEqual(espera_reconexion(1, tope), 1)
                self.assertEqual(espera_reconexion(7, tope), 1)


class TestFiltroNuevos(unittest.TestCase):

    def _filtro_arrancado(self):
        filtro = FiltroNuevos()
        filtro.arrancar()
        return filtro

    def test_rechaza_lo_anterior_al_corte(self):
        filtro = self._filtro_arrancado()
        antes = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.assertFalse(filtro.es_nuevo(_item("viejo", _ms(antes))))

    def test_acepta_lo_posterior_al_corte(self):
        filtro = self._filtro_arrancado()
        despues = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.assertTrue(filtro.es_nuevo(_item("nuevo", _ms(despues))))

    def test_rechaza_un_id_repetido(self):
        filtro = self._filtro_arrancado()
        despues = datetime.now(timezone.utc) + timedelta(seconds=1)
        item = _item("repetido", _ms(despues))
        self.assertTrue(filtro.es_nuevo(item))
        self.assertFalse(filtro.es_nuevo(item))

    def test_un_item_sin_id_se_decide_solo_por_la_hora(self):
        filtro = self._filtro_arrancado()
        despues = datetime.now(timezone.utc) + timedelta(seconds=1)
        item = _item(ts=_ms(despues))
        self.assertTrue(filtro.es_nuevo(item))
        self.assertTrue(filtro.es_nuevo(item))

    def test_acepta_una_hora_datetime(self):
        filtro = self._filtro_arrancado()
        despues = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.assertTrue(filtro.es_nuevo(_item("fecha", despues)))

    def test_arrancar_dos_veces_no_mueve_la_hora(self):
        filtro = self._filtro_arrancado()
        corte = filtro._corte
        filtro.arrancar()
        self.assertEqual(filtro._corte, corte)

    def test_la_memoria_no_pasa_de_dos_mil(self):
        filtro = self._filtro_arrancado()
        despues = datetime.now(timezone.utc) + timedelta(seconds=1)
        for numero in range(2005):
            self.assertTrue(filtro.es_nuevo(_item(numero, _ms(despues))))
        self.assertEqual(len(filtro._vistos), 2000)
        self.assertEqual(len(filtro._ids), 2000)
        self.assertNotIn(0, filtro._ids)
        self.assertIn(2004, filtro._ids)


if __name__ == "__main__":
    unittest.main()
