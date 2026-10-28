"""Tests de obs_prevuelo con un doble que simula lo medido en OBS real."""

import base64
import binascii
import struct
import unittest
import zlib

from ytchat.obs import obs_prevuelo
from ytchat.obs.obs_prevuelo import (
    EntradaAudio, Fuente, Revision, frase_revision, imagen_vacia_png,
    revisar)


def _paeth(izquierda, arriba, diagonal):
    base = izquierda + arriba - diagonal
    da, db, dc = abs(base - izquierda), abs(base - arriba), abs(base - diagonal)
    if da <= db and da <= dc:
        return izquierda
    if db <= dc:
        return arriba
    return diagonal


def armar_png(ancho, alto, pixel, con_alfa=True, filtro=0):
    """PNG real armado con zlib en la propia prueba."""
    plano = 4 if con_alfa else 3
    anterior = bytearray(ancho * plano)
    crudo = bytearray()
    for y in range(alto):
        cruda = bytearray()
        for x in range(ancho):
            cruda += bytes(pixel(x, y))
        crudo.append(filtro)
        for i, valor in enumerate(cruda):
            izquierda = cruda[i - plano] if i >= plano else 0
            arriba = anterior[i]
            diagonal = anterior[i - plano] if i >= plano else 0
            if filtro == 0:
                crudo.append(valor)
            elif filtro == 1:
                crudo.append((valor - izquierda) & 255)
            elif filtro == 2:
                crudo.append((valor - arriba) & 255)
            elif filtro == 3:
                crudo.append((valor - ((izquierda + arriba) >> 1)) & 255)
            else:
                crudo.append((valor - _paeth(izquierda, arriba, diagonal)) & 255)
        anterior = cruda
    tipo = 6 if con_alfa else 2

    def trozo(nombre, cuerpo):
        return (struct.pack(">I", len(cuerpo)) + nombre + cuerpo
                + struct.pack(">I", binascii.crc32(nombre + cuerpo) & 0xffffffff))

    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, tipo,
                                        0, 0, 0))
            + trozo(b"IDAT", zlib.compress(bytes(crudo)))
            + trozo(b"IEND", b""))


def imagen_dato(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class DoblePrevuelo:
    """OBS medido el 13/10/2026: escena con captura de ventana del juego,
    entradas de audio globales y captura de pantalla por PNG."""

    def __init__(self, perfil="TikTok", coleccion="TikTok", ancho=720,
                 alto=1280, escena="Escena", elementos=None, entradas=None,
                 ajustes=None, silencios=None, escenas=(), imagen=None,
                 falla_imagen=False):
        self.perfil = perfil
        self.coleccion = coleccion
        self.ancho = ancho
        self.alto = alto
        self.escena = escena
        self.elementos = list(elementos if elementos is not None else (
            {"sourceName": "Captura de ventana", "sceneItemEnabled": True},
            {"sourceName": "Chat YTChat", "sceneItemEnabled": True}))
        self.entradas = list(entradas if entradas is not None else (
            {"inputName": "Captura de ventana",
             "inputKind": "window_capture"},
            {"inputName": "Chat YTChat", "inputKind": "browser_source"},
            {"inputName": "Audio del escritorio",
             "inputKind": "wasapi_output_capture"},
            {"inputName": "Mic/Aux", "inputKind": "wasapi_input_capture"}))
        self.ajustes = dict(ajustes if ajustes is not None else {
            "Captura de ventana": {
                "window": ("Champions of The Rift:SDL_app:"
                           "Champions of The Rift.exe")},
            "Chat YTChat": {"url": "http://127.0.0.1:8765/panel/chat"}})
        self.silencios = dict(silencios if silencios is not None else {
            "Audio del escritorio": False, "Mic/Aux": False})
        self.escenas = list(escenas)
        self.imagen = imagen
        self.falla_imagen = falla_imagen
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        datos = datos or {}
        self.llamadas.append((tipo, dict(datos)))
        if tipo == "GetProfileList":
            return {"responseData": {"currentProfileName": self.perfil}}
        if tipo == "GetSceneCollectionList":
            return {"responseData": {
                "currentSceneCollectionName": self.coleccion}}
        if tipo == "GetVideoSettings":
            return {"responseData": {"baseWidth": self.ancho,
                                     "baseHeight": self.alto}}
        if tipo == "GetCurrentProgramScene":
            return {"responseData": {"currentProgramSceneName": self.escena}}
        if tipo == "GetSceneList":
            return {"responseData": {"scenes": [
                {"sceneName": nombre} for nombre in self.escenas]}}
        if tipo == "GetSceneItemList":
            return {"responseData": {"sceneItems": list(self.elementos)}}
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputSettings":
            return {"responseData": {"inputSettings": dict(
                self.ajustes.get(datos["inputName"], {}))}}
        if tipo == "GetInputMute":
            return {"responseData": {
                "inputMuted": self.silencios[datos["inputName"]]}}
        if tipo == "GetSourceScreenshot":
            if self.falla_imagen:
                raise RuntimeError("fuente sin imagen")
            return {"responseData": {"imageData": self.imagen}}
        return {"responseData": {}}


def doble_con_imagen(png, **extras):
    return DoblePrevuelo(imagen=imagen_dato(png), **extras)


def png_plano(ancho, alto, valores, con_alfa=True, filtro=0):
    return armar_png(ancho, alto, lambda x, y: valores, con_alfa, filtro)


def _trozo(nombre: bytes, cuerpo: bytes) -> bytes:
    return (struct.pack(">I", len(cuerpo)) + nombre + cuerpo
            + struct.pack(">I", binascii.crc32(nombre + cuerpo) & 0xffffffff))


def _png_con_idat(ancho, alto, tipo_color, carga_idat: bytes) -> bytes:
    """PNG con la carga IDAT dada, para forzar ramas del decodificador."""
    return (b"\x89PNG\r\n\x1a\n"
            + _trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8,
                                         tipo_color, 0, 0, 0))
            + _trozo(b"IDAT", carga_idat)
            + _trozo(b"IEND", b""))


class DobleQueFalla(DoblePrevuelo):
    """Doble que rompe un pedido concreto, para las ramas de error."""

    def __init__(self, falla_en, **extras):
        super().__init__(**extras)
        self.falla_en = falla_en

    def pedir(self, tipo, datos=None, parada=None):
        if tipo == self.falla_en:
            raise RuntimeError("falla " + tipo)
        return super().pedir(tipo, datos, parada)


class RevisarTest(unittest.TestCase):
    def test_mide_lo_real_sin_problemas(self):
        templado = armar_png(4, 4,
                             lambda x, y: (200, 100, 50, 255) if (x, y) == (1, 2)
                             else (0, 0, 0, 0))
        doble = doble_con_imagen(templado)
        revision = revisar(doble, "TikTok")
        self.assertEqual((revision.destino, revision.perfil,
                          revision.coleccion), ("TikTok",) * 3)
        self.assertEqual((revision.ancho, revision.alto), (720, 1280))
        self.assertEqual(revision.escena, "Escena")
        self.assertEqual(revision.fuentes, (
            Fuente("Captura de ventana", "captura de ventana",
                   "Champions of The Rift", True),
            Fuente("Chat YTChat", "navegador",
                   "panel de chat de la app", True)))
        self.assertEqual([(e.nombre, e.silenciada) for e in revision.audio],
                         [("Mic/Aux", False), ("Audio del escritorio", False)])
        self.assertIs(revision.imagen_vacia, False)
        self.assertEqual(revision.problemas, ())
        # La captura de la escena se pide en png de 64 de ancho.
        llamada = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "GetSourceScreenshot")
        self.assertEqual(llamada[1], {"sourceName": "Escena",
                                      "imageFormat": "png", "imageWidth": 64})
        self.assertIsInstance(revision, Revision)

    def test_perfil_distinto_del_destino(self):
        doble = DoblePrevuelo(perfil="YouTube",
                              imagen=imagen_dato(png_plano(2, 2, (200, 0, 0, 255))))
        revision = revisar(doble, "TikTok")
        self.assertIn("OBS está en el perfil YouTube, no en TikTok. "
                      "Pulsa Preparar destino.", revision.problemas)
        self.assertEqual(revision.problemas[0],
                         "OBS está en el perfil YouTube, no en TikTok. "
                         "Pulsa Preparar destino.")

    def test_microfono_silenciado(self):
        doble = DoblePrevuelo(
            silencios={"Audio del escritorio": False, "Mic/Aux": True},
            imagen=imagen_dato(png_plano(2, 2, (200, 0, 0, 255))))
        revision = revisar(doble, "TikTok")
        self.assertIn("El micrófono Mic/Aux está silenciado.",
                      revision.problemas)

    def test_escritorio_silenciado(self):
        doble = DoblePrevuelo(
            silencios={"Audio del escritorio": True, "Mic/Aux": False},
            imagen=imagen_dato(png_plano(2, 2, (200, 0, 0, 255))))
        revision = revisar(doble, "TikTok")
        self.assertIn("El audio del escritorio Audio del escritorio "
                      "está silenciado.", revision.problemas)

    def test_problemas_en_orden(self):
        doble = DoblePrevuelo(
            perfil="YouTube", elementos=(),
            silencios={"Audio del escritorio": True, "Mic/Aux": True},
            imagen=imagen_dato(png_plano(2, 2, (0, 0, 0, 0))))
        revision = revisar(doble, "TikTok")
        self.assertEqual(list(revision.problemas), [
            "OBS está en el perfil YouTube, no en TikTok. "
            "Pulsa Preparar destino.",
            "El micrófono Mic/Aux está silenciado.",
            "El audio del escritorio Audio del escritorio está silenciado.",
            "La escena no tiene ninguna fuente visible. "
            "Para agregar una: Transmisión, sección Escena, "
            "elegir la ventana en Ventana que se captura y "
            "pulsar Usar esa ventana.",
            "La imagen está vacía: la escena se ve en negro. "
            "Revisar que la ventana capturada esté abierta y "
            "no minimizada."])

    def test_escena_sin_fuentes_visibles(self):
        doble = DoblePrevuelo(
            elementos=[{"sourceName": "Captura de ventana",
                        "sceneItemEnabled": False}],
            imagen=imagen_dato(png_plano(2, 2, (200, 0, 0, 255))))
        revision = revisar(doble, "TikTok")
        self.assertIn("La escena no tiene ninguna fuente visible. "
                      "Para agregar una: Transmisión, sección Escena, "
                      "elegir la ventana en Ventana que se captura y "
                      "pulsar Usar esa ventana.",
                      revision.problemas)

    def test_imagen_vacia_da_problema(self):
        doble = DoblePrevuelo(
            imagen=imagen_dato(png_plano(3, 3, (0, 0, 0, 0))))
        revision = revisar(doble, "TikTok")
        self.assertIs(revision.imagen_vacia, True)
        self.assertIn("La imagen está vacía: la escena se ve en negro. "
                      "Revisar que la ventana capturada esté abierta y "
                      "no minimizada.",
                      revision.problemas)

    def test_imagen_ilesa_da_none_sin_problema(self):
        doble = DoblePrevuelo(imagen="data:image/png;base64,aG9sYQ==")
        revision = revisar(doble, "TikTok")
        self.assertIsNone(revision.imagen_vacia)
        self.assertNotIn("vacía", " ".join(revision.problemas))

    def test_imagen_que_falla_da_none_sin_problema(self):
        doble = DoblePrevuelo(imagen=None, falla_imagen=True)
        revision = revisar(doble, "TikTok")
        self.assertIsNone(revision.imagen_vacia)
        self.assertNotIn("vacía", " ".join(revision.problemas))

    def test_tipos_legibles(self):
        casos = {"window_capture": "captura de ventana",
                 "game_capture": "captura de juego",
                 "monitor_capture": "captura de pantalla",
                 "dshow_input": "cámara",
                 "browser_source": "navegador",
                 "image_source": "imagen",
                 "ffmpeg_source": "vídeo",
                 "text_gdiplus_v3": "texto",
                 "text_gdiplus": "texto",
                 "otro_nuevo": "otro_nuevo"}
        for clase, esperado in casos.items():
            with self.subTest(clase=clase):
                doble = DoblePrevuelo(
                    elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
                    entradas=[{"inputName": "F", "inputKind": clase}],
                    ajustes={}, silencios={},
                    imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
                (fuente,) = revisar(doble, "TikTok").fuentes
                self.assertEqual(fuente.tipo, esperado)

    def test_escena_anidada_cuenta_como_escena(self):
        doble = DoblePrevuelo(
            elementos=[{"sourceName": "Juego", "sceneItemEnabled": True}],
            entradas=[{"inputName": "Juego", "inputKind": "scene"}],
            escenas=["Escena", "Juego"], ajustes={}, silencios={},
            imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
        (fuente,) = revisar(doble, "TikTok").fuentes
        self.assertEqual(fuente.tipo, "escena")

    def test_detalle_ventana_titulo_y_ejecutable(self):
        with self.subTest(caso="título"):
            doble = DoblePrevuelo(
                elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
                entradas=[{"inputName": "F", "inputKind": "game_capture"}],
                ajustes={"F": {"window": "Mi Juego:clase:juego.exe"}},
                silencios={},
                imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
            (fuente,) = revisar(doble, "TikTok").fuentes
            self.assertEqual(fuente.detalle, "Mi Juego")
        with self.subTest(caso="sin título usa el ejecutable"):
            doble = DoblePrevuelo(
                elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
                entradas=[{"inputName": "F", "inputKind": "game_capture"}],
                ajustes={"F": {"window": ":clase:juego.exe"}},
                silencios={},
                imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
            (fuente,) = revisar(doble, "TikTok").fuentes
            self.assertEqual(fuente.detalle, "juego.exe")

    def test_detalle_navegador_solo_para_el_chat(self):
        with self.subTest(caso="panel"):
            doble = DoblePrevuelo(
                elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
                entradas=[{"inputName": "F", "inputKind": "browser_source"}],
                ajustes={"F": {"url": "http://127.0.0.1:8765/panel/chat"}},
                silencios={},
                imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
            (fuente,) = revisar(doble, "TikTok").fuentes
            self.assertEqual(fuente.detalle, "panel de chat de la app")
        with self.subTest(caso="otra página"):
            doble = DoblePrevuelo(
                elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
                entradas=[{"inputName": "F", "inputKind": "browser_source"}],
                ajustes={"F": {"url": "https://ejemplo.com/algo"}},
                silencios={},
                imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
            (fuente,) = revisar(doble, "TikTok").fuentes
            self.assertEqual(fuente.detalle, "")


class FraseRevisionTest(unittest.TestCase):
    def test_frase_exacta_sin_problemas(self):
        doble = DoblePrevuelo(
            imagen=imagen_dato(armar_png(
                4, 4, lambda x, y: (200, 100, 50, 255) if (x, y) == (0, 0)
                else (0, 0, 0, 0))))
        self.assertEqual(frase_revision(revisar(doble, "TikTok")),
                         "Destino TikTok. Perfil TikTok, formato vertical "
                         "720 por 1280. Escena al aire: Escena. Fuentes: "
                         "captura de ventana Champions of The Rift, "
                         "navegador panel de chat de la app. "
                         "Micrófono Mic/Aux con sonido. "
                         "Audio del escritorio con sonido.")

    def test_frase_con_problemas_agrega_atencion(self):
        doble = DoblePrevuelo(
            perfil="YouTube",
            silencios={"Audio del escritorio": False, "Mic/Aux": True},
            imagen=imagen_dato(png_plano(2, 2, (0, 0, 0, 0))))
        frase = frase_revision(revisar(doble, "TikTok"))
        self.assertIn("Atención: OBS está en el perfil YouTube, no en "
                      "TikTok. Pulsa Preparar destino. "
                      "El micrófono Mic/Aux está silenciado.", frase)

    def test_frase_horizontal(self):
        revision = Revision("YouTube", "YouTube", "Juego", 1280, 720,
                            "Escena", (), (), False, ())
        self.assertIn("formato horizontal 1280 por 720",
                      frase_revision(revision))


class ImagenVaciaPngTest(unittest.TestCase):
    def test_todo_transparente_es_vacia(self):
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (0, 0, 0, 0))), True)

    def test_todo_negro_es_vacia(self):
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (0, 0, 0, 255))), True)
        self.assertIs(imagen_vacia_png(png_plano(3, 2, (15, 15, 15, 255))),
                      True)

    def test_un_pixel_claro_no_es_vacia(self):
        png = armar_png(3, 2, lambda x, y: (200, 100, 50, 255)
                        if (x, y) == (1, 1) else (0, 0, 0, 0))
        self.assertIs(imagen_vacia_png(png), False)

    def test_pixel_claro_transparente_sigue_vacia(self):
        png = armar_png(2, 2, lambda x, y: (200, 200, 200, 0))
        self.assertIs(imagen_vacia_png(png), True)

    def test_rgb_sin_alfa(self):
        self.assertIs(imagen_vacia_png(png_plano(2, 2, (0, 0, 0), False)),
                      True)
        png = armar_png(2, 2, lambda x, y: (0, 200, 0) if (x, y) == (0, 0)
                        else (0, 0, 0), False)
        self.assertIs(imagen_vacia_png(png), False)

    def test_filtros_distintos_decodifican(self):
        for filtro in (0, 1, 2, 3, 4):
            with self.subTest(filtro=filtro):
                png = armar_png(
                    4, 3, lambda x, y: ((x * 40 + y * 7) % 256,
                                        (x * 13 + y * 29) % 256,
                                        (x * 5 + y * 11) % 256, 255),
                    filtro=filtro)
                self.assertIs(imagen_vacia_png(png), False)

    def test_basura_da_none(self):
        self.assertIsNone(imagen_vacia_png(b"esto no es un png"))
        self.assertIsNone(imagen_vacia_png(b""))
        png = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        self.assertIsNone(imagen_vacia_png(png[:40]))

    def test_gris_sin_soporte_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[25] = 0
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_entrada_audio_conserva_si_es_escritorio(self):
        self.assertFalse(EntradaAudio("Mic/Aux", False).escritorio)
        self.assertTrue(EntradaAudio("Audio del escritorio", False,
                                     True).escritorio)

    def test_trozo_truncado_da_none(self):
        png = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        self.assertIsNone(imagen_vacia_png(png[:30]))

    def test_ihdr_con_largo_invalido_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[8:12] = b"\x00\x00\x00\x05"
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_ancho_cero_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[16:20] = b"\x00\x00\x00\x00"
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_dimension_enorme_da_none(self):
        png = bytearray(armar_png(2, 2, lambda x, y: (0, 0, 0, 0)))
        png[16:20] = struct.pack(">I", 5000)
        png[20:24] = struct.pack(">I", 5000)
        self.assertIsNone(imagen_vacia_png(bytes(png)))

    def test_idat_con_largo_incorrecto_da_none(self):
        png = _png_con_idat(2, 2, 6, zlib.compress(b"corto"))
        self.assertIsNone(imagen_vacia_png(png))

    def test_filtro_desconocido_da_none(self):
        png = _png_con_idat(1, 1, 6, zlib.compress(bytes([7, 0, 0, 0, 0])))
        self.assertIsNone(imagen_vacia_png(png))

    def test_idat_corrupto_da_none(self):
        png = _png_con_idat(2, 2, 6, b"esto-no-es-zlib")
        self.assertIsNone(imagen_vacia_png(png))

    def test_trozo_auxiliar_se_ignora(self):
        base = armar_png(2, 2, lambda x, y: (0, 0, 0, 0))
        con_texto = base[:33] + _trozo(b"tEXt", b"a\x00b") + base[33:]
        self.assertIs(imagen_vacia_png(con_texto), True)

    def test_paeth_elige_diagonal(self):
        self.assertEqual(obs_prevuelo._paeth(10, 200, 105), 105)

    def test_paeth_elige_arriba(self):
        self.assertEqual(obs_prevuelo._paeth(100, 0, 90), 0)


class RamasRevisarTest(unittest.TestCase):
    """Caracterización de las ramas de revisar que la cobertura del
    16/10/2026 mostró sin ejecutar, fijadas contra el código de hoy."""

    def test_imagen_sin_prefijo_data_funciona(self):
        png = png_plano(2, 2, (0, 0, 0, 0))
        doble = DoblePrevuelo(
            imagen=base64.b64encode(png).decode("ascii"))
        self.assertIs(revisar(doble, "TikTok").imagen_vacia, True)

    def test_imagen_base64_rota_da_none(self):
        doble = DoblePrevuelo(imagen="!!no-es-base64!!")
        revision = revisar(doble, "TikTok")
        self.assertIsNone(revision.imagen_vacia)
        self.assertNotIn("vacía", " ".join(revision.problemas))

    def test_formato_cuadrado(self):
        revision = Revision("YouTube", "YouTube", "Juego", 1280, 1280,
                            "Escena", (), (), False, ())
        self.assertIn("formato cuadrado 1280 por 1280",
                      frase_revision(revision))

    def test_frase_sin_dimensiones(self):
        revision = Revision("TikTok", "TikTok", "Colección", None, None,
                            "Escena", (), (), None, ())
        frase = frase_revision(revision)
        self.assertIn("Perfil TikTok.", frase)
        self.assertNotIn("formato", frase)

    def test_frase_escritorio_con_nombre_propio(self):
        revision = Revision("TikTok", "TikTok", "Colección", 720, 1280,
                            "Escena", (),
                            (EntradaAudio("Altavoces", True, True),),
                            False, ())
        self.assertIn("Audio del escritorio Altavoces silenciado.",
                      frase_revision(revision))

    def test_entrada_sin_clase_da_tipo_vacio(self):
        doble = DoblePrevuelo(
            elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
            entradas=[{"inputName": "F"}],
            ajustes={}, silencios={},
            imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
        (fuente,) = revisar(doble, "TikTok").fuentes
        self.assertEqual(fuente.tipo, "")

    def test_ajustes_ventana_que_fallan_dan_detalle_vacio(self):
        doble = DobleQueFalla(
            "GetInputSettings",
            elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
            entradas=[{"inputName": "F", "inputKind": "window_capture"}],
            ajustes={}, silencios={},
            imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
        (fuente,) = revisar(doble, "TikTok").fuentes
        self.assertEqual(fuente.detalle, "")

    def test_ajustes_navegador_que_fallan_dan_detalle_vacio(self):
        doble = DobleQueFalla(
            "GetInputSettings",
            elementos=[{"sourceName": "F", "sceneItemEnabled": True}],
            entradas=[{"inputName": "F", "inputKind": "browser_source"}],
            ajustes={}, silencios={},
            imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
        (fuente,) = revisar(doble, "TikTok").fuentes
        self.assertEqual(fuente.detalle, "")

    def test_silencio_que_falla_se_omite(self):
        doble = DobleQueFalla(
            "GetInputMute",
            imagen=imagen_dato(png_plano(2, 2, (200, 0, 0, 255))))
        revision = revisar(doble, "TikTok")
        self.assertEqual(revision.audio, ())
        self.assertNotIn("silenciado", " ".join(revision.problemas))

    def test_lista_escenas_que_falla_usa_el_tipo(self):
        doble = DobleQueFalla(
            "GetSceneList",
            elementos=[{"sourceName": "Juego", "sceneItemEnabled": True}],
            entradas=[{"inputName": "Juego", "inputKind": "window_capture"}],
            ajustes={"Juego": {"window": "Juego:clase:juego.exe"}},
            silencios={},
            imagen=imagen_dato(png_plano(1, 1, (200, 0, 0, 255))))
        (fuente,) = revisar(doble, "TikTok").fuentes
        self.assertEqual(fuente.tipo, "captura de ventana")


if __name__ == "__main__":
    unittest.main()
