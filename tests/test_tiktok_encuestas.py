"""Lectura de encuestas de TikTokLive con objetos reales.

Construye `PollEvent` con sus clases, no con dobles: la etapa se reconoce
por el contenido cargado y cada encuesta se anuncia una sola vez.
"""

import asyncio
import queue
import types
import unittest

from TikTokLive.events import PollEvent
from TikTokLiveProto.v3.webcast.model.message import (
    PollBasicInfo,
    PollEndContent,
    PollOptionInfo,
    PollStartContent,
    PollUpdateVotesContent,
)

from bellbird.capture import encuestas
from bellbird.capture import tiktok_encuestas
from bellbird.capture.tiktok_manejadores import registrar_manejadores
from bellbird.core.tipos_mensaje import TIPO_ENCUESTA, TIPO_ENCUESTA_FIN
import main


def _opciones(*pares):
    return [PollOptionInfo(display_content=texto, votes=votos,
                           option_idx=indice)
            for indice, (texto, votos) in enumerate(pares)]


def _apertura(titulo="¿Qué almorzamos?", pares=(("pizza", 0),
                                                ("empanadas", 0),
                                                ("sushi", 0))):
    return PollEvent(
        poll_id=7,
        start_content=PollStartContent(title=titulo,
                                       option_list=_opciones(*pares)))


def _cierre(pares=(("pizza", 12), ("empanadas", 8), ("sushi", 3)),
            titulo="¿Qué almorzamos?"):
    return PollEvent(
        poll_id=7,
        end_content=PollEndContent(option_list=_opciones(*pares)),
        poll_basic_info=PollBasicInfo(title=titulo))


class TestProcesar(unittest.TestCase):

    def setUp(self):
        tiktok_encuestas.reiniciar()

    def _procesar(self, evento):
        recibidos = []
        tiktok_encuestas.procesar(evento, lambda *a: recibidos.append(a))
        return recibidos

    def test_apertura_con_titulo(self):
        recibidos = self._procesar(_apertura())
        self.assertEqual(recibidos, [(
            "", "Encuesta: ¿Qué almorzamos? Opciones: pizza, empanadas "
            "y sushi", TIPO_ENCUESTA, "", "")])

    def test_cierre_con_los_votos(self):
        self._procesar(_apertura())
        recibidos = self._procesar(_cierre())
        self.assertEqual(recibidos, [(
            "", "Encuesta terminada: ¿Qué almorzamos? Ganó pizza con 12 "
            "votos, empanadas con 8 votos y sushi con 3 votos",
            TIPO_ENCUESTA_FIN, "", "")])

    def test_cierre_repetido_solo_anuncia_una_vez(self):
        self._procesar(_apertura())
        self._procesar(_cierre())
        recibidos = self._procesar(_cierre())
        self.assertEqual(recibidos, [])

    def test_los_votos_no_emiten_fila(self):
        self._procesar(_apertura())
        evento = PollEvent(
            poll_id=7,
            update_votes_content=PollUpdateVotesContent(
                option_list=_opciones(("pizza", 5), ("empanadas", 3),
                                      ("sushi", 0))))
        self.assertEqual(self._procesar(evento), [])
        self.assertEqual(
            encuestas.registro.en_curso(),
            "Encuesta en curso: ¿Qué almorzamos? pizza con 5 votos, "
            "empanadas con 3 votos y sushi sin votos")

    def test_titulo_desde_poll_basic_info(self):
        evento = PollEvent(
            poll_id=7,
            start_content=PollStartContent(
                title="", option_list=_opciones(("pizza", 0))),
            poll_basic_info=PollBasicInfo(title="¿Qué almorzamos?"))
        recibidos = self._procesar(evento)
        self.assertIn("Encuesta: ¿Qué almorzamos? Opciones: pizza",
                      recibidos[0][1])

    def test_cierre_sin_apertura_se_anuncia_igual(self):
        recibidos = self._procesar(_cierre())
        self.assertEqual(recibidos[0][2], TIPO_ENCUESTA_FIN)
        self.assertIn("Encuesta terminada: ¿Qué almorzamos?", recibidos[0][1])


class _ClienteFalso:
    def __init__(self):
        self.manejadores = {}

    def on(self, evento):
        def decorar(funcion):
            self.manejadores[evento] = funcion
            return funcion
        return decorar


def _modulo_con_poll():
    modulo = types.ModuleType("TikTokLive.events")
    for nombre in ("CommentEvent", "GiftEvent", "JoinEvent",
                   "RoomUserSeqEvent"):
        setattr(modulo, nombre, type(nombre, (), {}))
    modulo.PollEvent = PollEvent
    return modulo


class TestCableadoDeRegistro(unittest.TestCase):

    def setUp(self):
        tiktok_encuestas.reiniciar()

    def test_registrar_y_recibir_una_apertura_emite_su_tipo(self):
        cliente = _ClienteFalso()
        modulo = _modulo_con_poll()
        recibidos = []
        registrar_manejadores(
            cliente, modulo, on_evento=lambda *a: recibidos.append(a),
            on_espectadores=lambda *a: None, config={},
            descartar=lambda evento: False)
        asyncio.run(cliente.manejadores[PollEvent](_apertura()))
        self.assertEqual(recibidos[0][2], TIPO_ENCUESTA)


def _config(**extras):
    base = {
        "usuarios_silenciados": [], "palabras_silenciadas": [],
        "silenciados_ocultar": set(), "silenciados_runtime": set(),
        "silenciar_lectura": False, "limpiar_emojis": False,
        "eliminar_urls": False, "max_longitud_mensaje": 200,
        "umbral_solo_nombre": 0, "formato_prefijo": "nombre_mensaje",
        "estrategia": "todas", "tamanio_maximo": 10,
        "evento_encuesta": "principal",
    }
    base.update(extras)
    return base


class TestCableadoConProcesarEntrante(unittest.TestCase):

    def test_la_lectura_es_la_frase_de_la_encuesta(self):
        frase = "Encuesta: ¿Qué almorzamos? Opciones: pizza y sushi"
        cola = queue.Queue()
        main.procesar_entrante(
            "", frase, TIPO_ENCUESTA, "", "", cola, _config(), main.Stats(),
            on_message=lambda *a, **k: None)
        self.assertEqual(cola.get_nowait()["texto_tts"], frase)

    def test_ocultar_no_deja_pasar_ni_apertura_ni_cierre(self):
        for tipo in (TIPO_ENCUESTA, TIPO_ENCUESTA_FIN):
            with self.subTest(tipo=tipo):
                recibidos = []
                cola = queue.Queue()
                main.procesar_entrante(
                    "", "frase", tipo, "", "", cola,
                    _config(evento_encuesta="ocultar"), main.Stats(),
                    on_message=lambda *a, **k: recibidos.append(a))
                self.assertEqual(recibidos, [])
                self.assertTrue(cola.empty())


if __name__ == "__main__":
    unittest.main()
