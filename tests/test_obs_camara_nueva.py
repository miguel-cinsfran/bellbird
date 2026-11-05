"""Pruebas de cómo se agrega a OBS una cámara de Windows.

Sin ventanas: todo pasa por un cliente falso que guarda los pedidos.
"""

import unittest

from guyrapu.obs import obs_camara_nueva
from guyrapu.obs import obs_disposicion


def item(nombre, valor, habilitado=True):
    return {"itemName": nombre, "itemValue": valor,
            "itemEnabled": habilitado}


class Doble:
    def __init__(self, elementos=(), entradas=(), propiedades=(), ajustes=None,
                 video=None, falla_lista=False, retiene_sonda=False):
        self.elementos = list(elementos)
        self.entradas = list(entradas)
        self.propiedades = list(propiedades)
        self.ajustes = dict(ajustes or {})
        self.video = dict(video or {"baseWidth": 1600, "baseHeight": 900})
        self.falla_lista = falla_lista
        self.retiene_sonda = retiene_sonda
        self.llamadas = []
        self.siguiente_id = 40

    def pedir(self, tipo, datos=None, parada=None):
        datos = dict(datos or {})
        self.llamadas.append((tipo, datos))
        if tipo == "GetSceneItemList":
            return {"responseData": {"sceneItems": list(self.elementos)}}
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputPropertiesListPropertyItems":
            if self.falla_lista:
                raise RuntimeError("OBS no contesta")
            return {"responseData": {"propertyItems": list(self.propiedades)}}
        if tipo == "GetInputSettings":
            ajustes = self.ajustes.get(datos.get("inputName", ""), {})
            return {"responseData": {"inputSettings": dict(ajustes)}}
        if tipo == "GetVideoSettings":
            return {"responseData": dict(self.video)}
        if tipo == "CreateInput":
            self.siguiente_id += 1
            nombre = datos.get("inputName", "")
            self.entradas.append({"inputName": nombre,
                                  "inputKind": datos.get("inputKind", "")})
            self.ajustes[nombre] = dict(datos.get("inputSettings") or {})
            self.elementos.append({
                "sceneItemId": self.siguiente_id,
                "sourceName": nombre,
                "inputKind": datos.get("inputKind", ""),
                "sceneItemEnabled": datos.get("sceneItemEnabled", True),
                "sceneItemIndex": 0})
            return {"responseData": {"sceneItemId": self.siguiente_id}}
        if tipo == "RemoveSceneItem":
            identificador = datos.get("sceneItemId")
            self.elementos = [elemento for elemento in self.elementos
                              if elemento.get("sceneItemId") != identificador]
            return {"responseData": {}}
        if tipo == "RemoveInput":
            nombre = datos.get("inputName", "")
            if (self.retiene_sonda
                    and nombre == obs_camara_nueva.NOMBRE_SONDA):
                return {"responseData": {}}
            if any(elemento.get("sourceName") == nombre
                   for elemento in self.elementos):
                return {"responseData": {}}
            self.entradas = [entrada for entrada in self.entradas
                             if entrada.get("inputName") != nombre]
            self.ajustes.pop(nombre, None)
            return {"responseData": {}}
        return {"responseData": {}}

    def tipos(self):
        return [llamada[0] for llamada in self.llamadas]


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.ahora += segundos


def _disponibles(doble):
    reloj = RelojFalso()
    return obs_camara_nueva.camaras_disponibles(
        doble, "Escena", dormir=reloj.dormir, reloj=reloj)


class CamarasDisponiblesTest(unittest.TestCase):
    def test_crea_la_sonda_oculta_y_la_borra_al_terminar(self):
        doble = Doble(propiedades=(item("EasyCamera", "abc", True),))
        self.assertEqual(_disponibles(doble), (("EasyCamera", "abc"),))
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"],
                         obs_camara_nueva.NOMBRE_SONDA)
        self.assertEqual(crear[1]["inputKind"], "dshow_input")
        self.assertFalse(crear[1]["sceneItemEnabled"])
        lista = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "GetInputPropertiesListPropertyItems")
        self.assertEqual(lista[1]["propertyName"], "video_device_id")
        self.assertEqual(doble.entradas, [])
        self.assertEqual(doble.elementos, [])

    def test_borra_la_sonda_tambien_si_la_lectura_falla(self):
        doble = Doble(falla_lista=True)
        with self.assertRaises(RuntimeError):
            _disponibles(doble)
        tipos = doble.tipos()
        self.assertIn("CreateInput", tipos)
        self.assertIn("RemoveSceneItem", tipos)
        self.assertIn("RemoveInput", tipos)
        self.assertEqual(doble.entradas, [])
        self.assertEqual(doble.elementos, [])

    def test_reutiliza_la_sonda_que_ya_existe(self):
        doble = Doble(
            entradas=({"inputName": obs_camara_nueva.NOMBRE_SONDA,
                       "inputKind": "dshow_input"},),
            propiedades=(item("EasyCamera", "abc", True),),
            retiene_sonda=True)
        self.assertEqual(_disponibles(doble), (("EasyCamera", "abc"),))
        self.assertNotIn("CreateInput", doble.tipos())
        lista = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "GetInputPropertiesListPropertyItems")
        self.assertEqual(lista[1]["inputName"],
                         obs_camara_nueva.NOMBRE_SONDA)

    def test_solo_devuelve_las_camaras_habilitadas(self):
        doble = Doble(propiedades=(
            item("Seleccionar dispositivo", "", False),
            item("EasyCamera", "abc", True),
            item("Otra", "def", True)))
        self.assertEqual(_disponibles(doble),
                         (("EasyCamera", "abc"), ("Otra", "def")))


class AgregarTest(unittest.TestCase):
    def test_crea_la_camara_con_su_nombre_libre_y_la_ubica(self):
        doble = Doble(
            elementos=({"sceneItemId": 1, "sourceName": "Fondo",
                        "sceneItemIndex": 0},
                       {"sceneItemId": 2, "sourceName": "Texto",
                        "sceneItemIndex": 1},
                       {"sceneItemId": 3, "sourceName": "Chat",
                        "sceneItemIndex": 2}),
            entradas=({"inputName": "Cámara", "inputKind": "text_gdiplus"},
                      {"inputName": "Cámara 2", "inputKind": "browser_source"}),
            video={"baseWidth": 1080, "baseHeight": 1920})
        self.assertEqual(obs_camara_nueva.agregar(doble, "Escena", "abc123"),
                         ("Cámara 3", True))
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"], "Cámara 3")
        self.assertEqual(crear[1]["inputKind"], "dshow_input")
        self.assertEqual(crear[1]["inputSettings"],
                         {"video_device_id": "abc123"})
        self.assertTrue(crear[1]["sceneItemEnabled"])
        indice = next(llamada for llamada in doble.llamadas
                      if llamada[0] == "SetSceneItemIndex")
        self.assertEqual(indice[1]["sceneItemIndex"], 2)
        x, y, _mascara = obs_disposicion.coordenadas(
            "inferior-derecha", 1080, 1920)
        transformacion = next(llamada for llamada in doble.llamadas
                              if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(transformacion[1]["sceneItemTransform"], {
            "positionX": x, "positionY": y,
            "alignment": obs_disposicion.ANCLAJES["inferior-derecha"],
            "boundsType": "OBS_BOUNDS_SCALE_INNER",
            "boundsAlignment": obs_disposicion.ANCLAJES["inferior-derecha"],
            "boundsWidth": 540.0, "boundsHeight": 960.0})

    def test_con_la_camara_ya_en_obs_no_crea_otra(self):
        doble = Doble(
            entradas=({"inputName": "Mi cámara",
                       "inputKind": "dshow_input"},),
            ajustes={"Mi cámara": {"video_device_id": "abc123"}})
        self.assertEqual(obs_camara_nueva.agregar(doble, "Escena", "abc123"),
                         ("Mi cámara", False))
        tipos = doble.tipos()
        self.assertNotIn("CreateInput", tipos)
        self.assertNotIn("SetSceneItemTransform", tipos)


if __name__ == "__main__":
    unittest.main()
