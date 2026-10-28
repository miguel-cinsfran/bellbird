import unittest

from tests.pseudo_prueba import con_pseudo
from ytchat.obs import obs_captura
from ytchat.obs import obs_cliente


def elemento(identificador, nombre, clase, habilitado=True, indice=0):
    return {"sceneItemId": identificador, "sourceName": nombre,
            "inputKind": clase, "sceneItemEnabled": habilitado,
            "sceneItemIndex": indice}


def item(nombre, valor, habilitado=True):
    return {"itemName": nombre, "itemValue": valor,
            "itemEnabled": habilitado}


class Doble:
    def __init__(self, elementos=(), entradas=(), propiedades=(),
                 ajustes=None, video=None, falla_lista=False,
                 tarda_en_borrar=0, falla_borrado=False,
                 retiene_sonda=False):
        self.elementos = list(elementos)
        self.entradas = list(entradas)
        self.propiedades = list(propiedades)
        self.ajustes = dict(ajustes or {})
        self.video = dict(video or {"baseWidth": 1600, "baseHeight": 900})
        self.falla_lista = falla_lista
        self.tarda_en_borrar = tarda_en_borrar
        self.falla_borrado = falla_borrado
        self.retiene_sonda = retiene_sonda
        self._consultas_pendientes = 0
        self._borrado_diferido = False
        self.llamadas = []
        self.siguiente_id = 40

    def pedir(self, tipo, datos=None, parada=None):
        self.llamadas.append((tipo, dict(datos or {})))
        if tipo == "GetSceneItemList":
            self._aplicar_borrado()
            return {"responseData": {"sceneItems": list(self.elementos)}}
        if tipo == "GetInputList":
            if self._borrado_diferido and self._consultas_pendientes > 0:
                self._consultas_pendientes -= 1
            else:
                self._aplicar_borrado()
            return {"responseData": {"inputs": list(self.entradas)}}
        if tipo == "GetInputPropertiesListPropertyItems":
            if self.falla_lista:
                raise RuntimeError("OBS no contesta")
            return {"responseData": {"propertyItems": list(self.propiedades)}}
        if tipo == "GetInputSettings":
            return {"responseData": {"inputSettings": dict(self.ajustes)}}
        if tipo == "SetInputSettings":
            self.ajustes = dict((datos or {}).get("inputSettings", {}))
            return {"responseData": {}}
        if tipo == "SetSceneItemEnabled":
            for actual in self.elementos:
                if actual["sceneItemId"] == (datos or {}).get("sceneItemId"):
                    actual["sceneItemEnabled"] = (datos or {})["sceneItemEnabled"]
            return {"responseData": {}}
        if tipo == "CreateInput":
            self.siguiente_id += 1
            nombre = (datos or {}).get("inputName", "")
            self.entradas.append({"inputName": nombre,
                                  "inputKind": (datos or {}).get("inputKind", "")})
            if (datos or {}).get("sceneName"):
                self.elementos.append(
                    {"sceneItemId": self.siguiente_id,
                     "sourceName": nombre,
                     "inputKind": (datos or {}).get("inputKind", ""),
                     "sceneItemEnabled": (datos or {}).get(
                         "sceneItemEnabled", True),
                     "sceneItemIndex": 0})
            return {"responseData": {"sceneItemId": self.siguiente_id}}
        if tipo == "RemoveInput":
            nombre = (datos or {}).get("inputName", "")
            if self.falla_borrado:
                raise obs_cliente.ObsError("no encontrado")
            if (self.retiene_sonda
                    and nombre == obs_captura.NOMBRE_SONDA):
                # Como OBS 32.2.2 con la sonda suelta (medido el
                # 14/10/2026): éxito sin borrarla de la lista.
                return {"responseData": {}}
            if any(actual.get("sourceName") == nombre
                   for actual in self.elementos):
                # Como OBS 32.2.2: éxito sin borrar la entrada en escena.
                return {"responseData": {}}
            self.entradas = [entrada for entrada in self.entradas
                             if entrada.get("inputName") != nombre]
            return {"responseData": {}}
        if tipo == "RemoveSceneItem":
            identificador = (datos or {}).get("sceneItemId")
            quitados = [actual for actual in self.elementos
                        if actual.get("sceneItemId") == identificador]
            if (quitados and quitados[0].get("sourceName")
                    == obs_captura.NOMBRE_SONDA and self.tarda_en_borrar):
                self._consultas_pendientes += self.tarda_en_borrar
                self._borrado_diferido = True
                return {"responseData": {}}
            self.elementos = [actual for actual in self.elementos
                              if actual.get("sceneItemId") != identificador]
            for quitado in quitados:
                if not any(actual.get("sourceName")
                           == quitado.get("sourceName")
                           for actual in self.elementos):
                    self.entradas = [
                        entrada for entrada in self.entradas
                        if entrada.get("inputName")
                        != quitado.get("sourceName")]
            return {"responseData": {}}
        if tipo == "GetVideoSettings":
            return {"responseData": dict(self.video)}
        if tipo in ("SetSceneItemIndex", "SetSceneItemTransform"):
            return {"responseData": {}}
        return {"responseData": {}}

    def _aplicar_borrado(self):
        if self._borrado_diferido and self._consultas_pendientes <= 0:
            self._borrado_diferido = False
            self.entradas = [
                entrada for entrada in self.entradas
                if entrada.get("inputName") != obs_captura.NOMBRE_SONDA]
            self.elementos = [
                actual for actual in self.elementos
                if actual.get("sourceName") != obs_captura.NOMBRE_SONDA]

    def tipos(self):
        return [llamada[0] for llamada in self.llamadas]


class RelojFalso:
    def __init__(self):
        self.ahora = 0.0
        self.pausas = []

    def __call__(self):
        return self.ahora

    def dormir(self, segundos):
        self.pausas.append(segundos)
        self.ahora += segundos


class VentanaLegibleTest(unittest.TestCase):
    def test_con_corchetes_da_titulo_de_programa(self):
        self.assertEqual(obs_captura.ventana_legible("[juego.exe]: Champions"),
                         "Champions, de juego.exe")

    def test_sin_corchetes_devuelve_el_texto(self):
        self.assertEqual(obs_captura.ventana_legible("Pantalla completa"),
                         "Pantalla completa")


class SinTituloTest(unittest.TestCase):
    def test_nulo_de_python_es_sin_titulo(self):
        self.assertTrue(
            obs_captura.es_ventana_sin_titulo("[python.exe]: (null)"))

    def test_titulo_vacio_es_sin_titulo(self):
        self.assertTrue(obs_captura.es_ventana_sin_titulo("[x.exe]: "))

    def test_nulo_con_espacios_y_mayusculas_es_sin_titulo(self):
        self.assertTrue(
            obs_captura.es_ventana_sin_titulo("[x.exe]:   (NULL)  "))

    def test_con_titulo_no_es_sin_titulo(self):
        self.assertFalse(
            obs_captura.es_ventana_sin_titulo("[chrome.exe]: YouTube"))

    def test_sin_corchetes_con_texto_no_es_sin_titulo(self):
        self.assertFalse(
            obs_captura.es_ventana_sin_titulo("Bloc de notas"))

    def test_vacia_es_sin_titulo(self):
        self.assertTrue(obs_captura.es_ventana_sin_titulo(""))


class OpcionesTest(unittest.TestCase):
    def test_descarta_las_sin_titulo(self):
        items = (item("[python.exe]: (null)",
                      "(null):Ventana:python.exe"),
                 item("[chrome.exe]: YouTube",
                      "YouTube:Ventana:chrome.exe"))
        self.assertEqual(
            obs_captura._opciones(items),
            (("YouTube, de chrome.exe", "YouTube:Ventana:chrome.exe"),))

    def test_conserva_la_actual_aunque_sea_sin_titulo(self):
        items = (item("[python.exe]: (null)",
                      "(null):Ventana:python.exe"),
                 item("[chrome.exe]: YouTube",
                      "YouTube:Ventana:chrome.exe"))
        opciones = obs_captura._opciones(
            items, conservar="(null):Ventana:python.exe")
        self.assertEqual(
            opciones,
            (("(null), de python.exe", "(null):Ventana:python.exe"),
             ("YouTube, de chrome.exe", "YouTube:Ventana:chrome.exe")))


class VentanasSinTituloTest(unittest.TestCase):
    def test_con_captura_sin_titulo_la_conserva_en_opciones(self):
        propiedades = (
            item("[python.exe]: (null)", "(null):Ventana:python.exe"),
            item("[chrome.exe]: YouTube", "YouTube:Ventana:chrome.exe"))
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},),
            propiedades=propiedades,
            ajustes={"window": "(null):Ventana:python.exe"})
        opciones, actual = obs_captura.ventanas(doble, "Escena")
        self.assertEqual(actual, "(null):Ventana:python.exe")
        self.assertEqual(
            opciones,
            (("(null), de python.exe", "(null):Ventana:python.exe"),
             ("YouTube, de chrome.exe", "YouTube:Ventana:chrome.exe")))


class CapturaDeEscenaTest(unittest.TestCase):
    def test_prefiere_las_habilitadas(self):
        doble = Doble(
            elementos=(elemento(1, "Apagada", "window_capture", False),
                       elemento(2, "Encendida", "game_capture", True)),
            entradas=({"inputName": "Apagada", "inputKind": "window_capture"},
                      {"inputName": "Encendida", "inputKind": "game_capture"}))
        captura = obs_captura.captura_de_escena(doble, "Escena")
        self.assertEqual(captura["sourceName"], "Encendida")

    def test_devuelve_la_deshabilitada_si_es_la_unica(self):
        doble = Doble(elementos=(elemento(1, "Juego", "window_capture", False),),
                      entradas=({"inputName": "Juego", "inputKind": "window_capture"},))
        captura = obs_captura.captura_de_escena(doble, "Escena")
        self.assertEqual(captura["sourceName"], "Juego")

    def test_none_sin_captura(self):
        doble = Doble(elementos=(elemento(1, "Cámara", "dshow_input"),),
                      entradas=({"inputName": "Cámara", "inputKind": "dshow_input"},))
        self.assertIsNone(obs_captura.captura_de_escena(doble, "Escena"))

    def test_no_toca_otras_fuentes(self):
        doble = Doble(
            elementos=(elemento(1, "Navegador", "browser_source"),
                       elemento(2, "Juego", "game_capture")),
            entradas=({"inputName": "Navegador", "inputKind": "browser_source"},
                      {"inputName": "Juego", "inputKind": "game_capture"}))
        self.assertEqual(obs_captura.captura_de_escena(doble, "Escena")["sourceName"],
                         "Juego")

    def test_la_sonda_no_cuenta_como_captura(self):
        doble = Doble(
            elementos=(elemento(7, obs_captura.NOMBRE_SONDA,
                                "window_capture"),),
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},))
        self.assertIsNone(obs_captura.captura_de_escena(doble, "Escena"))

    def test_la_sonda_no_tapa_a_una_captura_real(self):
        doble = Doble(
            elementos=(elemento(7, obs_captura.NOMBRE_SONDA,
                                "window_capture"),
                       elemento(8, "Juego", "window_capture")),
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},
                      {"inputName": "Juego",
                        "inputKind": "window_capture"}))
        captura = obs_captura.captura_de_escena(doble, "Escena")
        self.assertEqual(captura["sourceName"], "Juego")


class VentanasTest(unittest.TestCase):
    def _propiedades(self):
        return (item("[Seleccionar ventana para capturar]", "", False),
                item("[juego.exe]: Champions", "Champions:Ventana:juego.exe", True),
                item("[otro.exe]: Charla", "Charla:Ventana:otro.exe", True),
                item("Oculta", "Oculta:Ventana:oculta.exe", False),
                item("Vacía", "", True))

    def test_con_captura_pide_sobre_ella_y_lee_la_actual(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},),
            propiedades=self._propiedades(),
            ajustes={"window": "Charla:Ventana:otro.exe"})
        opciones, actual = obs_captura.ventanas(doble, "Escena")
        self.assertEqual(opciones, (("Champions, de juego.exe",
                                     "Champions:Ventana:juego.exe"),
                                    ("Charla, de otro.exe",
                                     "Charla:Ventana:otro.exe")))
        self.assertEqual(actual, "Charla:Ventana:otro.exe")
        lista = [llamada for llamada in doble.llamadas
                 if llamada[0] == "GetInputPropertiesListPropertyItems"][0]
        self.assertEqual(lista[1]["inputName"], "Juego")
        self.assertNotIn("CreateInput", doble.tipos())

    def test_con_captura_sin_ventana_actual_da_vacio(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},),
            propiedades=self._propiedades(), ajustes={})
        _, actual = obs_captura.ventanas(doble, "Escena")
        self.assertEqual(actual, "")

    def test_sin_captura_crea_la_sonda_deshabilitada_y_la_borra(self):
        doble = Doble(propiedades=self._propiedades())
        opciones, actual = obs_captura.ventanas(doble, "Escena")
        self.assertEqual(actual, "")
        self.assertEqual(len(opciones), 2)
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"], obs_captura.NOMBRE_SONDA)
        self.assertEqual(crear[1]["inputKind"], "window_capture")
        self.assertFalse(crear[1]["sceneItemEnabled"])
        quitados = [llamada for llamada in doble.llamadas
                    if llamada[0] == "RemoveSceneItem"]
        self.assertEqual(len(quitados), 1)
        self.assertEqual(quitados[0][1]["sceneName"], "Escena")
        self.assertGreater(doble.llamadas.index(quitados[0]),
                           doble.llamadas.index(crear))
        self.assertEqual(doble.entradas, [])
        self.assertEqual(doble.elementos, [])

    def test_sin_captura_borra_la_sonda_tambien_si_la_lista_falla(self):
        doble = Doble(propiedades=self._propiedades(), falla_lista=True)
        with self.assertRaises(RuntimeError):
            obs_captura.ventanas(doble, "Escena")
        tipos = doble.tipos()
        self.assertIn("CreateInput", tipos)
        self.assertIn("RemoveSceneItem", tipos)
        self.assertLess(tipos.index("CreateInput"),
                        tipos.index("RemoveSceneItem"))

    def test_sin_captura_borra_una_sonda_vieja_antes(self):
        doble = Doble(
            elementos=(elemento(9, obs_captura.NOMBRE_SONDA,
                                "window_capture"),),
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},),
            propiedades=self._propiedades())
        obs_captura.ventanas(doble, "Escena")
        quitados = [llamada for llamada in doble.llamadas
                    if llamada[0] == "RemoveSceneItem"]
        self.assertEqual([llamada[1]["sceneItemId"] for llamada in quitados],
                         [9, 41])
        crear = [llamada for llamada in doble.llamadas
                 if llamada[0] == "CreateInput"][0]
        self.assertLess(doble.llamadas.index(quitados[0]),
                        doble.llamadas.index(crear))
        self.assertLess(doble.llamadas.index(crear),
                        doble.llamadas.index(quitados[1]))
        self.assertEqual(doble.entradas, [])
        self.assertEqual(doble.elementos, [])

    def test_sonda_vieja_solo_en_la_lista_se_borra_con_remove_input(self):
        doble = Doble(
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},),
            propiedades=self._propiedades())
        obs_captura.ventanas(doble, "Escena")
        borrados = [llamada[1]["inputName"] for llamada in doble.llamadas
                    if llamada[0] == "RemoveInput"]
        self.assertEqual(borrados, [obs_captura.NOMBRE_SONDA])
        self.assertEqual(doble.entradas, [])

    def test_sonda_suelta_irrompible_se_reusa_sin_crear(self):
        doble = Doble(
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},),
            propiedades=self._propiedades(), retiene_sonda=True)
        opciones, actual = obs_captura.ventanas(doble, "Escena")
        self.assertEqual(opciones, (("Champions, de juego.exe",
                                     "Champions:Ventana:juego.exe"),
                                    ("Charla, de otro.exe",
                                     "Charla:Ventana:otro.exe")))
        self.assertEqual(actual, "")
        self.assertNotIn("CreateInput", doble.tipos())
        lista = [llamada for llamada in doble.llamadas
                 if llamada[0] == "GetInputPropertiesListPropertyItems"][0]
        self.assertEqual(lista[1]["inputName"], obs_captura.NOMBRE_SONDA)

    def test_si_la_sonda_sigue_tras_borrar_se_avisa_el_error(self):
        doble = Doble(
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},),
            propiedades=self._propiedades(), falla_borrado=True)
        with self.assertRaises(obs_cliente.ObsError):
            obs_captura.ventanas(doble, "Escena")

    def test_espera_a_que_la_sonda_desaparezca_antes_de_volver(self):
        doble = Doble(propiedades=self._propiedades(), tarda_en_borrar=2)
        reloj = RelojFalso()
        opciones, actual = obs_captura.ventanas(
            doble, "Escena", dormir=reloj.dormir, reloj=reloj)
        self.assertEqual(len(opciones), 2)
        self.assertEqual(actual, "")
        self.assertEqual(reloj.pausas, [0.05])
        self.assertEqual(doble.entradas, [])
        self.assertFalse(any(actual_elemento.get("sourceName")
                             == obs_captura.NOMBRE_SONDA
                             for actual_elemento in doble.elementos))
        listas = [llamada for llamada in doble.llamadas
                  if llamada[0] == "GetInputList"]
        self.assertGreaterEqual(len(listas), 3)

    def test_plazo_vencido_vuelve_igual_sin_error(self):
        doble = Doble(propiedades=self._propiedades(),
                      tarda_en_borrar=10000)
        reloj = RelojFalso()
        opciones, actual = obs_captura.ventanas(
            doble, "Escena", dormir=reloj.dormir, reloj=reloj)
        self.assertEqual(len(opciones), 2)
        self.assertEqual(actual, "")
        self.assertGreaterEqual(sum(reloj.pausas), 3.0)
        self.assertTrue(all(pausa == 0.05 for pausa in reloj.pausas))


class UsarVentanaTest(unittest.TestCase):
    def test_con_window_capture_solo_cambia_la_ventana(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},))
        frase = obs_captura.usar_ventana(doble, "Escena",
                                         "Champions:Ventana:juego.exe")
        self.assertEqual(frase, "Ahora se captura Champions, de juego.exe.")
        escrito = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetInputSettings")
        self.assertEqual(escrito[1]["inputName"], "Juego")
        self.assertEqual(escrito[1]["inputSettings"],
                         {"window": "Champions:Ventana:juego.exe",
                          "overlay": True})
        self.assertNotIn("SetSceneItemEnabled", doble.tipos())
        self.assertNotIn("CreateInput", doble.tipos())

    def test_con_game_capture_lleva_capture_mode(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "game_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "game_capture"},))
        obs_captura.usar_ventana(doble, "Escena", "Juego:Ventana:juego.exe")
        escrito = next(llamada for llamada in doble.llamadas
                       if llamada[0] == "SetInputSettings")
        self.assertEqual(escrito[1]["inputSettings"],
                         {"window": "Juego:Ventana:juego.exe",
                          "capture_mode": "window", "overlay": True})

    def test_con_captura_deshabilitada_la_habilita(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture", False),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},))
        obs_captura.usar_ventana(doble, "Escena", "Juego:Ventana:juego.exe")
        habilitar = next(llamada for llamada in doble.llamadas
                         if llamada[0] == "SetSceneItemEnabled")
        self.assertEqual(habilitar[1], {"sceneName": "Escena",
                                        "sceneItemId": 5,
                                        "sceneItemEnabled": True})

    def test_sin_captura_crea_manda_al_fondo_y_ajusta_al_lienzo(self):
        doble = Doble(video={"baseWidth": 1280, "baseHeight": 720})
        frase = obs_captura.usar_ventana(doble, "Escena",
                                         "Champions:Ventana:juego.exe")
        self.assertEqual(frase, "Ahora se captura Champions, de juego.exe.")
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"], obs_captura.NOMBRE_CAPTURA)
        self.assertEqual(crear[1]["inputKind"], "window_capture")
        self.assertEqual(crear[1]["inputSettings"],
                         {"window": "Champions:Ventana:juego.exe"})
        self.assertTrue(crear[1]["sceneItemEnabled"])
        fondo = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "SetSceneItemIndex")
        self.assertEqual(fondo[1]["sceneItemIndex"], 0)
        ajuste = next(llamada for llamada in doble.llamadas
                      if llamada[0] == "SetSceneItemTransform")
        self.assertEqual(ajuste[1]["sceneItemTransform"],
                         {"positionX": 0, "positionY": 0, "alignment": 5,
                          "boundsType": "OBS_BOUNDS_SCALE_INNER",
                          "boundsAlignment": 0, "boundsWidth": 1280,
                          "boundsHeight": 720})

    def test_sin_captura_usa_nombre_alternativo_si_esta_ocupado(self):
        doble = Doble(
            entradas=({"inputName": obs_captura.NOMBRE_CAPTURA,
                       "inputKind": "text_gdiplus"},
                      {"inputName": f"{obs_captura.NOMBRE_CAPTURA} 2",
                       "inputKind": "browser_source"}),
            video={"baseWidth": 1280, "baseHeight": 720})
        obs_captura.usar_ventana(doble, "Escena", "Juego:Ventana:juego.exe")
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"],
                         f"{obs_captura.NOMBRE_CAPTURA} 3")

    def test_con_solo_la_sonda_crea_captura_nueva(self):
        doble = Doble(
            elementos=(elemento(7, obs_captura.NOMBRE_SONDA,
                                "window_capture"),),
            entradas=({"inputName": obs_captura.NOMBRE_SONDA,
                        "inputKind": "window_capture"},),
            video={"baseWidth": 1280, "baseHeight": 720})
        frase = obs_captura.usar_ventana(doble, "Escena",
                                         "Juego:Ventana:juego.exe")
        self.assertEqual(frase, "Ahora se captura Juego, de juego.exe.")
        self.assertNotIn("SetInputSettings", doble.tipos())
        crear = next(llamada for llamada in doble.llamadas
                     if llamada[0] == "CreateInput")
        self.assertEqual(crear[1]["inputName"], obs_captura.NOMBRE_CAPTURA)


class TestPseudoCaptura(unittest.TestCase):
    """Pseudotraducción de las frases de `obs_captura`.

    Sin ventanas: llama a las funciones bajo `con_pseudo()` y exige el
    texto propio marcado. El título y el programa de la ventana son datos
    de OBS y viajan sin marcar.
    """

    def test_ventana_legible_marca_la_frase_con_los_datos(self):
        with con_pseudo():
            frase = obs_captura.ventana_legible("[juego.exe]: Champions")
        self.assertTrue(frase.startswith("[¡"), frase)
        self.assertIn("Champions", frase)
        self.assertIn("juego.exe", frase)

    def test_usar_ventana_marca_las_dos_frases(self):
        doble = Doble(
            elementos=(elemento(5, "Juego", "window_capture"),),
            entradas=({"inputName": "Juego", "inputKind": "window_capture"},))
        with con_pseudo():
            existente = obs_captura.usar_ventana(
                doble, "Escena", "Champions:Ventana:juego.exe")
            creada = obs_captura.usar_ventana(
                Doble(video={"baseWidth": 1280, "baseHeight": 720}),
                "Escena", "Champions:Ventana:juego.exe")
        self.assertTrue(existente.startswith("[¡"), existente)
        self.assertIn("Champions", existente)
        self.assertTrue(creada.startswith("[¡"), creada)
        self.assertIn("Champions", creada)


if __name__ == "__main__":
    unittest.main()
