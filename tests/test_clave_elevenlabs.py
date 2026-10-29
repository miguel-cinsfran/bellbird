"""Pruebas de la consulta de la clave de ElevenLabs, sin ventanas."""

import unittest
from unittest import mock

from tests.pseudo_prueba import con_pseudo
from ytchat.ui import clave_elevenlabs
from ytchat.voice import elevenlabs


class _HiloInmediato:

    def __init__(self, target):
        self._target = target

    def start(self):
        self._target()


class TestTextoClaveValida(unittest.TestCase):

    def test_usa_los_miles_con_punto(self):
        self.assertEqual(
            clave_elevenlabs.texto_clave_valida(2, 1234, 10000),
            "Clave válida. 2 voces. Usados 1.234 de 10.000 caracteres este mes.")

    def test_miles_devuelve_el_texto_si_no_es_numero(self):
        self.assertEqual(clave_elevenlabs._miles("sin número"), "sin número")

    def test_clave_valida_sale_marcada_en_plural_y_singular(self):
        with con_pseudo():
            plural = clave_elevenlabs.texto_clave_valida(2, 1234, 10000)
            singular = clave_elevenlabs.texto_clave_valida(1, 0, 10000)
        for texto in (plural, singular):
            with self.subTest(texto=texto):
                self.assertTrue(texto.startswith("[¡"), texto)


class TestComprobar(unittest.TestCase):

    def _comprobar(self, cliente):
        al_ok = mock.Mock()
        al_fallo = mock.Mock()
        with mock.patch.object(
                clave_elevenlabs.diagnostico, "crear_hilo",
                side_effect=lambda target, nombre, **kw: _HiloInmediato(target)), \
                mock.patch.object(
                    clave_elevenlabs.wx, "CallAfter",
                    side_effect=lambda funcion, *args: funcion(*args)), \
                mock.patch.object(
                    elevenlabs, "ClienteElevenLabs", return_value=cliente):
            clave_elevenlabs.comprobar("clave", al_ok, al_fallo)
        return al_ok, al_fallo

    def test_llama_a_al_ok_con_voces_y_saldo(self):
        cliente = mock.Mock()
        cliente.voces.return_value = [("id1", "Ana")]
        cliente.saldo.return_value = (1234, 10000)
        al_ok, al_fallo = self._comprobar(cliente)
        al_ok.assert_called_once_with([("id1", "Ana")], 1234, 10000)
        al_fallo.assert_not_called()

    def test_si_el_cliente_lanza_llama_a_al_fallo(self):
        cliente = mock.Mock()
        cliente.voces.side_effect = RuntimeError("falla de prueba")
        al_ok, al_fallo = self._comprobar(cliente)
        al_fallo.assert_called_once_with("falla de prueba")
        al_ok.assert_not_called()
