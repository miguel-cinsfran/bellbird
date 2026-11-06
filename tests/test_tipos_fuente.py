"""Pruebas del catálogo de tipos de fuente y su traducción a OBS."""

import unittest

from guyrapu.obs import tipos_fuente


class CatalogoTest(unittest.TestCase):
    def test_tiene_los_ocho_tipos_en_orden(self):
        self.assertEqual(
            [tipo.clave for tipo in tipos_fuente.CATALOGO],
            ["camara", "pantalla", "ventana", "juego", "imagen",
             "multimedia", "texto", "otra_escena"])

    def test_las_etiquetas_del_menu_son_las_del_encargo(self):
        self.assertEqual(
            tipos_fuente.etiquetas_menu(),
            ("&Cámara…", "Captura de &pantalla…", "Captura de &ventana…",
             "Captura de &juego…", "&Imagen…", "&Archivo multimedia…",
             "&Texto…", "&Fuente de otra escena…"))

    def test_los_nombres_propuestos_son_los_del_encargo(self):
        self.assertEqual(
            [tipos_fuente.nombre_propuesto(tipo, ())
             for tipo in tipos_fuente.CATALOGO if tipo.clave != "otra_escena"],
            ["Cámara", "Captura de pantalla", "Captura de ventana",
             "Captura de juego", "Imagen", "Archivo multimedia", "Texto"])

    def test_cada_tipo_tiene_su_lugar(self):
        lugares = {tipo.clave: tipo.lugar for tipo in tipos_fuente.CATALOGO}
        self.assertEqual(lugares, {
            "camara": "camara", "pantalla": "ajustada",
            "ventana": "ventana", "juego": "ajustada", "imagen": "ajustada",
            "multimedia": "ajustada", "texto": "texto",
            "otra_escena": "otra_escena"})


class NombreLibreTest(unittest.TestCase):
    def test_sin_repetidos_devuelve_el_base(self):
        self.assertEqual(tipos_fuente.nombre_libre("Imagen", ()), "Imagen")

    def test_con_el_base_ocupado_agrega_dos(self):
        self.assertEqual(
            tipos_fuente.nombre_libre("Imagen", {"Imagen"}), "Imagen 2")

    def test_con_dos_y_tres_ocupados_sigue_el_numero(self):
        self.assertEqual(
            tipos_fuente.nombre_libre(
                "Imagen", {"Imagen", "Imagen 2", "Imagen 3"}),
            "Imagen 4")

    def test_salta_los_huecos_ocupados(self):
        self.assertEqual(
            tipos_fuente.nombre_libre(
                "Imagen", {"Imagen", "Imagen 2", "Imagen 4"}),
            "Imagen 3")


class TipoDeTextoTest(unittest.TestCase):
    def test_toma_la_version_que_trae_la_lista(self):
        self.assertEqual(
            tipos_fuente.tipo_de_texto(
                ("monitor_capture", "text_gdiplus_v3")),
            "text_gdiplus_v3")

    def test_sin_version_usa_la_base(self):
        self.assertEqual(
            tipos_fuente.tipo_de_texto(("text_gdiplus",)), "text_gdiplus")

    def test_sin_texto_en_la_lista_usa_la_base(self):
        self.assertEqual(
            tipos_fuente.tipo_de_texto(("monitor_capture",)),
            "text_gdiplus")


class AjustesTest(unittest.TestCase):
    def _ida_y_vuelta(self, clave, valores):
        ajustes = tipos_fuente.ajustes(clave, valores)
        self.assertEqual(tipos_fuente.valores(clave, ajustes), valores)
        return ajustes

    def test_camara(self):
        self._ida_y_vuelta("camara", {"dispositivo": "abc"})

    def test_pantalla(self):
        self._ida_y_vuelta("pantalla", {"pantalla": "DUMMY"})

    def test_ventana(self):
        self._ida_y_vuelta(
            "ventana", {"ventana": "Champions:Ventana:juego.exe"})

    def test_juego_a_pantalla_completa(self):
        self._ida_y_vuelta(
            "juego", {"modo": "any_fullscreen", "ventana": ""})

    def test_juego_de_una_ventana(self):
        self._ida_y_vuelta(
            "juego", {"modo": "window",
                      "ventana": "Champions:Ventana:juego.exe"})

    def test_imagen(self):
        self._ida_y_vuelta("imagen", {"archivo": "C:/imagen.png"})

    def test_multimedia(self):
        self._ida_y_vuelta(
            "multimedia", {"archivo": "C:/video.mp4", "repetir": True})

    def test_texto(self):
        self._ida_y_vuelta(
            "texto", {"texto": "Hola", "tamano": 72, "cara": "Arial"})

    def test_texto_conserva_la_cara_actual(self):
        ajustes = tipos_fuente.ajustes(
            "texto", {"texto": "Hola", "tamano": 72},
            actual={"font": {"face": "Verdana", "size": 256, "flags": 1}})
        self.assertEqual(
            ajustes["font"],
            {"face": "Verdana", "size": 72, "flags": 1})

    def test_texto_usa_arial_si_no_hay_actual(self):
        ajustes = tipos_fuente.ajustes(
            "texto", {"texto": "Hola", "tamano": 72})
        self.assertEqual(ajustes["font"], {"face": "Arial", "size": 72})

    def test_imagen_usa_la_clave_file(self):
        self.assertEqual(
            tipos_fuente.ajustes("imagen", {"archivo": "C:/a.png"}),
            {"file": "C:/a.png"})

    def test_multimedia_usa_las_claves_de_obs(self):
        self.assertEqual(
            tipos_fuente.ajustes(
                "multimedia", {"archivo": "C:/v.mp4", "repetir": True}),
            {"local_file": "C:/v.mp4", "is_local_file": True,
             "looping": True})


class FiltrarItemsTest(unittest.TestCase):
    def test_saca_deshabilitados_y_vacios(self):
        items = (
            {"itemEnabled": False,
             "itemName": "[Seleccionar pantalla para capturar]",
             "itemValue": "DUMMY"},
            {"itemEnabled": True,
             "itemName": "HP V202: 1600x900 @ 0,0 (Monitor principal)",
             "itemValue": "\\\\?\\DISPLAY#..."},
            {"itemEnabled": True, "itemName": "Vacía", "itemValue": ""},
            {"itemEnabled": False, "itemName": "Apagada",
             "itemValue": "apagada"})
        self.assertEqual(
            tipos_fuente.filtrar_items(items),
            (("HP V202: 1600x900 @ 0,0 (Monitor principal)",
              "\\\\?\\DISPLAY#..."),))

    def test_sin_items_devuelve_tupla_vacia(self):
        self.assertEqual(tipos_fuente.filtrar_items(None), ())


class ClaveDeObsTest(unittest.TestCase):
    def test_reconoce_la_captura_de_pantalla(self):
        self.assertEqual(tipos_fuente.clave_de_obs("monitor_capture"),
                         "pantalla")

    def test_reconoce_el_texto_versionado(self):
        self.assertEqual(tipos_fuente.clave_de_obs("text_gdiplus_v3"),
                         "texto")

    def test_una_fuente_ajena_no_tiene_clave(self):
        self.assertEqual(tipos_fuente.clave_de_obs("color_source_v3"), "")


class TransformacionTextoTest(unittest.TestCase):
    def test_queda_abajo_al_centro_y_sin_cuadro(self):
        self.assertEqual(
            tipos_fuente.transformacion_texto(1600, 900),
            {"positionX": 800.0, "positionY": 855.0, "alignment": 8,
             "boundsType": "OBS_BOUNDS_NONE"})


if __name__ == "__main__":
    unittest.main()
