"""Pruebas de las operaciones sobre fuentes de OBS."""

import unittest

from guyrapu.obs import fuentes_obs, obs_cliente
from guyrapu.obs.obs_panel import NOMBRE_FUENTE


def elemento(nombre, identificador, indice, visible=True):
    return {
        "sceneItemId": identificador, "sourceName": nombre,
        "sceneItemIndex": indice, "sceneItemEnabled": visible,
        "sceneItemTransform": {
            "positionX": 10, "positionY": 20, "alignment": 5,
            "rotation": 0, "scaleX": 1, "scaleY": 1,
            "boundsType": "OBS_BOUNDS_NONE", "boundsAlignment": 0,
            "boundsWidth": 0, "boundsHeight": 0,
            "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
        },
    }


class ClienteFalso:

    def __init__(self, respuestas=None):
        self.respuestas = respuestas or {}
        self.peticiones = []

    def pedir(self, tipo, datos=None, parada=None):
        self.peticiones.append((tipo, datos))
        return {"responseData": self.respuestas.get(tipo, {})}


class GestorFalso:

    def __init__(self, cliente, elementos):
        self.cliente = cliente
        self.elementos_datos = elementos
        self.transformadas = []

    def _pedir(self, tipo, datos=None, parada=None):
        return self.cliente.pedir(tipo, datos, parada).get("responseData", {})

    def elementos(self, escena, parada=None):
        return list(self.elementos_datos)

    def transformar(self, escena, transformacion, parada=None, *, fuente=""):
        self.transformadas.append((escena, transformacion, fuente))


def _respuestas_duplicado():
    return {
        "GetInputList": {"inputs": [
            {"inputName": "Panel", "inputKind": "browser_source"},
            {"inputName": "Cámara", "inputKind": "dshow_input"},
            {"inputName": NOMBRE_FUENTE, "inputKind": "browser_source"},
        ]},
        "GetInputSettings": {"inputSettings": {"url": "https://ejemplo"}},
        "CreateInput": {"sceneItemId": 99},
    }


class MotivoParaNoDuplicarTest(unittest.TestCase):

    def test_el_chat_no_se_duplica(self):
        self.assertEqual(
            fuentes_obs.motivo_para_no_duplicar(NOMBRE_FUENTE, ""),
            "Solo puede haber un chat en el vídeo.")

    def test_una_camara_no_se_duplica(self):
        self.assertEqual(
            fuentes_obs.motivo_para_no_duplicar("Cámara", "cámara"),
            "Una cámara no se puede abrir dos veces. Para usarla en otra "
            "escena, duplica la escena.")

    def test_una_fuente_normal_si_se_duplica(self):
        self.assertEqual(
            fuentes_obs.motivo_para_no_duplicar("Panel", "navegador"), "")


class EliminarYRenombrarTest(unittest.TestCase):

    def test_eliminar_quita_el_elemento_de_la_escena(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [elemento("Panel", 7, 0)])
        fuentes_obs.eliminar(gestor, "Principal", "Panel")
        self.assertEqual(
            cliente.peticiones,
            [("RemoveSceneItem",
              {"sceneName": "Principal", "sceneItemId": 7})])

    def test_renombrar_cambia_el_nombre_en_todas_las_escenas(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [elemento("Panel", 7, 0)])
        fuentes_obs.renombrar(gestor, "Principal", "Panel", "Panel nuevo")
        self.assertEqual(
            cliente.peticiones,
            [("SetInputName",
              {"inputName": "Panel", "newInputName": "Panel nuevo"})])

    def test_sin_fuente_no_pide_nada(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [])
        with self.assertRaises(obs_cliente.ObsError):
            fuentes_obs.eliminar(gestor, "Principal", "Panel")
        self.assertEqual(cliente.peticiones, [])


class DuplicarTest(unittest.TestCase):

    def test_copia_ajustes_forma_y_queda_justo_delante(self):
        cliente = ClienteFalso(_respuestas_duplicado())
        original = elemento("Panel", 7, 0)
        gestor = GestorFalso(cliente, [original])
        nombre = fuentes_obs.duplicar(
            gestor, "Principal", "Panel", tipo="navegador")
        self.assertEqual(nombre, "Panel - copia")
        tipos = [tipo for tipo, _datos in cliente.peticiones]
        self.assertEqual(
            tipos,
            ["GetInputList", "GetInputSettings", "CreateInput",
             "SetSceneItemTransform", "SetSceneItemIndex"])
        crear = cliente.peticiones[2][1]
        self.assertEqual(crear["inputName"], "Panel - copia")
        self.assertEqual(crear["inputKind"], "browser_source")
        self.assertEqual(crear["inputSettings"], {"url": "https://ejemplo"})
        self.assertTrue(crear["sceneItemEnabled"])
        transformar = cliente.peticiones[3][1]
        self.assertEqual(transformar["sceneItemId"], 99)
        self.assertEqual(
            transformar["sceneItemTransform"],
            original["sceneItemTransform"])
        indice = cliente.peticiones[4][1]
        self.assertEqual(indice["sceneItemId"], 99)
        self.assertEqual(indice["sceneItemIndex"], 1)

    def test_si_ya_hay_una_copia_usa_el_numero_siguiente(self):
        respuestas = _respuestas_duplicado()
        respuestas["GetInputList"]["inputs"].append(
            {"inputName": "Panel - copia", "inputKind": "browser_source"})
        cliente = ClienteFalso(respuestas)
        gestor = GestorFalso(cliente, [elemento("Panel", 7, 0)])
        self.assertEqual(
            fuentes_obs.duplicar(gestor, "Principal", "Panel",
                                 tipo="navegador"),
            "Panel - copia 2")

    def test_el_chat_no_se_duplica_y_no_pide_nada(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [elemento(NOMBRE_FUENTE, 7, 0)])
        with self.assertRaises(fuentes_obs.NoSePuedeDuplicar):
            fuentes_obs.duplicar(gestor, "Principal", NOMBRE_FUENTE)
        self.assertEqual(cliente.peticiones, [])

    def test_una_camara_conocida_por_el_tipo_no_pide_nada(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [elemento("Cámara", 7, 0)])
        with self.assertRaises(fuentes_obs.NoSePuedeDuplicar):
            fuentes_obs.duplicar(
                gestor, "Principal", "Cámara", tipo="cámara")
        self.assertEqual(cliente.peticiones, [])

    def test_una_camara_conocida_por_obs_tampoco_se_duplica(self):
        cliente = ClienteFalso(_respuestas_duplicado())
        gestor = GestorFalso(cliente, [elemento("Cámara", 7, 0)])
        with self.assertRaises(fuentes_obs.NoSePuedeDuplicar):
            fuentes_obs.duplicar(gestor, "Principal", "Cámara")
        self.assertEqual(
            [tipo for tipo, _datos in cliente.peticiones], ["GetInputList"])


class AplicarTransformacionTest(unittest.TestCase):

    def test_lee_el_lienzo_calcula_y_transformar_la_fuente(self):
        cliente = ClienteFalso(
            {"GetVideoSettings": {"baseWidth": 1600, "baseHeight": 900}})
        gestor = GestorFalso(cliente, [elemento("Panel", 7, 0)])
        vistos = []

        def calculo(transformacion, ancho, alto):
            vistos.append((transformacion, ancho, alto))
            return {"positionX": 800, "positionY": 450, "alignment": 0}

        nueva = fuentes_obs.aplicar_transformacion(
            gestor, "Principal", "Panel", calculo)
        self.assertEqual(vistos[0][1:], (1600, 900))
        self.assertEqual(
            nueva, {"positionX": 800, "positionY": 450, "alignment": 0})
        self.assertEqual(
            gestor.transformadas,
            [("Principal", nueva, "Panel")])

    def test_sin_fuente_falla_antes_de_calcular(self):
        cliente = ClienteFalso()
        gestor = GestorFalso(cliente, [])
        with self.assertRaises(obs_cliente.ObsError):
            fuentes_obs.aplicar_transformacion(
                gestor, "Principal", "Panel", lambda *args: {})
        self.assertEqual(cliente.peticiones, [])


if __name__ == "__main__":
    unittest.main()
