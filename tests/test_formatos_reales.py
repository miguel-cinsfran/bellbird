"""Opciones reales de un vídeo a partir de lo que devuelve yt-dlp, sin wx."""

import itertools
import random
import unittest

from bellbird.downloads import formatos_reales as fr


def formato(fid, ext="mp4", alto=None, vcodec="none", acodec="none",
            abr=None, tamano=None, nota="", fps=None, proto="https",
            aprox=False, tbr=None):
    """Un formato como los de `--dump-json`, con lo que usa `opciones()`."""
    f = {"format_id": fid, "ext": ext, "height": alto, "vcodec": vcodec,
         "acodec": acodec, "protocol": proto, "format_note": nota}
    if fps is not None:
        f["fps"] = fps
    if abr is not None:
        f["abr"] = abr
    if tamano is not None:
        f["filesize_approx" if aprox else "filesize"] = tamano
    if tbr is not None:
        f["tbr"] = tbr
    return f


# Extracto medido el 30/10/2026 con `-J` sobre
# https://www.youtube.com/watch?v=aqz-KE-bpKQ.
EVIDENCIA = [
    formato("139-drc", "m4a", None, "none", "mp4a.40.2", 48.8, 3871021,
            "low, DRC"),
    formato("140", "m4a", None, "none", "mp4a.40.2", 129.5, 10271496,
            "medium"),
    formato("251", "webm", None, "none", "opus", 128.6, 10202210, "medium"),
    formato("251-drc", "webm", None, "none", "opus", 129.3, 10258925,
            "medium, DRC"),
    formato("258", "m4a", None, "none", "mp4a.40.2", 387.9, 30767611,
            "high"),
    formato("380", "m4a", None, "none", "ac-3", 384.1, 30468809, "high"),
    formato("18", "mp4", 360, "avc1.42001E", "mp4a.40.2", None, 28526904,
            "360p", fps=30),
    formato("134", "mp4", 360, "avc1.4D401E", "none", None, 18294110,
            "360p", fps=30),
    formato("243", "webm", 360, "vp9", "none", None, 24109536, "360p",
            fps=30),
    formato("396", "mp4", 360, "av01.0.01M.08", "none", None, 15298808,
            "360p", fps=30),
    formato("136", "mp4", 720, "avc1.4D401F", "none", None, 87293859,
            "720p", fps=30),
    formato("298", "mp4", 720, "avc1.4D4020", "none", None, 150524867,
            "720p60", fps=60),
    formato("302", "webm", 720, "vp9", "none", None, 112676322, "720p60",
            fps=60),
    formato("299", "mp4", 1080, "avc1.64002A", "none", None, 257619653,
            "1080p60", fps=60),
    formato("303", "webm", 1080, "vp9", "none", None, 168736189, "1080p60",
            fps=60),
    formato("308", "webm", 1440, "vp9", "none", None, 473363704, "1440p60",
            fps=60),
    formato("400", "mp4", 1440, "av01.0.08M.08", "none", None, 312554313,
            "1440p60", fps=60),
    formato("315", "webm", 2160, "vp9", "none", None, 1362269481, "2160p60",
            fps=60),
]


def info_con(*formatos):
    return {"id": "aqz-KE-bpKQ", "formats": list(formatos)}


def por_selector(opciones, inicio):
    return [o for o in opciones if o.selector.startswith(inicio)]


class TestEligeVideo(unittest.TestCase):
    def test_720p60_elige_h264_y_no_vp9(self):
        opciones = fr.opciones(info_con(
            formato("298", "mp4", 720, "avc1.4D4020", "none", None,
                    150524867, "720p60", fps=60),
            formato("302", "webm", 720, "vp9", "none", None, 112676322,
                    "720p60", fps=60),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium"),
            formato("251", "webm", None, "none", "opus", 128.6, 10202210,
                    "medium")))
        self.assertEqual([o.selector for o in opciones
                          if o.selector.startswith(("298", "302"))],
                         ["298+140"])

    def test_1440p60_sin_h264_elige_vp9_y_no_av1(self):
        opciones = fr.opciones(info_con(
            formato("308", "webm", 1440, "vp9", "none", None, 473363704,
                    "1440p60", fps=60),
            formato("400", "mp4", 1440, "av01.0.08M.08", "none", None,
                    312554313, "1440p60", fps=60),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium"),
            formato("251", "webm", None, "none", "opus", 128.6, 10202210,
                    "medium")))
        self.assertEqual([o.selector for o in opciones
                          if o.selector.startswith(("308", "400"))],
                         ["308+251"])

    def test_entre_iguales_gana_mas_tbr(self):
        opciones = fr.opciones(info_con(
            formato("a", "mp4", 720, "avc1.4D4020", "none", None, 100,
                    tbr=1000, fps=30),
            formato("b", "mp4", 720, "avc1.4D4020", "none", None, 100,
                    tbr=2000, fps=30),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5, 100,
                    "medium")))
        self.assertEqual([o.selector for o in opciones
                          if o.contenedor == "mp4" and "+" in o.selector],
                         ["b+140"])


class TestSelectorYAudios(unittest.TestCase):
    def test_1080p60_une_video_y_audio(self):
        opciones = fr.opciones(info_con(
            formato("299", "mp4", 1080, "avc1.64002A", "none", None,
                    257619653, "1080p60", fps=60),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium"),
            formato("380", "m4a", None, "none", "ac-3", 384.1, 30468809,
                    "high")))
        self.assertEqual(por_selector(opciones, "299")[0].selector,
                         "299+140")

    def test_webm_une_con_opus(self):
        opciones = fr.opciones(info_con(
            formato("308", "webm", 1440, "vp9", "none", None, 473363704,
                    "1440p60", fps=60),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium"),
            formato("251", "webm", None, "none", "opus", 128.6, 10202210,
                    "medium")))
        self.assertTrue(por_selector(opciones, "308")[0].selector.endswith(
            "+251"))

    def test_mejor_audio_es_mas_abr(self):
        opciones = fr.opciones(info_con(
            formato("299", "mp4", 1080, "avc1.64002A", "none", None,
                    257619653, "1080p60", fps=60),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium"),
            formato("258", "m4a", None, "none", "mp4a.40.2", 387.9,
                    30767611, "high")))
        self.assertEqual(por_selector(opciones, "299")[0].selector,
                         "299+258")

    def test_18_no_entra_si_hay_solo_video_en_su_par(self):
        opciones = fr.opciones(info_con(
            formato("18", "mp4", 360, "avc1.42001E", "mp4a.40.2", None,
                    28526904, "360p", fps=30),
            formato("134", "mp4", 360, "avc1.4D401E", "none", None,
                    18294110, "360p", fps=30),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium")))
        selectores = [o.selector for o in opciones
                      if o.contenedor == "mp4" and "360" in o.etiqueta]
        self.assertEqual(selectores, ["134+140"])

    def test_mixto_entra_solo_si_no_hay_solo_video(self):
        opciones = fr.opciones(info_con(
            formato("18", "mp4", 360, "avc1.42001E", "mp4a.40.2", None,
                    28526904, "360p", fps=30),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium")))
        self.assertEqual([o.selector for o in opciones
                          if o.contenedor == "mp4"], ["18"])

    def test_drc_y_ac3_nunca_se_eligen(self):
        opciones = fr.opciones(info_con(*EVIDENCIA))
        for o in opciones:
            with self.subTest(selector=o.selector):
                self.assertNotIn("drc", o.selector)
                self.assertNotIn("139", o.selector.split("+"))
                self.assertNotIn("380", o.selector.split("+"))


class TestTamano(unittest.TestCase):
    def test_es_la_suma_de_video_y_audio(self):
        opciones = fr.opciones(info_con(
            formato("134", "mp4", 360, "avc1.4D401E", "none", None,
                    18294110, "360p", fps=30),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5,
                    10271496, "medium")))
        self.assertEqual(por_selector(opciones, "134")[0].tamano,
                         18294110 + 10271496)

    def test_usa_aprox_si_falta_el_exacto(self):
        opciones = fr.opciones(info_con(
            formato("134", "mp4", 360, "avc1.4D401E", "none", None, 1000,
                    "360p", fps=30, aprox=True),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5, 2000,
                    "medium")))
        self.assertEqual(por_selector(opciones, "134")[0].tamano, 3000)

    def test_es_none_si_falta_en_uno(self):
        opciones = fr.opciones(info_con(
            formato("134", "mp4", 360, "avc1.4D401E", "none", None, 1000,
                    "360p", fps=30),
            formato("140", "m4a", None, "none", "mp4a.40.2", 129.5, None,
                    "medium")))
        self.assertIsNone(por_selector(opciones, "134")[0].tamano)


class TestOrden(unittest.TestCase):
    def test_de_mayor_a_menor_con_audio_al_final(self):
        opciones = fr.opciones(info_con(*EVIDENCIA))
        self.assertTrue(opciones)
        *videos, ultima = opciones
        self.assertTrue(videos[0].etiqueta.startswith("2160p"))
        self.assertTrue(videos[-1].etiqueta.startswith("360p"))
        for primera, segunda in itertools.pairwise(videos):
            with self.subTest(primera=primera.etiqueta,
                              segunda=segunda.etiqueta):
                self.assertGreaterEqual(_clave(primera), _clave(segunda))
        self.assertTrue(ultima.etiqueta.startswith("Solo audio"))

    def test_sin_formatos_da_lista_vacia(self):
        self.assertEqual(fr.opciones({}), [])
        self.assertEqual(fr.opciones({"formats": []}), [])
        self.assertEqual(fr.opciones({"formats": [
            formato("malo", "mp4", 720, "none", "none", None, 100)]}), [])


def _clave(opcion):
    etiqueta = opcion.etiqueta
    alto = int(etiqueta.split("p")[0].split()[-1])
    cuadros = 0
    if " fps," in etiqueta:
        cuadros = int(etiqueta.split(" fps,")[0].split()[-1])
    return (alto, cuadros)


class TestEtiquetas(unittest.TestCase):
    def _video(self, fps, tamano):
        opciones = fr.opciones(info_con(
            formato("v", "mp4", 720, "avc1.4D4020", "none", None, tamano,
                    fps=fps),
            formato("140", "m4a", None, "none", "mp4a.40.2", 128, 1000,
                    "medium")))
        return por_selector(opciones, "v")[0]

    def test_video_sin_cuadros(self):
        self.assertEqual(self._video(30, 3000000).etiqueta,
                         "720p, MP4, 3 MB")

    def test_video_con_cuadros(self):
        self.assertEqual(self._video(60, 3000000).etiqueta,
                         "720p 60 fps, MP4, 3 MB")

    def test_solo_audio(self):
        opciones = fr.opciones(info_con(
            formato("140", "m4a", None, "none", "mp4a.40.2", 128, 2000000,
                    "medium")))
        audios = [o for o in opciones if "+" not in o.selector]
        self.assertEqual(len(audios), 1)
        self.assertEqual(audios[0].etiqueta,
                         "Solo audio, M4A, 128 kbps, 2 MB")


class TestTextosDeTamano(unittest.TestCase):
    def _etiqueta_con_tamano(self, tamano):
        opciones = fr.opciones(info_con(
            formato("v", "mp4", 720, "avc1.4D4020", "none", None, tamano),
            formato("140", "m4a", None, "none", "mp4a.40.2", 128, 1000,
                    "medium")))
        return por_selector(opciones, "v")[0].etiqueta

    def test_megas_redondeados(self):
        self.assertTrue(self._etiqueta_con_tamano(3000000).endswith("3 MB"))

    def test_menos_de_un_mega(self):
        self.assertTrue(self._etiqueta_con_tamano(100).endswith(
            "menos de 1 MB"))

    def test_desconocido(self):
        self.assertTrue(self._etiqueta_con_tamano(None).endswith(
            "tamaño desconocido"))


class TestPropiedadOrden(unittest.TestCase):
    def test_cualquier_orden_da_lo_mismo(self):
        esperado = [(o.etiqueta, o.selector, o.contenedor, o.tamano)
                    for o in fr.opciones(info_con(*EVIDENCIA))]
        ordenes = [list(reversed(EVIDENCIA))]
        azar = random.Random(30)
        for _ in range(5):
            copia = list(EVIDENCIA)
            azar.shuffle(copia)
            ordenes.append(copia)
        for i, orden in enumerate(ordenes):
            with self.subTest(orden=i):
                obtenido = [(o.etiqueta, o.selector, o.contenedor, o.tamano)
                            for o in fr.opciones(info_con(*orden))]
                self.assertEqual(obtenido, esperado)


class TestTransitorias(unittest.TestCase):
    def test_pasa_selector_y_contenedor(self):
        opcion = fr.OpcionFormato(etiqueta="720p, MP4, 3 MB",
                                  selector="298+140", contenedor="mp4",
                                  tamano=3000000)
        self.assertEqual(fr.transitorias(opcion),
                         {"formato": "exacto", "selector": "298+140",
                          "contenedor": "mp4"})


if __name__ == "__main__":
    unittest.main()
