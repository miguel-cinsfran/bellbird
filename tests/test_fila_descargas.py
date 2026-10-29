from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace

from bellbird.downloads.fila_descargas import bloqueado_por_anterior


class TestBloqueadoPorAnterior(unittest.TestCase):
    def armar(self, orden, estados, empezados=(), cancelados=()):
        items = {ident: SimpleNamespace(estado=estados.get(ident, "en_cola"))
                 for ident in orden}
        eventos = {}
        for ident in orden:
            evento = threading.Event()
            if ident in cancelados:
                evento.set()
            eventos[ident] = evento
        return list(orden), set(empezados), items, eventos

    def test_sin_anteriores_no_bloquea(self):
        orden, empezados, items, eventos = self.armar(["a"], {"a": "en_cola"})
        self.assertFalse(bloqueado_por_anterior("a", orden, empezados, items, eventos))

    def test_anterior_en_cola_sin_empezar_bloquea(self):
        orden, empezados, items, eventos = self.armar(
            ["previo", "actual"], {"previo": "en_cola", "actual": "en_cola"})
        self.assertTrue(bloqueado_por_anterior("actual", orden, empezados, items, eventos))

    def test_anterior_ya_empezado_no_bloquea(self):
        orden, empezados, items, eventos = self.armar(
            ["previo", "actual"], {"previo": "en_cola", "actual": "en_cola"},
            empezados=("previo",))
        self.assertFalse(bloqueado_por_anterior("actual", orden, empezados, items, eventos))

    def test_anterior_cancelado_no_bloquea(self):
        orden, empezados, items, eventos = self.armar(
            ["previo", "actual"], {"previo": "en_cola", "actual": "en_cola"},
            cancelados=("previo",))
        self.assertFalse(bloqueado_por_anterior("actual", orden, empezados, items, eventos))

    def test_anterior_en_otro_estado_no_bloquea(self):
        orden, empezados, items, eventos = self.armar(
            ["previo", "actual"], {"previo": "descargando", "actual": "en_cola"})
        self.assertFalse(bloqueado_por_anterior("actual", orden, empezados, items, eventos))

    def test_posterior_en_cola_no_bloquea(self):
        orden, empezados, items, eventos = self.armar(
            ["actual", "posterior"], {"actual": "en_cola", "posterior": "en_cola"})
        self.assertFalse(bloqueado_por_anterior("actual", orden, empezados, items, eventos))


if __name__ == "__main__": unittest.main()
