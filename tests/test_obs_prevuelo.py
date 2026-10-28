"""Tests de obs_prevuelo con un doble que simula lo medido en OBS real."""

import base64
import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.core.idioma import _
from ytchat.obs import obs_prevuelo
from ytchat.obs.obs_prevuelo import (
    EntradaAudio, Fuente, Revision, frase_revision, revisar)
from ytchat.obs.obs_grabacion import AVISO_CODIFICADOR
from tests.png_prueba import armar_png, png_plano


def imagen_dato(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class DoblePrevuelo:
    """OBS medido el 13/10/2026: escena con captura de ventana del juego,
    entradas de audio globales y captura de pantalla por PNG."""

    def __init__(self, perfil="TikTok", coleccion="TikTok", ancho=720,
                 alto=1280, escena="Escena", elementos=None, entradas=None,
                 ajustes=None, silencios=None, escenas=(), imagen=None,
                 falla_imagen=False, modo="Simple", calidad="Stream",
                 codificador="none"):
        self.perfil = perfil
        self.coleccion = coleccion
        self.ancho = ancho
        self.alto = alto
        self.escena = escena
        self.modo = modo
        self.calidad = calidad
        self.codificador = codificador
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
        if tipo == "GetProfileParameter":
            valores = {
                ("Output", "Mode"): self.modo,
                ("SimpleOutput", "RecQuality"): self.calidad,
                ("AdvOut", "RecEncoder"): self.codificador,
            }
            clave = (datos.get("parameterCategory"),
                     datos.get("parameterName"))
            return {"responseData": {
                "parameterValue": valores.get(clave, "")}}
        return {"responseData": {}}


def doble_con_imagen(png, **extras):
    return DoblePrevuelo(imagen=imagen_dato(png), **extras)


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


class AvisosGrabacionTest(unittest.TestCase):
    def _imagen(self):
        return imagen_dato(png_plano(2, 2, (200, 0, 0, 255)))

    def test_codificador_propio_va_a_avisos_y_no_a_problemas(self):
        doble = DoblePrevuelo(modo="Advanced", codificador="x264",
                              imagen=self._imagen())
        revision = revisar(doble, "TikTok", grabar=True)
        self.assertEqual(revision.avisos, (AVISO_CODIFICADOR,))
        self.assertEqual(revision.problemas, ())

    def test_la_frase_lleva_el_aviso_al_final(self):
        doble = DoblePrevuelo(modo="Advanced", codificador="x264",
                              imagen=self._imagen())
        frase = frase_revision(revisar(doble, "TikTok", grabar=True))
        self.assertTrue(frase.endswith(AVISO_CODIFICADOR), frase)

    def test_el_aviso_va_despues_de_atencion(self):
        doble = DoblePrevuelo(perfil="YouTube", modo="Advanced",
                              codificador="x264", imagen=self._imagen())
        frase = frase_revision(revisar(doble, "TikTok", grabar=True))
        self.assertIn("Atención: OBS está en el perfil YouTube", frase)
        self.assertTrue(frase.endswith(AVISO_CODIFICADOR), frase)

    def test_codificador_compartido_no_avisa(self):
        doble = DoblePrevuelo(imagen=self._imagen())
        revision = revisar(doble, "TikTok", grabar=True)
        self.assertEqual(revision.avisos, ())

    def test_sin_grabar_no_pregunta_el_codificador(self):
        doble = DoblePrevuelo(imagen=self._imagen())
        revisar(doble, "TikTok", grabar=False)
        self.assertFalse(any(tipo == "GetProfileParameter"
                             for tipo, _ in doble.llamadas))

    def test_si_obs_falla_no_hay_aviso(self):
        doble = DobleQueFalla("GetProfileParameter", imagen=self._imagen())
        revision = revisar(doble, "TikTok", grabar=True)
        self.assertEqual(revision.avisos, ())


class TestTablaTiposSinVentana(unittest.TestCase):
    # Sin ventana: la tabla vive en el módulo, así no se crea ningún control.

    def test_tabla_cubre_los_tipos_conocidos_con_el_texto_de_hoy(self):
        self.assertEqual(set(obs_prevuelo._TIPOS),
                         {"window_capture", "game_capture", "monitor_capture",
                          "dshow_input", "browser_source", "image_source",
                          "ffmpeg_source", "text_gdiplus_v3", "text_gdiplus"})
        self.assertEqual(
            {clase: texto for clase, texto in obs_prevuelo._TIPOS.items()},
            {"window_capture": "captura de ventana",
             "game_capture": "captura de juego",
             "monitor_capture": "captura de pantalla",
             "dshow_input": "cámara",
             "browser_source": "navegador",
             "image_source": "imagen",
             "ffmpeg_source": "vídeo",
             "text_gdiplus_v3": "texto",
             "text_gdiplus": "texto"})

    def test_tabla_se_traduce_donde_se_usa(self):
        with con_pseudo():
            for clase in obs_prevuelo._TIPOS:
                with self.subTest(clase=clase):
                    self.assertTrue(
                        _(obs_prevuelo._TIPOS[clase]).startswith("[¡"),
                        clase)
            self.assertTrue(_(obs_prevuelo._TIPO_ESCENA).startswith("[¡"))

    def test_formato_sale_marcado(self):
        with con_pseudo():
            self.assertTrue(obs_prevuelo._formato(720, 1280).startswith("[¡"))
            self.assertTrue(obs_prevuelo._formato(1280, 720).startswith("[¡"))
            self.assertTrue(obs_prevuelo._formato(1280, 1280).startswith("[¡"))


class TestPseudoFraseRevision(unittest.TestCase):
    """Pseudotraducción de `frase_revision` y de los problemas.

    Sin ventana: llama a las funciones bajo `con_pseudo()` y exige los
    fragmentos propios marcados, con los datos de ejemplo presentes. El
    aviso del codificador lo arma `obs_grabacion`, fuera del alcance: se
    exige marcado donde se muestra, en `frase_revision`. El nombre de la
    fuente de audio que compara la revisión es un dato de OBS y queda
    como está.
    """

    def _revision_ejemplo(self, problemas=(), avisos=()):
        return Revision(
            "TikTok", "TikTok", "TikTok", 720, 1280, "Escena",
            (Fuente("Juego", "captura de ventana", "Mi Juego", True),
             Fuente("Chat", "navegador", "panel de chat de la app", True)),
            (EntradaAudio("Mic/Aux", False),
             EntradaAudio("Audio del escritorio", False, True)),
            False, tuple(problemas), tuple(avisos))

    def _imagen(self):
        return imagen_dato(png_plano(2, 2, (200, 0, 0, 255)))

    def test_frase_marca_los_fragmentos_propios_con_los_datos(self):
        with con_pseudo():
            frase = frase_revision(self._revision_ejemplo())
        self.assertTrue(frase.startswith("[¡"), frase)
        for dato in ("TikTok", "Escena", "Mi Juego", "Mic/Aux"):
            self.assertIn(dato, frase)

    def test_fuentes_y_detalles_propios_de_revisar_salen_marcados(self):
        doble = DoblePrevuelo(imagen=self._imagen())
        with con_pseudo():
            revision = revisar(doble, "TikTok")
        tipos = {fuente.nombre: fuente.tipo for fuente in revision.fuentes}
        self.assertTrue(tipos["Captura de ventana"].startswith("[¡"),
                        tipos["Captura de ventana"])
        detalles = {fuente.nombre: fuente.detalle
                    for fuente in revision.fuentes}
        # El título de la ventana es un dato de OBS y queda sin marcar.
        self.assertEqual(detalles["Captura de ventana"],
                         "Champions of The Rift")
        self.assertTrue(detalles["Chat YTChat"].startswith("[¡"),
                        detalles["Chat YTChat"])

    def test_cada_problema_sale_marcado(self):
        doble = DoblePrevuelo(
            perfil="YouTube", elementos=(),
            silencios={"Audio del escritorio": True, "Mic/Aux": True},
            imagen=imagen_dato(png_plano(2, 2, (0, 0, 0, 0))))
        with con_pseudo():
            revision = revisar(doble, "TikTok")
        self.assertEqual(len(revision.problemas), 5)
        for problema in revision.problemas:
            self.assertTrue(problema.startswith("[¡"), problema)

    def test_aviso_de_grabacion_se_muestra_marcado(self):
        doble = DoblePrevuelo(modo="Advanced", codificador="x264",
                              imagen=self._imagen())
        with con_pseudo():
            frase = frase_revision(revisar(doble, "TikTok", grabar=True))
        self.assertTrue(frase.startswith("[¡"), frase)
        self.assertIn(AVISO_CODIFICADOR, frase)


if __name__ == "__main__":
    unittest.main()
