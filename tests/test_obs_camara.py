"""Tests de obs_camara con un doble como el de test_obs_captura_ia."""

import base64
import unittest

from bellbird.obs import obs_camara
from bellbird.obs import obs_cliente
from bellbird.obs.obs_camara import CamaraNoEncontrada
from bellbird.obs.obs_captura_ia import CapturaFallida


def dato_imagen(crudo, formato):
    return ("data:image/%s;base64," % formato
            + base64.b64encode(crudo).decode("ascii"))


def elemento(nombre, indice, habilitado=None, transformacion=None,
             es_grupo=False):
    item = {"sourceName": nombre, "sceneItemIndex": indice,
            "isGroup": es_grupo}
    if habilitado is not None:
        item["sceneItemEnabled"] = habilitado
    if transformacion is not None:
        item["sceneItemTransform"] = dict(transformacion)
    return item


def entrada(nombre, clase="dshow_input"):
    return {"inputName": nombre, "inputKind": clase}


class Doble:
    """OBS con escena al aire, escenas anidadas, grupos y captura."""

    def __init__(self, escena="Principal", por_escena=None, grupos=None,
                 entradas=(), cuadro=b"CUADRO", falla_cuadro=False):
        self.escena = escena
        self.por_escena = dict(por_escena or {})
        self.grupos = dict(grupos or {})
        self.entradas = list(entradas)
        self.cuadro_dato = dato_imagen(cuadro, "bmp")
        self.cuadro = cuadro
        self.falla_cuadro = falla_cuadro
        self.llamadas = []

    def pedir(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, dict(datos or {})))
        if tipo == "GetCurrentProgramScene":
            return {"responseData": {"currentProgramSceneName": self.escena}}
        if tipo == "GetSceneItemList":
            nombre = (datos or {}).get("sceneName", "")
            return {"responseData": {
                "sceneItems": list(self.por_escena.get(nombre, ())) } }
        if tipo == "GetGroupSceneItemList":
            nombre = (datos or {}).get("sceneName", "")
            return {"responseData": {
                "sceneItems": list(self.grupos.get(nombre, ())) } }
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetSourceScreenshot":
            if self.falla_cuadro:
                raise obs_cliente.ObsError("Failed to render screenshot")
            return {"responseData": {"imageData": self.cuadro_dato}}
        raise AssertionError(tipo)

    def tipos(self):
        return [tipo for (tipo, _datos) in self.llamadas]


class TestBuscarDirecta(unittest.TestCase):
    def test_directa_en_la_escena(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Cam")
        self.assertFalse(camara.espejo)

    def test_la_de_adelante_cuando_hay_dos(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Atras", 1),
                                      elemento("Adelante", 2)]},
            entradas=[entrada("Atras"), entrada("Adelante")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Adelante")

    def test_apagada_no_cuenta(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Apagada", 2, habilitado=False),
                                      elemento("Encendida", 1)]},
            entradas=[entrada("Apagada"), entrada("Encendida")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Encendida")

    def test_sin_habilitado_cuenta_como_visible(self):
        item = elemento("Cam", 1)
        self.assertNotIn("sceneItemEnabled", item)
        doble = Doble(
            por_escena={"Principal": [item]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Cam")

    def test_entrada_sale_una_sola_vez(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        obs_camara.buscar_camara(doble)
        self.assertEqual(doble.tipos().count("GetInputList"), 1)


class TestBuscarAnidada(unittest.TestCase):
    def test_dentro_de_escena_anidada(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Anidada", 1)],
                        "Anidada": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Cam")

    def test_dentro_de_grupo(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Grupo", 1, es_grupo=True)]},
            grupos={"Grupo": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Cam")

    def test_hasta_tres_niveles(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Anidada", 1)],
                        "Anidada": [elemento("Grupo", 1, es_grupo=True)]},
            grupos={"Grupo": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertEqual(camara.nombre, "Cam")


class TestBuscarConNombre(unittest.TestCase):
    def test_con_nombre_una_imagen_sirve(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Foto", 1)]},
            entradas=[entrada("Foto", "image_source")])
        camara = obs_camara.buscar_camara(doble, "Foto")
        self.assertEqual(camara.nombre, "Foto")

    def test_con_nombre_fuera_de_la_escena_da_su_frase(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Otra", 1)]},
            entradas=[entrada("Foto", "image_source"),
                      entrada("Otra", "image_source")])
        with self.assertRaises(CamaraNoEncontrada) as contexto:
            obs_camara.buscar_camara(doble, "Foto")
        self.assertEqual(str(contexto.exception),
                         "La fuente Foto no está en la escena al aire.")


class TestFrasesDeError(unittest.TestCase):
    def test_sin_camara_en_obs(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Foto", 1)]},
            entradas=[entrada("Foto", "image_source")])
        with self.assertRaises(CamaraNoEncontrada) as contexto:
            obs_camara.buscar_camara(doble)
        self.assertEqual(str(contexto.exception),
                         "No hay ninguna cámara en OBS.")

    def test_camara_fuera_de_la_escena(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Foto", 1)]},
            entradas=[entrada("Cam"), entrada("Foto", "image_source")])
        with self.assertRaises(CamaraNoEncontrada) as contexto:
            obs_camara.buscar_camara(doble)
        self.assertEqual(str(contexto.exception),
                         "La cámara de OBS no está en la escena al aire.")

    def test_solo_apagada_es_fuera_de_la_escena(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1, habilitado=False)]},
            entradas=[entrada("Cam")])
        with self.assertRaises(CamaraNoEncontrada) as contexto:
            obs_camara.buscar_camara(doble)
        self.assertEqual(str(contexto.exception),
                         "La cámara de OBS no está en la escena al aire.")


class TestEspejo(unittest.TestCase):
    def test_escala_negativa_en_el_elemento(self):
        doble = Doble(
            por_escena={"Principal": [
                elemento("Cam", 1, transformacion={"scaleX": -1.0})]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertTrue(camara.espejo)

    def test_negativo_en_elemento_y_contenedor_da_falso(self):
        doble = Doble(
            por_escena={
                "Principal": [elemento("Anidada", 1,
                                        transformacion={"scaleX": -1.0})],
                "Anidada": [elemento("Cam", 1,
                                      transformacion={"scaleX": -1.0})]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertFalse(camara.espejo)

    def test_sin_transformacion_da_falso(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")])
        camara = obs_camara.buscar_camara(doble)
        self.assertFalse(camara.espejo)


class TestFuentesVideo(unittest.TestCase):
    def test_solo_dshow_en_orden_y_sin_vacias(self):
        doble = Doble(entradas=[
            entrada("Cam"), entrada("Sonido", "wasapi_input_capture"),
            {"inputName": "", "inputKind": "dshow_input"},
            entrada("Otra")])
        self.assertEqual(obs_camara.fuentes_video(doble), ("Cam", "Otra"))

    def test_sin_camaras_da_vacio(self):
        doble = Doble(entradas=[entrada("Sonido", "wasapi_input_capture")])
        self.assertEqual(obs_camara.fuentes_video(doble), ())


class TestCapturarCuadro(unittest.TestCase):
    def test_pide_bmp_con_el_ancho_a_la_fuente(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")], cuadro=b"CUADRO")
        camara = obs_camara.buscar_camara(doble)
        cuadro = obs_camara.capturar_cuadro(doble, camara, lado=200)
        self.assertEqual(cuadro, b"CUADRO")
        pedidos = [datos for (tipo, datos) in doble.llamadas
                   if tipo == "GetSourceScreenshot"]
        self.assertEqual(len(pedidos), 1)
        self.assertEqual(pedidos[0]["sourceName"], "Cam")
        self.assertEqual(pedidos[0]["imageFormat"], "bmp")
        self.assertEqual(pedidos[0]["imageWidth"], 200)

    def test_fallo_da_captura_fallida(self):
        doble = Doble(
            por_escena={"Principal": [elemento("Cam", 1)]},
            entradas=[entrada("Cam")], falla_cuadro=True)
        camara = obs_camara.buscar_camara(doble)
        with self.assertRaises(CapturaFallida) as contexto:
            obs_camara.capturar_cuadro(doble, camara)
        self.assertEqual(str(contexto.exception),
                         "No se pudo capturar Cam. Comprueba que esté "
                         "visible en la escena al aire.")


if __name__ == "__main__":
    unittest.main()
