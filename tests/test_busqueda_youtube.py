"""Pruebas del motor de búsqueda de YouTube, sin interfaz."""

import base64
import json
import os
import tempfile
import unittest
from unittest import mock

from bellbird.downloads import busqueda_youtube as busqueda
from bellbird.downloads.busqueda_youtube import (
    CANTIDADES,
    CANTIDAD_DEFECTO,
    Filtros,
    Resultado,
    buscar,
    clasificar_entrada,
    codigo_sp,
    interpretar,
    ordenar,
    refiltrar,
    texto_duracion,
    texto_detalles,
    texto_fecha,
    texto_vistas,
    url_busqueda,
)


def _video(id="ZWLD8wyDt9U"):
    return {
        "_type": "url",
        "ie_key": "Youtube",
        "id": id,
        "url": f"https://www.youtube.com/watch?v={id}",
        "title": "CUMBIA PARAGUAYA RETRO",
        "channel": "Sanabria OK",
        "uploader": "Sanabria OK",
        "duration": 1068,
        "view_count": 4353830,
        "live_status": None,
        "description": "Una descripción",
        "timestamp": 1604102400,
    }


def _lista():
    return {
        "_type": "url",
        "ie_key": "YoutubeTab",
        "id": "PL123",
        "url": "https://www.youtube.com/playlist?list=PL123",
        "title": "Una lista",
        "channel": "Un canal",
        "uploader": "Un canal",
        "duration": None,
        "view_count": None,
        "playlist_count": 12,
        "live_status": None,
        "description": "Lista",
        "timestamp": None,
    }


def _canal():
    return {
        "_type": "url",
        "ie_key": "YoutubeTab",
        "id": "UC123",
        "url": "https://www.youtube.com/channel/UC123",
        "title": "Un canal",
        "channel": "Un canal",
        "uploader": "Un canal",
        "duration": None,
        "view_count": None,
        "live_status": None,
        "description": "Canal",
        "timestamp": None,
    }


def _directo():
    dato = _video(id="LIVE1")
    dato.update({
        "title": "En directo",
        "duration": None,
        "view_count": None,
        "live_status": "is_live",
    })
    return dato


class TestCantidades(unittest.TestCase):

    def test_valores_permitidos_y_defecto(self):
        self.assertEqual(CANTIDADES, (10, 20, 30, 50))
        self.assertEqual(CANTIDAD_DEFECTO, 20)


class TestClasificar(unittest.TestCase):

    def test_vacio(self):
        self.assertEqual(clasificar_entrada(""), ("vacio", ""))
        self.assertEqual(clasificar_entrada("   "), ("vacio", ""))

    def test_palabra_y_frase_son_busqueda(self):
        self.assertEqual(clasificar_entrada("cumbia"), ("busqueda", "cumbia"))
        self.assertEqual(
            clasificar_entrada("cumbia paraguaya"),
            ("busqueda", "cumbia paraguaya"))

    def test_enlaces_con_esquema(self):
        url = "https://www.youtube.com/watch?v=ZWLD8wyDt9U"
        self.assertEqual(clasificar_entrada(url), ("enlace", url))
        url2 = "http://example.com/video"
        self.assertEqual(clasificar_entrada(url2), ("enlace", url2))

    def test_www_sin_esquema_agrega_https(self):
        self.assertEqual(
            clasificar_entrada("www.youtube.com/watch?v=abc"),
            ("enlace", "https://www.youtube.com/watch?v=abc"))

    def test_dominio_con_barra_de_otra_plataforma(self):
        self.assertEqual(
            clasificar_entrada("vimeo.com/12345"),
            ("enlace", "https://vimeo.com/12345"))
        self.assertEqual(
            clasificar_entrada("tiktok.com/@usuario/video/123"),
            ("enlace", "https://tiktok.com/@usuario/video/123"))

    def test_palabra_con_punto_sin_barra_es_busqueda(self):
        self.assertEqual(clasificar_entrada("node.js"), ("busqueda", "node.js"))

    def test_dominio_sin_barra_es_busqueda(self):
        self.assertEqual(
            clasificar_entrada("example.com"), ("busqueda", "example.com"))

    def test_enlace_con_espacios_es_busqueda(self):
        self.assertEqual(
            clasificar_entrada("https://example.com/a b"),
            ("busqueda", "https://example.com/a b"))


class TestCodigoSp(unittest.TestCase):

    def test_defecto_es_video(self):
        self.assertEqual(codigo_sp(Filtros()), "EgIQAQ==")

    def test_directo_solo(self):
        self.assertEqual(codigo_sp(Filtros(tipo="directo")), "EgJAAQ==")

    def test_listas_y_canales(self):
        self.assertEqual(codigo_sp(Filtros(tipo="listas")), "EgIQAw==")
        self.assertEqual(codigo_sp(Filtros(tipo="canales")), "EgIQAg==")

    def test_videos_con_corta(self):
        self.assertEqual(
            codigo_sp(Filtros(tipo="videos", duracion="corta")), "EgQQARgB")

    def test_videos_con_mes_y_corta(self):
        self.assertEqual(
            codigo_sp(Filtros(tipo="videos", fecha="mes", duracion="corta")),
            "EgYIBBABGAE=")

    def test_listas_ignora_duracion_y_fecha(self):
        self.assertEqual(
            codigo_sp(Filtros(tipo="listas", duracion="corta", fecha="mes")),
            "EgIQAw==")
        self.assertEqual(
            codigo_sp(Filtros(tipo="canales", duracion="larga", fecha="anio")),
            "EgIQAg==")

    def test_directo_con_corta_no_lleva_tipo(self):
        codigo = codigo_sp(Filtros(tipo="directo", duracion="corta"))
        self.assertEqual(codigo, "EgQYAUAB")
        crudo = base64.b64decode(codigo)
        self.assertNotIn(bytes([0x10, 0x01]), crudo)
        self.assertIn(bytes([0x18, 0x01]), crudo)
        self.assertIn(bytes([0x40, 0x01]), crudo)

    def test_orden_de_campos_fecha_tipo_duracion_directo(self):
        codigo = codigo_sp(
            Filtros(tipo="videos", fecha="hoy", duracion="media"))
        crudo = base64.b64decode(codigo)
        self.assertTrue(
            crudo.index(bytes([0x08])) < crudo.index(bytes([0x10]))
            < crudo.index(bytes([0x18])))


class TestUrlBusqueda(unittest.TestCase):

    def test_codifica_texto_y_sp(self):
        url = url_busqueda("cumbia paraguaya", Filtros())
        self.assertIn("search_query=cumbia+paraguaya", url)
        self.assertIn("sp=EgIQAQ%3D%3D", url)
        self.assertTrue(url.startswith("https://www.youtube.com/results?"))


class TestInterpretar(unittest.TestCase):

    def test_cuatro_formas(self):
        texto = json.dumps({"entries": [_video(), _lista(), _canal(), _directo()]})
        resultados = interpretar(texto)
        self.assertEqual(len(resultados), 4)
        video, lista, canal, directo = resultados
        self.assertEqual(video.tipo, "video")
        self.assertEqual(video.titulo, "CUMBIA PARAGUAYA RETRO")
        self.assertEqual(video.canal, "Sanabria OK")
        self.assertEqual(video.duracion, 1068)
        self.assertEqual(video.vistas, 4353830)
        self.assertFalse(video.en_directo)
        self.assertFalse(video.programado)
        self.assertEqual(lista.tipo, "lista")
        self.assertEqual(canal.tipo, "canal")
        self.assertEqual(directo.tipo, "video")
        self.assertTrue(directo.en_directo)
        self.assertFalse(directo.programado)

    def test_canal_sale_de_uploader_si_falta_channel(self):
        dato = _video()
        del dato["channel"]
        texto = json.dumps({"entries": [dato]})
        self.assertEqual(interpretar(texto)[0].canal, "Sanabria OK")

    def test_programado(self):
        dato = _video()
        dato["live_status"] = "is_upcoming"
        texto = json.dumps({"entries": [dato]})
        resultado = interpretar(texto)[0]
        self.assertTrue(resultado.programado)
        self.assertFalse(resultado.en_directo)

    def test_descarta_sin_url_o_sin_titulo(self):
        sin_url = _video()
        del sin_url["url"]
        sin_titulo = _video(id="OTRO")
        del sin_titulo["title"]
        texto = json.dumps({"entries": [sin_url, sin_titulo, _video()]})
        resultados = interpretar(texto)
        self.assertEqual(len(resultados), 1)

    def test_json_roto_da_lista_vacia(self):
        self.assertEqual(interpretar("esto no es json"), [])
        self.assertEqual(interpretar(""), [])


class TestRefiltrar(unittest.TestCase):

    AHORA = 1700000000

    def _con_marca(self, dias_atras=None):
        marca = None if dias_atras is None else self.AHORA - dias_atras * 86400
        return Resultado(
            id="1", url="https://www.youtube.com/watch?v=1", titulo="T",
            canal="C", duracion=60, vistas=10, marca_tiempo=marca,
            descripcion="", tipo="video", en_directo=False, programado=False)

    def test_sin_fecha_no_filtra(self):
        items = [self._con_marca(400), self._con_marca(None)]
        self.assertEqual(len(refiltrar(items, Filtros(), self.AHORA)), 2)

    def test_ventanas(self):
        self.assertEqual(
            len(refiltrar(
                [self._con_marca(0), self._con_marca(2)],
                Filtros(fecha="hoy"), self.AHORA)), 1)
        self.assertEqual(
            len(refiltrar(
                [self._con_marca(6), self._con_marca(8)],
                Filtros(fecha="semana"), self.AHORA)), 1)
        self.assertEqual(
            len(refiltrar(
                [self._con_marca(30), self._con_marca(32)],
                Filtros(fecha="mes"), self.AHORA)), 1)
        self.assertEqual(
            len(refiltrar(
                [self._con_marca(365), self._con_marca(400)],
                Filtros(fecha="anio"), self.AHORA)), 1)

    def test_conserva_sin_fecha(self):
        items = [self._con_marca(None)]
        self.assertEqual(
            len(refiltrar(items, Filtros(fecha="hoy"), self.AHORA)), 1)


class TestOrdenar(unittest.TestCase):

    def _item(self, id, marca=None, vistas=None, duracion=None):
        return Resultado(
            id=id, url=f"https://x/{id}", titulo=id, canal="C",
            duracion=duracion, vistas=vistas, marca_tiempo=marca,
            descripcion="", tipo="video", en_directo=False, programado=False)

    def test_relevancia_no_cambia(self):
        items = [self._item("a", 1), self._item("b", 3), self._item("c", 2)]
        self.assertEqual([r.id for r in ordenar(items, "relevancia")],
                         ["a", "b", "c"])

    def test_fecha_vistas_duracion_de_mayor_a_menor(self):
        items = [self._item("a", 1, 5, 30), self._item("b", 3, 9, 10),
                 self._item("c", 2, 7, 20)]
        self.assertEqual([r.id for r in ordenar(items, "fecha")],
                         ["b", "c", "a"])
        self.assertEqual([r.id for r in ordenar(items, "vistas")],
                         ["b", "c", "a"])
        self.assertEqual([r.id for r in ordenar(items, "duracion")],
                         ["a", "c", "b"])

    def test_sin_dato_al_final_y_no_pierde_ni_agrega(self):
        for orden in ("fecha", "vistas", "duracion"):
            fila = [self._item("a", None, None, None),
                    self._item("b", 3, 9, 30),
                    self._item("c", None, None, 10),
                    self._item("d", 1, 2, None)]
            vistos = ordenar(fila, orden)
            self.assertEqual(len(vistos), 4)
            self.assertEqual({r.id for r in vistos}, {"a", "b", "c", "d"})
            if orden == "fecha":
                self.assertEqual([r.id for r in vistos][:2], ["b", "d"])
                self.assertIsNone(vistos[2].marca_tiempo)
                self.assertIsNone(vistos[3].marca_tiempo)
            elif orden == "vistas":
                self.assertEqual([r.id for r in vistos][:2], ["b", "d"])
                self.assertIsNone(vistos[2].vistas)
                self.assertIsNone(vistos[3].vistas)
            else:
                self.assertEqual([r.id for r in vistos][:2], ["b", "c"])
                self.assertIsNone(vistos[2].duracion)
                self.assertIsNone(vistos[3].duracion)


class TestTextos(unittest.TestCase):

    def test_duracion(self):
        self.assertEqual(texto_duracion(None), "")
        self.assertEqual(texto_duracion(1068), "17:48")
        self.assertEqual(texto_duracion(3725), "1:02:05")
        self.assertEqual(texto_duracion(0), "0:00")
        self.assertEqual(texto_duracion(59), "0:59")
        self.assertEqual(texto_duracion(60), "1:00")
        self.assertEqual(texto_duracion(3600), "1:00:00")

    def test_vistas(self):
        self.assertEqual(texto_vistas(None), "")
        self.assertEqual(texto_vistas(1), "1 vista")
        self.assertEqual(texto_vistas(2), "2 vistas")
        self.assertEqual(texto_vistas(4353830), "4.353.830 vistas")

    def test_fecha_tramos_y_bordes(self):
        ahora = 1700000000
        marca = lambda dias: ahora - dias * 86400
        self.assertEqual(texto_fecha(None, ahora), "")
        self.assertEqual(texto_fecha(ahora + 3600, ahora), "hoy")
        self.assertEqual(texto_fecha(ahora, ahora), "hoy")
        self.assertEqual(texto_fecha(marca(1), ahora), "hace 1 día")
        self.assertEqual(texto_fecha(marca(3), ahora), "hace 3 días")
        self.assertEqual(texto_fecha(marca(6), ahora), "hace 6 días")
        self.assertEqual(texto_fecha(marca(7), ahora), "hace 1 semana")
        self.assertEqual(texto_fecha(marca(14), ahora), "hace 2 semanas")
        self.assertEqual(texto_fecha(marca(30), ahora), "hace 1 mes")
        self.assertEqual(texto_fecha(marca(150), ahora), "hace 5 meses")
        self.assertEqual(texto_fecha(marca(365), ahora), "hace 1 año")
        self.assertEqual(texto_fecha(marca(5 * 365), ahora), "hace 5 años")


class TestBuscarArgumentos(unittest.TestCase):

    def _respuesta_ok(self, entradas):
        terminado = mock.Mock()
        terminado.returncode = 0
        terminado.stdout = json.dumps({"entries": entradas})
        terminado.stderr = ""
        return terminado

    def test_pasa_inicio_y_fin_y_hay_mas(self):
        entradas = [_video(id=f"v{i}") for i in range(10)]
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       return_value=self._respuesta_ok(entradas)) as correr:
            respuesta = buscar("cumbia", Filtros(), 6, 10)
        args = correr.call_args.args[0]
        self.assertIn("--playlist-start", args)
        self.assertIn("--playlist-end", args)
        self.assertEqual(
            args[args.index("--playlist-start") + 1], "6")
        self.assertEqual(args[args.index("--playlist-end") + 1], "15")
        self.assertIn("--extractor-args", args)
        self.assertIn("youtubetab:approximate_date", args)
        self.assertEqual(respuesta.error, "")
        self.assertTrue(respuesta.hay_mas)
        self.assertEqual(len(respuesta.resultados), 10)

    def test_hay_mas_falso_si_llegan_menos(self):
        entradas = [_video(id=f"v{i}") for i in range(4)]
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       return_value=self._respuesta_ok(entradas)):
            respuesta = buscar("cumbia", Filtros(), 1, 10)
        self.assertFalse(respuesta.hay_mas)

    def test_hay_mas_antes_de_refiltrar(self):
        viejo = _video(id="viejo")
        viejo["timestamp"] = 1000000000
        entradas = [viejo for _ in range(10)]
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       return_value=self._respuesta_ok(entradas)):
            respuesta = buscar("cumbia", Filtros(fecha="hoy"), 1, 10)
        self.assertTrue(respuesta.hay_mas)
        self.assertEqual(respuesta.resultados, [])

    def test_sin_ytdlp(self):
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value=None):
            respuesta = buscar("cumbia", Filtros(), 1, 10)
        self.assertEqual(respuesta.error, "yt-dlp no está instalado")
        self.assertEqual(respuesta.resultados, [])
        self.assertFalse(respuesta.hay_mas)

    def test_fallo_con_motivo_conocido(self):
        terminado = mock.Mock()
        terminado.returncode = 1
        terminado.stdout = ""
        terminado.stderr = "ERROR: [youtube] abc: Private video."
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       return_value=terminado):
            respuesta = buscar("cumbia", Filtros(), 1, 10)
        self.assertEqual(respuesta.error, "El vídeo es privado.")

    def test_fallo_generico_y_tiempo_agotado(self):
        from subprocess import TimeoutExpired
        generico = ("No se pudo completar la búsqueda. Comprueba la "
                    "conexión e inténtalo de nuevo.")
        terminado = mock.Mock()
        terminado.returncode = 1
        terminado.stdout = ""
        terminado.stderr = "ERROR: algo raro sin motivo"
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       return_value=terminado):
            self.assertEqual(
                buscar("cumbia", Filtros(), 1, 10).error, generico)
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       side_effect=TimeoutExpired("yt-dlp", 60)):
            self.assertEqual(
                buscar("cumbia", Filtros(), 1, 10).error, generico)
        with mock.patch(
                "bellbird.downloads.busqueda_youtube.ytdlp_bin.ruta_ytdlp",
                return_value="/fake/yt-dlp"), \
            mock.patch("bellbird.downloads.busqueda_youtube.subprocess.run",
                       side_effect=OSError("red caída")):
            self.assertEqual(
                buscar("cumbia", Filtros(), 1, 10).error, generico)


class TestBuscarRealConFalso(unittest.TestCase):

    def test_ejecuta_un_cmd_que_devuelve_json_utf8(self):
        from bellbird.downloads import ytdlp_bin
        with tempfile.TemporaryDirectory() as tmp:
            falso = os.path.join(tmp, "falso.cmd")
            datos = {"entries": [dict(
                _video(), title="Peña con acentos y 🎶",
                description="Árbol y emojis 🎉")]}
            texto = json.dumps(datos, ensure_ascii=False)
            with open(falso, "w", encoding="utf-8") as salida:
                salida.write("@echo off\r\n")
                salida.write("chcp 65001 >nul\r\n")
                salida.write("echo " + texto + "\r\n")
            # La URL lleva &sp=: cmd parte la línea y corre sp=... aparte.
            # Un sp.cmd mudo en el PATH deja el código en 0 sin ensuciar.
            with open(os.path.join(tmp, "sp.cmd"), "w",
                      encoding="utf-8") as salida:
                salida.write("@exit /b 0\r\n")
            entorno = dict(os.environ)
            entorno["PATH"] = tmp + os.pathsep + entorno.get("PATH", "")
            with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value=falso), \
                mock.patch.dict(os.environ, {"PATH": entorno["PATH"]}):
                respuesta = buscar("cumbia", Filtros(), 1, 20)
        self.assertEqual(respuesta.error, "")
        self.assertEqual(len(respuesta.resultados), 1)
        self.assertIn("Peña", respuesta.resultados[0].titulo)
        self.assertIn("🎶", respuesta.resultados[0].titulo)
        self.assertIn("Árbol", respuesta.resultados[0].descripcion)

    def test_ejecuta_un_cmd_que_falla(self):
        from bellbird.downloads import ytdlp_bin
        with tempfile.TemporaryDirectory() as tmp:
            falso = os.path.join(tmp, "falla.cmd")
            with open(falso, "w", encoding="utf-8") as salida:
                salida.write("@echo off\r\n")
                salida.write("echo ERROR: algo raro sin motivo 1>&2\r\n")
                salida.write("exit /b 1\r\n")
            with mock.patch.object(ytdlp_bin, "ruta_ytdlp", return_value=falso):
                respuesta = buscar("cumbia", Filtros(), 1, 10)
        self.assertEqual(respuesta.resultados, [])
        self.assertEqual(
            respuesta.error,
            "No se pudo completar la búsqueda. Comprueba la conexión e "
            "inténtalo de nuevo.")


class TestTextoDetalles(unittest.TestCase):

    AHORA = 1700000000

    def _resultado(self, **cambios):
        datos = dict(
            id="1", url="https://www.youtube.com/watch?v=1",
            titulo="CUMBIA PARAGUAYA RETRO", canal="Sanabria OK",
            duracion=1068, vistas=4353830,
            marca_tiempo=self.AHORA - 3 * 86400,
            descripcion="Una descripción", tipo="video",
            en_directo=False, programado=False)
        datos.update(cambios)
        return Resultado(**datos)

    def test_completo_una_linea_por_dato(self):
        self.assertEqual(
            texto_detalles(self._resultado(), self.AHORA),
            "CUMBIA PARAGUAYA RETRO\nSanabria OK\n17:48\n"
            "4.353.830 vistas\nhace 3 días\nUna descripción")

    def test_omite_los_vacios(self):
        self.assertEqual(
            texto_detalles(self._resultado(
                canal="", duracion=None, vistas=None, marca_tiempo=None,
                descripcion=""), self.AHORA),
            "CUMBIA PARAGUAYA RETRO")

    def test_en_directo_y_programado_agregan_su_linea(self):
        self.assertIn(
            "En directo",
            texto_detalles(self._resultado(
                duracion=None, vistas=None, marca_tiempo=None,
                descripcion="", en_directo=True), self.AHORA).splitlines())
        self.assertIn(
            "Programado",
            texto_detalles(self._resultado(
                duracion=None, vistas=None, marca_tiempo=None,
                descripcion="", programado=True), self.AHORA).splitlines())


if __name__ == "__main__":
    unittest.main()
