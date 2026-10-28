"""Tests de obs_captura_ia con un doble que registra lo pedido a OBS."""

import base64
import struct
import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.obs import obs_captura_ia
from ytchat.obs import obs_cliente
from ytchat.obs.obs_captura_ia import CapturaFallida, OpcionCaptura


def armar_bmp(ancho, alto, blancos=()):
    blancos = set(blancos)
    paso = ((ancho * 3 + 3) // 4) * 4
    cuerpo = bytearray()
    for y in range(alto - 1, -1, -1):
        fila = bytearray()
        for x in range(ancho):
            fila += b"\xff\xff\xff" if (x, y) in blancos else b"\x00\x00\x00"
        fila += b"\x00" * (paso - ancho * 3)
        cuerpo += fila
    cabecera = struct.pack("<2sIHHI", b"BM", 54 + len(cuerpo), 0, 0, 54)
    dib = struct.pack("<IiiHHII", 40, ancho, alto, 1, 24, 0, 0)
    dib += struct.pack("<IIII", 0, 0, 0, 0)
    return bytes(cabecera + dib + cuerpo)


def dato_imagen(bmp, formato):
    return ("data:image/%s;base64," % formato
            + base64.b64encode(bmp).decode("ascii"))


def elemento(nombre, indice, habilitado=True, ancho=640, alto=360):
    return {"sourceName": nombre, "sceneItemIndex": indice,
            "sceneItemEnabled": habilitado,
            "sceneItemTransform": {"sourceWidth": ancho,
                                   "sourceHeight": alto}}


ENTRADAS = ({"inputName": "Juego", "inputKind": "window_capture"},
            {"inputName": "Chat", "inputKind": "browser_source"},
            {"inputName": "Micro", "inputKind": "wasapi_input_capture"},
            {"inputName": "Parlantes",
             "inputKind": "wasapi_process_output_capture"},
            {"inputName": "Rara", "inputKind": "efecto_nuevo"})


class Doble:
    """OBS medido el 21/10/2026: escena al aire con fuentes variadas."""

    def __init__(self, escena="Juego", base=(1600, 900), elementos=(),
                 entradas=ENTRADAS, jpeg=b"JPEG",
                 bmp=None, falla_bmp=False, falla_principal=False,
                 ajustes=None, falla_ajustes=False):
        self.escena = escena
        self.base = base
        self.elementos = list(elementos)
        self.entradas = list(entradas)
        self.jpeg_dato = dato_imagen(jpeg, "jpg")
        if bmp is None:
            bmp = armar_bmp(16, 9)
        self.bmp_dato = dato_imagen(bmp, "bmp")
        self.falla_bmp = falla_bmp
        self.falla_principal = falla_principal
        self.ajustes = dict(ajustes or {})
        self.falla_ajustes = falla_ajustes
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, dict(datos or {})))
        if tipo == "GetCurrentProgramScene":
            return {"responseData": {"currentProgramSceneName": self.escena}}
        if tipo == "GetVideoSettings":
            return {"responseData": {"baseWidth": self.base[0],
                                     "baseHeight": self.base[1]}}
        if tipo == "GetSceneItemList":
            return {"responseData": {"sceneItems": list(self.elementos)}}
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputSettings":
            if self.falla_ajustes:
                raise obs_cliente.ObsError("sin ajustes")
            nombre = (datos or {}).get("inputName", "")
            return {"responseData": {
                "inputSettings": dict(self.ajustes.get(nombre, {}))}}
        if tipo == "GetSourceScreenshot":
            if (datos or {}).get("imageFormat") == "jpg":
                if self.falla_principal:
                    raise obs_cliente.ObsError("OBS no pudo completar.")
                return {"responseData": {"imageData": self.jpeg_dato}}
            if self.falla_bmp:
                raise obs_cliente.ObsError("Failed to render screenshot")
            return {"responseData": {"imageData": self.bmp_dato}}
        raise AssertionError(tipo)

    def capturas(self):
        return [datos for (tipo, datos) in self.llamadas
                if tipo == "GetSourceScreenshot"]

    def tipos(self):
        return [tipo for (tipo, _datos) in self.llamadas]


class TestOpciones(unittest.TestCase):
    def test_escena_primero(self):
        doble = Doble()
        primera = obs_captura_ia.opciones(doble)[0]
        self.assertEqual(primera, OpcionCaptura(
            "Juego", "Escena al aire: Juego", 1600, 900))

    def test_orden_y_filtrado(self):
        doble = Doble(elementos=(
            elemento("Juego", 6, ancho=1280, alto=720),
            elemento("Oculta", 5, habilitado=False),
            elemento("Micro", 4),
            elemento("Angosta", 3, ancho=0),
            elemento("Rara", 2, ancho=320, alto=240),
            elemento("Chat", 1, ancho=800, alto=600)))
        opciones = obs_captura_ia.opciones(doble)
        self.assertEqual([o.etiqueta for o in opciones],
                         ["Escena al aire: Juego",
                          "Juego (captura de ventana)", "Rara",
                          "Chat (navegador)"])
        self.assertEqual((opciones[1].ancho, opciones[1].alto),
                         (1280, 720))

    def test_audio_fuera_aunque_visible(self):
        doble = Doble(elementos=(
            elemento("Micro", 4), elemento("Parlantes", 7)))
        self.assertEqual(len(obs_captura_ia.opciones(doble)), 1)

    def test_vista_pide_lista_de_la_escena_al_aire(self):
        doble = Doble()
        obs_captura_ia.opciones(doble)
        listas = [datos for (tipo, datos) in doble.llamadas
                  if tipo == "GetSceneItemList"]
        self.assertEqual(listas, [{"sceneName": "Juego"}])


class TestCapturar(unittest.TestCase):
    def test_apaisada_pide_solo_ancho(self):
        doble = Doble()
        opcion = OpcionCaptura("Juego", "Escena al aire: Juego", 1600, 900)
        captura = obs_captura_ia.capturar(doble, opcion)
        principal = doble.capturas()[0]
        self.assertEqual(principal["imageFormat"], "jpg")
        self.assertEqual(principal["imageWidth"], 1280)
        self.assertNotIn("imageHeight", principal)
        self.assertEqual(principal["imageCompressionQuality"], 75)
        self.assertEqual((captura.ancho, captura.alto), (1280, 720))
        self.assertEqual(captura.jpeg, b"JPEG")
        self.assertTrue(captura.negra)

    def test_alta_pide_solo_alto(self):
        doble = Doble()
        opcion = OpcionCaptura("Celular", "Celular (cámara)", 900, 1600)
        captura = obs_captura_ia.capturar(doble, opcion)
        principal = doble.capturas()[0]
        self.assertEqual(principal["imageHeight"], 1280)
        self.assertNotIn("imageWidth", principal)
        self.assertEqual((captura.ancho, captura.alto), (720, 1280))

    def test_nunca_pide_los_dos_lados(self):
        doble = Doble(bmp=armar_bmp(16, 9, [(x, 0) for x in range(16)]))
        obs_captura_ia.capturar(
            doble, OpcionCaptura("Juego", "Escena", 1600, 900))
        obs_captura_ia.capturar(
            doble, OpcionCaptura("Celular", "Celular", 900, 1600))
        for pedido in doble.capturas():
            self.assertEqual("imageWidth" in pedido,
                             "imageHeight" not in pedido)

    def test_medicion_usa_bmp_chico(self):
        doble = Doble()
        obs_captura_ia.capturar(
            doble, OpcionCaptura("Juego", "Escena", 1600, 900))
        segunda = doble.capturas()[1]
        self.assertEqual(segunda["imageFormat"], "bmp")
        self.assertEqual(segunda["imageWidth"], 160)
        self.assertNotIn("imageHeight", segunda)

    def test_principal_pide_fuente(self):
        doble = Doble()
        opcion = OpcionCaptura(
            "Juego", "Juego (captura de ventana)", 1280, 720)
        obs_captura_ia.capturar(doble, opcion)
        principal = doble.capturas()[0]
        self.assertEqual(principal["imageFormat"], "jpg")
        self.assertEqual(principal["sourceName"], "Juego")

    def test_medicion_pide_fuente(self):
        doble = Doble()
        opcion = OpcionCaptura(
            "Juego", "Juego (captura de ventana)", 1280, 720)
        obs_captura_ia.capturar(doble, opcion)
        segunda = doble.capturas()[1]
        self.assertEqual(segunda["imageFormat"], "bmp")
        self.assertEqual(segunda["sourceName"], "Juego")

    def test_bmp_con_luz_no_es_negra(self):
        blancos = [(x, 0) for x in range(40)]
        doble = Doble(bmp=armar_bmp(50, 40, blancos))
        captura = obs_captura_ia.capturar(
            doble, OpcionCaptura("Juego", "Escena", 1600, 900))
        self.assertFalse(captura.negra)
        self.assertEqual(captura.jpeg, b"JPEG")

    def test_falla_medicion_deja_negra_none(self):
        doble = Doble(falla_bmp=True)
        captura = obs_captura_ia.capturar(
            doble, OpcionCaptura("Juego", "Escena", 1600, 900))
        self.assertIsNone(captura.negra)
        self.assertEqual(captura.jpeg, b"JPEG")

    def test_falla_principal_da_captura_fallida(self):
        doble = Doble(falla_principal=True)
        opcion = OpcionCaptura("Juego", "Escena al aire: Juego", 1600, 900)
        with self.assertRaises(CapturaFallida) as contexto:
            obs_captura_ia.capturar(doble, opcion)
        self.assertEqual(str(contexto.exception),
                         "No se pudo capturar Escena al aire: Juego. "
                         "Comprueba que esté visible en la escena al aire.")
        self.assertIsInstance(contexto.exception.__cause__,
                              obs_cliente.ObsError)

    def test_fuente_chica_no_se_agranda(self):
        doble = Doble()
        captura = obs_captura_ia.capturar(
            doble, OpcionCaptura("Chica", "Chica", 640, 360))
        self.assertEqual(doble.capturas()[0]["imageWidth"], 640)
        self.assertEqual((captura.ancho, captura.alto), (640, 360))

    def test_sin_tamano_pide_ancho(self):
        doble = Doble()
        captura = obs_captura_ia.capturar(
            doble, OpcionCaptura("X", "Equis", 0, 0))
        self.assertEqual(doble.capturas()[0]["imageWidth"], 1280)
        self.assertEqual(captura.ancho, 1280)


class TestSinElegir(unittest.TestCase):
    def test_monitor_sin_pantalla(self):
        self.assertTrue(obs_captura_ia.sin_elegir("monitor_capture", {}))
        self.assertTrue(
            obs_captura_ia.sin_elegir("monitor_capture", {"method": 2}))
        self.assertTrue(obs_captura_ia.sin_elegir(
            "monitor_capture", {"monitor_id": ""}))
        self.assertTrue(obs_captura_ia.sin_elegir(
            "monitor_capture", {"monitor_id": "DUMMY"}))

    def test_monitor_con_pantalla(self):
        self.assertFalse(obs_captura_ia.sin_elegir(
            "monitor_capture", {"monitor_id": "1"}))
        self.assertFalse(obs_captura_ia.sin_elegir(
            "monitor_capture", {"monitor_id": 0, "method": 2}))

    def test_ventana(self):
        self.assertTrue(obs_captura_ia.sin_elegir("window_capture", {}))
        self.assertTrue(
            obs_captura_ia.sin_elegir("window_capture", {"window": ""}))
        self.assertFalse(obs_captura_ia.sin_elegir(
            "window_capture", {"window": "notepad.exe"}))

    def test_juego(self):
        self.assertTrue(obs_captura_ia.sin_elegir(
            "game_capture", {"capture_mode": "window"}))
        self.assertTrue(obs_captura_ia.sin_elegir(
            "game_capture", {"capture_mode": "window", "window": ""}))
        self.assertFalse(obs_captura_ia.sin_elegir(
            "game_capture",
            {"capture_mode": "window", "window": "juego.exe"}))
        self.assertFalse(obs_captura_ia.sin_elegir(
            "game_capture", {"capture_mode": "any_fullscreen"}))
        self.assertFalse(obs_captura_ia.sin_elegir("game_capture", {}))

    def test_camara(self):
        self.assertTrue(obs_captura_ia.sin_elegir("dshow_input", {}))
        self.assertTrue(obs_captura_ia.sin_elegir(
            "dshow_input", {"video_device_id": ""}))
        self.assertFalse(obs_captura_ia.sin_elegir(
            "dshow_input", {"video_device_id": "camara 1"}))

    def test_clase_ajena(self):
        self.assertFalse(obs_captura_ia.sin_elegir("browser_source", {}))
        self.assertFalse(obs_captura_ia.sin_elegir("v4l2_input", {}))


class TestMotivoNegra(unittest.TestCase):
    def test_solo_navegador_da_sin_fuente(self):
        self.assertEqual(
            obs_captura_ia.motivo_negra([("Chat", "browser_source")], {}),
            ("sin_fuente", ""))

    def test_sin_elementos_da_sin_fuente(self):
        self.assertEqual(obs_captura_ia.motivo_negra([], {}),
                         ("sin_fuente", ""))

    def test_captura_elegida_mas_navegador_da_vacio(self):
        pares = [("Pantalla", "monitor_capture"), ("Chat", "browser_source")]
        self.assertEqual(
            obs_captura_ia.motivo_negra(
                pares, {"Pantalla": {"monitor_id": "1"}}),
            ("", ""))

    def test_primera_sin_elegir_la_nombra(self):
        pares = [("Pantalla", "monitor_capture"), ("Chat", "browser_source")]
        self.assertEqual(
            obs_captura_ia.motivo_negra(pares, {"Pantalla": {"method": 2}}),
            ("sin_elegir", "Pantalla"))

    def test_dos_capturas_nombra_la_segunda_sin_elegir(self):
        pares = [("Pantalla", "monitor_capture"),
                 ("Ventana", "window_capture")]
        ajustes = {"Pantalla": {"monitor_id": "0"}, "Ventana": {}}
        self.assertEqual(
            obs_captura_ia.motivo_negra(pares, ajustes),
            ("sin_elegir", "Ventana"))


class TestCapturarMotivo(unittest.TestCase):
    def _opcion_escena(self, escena):
        return OpcionCaptura(escena, f"Escena al aire: {escena}", 1600, 900)

    def test_negra_solo_navegador_da_sin_fuente(self):
        doble = Doble(
            escena="Escena",
            elementos=(elemento("Chat YTChat", 1),),
            entradas=({"inputName": "Chat YTChat",
                       "inputKind": "browser_source"},))
        captura = obs_captura_ia.capturar(
            doble, self._opcion_escena("Escena"))
        self.assertTrue(captura.negra)
        self.assertEqual(
            (captura.motivo, captura.fuente_motivo), ("sin_fuente", ""))
        self.assertEqual(captura.jpeg, b"JPEG")

    def test_negra_monitor_sin_pantalla_da_sin_elegir(self):
        doble = Doble(
            escena="Escena",
            elementos=(elemento("Pantalla", 1),),
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},),
            ajustes={"Pantalla": {"method": 2}})
        captura = obs_captura_ia.capturar(
            doble, self._opcion_escena("Escena"))
        self.assertTrue(captura.negra)
        self.assertEqual(
            (captura.motivo, captura.fuente_motivo),
            ("sin_elegir", "Pantalla"))

    def test_negra_de_fuente_usa_solo_ese_elemento(self):
        doble = Doble(
            escena="Escena",
            elementos=(elemento("Pantalla", 2), elemento("Chat", 1)),
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},
                      {"inputName": "Chat",
                       "inputKind": "browser_source"}),
            ajustes={"Pantalla": {"method": 2}})
        captura = obs_captura_ia.capturar(
            doble, OpcionCaptura("Pantalla", "Pantalla", 640, 360))
        self.assertTrue(captura.negra)
        self.assertEqual(
            (captura.motivo, captura.fuente_motivo),
            ("sin_elegir", "Pantalla"))

    def test_con_luz_no_pide_escena_ni_ajustes(self):
        blancos = [(x, 0) for x in range(40)]
        doble = Doble(
            escena="Escena",
            elementos=(elemento("Pantalla", 1),),
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},),
            bmp=armar_bmp(50, 40, blancos))
        captura = obs_captura_ia.capturar(
            doble, self._opcion_escena("Escena"))
        self.assertFalse(captura.negra)
        self.assertEqual(
            (captura.motivo, captura.fuente_motivo), ("", ""))
        self.assertNotIn("GetSceneItemList", doble.tipos())
        self.assertNotIn("GetInputSettings", doble.tipos())

    def test_ajustes_fallan_deja_motivo_vacio(self):
        doble = Doble(
            escena="Escena",
            elementos=(elemento("Pantalla", 1),),
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},),
            falla_ajustes=True)
        captura = obs_captura_ia.capturar(
            doble, self._opcion_escena("Escena"))
        self.assertTrue(captura.negra)
        self.assertEqual(
            (captura.motivo, captura.fuente_motivo), ("", ""))
        self.assertEqual(captura.jpeg, b"JPEG")


class TestVistaPrevia(unittest.TestCase):
    def test_devuelve_solo_bytes(self):
        doble = Doble()
        vista = obs_captura_ia.vista_previa(
            doble, OpcionCaptura("Juego", "Escena", 1600, 900))
        self.assertEqual(vista, b"JPEG")
        pedido = doble.capturas()[0]
        self.assertEqual(pedido["imageWidth"], 320)
        self.assertEqual(pedido["imageCompressionQuality"], 60)

    def test_alta_pide_alto(self):
        doble = Doble()
        obs_captura_ia.vista_previa(
            doble, OpcionCaptura("Celular", "Celular", 900, 1600))
        pedido = doble.capturas()[0]
        self.assertEqual(pedido["imageHeight"], 320)
        self.assertNotIn("imageWidth", pedido)

    def test_falla_da_captura_fallida(self):
        doble = Doble(falla_principal=True)
        with self.assertRaises(CapturaFallida) as contexto:
            obs_captura_ia.vista_previa(
                doble, OpcionCaptura("Juego", "Escena al aire: Juego",
                                     1600, 900))
        self.assertEqual(str(contexto.exception),
                         "No se pudo capturar Escena al aire: Juego. "
                         "Comprueba que esté visible en la escena al aire.")

    def test_pide_fuente(self):
        doble = Doble()
        opcion = OpcionCaptura(
            "Juego", "Juego (captura de ventana)", 1280, 720)
        obs_captura_ia.vista_previa(doble, opcion)
        pedido = doble.capturas()[0]
        self.assertEqual(pedido["sourceName"], "Juego")


class TestPseudoTextos(unittest.TestCase):
    """Bajo pseudotraducción, cada frase al usuario sale marcada."""

    def test_etiquetas_y_fallos_salen_marcados(self):
        doble = Doble(elementos=(
            elemento("Juego", 6, ancho=1280, alto=720),
            elemento("Rara", 2, ancho=320, alto=240)))
        with con_pseudo():
            etiquetas = [opcion.etiqueta
                         for opcion in obs_captura_ia.opciones(doble)]
            with self.assertRaises(CapturaFallida) as fallo:
                obs_captura_ia.capturar(
                    Doble(falla_principal=True),
                    OpcionCaptura("Juego", "Juego", 1280, 720))
        self.assertTrue(etiquetas[0].startswith("[¡"), etiquetas)
        self.assertIn("Juego", etiquetas[0])
        self.assertTrue(etiquetas[1].startswith("[¡"), etiquetas)
        self.assertIn("Juego", etiquetas[1])
        # Sin tipo es dato del usuario: pasa sin marcar.
        self.assertEqual(etiquetas[2], "Rara")
        self.assertTrue(str(fallo.exception).startswith("[¡"),
                        str(fallo.exception))


if __name__ == "__main__":
    unittest.main()
