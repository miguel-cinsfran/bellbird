"""Pruebas de los eventos de Restream, sin red y sin interfaz."""

import unittest
from datetime import datetime, timezone

from guyrapu.restream import eventos

ID_EVENTO = "fa2f5c54-4de5-4118-a4b0-925c648c49d6"
ID_DESTINO = "51ef373f-d7d2-4993-9af2-faa14f245962"
ID_HISTORIA = "0b6b1f7e-2f34-4d0a-9c11-4c3f7d2a5e10"


def _segundos(anio, mes, dia, hora, minuto):
    return datetime(anio, mes, dia, hora, minuto,
                    tzinfo=timezone.utc).timestamp()


def _evento(**cambios):
    datos = dict(
        id=ID_EVENTO,
        estado="upcoming",
        titulo="Charla",
        descripcion="Una charla larga",
        programado=_segundos(2026, 11, 5, 20, 30),
        empezado=None,
        terminado=None,
        destinos=(eventos.DestinoEvento(ID_DESTINO, 17448019, 67, ""),),
    )
    datos.update(cambios)
    return eventos.Evento(**datos)


class TestLeerRespuestas(unittest.TestCase):

    def test_p3_la_lista_simple_se_lee_con_fechas_nulas_y_destino_sin_enlace(
            self):
        datos = [{
            "id": ID_EVENTO,
            "status": "upcoming",
            "title": "Charla",
            "description": "",
            "scheduledFor": None,
            "startedAt": None,
            "finishedAt": None,
            "destinations": [{
                "id": ID_DESTINO,
                "channelId": 17448019,
                "streamingPlatformId": 67,
                "externalUrl": None,
            }],
        }]

        leidos = eventos.leer_eventos(datos, eventos.TIPO_PROXIMOS)

        self.assertEqual(1, len(leidos))
        evento = leidos[0]
        self.assertEqual(ID_EVENTO, evento.id)
        self.assertIsNone(evento.programado)
        self.assertIsNone(evento.empezado)
        self.assertIsNone(evento.terminado)
        self.assertEqual("", evento.destinos[0].enlace)
        self.assertEqual([], eventos.enlaces(evento))

    def test_p3_el_historial_llega_con_items_y_se_lee(self):
        datos = {
            "items": [{
                "id": ID_HISTORIA,
                "status": "finished",
                "title": "Terminada",
                "description": "",
                "scheduledFor": None,
                "startedAt": _segundos(2026, 11, 4, 18, 0),
                "finishedAt": _segundos(2026, 11, 4, 19, 0),
                "destinations": [],
            }],
            "pagination": {"pages_total": 1, "page": 1, "limit": 50},
        }

        leidos = eventos.leer_eventos(datos, eventos.TIPO_HISTORIAL)

        self.assertEqual([ID_HISTORIA], [evento.id for evento in leidos])
        self.assertEqual("finished", leidos[0].estado)


class TestFila(unittest.TestCase):

    def test_p3_proximos_dice_programado_para(self):
        self.assertEqual(
            "Charla, programado para 05/11/2026 20:30",
            eventos.fila(_evento(), eventos.TIPO_PROXIMOS,
                         zona=timezone.utc))

    def test_p3_proximos_sin_fecha_dice_sin_programar(self):
        self.assertEqual(
            "Charla, sin programar",
            eventos.fila(_evento(programado=None), eventos.TIPO_PROXIMOS,
                         zona=timezone.utc))

    def test_p3_en_directo_dice_desde_la_hora(self):
        evento = _evento(estado="live", programado=None,
                         empezado=_segundos(2026, 11, 5, 20, 30))
        self.assertEqual(
            "Charla, en directo desde 20:30",
            eventos.fila(evento, eventos.TIPO_EN_DIRECTO, zona=timezone.utc))

    def test_p3_historial_dice_fecha_y_duracion_en_palabras(self):
        evento = _evento(
            estado="finished", programado=None,
            empezado=_segundos(2026, 11, 5, 20, 30),
            terminado=_segundos(2026, 11, 5, 21, 32) + 5)
        self.assertEqual(
            "Charla, 05/11/2026 20:30, duró 1 hora, 2 minutos y 5 segundos",
            eventos.fila(evento, eventos.TIPO_HISTORIAL, zona=timezone.utc))


class TestDetalle(unittest.TestCase):

    def test_p4_muestra_estado_momentos_destino_y_descripcion_al_final(self):
        texto = eventos.detalle(
            _evento(), {17448019: "TikTok: szeiryuGaming"},
            zona=timezone.utc)

        self.assertIn("Título: Charla", texto)
        self.assertIn("Estado: Próximo", texto)
        self.assertIn("Programado para: 05/11/2026 20:30", texto)
        self.assertIn("Destinos:", texto)
        self.assertIn("TikTok: szeiryuGaming", texto)
        self.assertTrue(texto.endswith("Una charla larga"))

    def test_p4_el_historial_muestra_inicio_y_fin(self):
        evento = _evento(
            estado="finished", programado=None,
            empezado=_segundos(2026, 11, 5, 20, 30),
            terminado=_segundos(2026, 11, 5, 21, 30))
        texto = eventos.detalle(evento, {}, zona=timezone.utc)

        self.assertIn("Estado: Finalizado", texto)
        self.assertIn("Inició: 05/11/2026 20:30", texto)
        self.assertIn("Terminó: 05/11/2026 21:30", texto)


class TestEstadisticas(unittest.TestCase):

    def test_p6_la_respuesta_se_lee_del_total(self):
        datos = {
            "total": {
                "mean": 12.5,
                "max": 30,
                "viewsTotal": 345,
                "peakTime": None,
                "watchedTime": 3725,
            },
            "byChannel": {},
        }

        leidas = eventos.leer_estadisticas(datos)

        self.assertEqual(12.5, leidas.promedio)
        self.assertEqual(30, leidas.maximo)
        self.assertEqual(345, leidas.vistas)
        self.assertEqual(3725, leidas.tiempo_visto)

    def test_p6_la_frase_dice_promedio_maximo_vistas_y_tiempo(self):
        leidas = eventos.Estadisticas(
            promedio=12.5, maximo=30, vistas=345, tiempo_visto=3725)

        self.assertEqual(
            "Espectadores: promedio 12,5, máximo 30. Vistas: 345. "
            "Tiempo visto: 1 hora, 2 minutos y 5 segundos.",
            eventos.frase_estadisticas(leidas))


class TestEnlaces(unittest.TestCase):

    def test_p5_solo_devuelve_los_destinos_que_tienen_enlace(self):
        evento = _evento(destinos=(
            eventos.DestinoEvento(
                ID_DESTINO, 17448019, 67, "https://tiktok.com/@uno"),
            eventos.DestinoEvento(
                "6d3f0a1c-1d7e-4c2b-8a4f-5e6d7c8b9a01", 17448020, 5, ""),
            eventos.DestinoEvento(
                "7e4a1b2d-2e8f-4d3c-9b5a-6f7e8d9c0b12", 17448021, 1,
                "https://twitch.tv/tres"),
        ))

        self.assertEqual(
            ["https://tiktok.com/@uno", "https://twitch.tv/tres"],
            eventos.enlaces(evento))


if __name__ == "__main__":
    unittest.main()
