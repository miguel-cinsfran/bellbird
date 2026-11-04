import unittest

from bellbird.obs import disenos_escena as disenos


class DisenosEscenaTest(unittest.TestCase):
    def test_pantalla_completa_ajusta(self):
        fuente = disenos.Fuente("Captura", "otra", 1280, 720)
        diseno = disenos.Diseno(clase="pantalla_completa", principal="Captura")
        [resultado] = disenos.calcular(1920, 1080, [fuente], diseno)
        self.assertEqual(resultado["nombre"], "Captura")
        self.assertEqual((resultado["positionX"], resultado["positionY"]),
                         (0, 0))
        self.assertEqual((resultado["boundsWidth"], resultado["boundsHeight"]),
                         (1920, 1080))
        self.assertEqual(resultado["alignment"], 5)
        self.assertEqual(resultado["boundsType"], "OBS_BOUNDS_SCALE_INNER")
        self.assertEqual(resultado["boundsAlignment"], 0)
        self.assertEqual(
            (resultado["cropLeft"], resultado["cropRight"],
             resultado["cropTop"], resultado["cropBottom"]),
            (0, 0, 0, 0))
        self.assertEqual(resultado["estado"], disenos.ESTADO_AJUSTA)

    def test_imagen_en_imagen_mediana_abajo_derecha(self):
        camara = disenos.Fuente("Cámara", "camara", 1280, 720)
        juego = disenos.Fuente("Juego", "otra", 1920, 1080)
        diseno = disenos.Diseno(
            clase="imagen_en_imagen", principal="Juego", secundaria="Cámara",
            esquina="inferior-derecha", tamano="mediana")
        resultados = disenos.calcular(1920, 1080, [juego, camara], diseno)
        self.assertEqual([resultado["nombre"] for resultado in resultados],
                         ["Cámara", "Juego"])
        camara_res, juego_res = resultados
        self.assertEqual(
            (camara_res["boundsWidth"], camara_res["boundsHeight"]), (480, 270))
        self.assertEqual(
            1920 - (camara_res["positionX"] + camara_res["boundsWidth"]), 38)
        self.assertEqual(
            1080 - (camara_res["positionY"] + camara_res["boundsHeight"]), 22)
        self.assertEqual(camara_res["estado"], disenos.ESTADO_LLENA)
        self.assertEqual(juego_res["positionX"], 0)
        self.assertEqual(juego_res["boundsWidth"], 1920)
        self.assertEqual(juego_res["estado"], disenos.ESTADO_AJUSTA)

    def test_dividida_mitades(self):
        camara = disenos.Fuente("Cámara", "camara", 1920, 1080)
        captura = disenos.Fuente("Captura", "otra", 1280, 720)
        diseno = disenos.Diseno(clase="dividida", izquierda="Cámara",
                                derecha="Captura", proporcion="mitades")
        resultados = disenos.calcular(1920, 1080, [camara, captura], diseno)
        self.assertEqual([resultado["nombre"] for resultado in resultados],
                         ["Cámara", "Captura"])
        izquierda, derecha = resultados
        self.assertEqual(
            (izquierda["positionX"], izquierda["positionY"],
             izquierda["boundsWidth"], izquierda["boundsHeight"]),
            (0, 0, 960, 1080))
        self.assertEqual(
            (izquierda["cropLeft"], izquierda["cropRight"],
             izquierda["cropTop"], izquierda["cropBottom"]),
            (480, 480, 0, 0))
        self.assertEqual(izquierda["estado"], disenos.ESTADO_LLENA)
        self.assertEqual((derecha["positionX"], derecha["boundsWidth"]),
                         (960, 960))
        self.assertEqual(
            (derecha["cropLeft"], derecha["cropRight"],
             derecha["cropTop"], derecha["cropBottom"]),
            (0, 0, 0, 0))
        self.assertEqual(derecha["estado"], disenos.ESTADO_AJUSTA)

    def test_dividida_dos_tercios_y_modos(self):
        camara = disenos.Fuente("Cámara", "camara", 640, 480)
        captura = disenos.Fuente("Captura", "otra", 1280, 720)
        diseno = disenos.Diseno(
            clase="dividida", izquierda="Cámara", derecha="Captura",
            proporcion="dos_tercios",
            modos={"Cámara": "ajustar", "Captura": "llenar"})
        izquierda, derecha = disenos.calcular(
            1920, 1080, [camara, captura], diseno)
        self.assertEqual(izquierda["boundsWidth"], 1280)
        self.assertEqual((derecha["positionX"], derecha["boundsWidth"]),
                         (1280, 640))
        self.assertEqual(izquierda["estado"], disenos.ESTADO_AJUSTA)
        self.assertEqual(
            (izquierda["cropLeft"], izquierda["cropRight"],
             izquierda["cropTop"], izquierda["cropBottom"]),
            (0, 0, 0, 0))
        self.assertEqual((derecha["cropLeft"], derecha["cropRight"]),
                         (426, 427))
        self.assertEqual(derecha["estado"], disenos.ESTADO_LLENA)

    def test_chat_en_franja(self):
        chat = disenos.Fuente("Chat", "chat", 460, 620)
        juego = disenos.Fuente("Juego", "otra", 1920, 1080)
        diseno = disenos.Diseno(clase="pantalla_completa", principal="Juego",
                                chat="franja")
        resultados = disenos.calcular(1920, 1080, [juego, chat], diseno)
        self.assertEqual([resultado["nombre"] for resultado in resultados],
                         ["Chat", "Juego"])
        chat_res, juego_res = resultados
        self.assertEqual((chat_res["positionX"], chat_res["positionY"]),
                         (1440, 0))
        self.assertEqual((chat_res["ancho"], chat_res["alto"]), (480, 1080))
        self.assertEqual(chat_res["alignment"], 5)
        self.assertEqual(juego_res["boundsWidth"], 1440)
        self.assertEqual(juego_res["boundsHeight"], 1080)

    def test_chat_superpuesto_conserva_tamano(self):
        chat = disenos.Fuente("Chat", "chat", 460, 620)
        juego = disenos.Fuente("Juego", "otra", 1920, 1080)
        diseno = disenos.Diseno(
            clase="pantalla_completa", principal="Juego", chat="superpuesto",
            esquina_chat="superior-izquierda")
        chat_res, juego_res = disenos.calcular(
            1920, 1080, [juego, chat], diseno)
        self.assertEqual(set(chat_res),
                         {"nombre", "positionX", "positionY", "alignment"})
        self.assertAlmostEqual(chat_res["positionX"], 38.4)
        self.assertAlmostEqual(chat_res["positionY"], 21.6)
        self.assertEqual(chat_res["alignment"], 5)
        self.assertEqual(juego_res["boundsWidth"], 1920)

    def test_llenar_sin_origen_ajusta_y_marca(self):
        camara = disenos.Fuente("Cámara", "camara", 0, 0)
        diseno = disenos.Diseno(clase="pantalla_completa", principal="Cámara")
        [resultado] = disenos.calcular(1920, 1080, [camara], diseno)
        self.assertEqual(resultado["estado"],
                         disenos.ESTADO_AJUSTA_SIN_ORIGEN)
        self.assertEqual(
            (resultado["cropLeft"], resultado["cropRight"],
             resultado["cropTop"], resultado["cropBottom"]),
            (0, 0, 0, 0))
        self.assertEqual((resultado["boundsWidth"], resultado["boundsHeight"]),
                         (1920, 1080))

    def test_errores(self):
        fuente = disenos.Fuente("A", "otra", 640, 480)
        otra = disenos.Fuente("B", "otra", 640, 480)
        casos = [
            (1920, 1080, [fuente], disenos.Diseno(
                clase="dividida", izquierda="A", derecha="A")),
            (1920, 1080, [fuente, otra], disenos.Diseno(
                clase="dividida", izquierda="", derecha="B")),
            (1920, 1080, [fuente], disenos.Diseno(
                clase="pantalla_completa", principal="NoExiste")),
            (1920, 1080, [fuente, otra], disenos.Diseno(
                clase="imagen_en_imagen", principal="A", secundaria="B",
                esquina="centro")),
            (1920, 1080, [fuente, otra], disenos.Diseno(
                clase="imagen_en_imagen", principal="A", secundaria="B",
                tamano="enorme")),
            (0, 1080, [fuente], disenos.Diseno(
                clase="pantalla_completa", principal="A")),
            (1920, -1, [fuente], disenos.Diseno(
                clase="pantalla_completa", principal="A")),
        ]
        for caso in casos:
            with self.subTest(caso=caso):
                with self.assertRaises(ValueError):
                    disenos.calcular(*caso)

    def test_propiedades_de_todas_las_combinaciones(self):
        lienzos = [(1920, 1080), (1280, 720), (1080, 1920)]
        origenes = [(1280, 720), (640, 480), (720, 1280)]
        for lienzo_ancho, lienzo_alto in lienzos:
            for origen in origenes:
                for clase in disenos.CLASES:
                    for esquina in disenos.ESQUINAS:
                        for tamano in disenos.TAMANOS:
                            for proporcion in disenos.PROPORCIONES:
                                for chat in disenos.CHATS:
                                    for modo in ("", "ajustar", "llenar"):
                                        self._comprobar_combinacion(
                                            lienzo_ancho, lienzo_alto, origen,
                                            clase, esquina, tamano,
                                            proporcion, chat, modo)

    def _comprobar_combinacion(self, lienzo_ancho, lienzo_alto, origen,
                               clase, esquina, tamano, proporcion, chat, modo):
        ancho_origen, alto_origen = origen
        fuentes = [
            disenos.Fuente("Principal", "camara", ancho_origen, alto_origen),
            disenos.Fuente("Secundaria", "otra", ancho_origen, alto_origen),
            disenos.Fuente("Izquierda", "camara", ancho_origen, alto_origen),
            disenos.Fuente("Derecha", "otra", ancho_origen, alto_origen),
            disenos.Fuente("Chat", "chat", 460, 620),
        ]
        modos = {}
        if modo:
            modos = {fuente.nombre: modo for fuente in fuentes[:4]}
        diseno = disenos.Diseno(
            clase=clase, principal="Principal", secundaria="Secundaria",
            izquierda="Izquierda", derecha="Derecha", esquina=esquina,
            tamano=tamano, proporcion=proporcion, chat=chat,
            esquina_chat=esquina, modos=modos)
        resultados = disenos.calcular(
            lienzo_ancho, lienzo_alto, fuentes, diseno)
        for resultado in resultados:
            if resultado["nombre"] == "Chat":
                if chat == "franja":
                    self.assertLessEqual(
                        resultado["positionX"] + resultado["ancho"],
                        lienzo_ancho)
                    self.assertLessEqual(
                        resultado["positionY"] + resultado["alto"],
                        lienzo_alto)
                continue
            self.assertGreaterEqual(resultado["positionX"], 0)
            self.assertGreaterEqual(resultado["positionY"], 0)
            self.assertLessEqual(
                resultado["positionX"] + resultado["boundsWidth"],
                lienzo_ancho)
            self.assertLessEqual(
                resultado["positionY"] + resultado["boundsHeight"],
                lienzo_alto)
            for clave in ("cropLeft", "cropRight", "cropTop", "cropBottom"):
                self.assertGreaterEqual(resultado[clave], 0)
            if resultado["estado"] == disenos.ESTADO_LLENA:
                restante_ancho = (
                    ancho_origen - resultado["cropLeft"]
                    - resultado["cropRight"])
                restante_alto = (
                    alto_origen - resultado["cropTop"]
                    - resultado["cropBottom"])
                proporcion_lugar = (resultado["boundsWidth"]
                                    / resultado["boundsHeight"])
                self.assertLessEqual(
                    abs(restante_ancho - restante_alto * proporcion_lugar), 1)
            else:
                self.assertEqual(
                    (resultado["cropLeft"], resultado["cropRight"],
                     resultado["cropTop"], resultado["cropBottom"]),
                    (0, 0, 0, 0))
        if clase == "dividida":
            por_nombre = {resultado["nombre"]: resultado
                          for resultado in resultados}
            izquierda = por_nombre["Izquierda"]
            derecha = por_nombre["Derecha"]
            self.assertLessEqual(
                izquierda["positionX"] + izquierda["boundsWidth"],
                derecha["positionX"])


if __name__ == "__main__":
    unittest.main()
