"""Qué aviso sale de cada mensaje del WebSocket de estado de Restream."""

import json
import unittest

from guyrapu.restream import senal

CANAL = 17448019
NOMBRE = "TikTok: szeiryuGaming"

DESTINOS = {CANAL: NOMBRE}


def _mensaje(accion, **campos):
    return json.dumps({"action": accion, **campos})


def _entrante(suid="4-12047861-1", total=3000):
    return _mensaje(
        "updateIncoming", suid=suid,
        streaming={"fps": 20, "bitrate": {"total": total, "audio": 160}})


def _saliente(estado, canal=CANAL):
    return _mensaje("updateOutgoing", channelId=canal, platformId=67,
                    streaming={"status": estado, "bitrate": 2664})


def _borrar(canal=CANAL):
    return _mensaje("deleteOutgoing", channelId=canal, platformId=67)


class TestDestinos(unittest.TestCase):

    def setUp(self):
        self.senal = senal.AnalizadorSenal(DESTINOS)

    def test_la_primera_conexion_no_se_anuncia(self):
        self.assertEqual(self.senal.recibir(_saliente("CONNECTED")), [])

    def test_conectado_a_conectando_avisa_la_caida(self):
        self.senal.recibir(_saliente("CONNECTED"))

        avisos = self.senal.recibir(_saliente("CONNECTING"))

        self.assertEqual(avisos, [
            senal.Aviso(f"{NOMBRE} se desconectó.", "restream_destino_caido")])

    def test_delete_outgoing_avisa_la_caida(self):
        self.senal.recibir(_saliente("CONNECTED"))

        avisos = self.senal.recibir(_borrar())

        self.assertEqual(avisos, [
            senal.Aviso(f"{NOMBRE} se desconectó.", "restream_destino_caido")])

    def test_la_vuelta_a_conectado_avisa_que_recibe(self):
        self.senal.recibir(_saliente("CONNECTED"))
        self.senal.recibir(_saliente("DISCONNECTED"))

        avisos = self.senal.recibir(_saliente("CONNECTED"))

        self.assertEqual(avisos, [
            senal.Aviso(f"{NOMBRE} vuelve a recibir la transmisión.",
                        "restream_destino_vuelve")])

    def test_diez_conectados_seguidos_no_repiten_el_aviso(self):
        avisos = []
        for _ in range(10):
            avisos.extend(self.senal.recibir(_saliente("CONNECTED")))

        self.assertEqual(avisos, [])

    def test_un_destino_desconocido_se_nombra_un_destino(self):
        self.senal.recibir(_saliente("CONNECTED", canal=999))

        avisos = self.senal.recibir(_saliente("CONNECTING", canal=999))

        self.assertEqual(avisos, [
            senal.Aviso("Un destino se desconectó.", "restream_destino_caido")])

    def test_un_mensaje_que_no_es_json_no_da_avisos_ni_excepcion(self):
        self.assertEqual(self.senal.recibir("esto no es json"), [])
        self.assertEqual(self.senal.recibir(""), [])
        self.assertEqual(self.senal.recibir("[]"), [])
        self.assertEqual(self.senal.recibir("{}"), [])
        self.assertEqual(self.senal.recibir('{"action": "otra"}'), [])


class TestSenalEntrante(unittest.TestCase):

    def setUp(self):
        self.senal = senal.AnalizadorSenal(DESTINOS)

    def test_delete_incoming_avisa_que_dejo_de_recibir(self):
        self.senal.recibir(_entrante())

        avisos = self.senal.recibir(_mensaje("deleteIncoming"))

        self.assertEqual(avisos, [
            senal.Aviso("Restream dejó de recibir la señal de OBS.",
                        "restream_sin_senal")])

    def test_una_sesion_nueva_avisa_que_vuelve(self):
        self.senal.recibir(_entrante(suid="uno"))
        self.senal.recibir(_mensaje("deleteIncoming"))

        avisos = self.senal.recibir(_entrante(suid="dos"))

        self.assertEqual(avisos, [
            senal.Aviso("Restream vuelve a recibir la señal.",
                        "restream_senal_vuelve")])

    def test_la_primera_sesion_no_anuncia_vuelta(self):
        self.assertEqual(self.senal.recibir(_entrante()), [])

    def test_la_referencia_es_la_mediana_de_los_cinco_primeros(self):
        for _ in range(5):
            self.assertEqual(self.senal.recibir(_entrante()), [])

        self.assertEqual(self.senal.recibir(_entrante(total=1400)), [])
        avisos = self.senal.recibir(_entrante(total=1400))

        self.assertEqual(avisos, [
            senal.Aviso("Señal débil: a Restream llegan 1400 kbps.",
                        "restream_senal_debil")])

    def test_la_senal_debil_no_se_repite(self):
        for _ in range(5):
            self.senal.recibir(_entrante())
        self.senal.recibir(_entrante(total=1400))
        self.senal.recibir(_entrante(total=1400))

        self.assertEqual(self.senal.recibir(_entrante(total=1400)), [])

    def test_la_senal_se_recupera_con_dos_mensajes_altos(self):
        for _ in range(5):
            self.senal.recibir(_entrante())
        self.senal.recibir(_entrante(total=1400))
        self.senal.recibir(_entrante(total=1400))

        self.assertEqual(self.senal.recibir(_entrante(total=2500)), [])
        avisos = self.senal.recibir(_entrante(total=2500))

        self.assertEqual(avisos, [
            senal.Aviso("La señal se recuperó.", "restream_senal_vuelve")])

    def test_una_sesion_nueva_reinicia_la_referencia(self):
        for _ in range(5):
            self.senal.recibir(_entrante(suid="uno", total=3000))
        self.senal.recibir(_mensaje("deleteIncoming"))

        avisos = self.senal.recibir(_entrante(suid="dos", total=1000))
        self.assertEqual(avisos, [
            senal.Aviso("Restream vuelve a recibir la señal.",
                        "restream_senal_vuelve")])
        for _ in range(4):
            self.assertEqual(
                self.senal.recibir(_entrante(suid="dos", total=1000)), [])
        for _ in range(2):
            self.assertEqual(
                self.senal.recibir(_entrante(suid="dos", total=1000)), [])


if __name__ == "__main__":
    unittest.main()
