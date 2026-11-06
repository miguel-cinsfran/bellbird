"""Pruebas de las peticiones a OBS para crear y cambiar fuentes.

Sin ventanas: un `pedir` falso guarda cada llamada.
"""

import unittest

from guyrapu.obs import fuente_nueva


def item(nombre, valor, habilitado=True):
    return {"itemName": nombre, "itemValue": valor,
            "itemEnabled": habilitado}


class Doble:
    def __init__(self, elementos=None, entradas=(), propiedades=(),
                 tipos=(), video=None, ajustes=None, falla_lista=False):
        self.elementos = {escena: list(valores)
                          for escena, valores in (elementos or {}).items()}
        self.entradas = list(entradas)
        self.propiedades = list(propiedades)
        self.tipos = list(tipos)
        self.video = dict(video or {"baseWidth": 1600, "baseHeight": 900})
        self.ajustes = dict(ajustes or {})
        self.falla_lista = falla_lista
        self.llamadas = []
        self.siguiente_id = 40

    def pedir(self, tipo, datos=None, parada=None):
        datos = dict(datos or {})
        self.llamadas.append((tipo, datos))
        if tipo == "GetInputList":
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetSceneList":
            return {"responseData": {
                "scenes": [{"sceneName": escena}
                           for escena in self.elementos]}}
        if tipo == "GetSceneItemList":
            return {"responseData": {
                "sceneItems": list(self.elementos.get(
                    datos.get("sceneName", ""), ()))}}
        if tipo == "GetInputKindList":
            return {"responseData": {"inputKinds": list(self.tipos)}}
        if tipo == "GetVideoSettings":
            return {"responseData": dict(self.video)}
        if tipo == "GetInputSettings":
            nombre = datos.get("inputName", "")
            ajustes = self.ajustes.get(nombre, {})
            if isinstance(ajustes, dict) and "inputSettings" in ajustes:
                return {"responseData": dict(ajustes)}
            return {"responseData": {
                "inputKind": self._tipo_de(nombre),
                "inputSettings": dict(ajustes)}}
        if tipo == "SetInputSettings":
            nombre = datos.get("inputName", "")
            actual = self.ajustes.get(nombre, {})
            if isinstance(actual, dict) and "inputSettings" in actual:
                actual = actual["inputSettings"]
            nuevo = dict(actual or {})
            if datos.get("overlay", True):
                nuevo.update(datos.get("inputSettings") or {})
            else:
                nuevo = dict(datos.get("inputSettings") or {})
            self.ajustes[nombre] = {
                "inputKind": self._tipo_de(nombre),
                "inputSettings": nuevo}
            return {"responseData": {}}
        if tipo == "GetInputPropertiesListPropertyItems":
            if self.falla_lista:
                raise RuntimeError("OBS no contesta")
            return {"responseData": {"propertyItems": list(self.propiedades)}}
        if tipo == "CreateInput":
            return {"responseData": self._crear(datos)}
        if tipo == "CreateSceneItem":
            self.siguiente_id += 1
            escena = datos.get("sceneName", "")
            self.elementos.setdefault(escena, []).append({
                "sceneItemId": self.siguiente_id,
                "sourceName": datos.get("sourceName", ""),
                "sceneItemIndex": 0})
            return {"responseData": {"sceneItemId": self.siguiente_id}}
        if tipo == "SetSceneItemIndex" or tipo == "SetSceneItemTransform":
            return {"responseData": {}}
        if tipo == "RemoveSceneItem":
            escena = datos.get("sceneName", "")
            self.elementos[escena] = [
                elemento for elemento in self.elementos.get(escena, ())
                if elemento.get("sceneItemId") != datos.get("sceneItemId")]
            return {"responseData": {}}
        if tipo == "RemoveInput":
            nombre = datos.get("inputName", "")
            if any(elemento.get("sourceName") == nombre
                   for elementos in self.elementos.values()
                   for elemento in elementos):
                return {"responseData": {}}
            self.entradas = [entrada for entrada in self.entradas
                             if entrada.get("inputName") != nombre]
            self.ajustes.pop(nombre, None)
            return {"responseData": {}}
        return {"responseData": {}}

    def _tipo_de(self, nombre):
        for entrada in self.entradas:
            if entrada.get("inputName") == nombre:
                return entrada.get("inputKind", "")
        return ""

    def _crear(self, datos):
        self.siguiente_id += 1
        nombre = datos.get("inputName", "")
        clase = datos.get("inputKind", "")
        self.entradas.append({"inputName": nombre, "inputKind": clase})
        self.ajustes[nombre] = {
            "inputKind": clase,
            "inputSettings": dict(datos.get("inputSettings") or {})}
        escena = datos.get("sceneName", "")
        if escena:
            self.elementos.setdefault(escena, []).append({
                "sceneItemId": self.siguiente_id,
                "sourceName": nombre,
                "sceneItemIndex": 0,
                "sceneItemEnabled": datos.get("sceneItemEnabled", True)})
        return {"sceneItemId": self.siguiente_id}

    def tipos_de_llamada(self):
        return [llamada[0] for llamada in self.llamadas]

    def primera(self, tipo):
        return next(llamada for llamada in self.llamadas
                    if llamada[0] == tipo)


class CrearTest(unittest.TestCase):
    def test_crea_con_los_ajustes_elegidos_una_sola_vez_y_despues_ubica(self):
        doble = Doble(video={"baseWidth": 1280, "baseHeight": 720})
        self.assertEqual(
            fuente_nueva.crear(
                doble.pedir, "Escena", "imagen", "Imagen",
                {"archivo": "C:/foto.png"}),
            "Imagen")
        creares = [llamada for llamada in doble.llamadas
                   if llamada[0] == "CreateInput"]
        self.assertEqual(len(creares), 1)
        self.assertEqual(creares[0][1], {
            "sceneName": "Escena", "inputName": "Imagen",
            "inputKind": "image_source",
            "inputSettings": {"file": "C:/foto.png"},
            "sceneItemEnabled": True})
        self.assertNotIn("SetInputSettings", doble.tipos_de_llamada())
        tipos = doble.tipos_de_llamada()
        self.assertLess(tipos.index("CreateInput"),
                        tipos.index("SetSceneItemTransform"))
        ajuste = doble.primera("SetSceneItemTransform")
        self.assertEqual(ajuste[1]["sceneItemTransform"], {
            "positionX": 640.0, "positionY": 360.0, "alignment": 0,
            "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsAlignment": 0,
            "boundsWidth": 1280.0, "boundsHeight": 720.0})
        fondo = doble.primera("SetSceneItemIndex")
        self.assertEqual(fondo[1]["sceneItemIndex"], 0)

    def test_el_texto_usa_el_tipo_versionado_y_queda_abajo_al_centro(self):
        doble = Doble(tipos=("monitor_capture", "text_gdiplus_v3"),
                      video={"baseWidth": 1600, "baseHeight": 900})
        fuente_nueva.crear(
            doble.pedir, "Escena", "texto", "Texto",
            {"texto": "Hola", "tamano": 72})
        crear = doble.primera("CreateInput")
        self.assertEqual(crear[1]["inputKind"], "text_gdiplus_v3")
        self.assertEqual(crear[1]["inputSettings"], {
            "text": "Hola", "font": {"face": "Arial", "size": 72}})
        ajuste = doble.primera("SetSceneItemTransform")
        self.assertEqual(ajuste[1]["sceneItemTransform"], {
            "positionX": 800.0, "positionY": 855.0, "alignment": 8,
            "boundsType": "OBS_BOUNDS_NONE"})


class OpcionesListaTest(unittest.TestCase):
    def _opciones(self, doble):
        return fuente_nueva.opciones_lista(
            doble.pedir, "Escena", "pantalla", "monitor_id",
            dormir=lambda _segundos: None, reloj=lambda: 0.0)

    def test_crea_la_sonda_y_la_borra_tambien_si_la_lectura_falla(self):
        doble = Doble(falla_lista=True)
        with self.assertRaises(RuntimeError):
            self._opciones(doble)
        tipos = doble.tipos_de_llamada()
        self.assertIn("CreateInput", tipos)
        self.assertIn("RemoveSceneItem", tipos)
        self.assertIn("RemoveInput", tipos)
        self.assertEqual(doble.entradas, [])
        self.assertEqual(doble.elementos.get("Escena", []), [])

    def test_devuelve_solo_los_items_que_se_pueden_ofrecer(self):
        doble = Doble(propiedades=(
            item("[Seleccionar pantalla para capturar]", "DUMMY", False),
            item("HP V202: 1600x900 @ 0,0 (Monitor principal)",
                 "\\\\?\\DISPLAY#...", True),
            item("Vacía", "", True)))
        self.assertEqual(
            self._opciones(doble),
            (("HP V202: 1600x900 @ 0,0 (Monitor principal)",
              "\\\\?\\DISPLAY#..."),))


class OtraEscenaTest(unittest.TestCase):
    def test_agrega_con_create_scene_item_y_copia_la_forma_limpia(self):
        transformacion = {
            "positionX": 32, "positionY": 18, "alignment": 5,
            "scaleX": 1, "scaleY": 1, "rotation": 0,
            "boundsType": "OBS_BOUNDS_NONE", "boundsAlignment": 0,
            "boundsWidth": 0, "boundsHeight": 0,
            "sourceWidth": 1920, "sourceHeight": 1080}
        doble = Doble(elementos={
            "Principal": [],
            "Otra": [{"sceneItemId": 5, "sourceName": "Juego",
                      "sceneItemTransform": transformacion}]})
        self.assertEqual(
            fuente_nueva.agregar_de_otra(doble.pedir, "Principal", "Juego"),
            "Juego")
        crear = doble.primera("CreateSceneItem")
        self.assertEqual(crear[1], {"sceneName": "Principal",
                                    "sourceName": "Juego"})
        copiada = doble.primera("SetSceneItemTransform")[1][
            "sceneItemTransform"]
        self.assertNotIn("sourceWidth", copiada)
        self.assertNotIn("boundsWidth", copiada)
        self.assertEqual(copiada, {
            "positionX": 32, "positionY": 18, "alignment": 5,
            "scaleX": 1, "scaleY": 1, "rotation": 0,
            "boundsType": "OBS_BOUNDS_NONE"})

    def test_las_fuentes_de_otras_no_repiten_ni_incluyen_la_actual(self):
        doble = Doble(elementos={
            "Principal": [{"sourceName": "A"}, {"sourceName": "B"}],
            "Juego": [{"sourceName": "B"}, {"sourceName": "C"}],
            "Otra": [{"sourceName": "D"}]})
        self.assertEqual(
            fuente_nueva.fuentes_de_otras(doble.pedir, "Principal"),
            ("C", "D"))


class PropiedadesTest(unittest.TestCase):
    def test_lee_el_tipo_y_los_valores_actuales(self):
        doble = Doble(
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},),
            ajustes={"Pantalla": {"monitor_id": "DUMMY"}})
        self.assertEqual(
            fuente_nueva.propiedades(doble.pedir, "Pantalla"),
            ("pantalla", {"pantalla": "DUMMY"}))

    def test_una_fuente_de_color_no_tiene_propiedades(self):
        doble = Doble(
            entradas=({"inputName": "Color",
                       "inputKind": "color_source_v3"},),
            ajustes={"Color": {}})
        self.assertEqual(
            fuente_nueva.propiedades(doble.pedir, "Color"), ("", {}))

    def test_aplica_solo_los_ajustes_del_tipo_sin_transformacion(self):
        doble = Doble(
            entradas=({"inputName": "Pantalla",
                       "inputKind": "monitor_capture"},),
            ajustes={"Pantalla": {"monitor_id": "DUMMY"}})
        fuente_nueva.aplicar_propiedades(
            doble.pedir, "Pantalla", "pantalla", {"pantalla": "HP"})
        escrito = doble.primera("SetInputSettings")
        self.assertEqual(escrito[1], {
            "inputName": "Pantalla",
            "inputSettings": {"monitor_id": "HP"},
            "overlay": True})
        tipos = doble.tipos_de_llamada()
        self.assertNotIn("SetSceneItemTransform", tipos)
        self.assertNotIn("SetSceneItemIndex", tipos)

    def test_el_texto_conserva_la_cara_actual(self):
        doble = Doble(
            entradas=({"inputName": "Texto",
                       "inputKind": "text_gdiplus_v3"},),
            ajustes={"Texto": {
                "inputKind": "text_gdiplus_v3",
                "inputSettings": {
                    "text": "viejo",
                    "font": {"face": "Verdana", "size": 256,
                             "flags": 1}}}})
        fuente_nueva.aplicar_propiedades(
            doble.pedir, "Texto", "texto",
            {"texto": "nuevo", "tamano": 72, "cara": "Verdana"})
        escrito = doble.primera("SetInputSettings")
        self.assertEqual(escrito[1]["inputSettings"], {
            "text": "nuevo",
            "font": {"face": "Verdana", "size": 72, "flags": 1}})


class NombresOcupadosTest(unittest.TestCase):
    def test_mira_entradas_y_elementos_de_las_escenas(self):
        doble = Doble(
            entradas=({"inputName": "A", "inputKind": "image_source"},),
            elementos={"Principal": [{"sourceName": "B"}]})
        self.assertEqual(fuente_nueva.nombres_ocupados(doble.pedir),
                         {"A", "B"})


if __name__ == "__main__":
    unittest.main()
